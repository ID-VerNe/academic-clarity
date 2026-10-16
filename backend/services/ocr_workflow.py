"""ocr_workflow — 全页 OCR → Markdown → Basic Insight 流水线（B-SRP-09 拆分）。

进度上报与失败收尾走 services.workflow_common（B-DRY-02/03）；
ai 调用经 ocr_service 门面晚绑定（保持既有 patch 语义）。
"""
import asyncio
import json
import os
from io import BytesIO

import fitz
from PIL import Image

from services.config_service import ConfigService
from services.ocr_images import process_page_task, replace_image_tags_with_markdown
from services.prompts import BASIC_INSIGHT_PROMPT
from services.workflow_common import fail_workflow, safe_complete, safe_stage, safe_start
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown

try:
    from backend.constants import MetadataConfig
except ImportError:
    from constants import MetadataConfig


class EmptyFileError(Exception):
    """Raised when the PDF file is 0 bytes or essentially empty."""
    pass


async def run_full_ocr_workflow(doc_id, pdf_path, db):
    print(f"[TaskHub] Starting Full Pipeline for: {os.path.basename(pdf_path)}")
    failed_pages = []

    try:
        await safe_start(doc_id, "ocr")
        await safe_stage(doc_id, 1, "解析 PDF 页面")
        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            raise EmptyFileError(f"File {pdf_path} is empty or missing.")

        db.update_document_ocr(doc_id, "processing")
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        config_service = ConfigService(db)
        ocr_api_config = config_service.get_ocr_config()

        if not ocr_api_config["api_key"]:
            raise Exception("OCR API Key missing")

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

        done_pages = 0
        progress_lock = asyncio.Lock()

        async def tracked_page(page_task):
            nonlocal done_pages
            try:
                return await page_task
            finally:
                async with progress_lock:
                    done_pages += 1
                    done = done_pages
                await safe_stage(
                    doc_id,
                    round(5 + (done / max(total_pages, 1)) * 55, 1),
                    f"OCR 第 {done}/{total_pages} 页",
                )

        results = await asyncio.gather(
            *(tracked_page(t) for t in page_tasks),
            return_exceptions=True,
        )
        doc.close()

        page_markdowns = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_pages.append(i + 1)
                error_msg = str(result)
                page_markdowns.append(f"\n\n> [Error on Page {i + 1}/{total_pages}] {error_msg}\n\n")
                print(f"[OCR] Page {i + 1} failed: {error_msg}")
            else:
                page_markdowns.append(replace_image_tags_with_markdown(result, page_images[i]))

        raw_full_content = "\n\n".join(page_markdowns)
        cleaned_markdown = clean_ocr_markdown(raw_full_content)
        title = extract_title_from_markdown(raw_full_content)

        print(f"[TaskHub] Stage 2: Deep Extraction for {title}")
        await safe_stage(doc_id, 65, "提取 Basic Insight")

        extract_api_config = config_service.get_extract_config()

        try:
            # 经门面模块解析（保持 tests 对 services.ocr_service.call_json_extraction_api 的 patch 语义）
            from services.ocr_service import call_json_extraction_api
            metadata_json = await call_json_extraction_api(cleaned_markdown, extract_api_config, BASIC_INSIGHT_PROMPT)
            db.add_document_metadata(doc_id, MetadataConfig.DEFAULT_LABEL, metadata_json)
        except Exception as e:
            print(f"[TaskHub] Metadata Stage Error: {e}")

        # Phase 1: CrossRef DOI 权威校验（失败不阻断主流水线，降级 unverified）
        await safe_stage(doc_id, 88, "校验 DOI")
        try:
            from services.doi_service import verify_document
            verify_document(db, doc_id)
        except Exception as e:
            print(f"[TaskHub] DOI Verify skipped: {e}")

        await safe_stage(doc_id, 96, "整理结果")
        if failed_pages:
            status_note = f" (Partial: {len(failed_pages)} pages failed: {failed_pages})"
            print(f"[TaskHub] Pipeline completed with failures: {status_note}")
            db.update_document_ocr(doc_id, "completed", markdown=cleaned_markdown, raw=raw_full_content, title=title)
            db.add_document_metadata(doc_id, "OCR Failures", json.dumps({"failed_pages": failed_pages, "total_pages": total_pages}))
        else:
            db.update_document_ocr(doc_id, "completed", markdown=cleaned_markdown, raw=raw_full_content, title=title)
        print(f"[TaskHub] Pipeline SUCCESS: {title}")
        await safe_complete(doc_id)

    except Exception as e:
        await fail_workflow(doc_id, db, e, log_prefix="TaskHub")
