"""tex_workflow — tex/zip → Markdown → Basic Insight 任务链（B-SRP-12 拆分）。

进度上报与失败收尾走 services.workflow_common（B-DRY-02/03）；
转换入口与 ai 调用经 tex_service 门面晚绑定（避免循环导入，
并保持 tests 对 services.tex_service.call_json_extraction_api 的 patch 语义）。
"""
from services.config_service import ConfigService
from services.prompts import BASIC_INSIGHT_PROMPT
from services.workflow_common import fail_workflow, safe_complete, safe_stage, safe_start
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown

try:
    from backend.constants import MetadataConfig
except ImportError:
    from constants import MetadataConfig


async def run_tex_workflow(doc_id, path, db):
    """任务链：tex/zip → ocr_markdown（跳过 OCR API）→ Basic Insight。
    签名匹配 task_manager 的 task_func(doc_id, *args, db=...) 调用约定。"""
    from services.tex_service import (call_json_extraction_api, convert_tex,
                                      convert_tex_zip, _extract_latex_title,
                                      _find_main_tex)
    try:
        await safe_start(doc_id, "tex")
        await safe_stage(doc_id, 10, "解析 LaTeX 源文件")
        db.update_document_ocr(doc_id, "processing")
        if path.lower().endswith(".zip"):
            md = convert_tex_zip(path, path + "_src")
            title = _extract_latex_title(_find_main_tex(path + "_src"))
        else:
            md = convert_tex(path)
            title = _extract_latex_title(path)
        cleaned = clean_ocr_markdown(md)      # 复用现有字段清洗（已验证兼容）
        title = title or extract_title_from_markdown(md)
        await safe_stage(doc_id, 60, "生成 Markdown")
        db.update_document_ocr(doc_id, "completed", markdown=cleaned, raw=md, title=title)
        cfg = ConfigService(db).get_extract_config()
        await safe_stage(doc_id, 75, "提取 Basic Insight")
        try:
            # tex2txt 产物不含标题行（\title{} 在导言区，已抽到 doc.title）；
            # 显式前置标题供 LLM 提取——否则严格模型对 title 返回 null
            # （OCR 路径 markdown 天然含标题，无此问题）。仅改 LLM 输入，
            # 存储 markdown 不变（证据引文锚定仍以存储文本为准）。
            llm_input = f"# {title}\n\n{cleaned}" if title else cleaned
            metadata_json = await call_json_extraction_api(llm_input, cfg, BASIC_INSIGHT_PROMPT)
            db.add_document_metadata(doc_id, MetadataConfig.DEFAULT_LABEL, metadata_json)
        except Exception as e:
            print(f"[TexWorkflow] Basic Insight Stage Error: {e}")  # 不阻断主链路
        await safe_complete(doc_id)
    except Exception as e:
        await fail_workflow(doc_id, db, e, log_prefix="TexWorkflow")
