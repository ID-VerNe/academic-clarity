"""ocr_service — OCR 流水线门面（B-SRP-09 拆分）。

实现拆分至：ocr_images（图像标签/单页任务）、ocr_workflow（全流水线）。
本模块仅 re-export，保持既有导入路径不变；call_ocr_api /
call_json_extraction_api 保留为模块属性——tests/integration/test_integration.py
依赖对该路径的 patch（工作流内经门面晚绑定解析，patch 语义不变）。
"""
from services.ai_service import call_ocr_api, call_json_extraction_api  # noqa: F401
from services.ocr_images import (  # noqa: F401
    PageOCRFailedError,
    process_page_task,
    replace_image_tags_with_markdown,
)
from services.ocr_workflow import EmptyFileError, run_full_ocr_workflow  # noqa: F401

__all__ = [
    "call_ocr_api",
    "call_json_extraction_api",
    "PageOCRFailedError",
    "process_page_task",
    "replace_image_tags_with_markdown",
    "EmptyFileError",
    "run_full_ocr_workflow",
]
