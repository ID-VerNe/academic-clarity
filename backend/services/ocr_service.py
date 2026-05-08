import os
import fitz
import asyncio
import re
import ast
import base64
from PIL import Image
from io import BytesIO
from services.ai_service import call_ocr_api, call_json_extraction_api
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown
from services.config_service import ConfigService

class EmptyFileError(Exception):
    """Raised when the PDF file is 0 bytes or essentially empty."""
    pass

def replace_image_tags_with_markdown(content, image):
    """
    Convert DeepSeek image grounding tags into embeddable markdown images.
    Example:
    <|ref|>image<|/ref|><|det|>[[x1,y1,x2,y2]]<|/det|> -> ![](data:image/jpeg;base64,...)
    """
    if not content:
        return ""

    pattern = re.compile(r'<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>', re.DOTALL)
    width, height = image.size
    def replacement(match):
        ref_text = (match.group(1) or "").strip()
        det_text = (match.group(2) or "").strip()

        # Keep textual grounding in markdown; extract actual image regions as embedded images.
        if ref_text.lower() != "image":
            return ref_text

        try:
            coords_list = ast.literal_eval(det_text)
        except Exception:
            return ""

        images_md = []
        for points in coords_list:
            if not isinstance(points, (list, tuple)) or len(points) != 4:
                continue
            x1, y1, x2, y2 = points
            x1 = max(0, min(width, int(x1 / 999 * width)))
            y1 = max(0, min(height, int(y1 / 999 * height)))
            x2 = max(0, min(width, int(x2 / 999 * width)))
            y2 = max(0, min(height, int(y2 / 999 * height)))
            if x2 <= x1 or y2 <= y1:
                continue

            cropped = image.crop((x1, y1, x2, y2))
            buffer = BytesIO()
            cropped.save(buffer, format="JPEG", quality=85)
            data_uri = base64.b64encode(buffer.getvalue()).decode("utf-8")
            images_md.append(f"![](data:image/jpeg;base64,{data_uri})")

        return "\n".join(images_md)

    replaced = pattern.sub(replacement, content)
    # Drop any leftover broken tags from partial responses
    replaced = re.sub(r'<\|/?ref\|>|<\|/?det\|>', '', replaced)
    return replaced

async def process_page_task(page_idx, total_pages, pix_data, api_config, retries=3):
    """
    Task for processing a single page of a PDF with automatic retries.
    """
    for attempt in range(retries):
        print(f"[OCR] Processing Page {page_idx + 1}/{total_pages} (Attempt {attempt + 1})...")
        try:
            image = Image.open(BytesIO(pix_data))
            content = await call_ocr_api(image, api_config)
            return content
        except Exception as e:
            wait_time = (attempt + 1) * 2
            print(f"  [OCR] Page {page_idx + 1} failed: {e}. Retrying...")
            if attempt < retries - 1:
                await asyncio.sleep(wait_time)
            else:
                return f"\n\n> [Error on Page {page_idx + 1}]\n\n"

async def run_full_ocr_workflow(doc_id, pdf_path, db):
    print(f"[TaskHub] Starting Full Pipeline for: {os.path.basename(pdf_path)}")
    try:
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            raise EmptyFileError(f"File {pdf_path} is empty or missing.")

        db.update_document_ocr(doc_id, "processing")
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        config_service = ConfigService(db)
        use_multi_key = config_service.initialize_key_manager()
        ocr_api_config = config_service.get_ocr_config()
        if use_multi_key:
            ocr_api_config['_use_multi_key'] = True

        if not ocr_api_config["api_key"] and not use_multi_key:
            raise Exception("API Key missing")

        page_tasks = []
        page_images = []
        for i in range(total_pages):
            pix = doc[i].get_pixmap(dpi=144)
            pix_bytes = pix.tobytes("png")
            try:
                page_images.append(Image.open(BytesIO(pix_bytes)).convert("RGB"))
            except Exception:
                page_images.append(Image.new("RGB", (1, 1), "white"))
            page_tasks.append(process_page_task(i, total_pages, pix_bytes, ocr_api_config))
        
        page_results = await asyncio.gather(*page_tasks)
        doc.close()

        page_markdowns = [
            replace_image_tags_with_markdown(page_results[i], page_images[i])
            for i in range(total_pages)
        ]

        raw_full_content = "\n\n".join(page_markdowns)
        cleaned_markdown = clean_ocr_markdown(raw_full_content)
        title = extract_title_from_markdown(raw_full_content)
        
        print(f"[TaskHub] Stage 2: Deep Extraction for {title}")
        default_prompt = """
        You are a world-class academic metadata curator. 
        Your mission is to extract precise metadata from the provided markdown.
        
        ### CRITICAL MISSION: DOI EXTRACTION
        - Look for strings starting with '10.' followed by a prefix and suffix (e.g., 10.1109/TVCG.2023.12345).
        - The DOI is often located in the very first or last lines of the markdown, or within 'Footnotes' section.
        - If you find multiple, pick the one that looks like a formal document identifier.
        
        ### OTHER FIELDS
        - title: The full academic title.
        - authors: All authors as a comma-separated string.
        - journal_or_conference: Full venue name (e.g., IEEE Transactions on...).
        - date: The year (YYYY) or full publication date.
        - abstract: A sharp 2-3 sentence summary.
        - keywords: 5-8 relevant terms.
        - summary: 3 power-bullets on 'Novelty', 'Method', and 'Impact'.
        
        Return ONLY a JSON object.
        """
        
        extract_api_config = config_service.get_extract_config()
        if use_multi_key:
            extract_api_config['_use_multi_key'] = True
        try:
            metadata_json = await call_json_extraction_api(cleaned_markdown, extract_api_config, default_prompt)
            db.add_document_metadata(doc_id, "Basic Insight", metadata_json)
        except Exception as e:
            print(f"[TaskHub] Metadata Stage Error: {e}")

        db.update_document_ocr(doc_id, "completed", markdown=cleaned_markdown, raw=raw_full_content, title=title)
        print(f"[TaskHub] Pipeline SUCCESS: {title}")
    except Exception as e:
        print(f"[TaskHub] Pipeline CRITICAL ERROR: {e}")
        db.update_document_ocr(doc_id, "failed")
        raise e
