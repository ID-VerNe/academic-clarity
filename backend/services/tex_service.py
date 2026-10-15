"""tex2txt 适配层门面（B-SRP-12 拆分）。

vendor（backend/vendor/tex2txt/）逐字拷贝不修改；本层负责 .tex/.zip →
Markdown 转换与任务链入口。实现拆分至：tex_security（安全预检/大小上限）、
tex_detect（主 .tex 探测/标题提取）、tex_workflow（任务链编排）；
本模块保留 convert_tex/convert_tex_zip 并全量 re-export（含 TexConfig），
保持既有导入路径与异常契约不变。
"""
import os
import sys

# vendor 加载：backend/vendor 入 sys.path（包内为绝对 import，禁改 vendor）
_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from tex2txt.resolver import resolve_inputs      # vendor API  # noqa: E402
from tex2txt.processor import process_tex        # vendor API  # noqa: E402
from services.ai_service import call_json_extraction_api  # noqa: E402,F401 (patch 目标)
from services.tex_security import (  # noqa: E402,F401
    TexConfig,
    TexConversionError,
    _check_main_tex_size,
    _check_zip_size,
    _safe_extract_zip,
    _validate_input_refs,
)
from services.tex_detect import _extract_latex_title, _find_main_tex  # noqa: E402,F401
from services.tex_workflow import run_tex_workflow  # noqa: E402,F401


def convert_tex(main_tex_path: str) -> str:
    """单 .tex（含 \\input 展开）→ Markdown。失败抛 TexConversionError。"""
    _check_main_tex_size(main_tex_path)
    _validate_input_refs(main_tex_path)
    try:
        md = process_tex(resolve_inputs(main_tex_path))       # vendor 流水线
    except UnicodeDecodeError as e:
        raise TexConversionError(f"非 UTF-8 编码的 .tex: {e}") from e
    except RecursionError as e:
        raise TexConversionError("\\input 嵌套过深") from e
    if not md.strip():
        raise TexConversionError("转换结果为空（可能只有导言区）")
    return md


def convert_tex_zip(zip_path: str, dest_dir: str) -> str:
    """arXiv 源码包 → Markdown。dest_dir 由调用方提供（{path}.zip_src）。"""
    _check_zip_size(zip_path)
    os.makedirs(dest_dir, exist_ok=True)
    _safe_extract_zip(zip_path, dest_dir)
    return convert_tex(_find_main_tex(dest_dir))


__all__ = [
    "TexConversionError",
    "TexConfig",
    "convert_tex",
    "convert_tex_zip",
    "run_tex_workflow",
    "_check_main_tex_size",
    "_check_zip_size",
    "_extract_latex_title",
    "_find_main_tex",
    "_safe_extract_zip",
    "_validate_input_refs",
]
