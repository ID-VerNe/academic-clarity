import os
import fitz
import asyncio
from PIL import Image
from io import BytesIO
from services.ai_service import call_ocr_api, call_json_extraction_api
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown

from services.config_service import ConfigService

ocr_semaphore = asyncio.Semaphore(10)

async def process_page_task(page_idx, total_pages, pix_data, api_config):
    """
    Task for processing a single page of a PDF.
    """
    async with ocr_semaphore:
        print(f"[OCR] Processing Page {page_idx + 1}/{total_pages}...")
        try:
            image = Image.open(BytesIO(pix_data))
            content = await call_ocr_api(image, api_config)
            return content
        except Exception as e:
            return f"\n\n> [Error on Page {page_idx + 1}: {str(e)}]\n\n"

async def run_full_ocr_workflow(doc_id, pdf_path, db):
    """
    Runs the full OCR workflow from PDF loading to database update.
    """
    print(f"[Task] Starting Full OCR for: {os.path.basename(pdf_path)}")
    try:
        db.update_document_ocr(doc_id, "processing")
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        config_service = ConfigService(db)
        ocr_api_config = config_service.get_ocr_config()

        if not ocr_api_config["api_key"]:
            print("[Task] Error: DEEPSEEK_API_KEY not found in configs.")
            db.update_document_ocr(doc_id, "failed")
            return

        page_tasks = []
        for i in range(total_pages):
            pix = doc[i].get_pixmap(dpi=144)
            page_tasks.append(process_page_task(i, total_pages, pix.tobytes("png"), ocr_api_config))
        
        page_results = await asyncio.gather(*page_tasks)
        doc.close()

        raw_full_content = "\n\n".join(page_results)
        cleaned_markdown = clean_ocr_markdown(raw_full_content)
        title = extract_title_from_markdown(raw_full_content)
        
        # --- 阶段 2: 结构化 JSON 提取 (多维智库卡片) ---
        print(f"[Task] Extracting DEFAULT metadata for: {title}")
        
        # 1. 定义基础信息提取 Prompt (Default Tags)
        default_prompt = """
        Extract the following basic metadata from this academic paper markdown content. 
        Return a JSON object with these EXACT keys:
        - title: The full title of the paper
        - authors: A list of all authors
        - journal_or_conference: Where it was published
        - date: Publication date (if available)
        - doi: DOI string
        - abstract: A concise 2-3 sentence summary of the abstract
        - keywords: A list of 5-8 key terms
        - summary: A 3-bullet point summary of 'what this paper wrote about/contributed'
        """
        
        config_service = ConfigService(db)
        extract_api_config = config_service.get_extract_config()
        
        try:
            # 提取基础信息
            metadata_json = await call_json_extraction_api(cleaned_markdown, extract_api_config, default_prompt)
            # 存入多维元数据表
            db.add_document_metadata(doc_id, "Basic Insight", metadata_json)
        except Exception as e:
            print(f"[Task] Default Metadata Extraction Error: {e}")

        # 检查是否还有用户自定义的额外提取需求 (可选扩展点)
        user_custom_prompt = db.get_config("CUSTOM_EXTRACT_PROMPT")
        if user_custom_prompt:
            try:
                custom_json = await call_json_extraction_api(cleaned_markdown, extract_api_config, user_custom_prompt)
                db.add_document_metadata(doc_id, "Custom Analysis", custom_json)
            except: pass

        db.update_document_ocr(doc_id, "completed", markdown=cleaned_markdown, raw=raw_full_content, title=title)
        print(f"[Task] Finished: {title}")
    except Exception as e:
        print(f"[Task] Error: {e}")
        db.update_document_ocr(doc_id, "failed")
