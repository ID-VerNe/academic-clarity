"""ocr_images — OCR 图像编码与单页任务（B-SRP-09 拆分）。

DeepSeek grounding 标签 → markdown 图片、单页 OCR 重试任务；
DataURI 编码统一走 utils.image.image_to_data_uri（B-DRY-14），
残留标签清洗统一走 utils.text_processor.strip_ref_det_tags（B-DRY-07）。
"""
import ast
import asyncio
import re
from io import BytesIO

from PIL import Image

from utils.image import image_to_data_uri
from utils.text_processor import strip_ref_det_tags

try:
    from backend.constants import OCRConfig
except ImportError:
    from constants import OCRConfig


class PageOCRFailedError(Exception):
    """Raised when a single page fails to OCR after all retries."""
    def __init__(self, page_idx: int, total_pages: int, original_error: str):
        self.page_idx = page_idx
        self.total_pages = total_pages
        self.original_error = original_error
        super().__init__(
            f"OCR failed for page {page_idx + 1}/{total_pages}: {original_error}"
        )


def _retry_backoff(attempt: int) -> float:
    """PAGE_RETRY_BACKOFF 越界时钳到末位（B-DRY-06 单一实现）。"""
    schedule = OCRConfig.PAGE_RETRY_BACKOFF
    return schedule[attempt] if attempt < len(schedule) else schedule[-1]


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
            images_md.append(f"![]({image_to_data_uri(cropped, format='JPEG', quality=85)})")

        return "\n".join(images_md)

    replaced = pattern.sub(replacement, content)
    return strip_ref_det_tags(replaced, keep_text=True)


async def process_page_task(page_idx, total_pages, pix_data, api_config, retries=None):
    """
    Task for processing a single page of a PDF with automatic retries.
    Raises PageOCRFailedError instead of silently returning error messages.
    """
    # 经门面模块解析 call_ocr_api（而非直接 import ai_service）：保持
    # tests 对 services.ocr_service.call_ocr_api 的 patch 语义不变。
    from services.ocr_service import call_ocr_api

    if retries is None:
        retries = OCRConfig.MAX_RETRIES

    last_error = None

    for attempt in range(retries):
        print(f"[OCR] Processing Page {page_idx + 1}/{total_pages} (Attempt {attempt + 1})...")
        try:
            image = Image.open(BytesIO(pix_data))
            content = await call_ocr_api(image, api_config)

            if isinstance(content, str) and content.startswith("OCR Failed:"):
                last_error = content
                if attempt < retries - 1:
                    await asyncio.sleep(_retry_backoff(attempt))
                continue

            return content

        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                await asyncio.sleep(_retry_backoff(attempt))

    raise PageOCRFailedError(page_idx, total_pages, last_error or "Unknown error")
