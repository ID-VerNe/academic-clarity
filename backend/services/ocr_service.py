import os
import fitz
import asyncio
from PIL import Image
from io import BytesIO
from services.ai_service import call_ocr_api, call_json_extraction_api
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown

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
        
        api_config = {
            "api_key": db.get_config("DEEPSEEK_API_KEY", ""),
            "api_base": db.get_config("API_BASE", "https://api.siliconflow.cn/v1"),
            "model_name": db.get_config("MODEL_NAME", "openai/deepseek-ai/DeepSeek-OCR")
        }

        if not api_config["api_key"]:
            print("[Task] Error: DEEPSEEK_API_KEY not found in configs.")
            db.update_document_ocr(doc_id, "failed")
            return

        page_tasks = []
        for i in range(total_pages):
            pix = doc[i].get_pixmap(dpi=144)
            page_tasks.append(process_page_task(i, total_pages, pix.tobytes("png"), api_config))
        
        page_results = await asyncio.gather(*page_tasks)
        doc.close()

        raw_full_content = "\n\n".join(page_results)
        cleaned_markdown = clean_ocr_markdown(raw_full_content)
        title = extract_title_from_markdown(raw_full_content)
        
        # --- 阶段 2: 结构化 JSON 提取 ---
        print(f"[Task] Extracting JSON metadata for: {title}")
        metadata_prompt = db.get_config("METADATA_EXTRACT_PROMPT", "Extract metadata from this academic paper. Return a JSON object with keys: title, authors, abstract, keywords, publication_date.")
        
        # 配置 JSON 提取专用的引擎 (默认指向本地 gpt-4.1)
        extract_api_config = {
            "api_key": db.get_config("EXTRACT_API_KEY", "sk-copilot-sdk-default"),
            "api_base": db.get_config("EXTRACT_API_BASE", "http://localhost:37210/v1"),
            "model_name": db.get_config("EXTRACT_MODEL_NAME", "gpt-4.1")
        }
        
        metadata_json = "{}"
        try:
            metadata_json = await call_json_extraction_api(cleaned_markdown, extract_api_config, metadata_prompt)
        except Exception as e:
            print(f"[Task] JSON Extraction Error: {e}")

        db.update_document_ocr(doc_id, "completed", markdown=cleaned_markdown, raw=raw_full_content, title=title, metadata_json=metadata_json)
        print(f"[Task] Finished: {title}")
    except Exception as e:
        print(f"[Task] Error: {e}")
        db.update_document_ocr(doc_id, "failed")
