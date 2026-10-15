"""tex2txt 适配层：.tex/.zip → Markdown → 触发现有 Basic Insight 链路。

vendor（backend/vendor/tex2txt/）逐字拷贝不修改；本层负责：
安全预检（绝对路径 \input 拒绝）、zip-slip 防护、arXiv 主 .tex 探测、
任务链编排。异常统一抛 TexConversionError（消息面向用户）。
"""
import os
import re
import sys
import zipfile

try:
    from backend.constants import TexConfig, MetadataConfig
except ImportError:
    from constants import TexConfig, MetadataConfig

# vendor 加载：backend/vendor 入 sys.path（包内为绝对 import，禁改 vendor）
_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from tex2txt.resolver import resolve_inputs      # vendor API
from tex2txt.processor import process_tex        # vendor API
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown
from services.prompts import BASIC_INSIGHT_PROMPT
from services.ai_service import call_json_extraction_api
from services.config_service import ConfigService


class TexConversionError(Exception):
    """LaTeX 转换失败（编码/空输出/zip 非法/探测失败等），消息面向用户。"""


def convert_tex(main_tex_path: str) -> str:
    """单 .tex（含 \\input 展开）→ Markdown。失败抛 TexConversionError。"""
    if os.path.getsize(main_tex_path) > TexConfig.MAX_MAIN_TEX_BYTES:
        raise TexConversionError("主 .tex 文件超过大小上限")
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


def _safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    """zip-slip 防护：逐条校验全部条目后才 extractall。"""
    dest_real = os.path.realpath(dest_dir)
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if os.path.isabs(name) or name.startswith(("/", "\\")) or os.path.splitdrive(name)[0]:
                raise TexConversionError(f"zip 含绝对路径条目: {name}")
            target = os.path.realpath(os.path.join(dest_real, name))
            if os.path.commonpath([dest_real, target]) != dest_real:
                raise TexConversionError(f"zip-slip 条目被拒绝: {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise TexConversionError(f"zip 含符号链接条目: {name}")
            total += info.file_size
            if total > TexConfig.MAX_ZIP_TOTAL_BYTES:
                raise TexConversionError("zip 解压总量超限")
        zf.extractall(dest_real)   # 全部条目已通过校验


def _find_main_tex(dest_dir: str) -> str:
    """arXiv 源码包主 .tex 探测：\\documentclass(+100) > 被 \\input 次数×10 >
    \\begin{document}(+5) > 常见文件名(+3) > 路径更浅(-2/层)。"""
    tex_files = []
    for root, dirs, files in os.walk(dest_dir):
        dirs[:] = [d for d in dirs if d != "__MACOSX"]
        tex_files += [os.path.join(root, f) for f in files if f.lower().endswith(".tex")]
    if not tex_files:
        raise TexConversionError("zip 中未找到 .tex 文件")
    texts = {}
    for p in tex_files:
        try:
            texts[p] = open(p, encoding='utf-8', errors='ignore').read()
        except OSError:
            texts[p] = ""
    stems = {p: os.path.splitext(os.path.basename(p))[0] for p in tex_files}
    refs = {p: sum(1 for q, qt in texts.items() if q != p
                   and re.search(r'\\(?:input|include)\{' + re.escape(stems[p]) + r'\}', qt))
            for p in tex_files}
    best, best_score = None, -1
    for p in tex_files:
        t = texts[p]
        score = (100 if r"\documentclass" in t else 0) + (5 if r"\begin{document}" in t else 0)
        score += 10 * refs[p] - 2 * os.path.relpath(p, dest_dir).count(os.sep)
        if stems[p].lower() in TexConfig.MAIN_TEX_NAME_HINTS:
            score += 3
        if score > best_score:
            best, best_score = p, score
    if best is None or best_score < 100:
        raise TexConversionError("未探测到含 \\documentclass 的主 .tex")
    return best


def convert_tex_zip(zip_path: str, dest_dir: str) -> str:
    """arXiv 源码包 → Markdown。dest_dir 由调用方提供（{path}.zip_src）。"""
    if os.path.getsize(zip_path) > TexConfig.MAX_ZIP_BYTES:
        raise TexConversionError("zip 文件超过大小上限")
    os.makedirs(dest_dir, exist_ok=True)
    _safe_extract_zip(zip_path, dest_dir)
    return convert_tex(_find_main_tex(dest_dir))


def _validate_input_refs(main_tex_path: str) -> None:
    """镜像 resolver 的解析语义遍历 \\input 图，拒绝绝对路径与越出 root_dir 的
    ref（对应 resolver.py:23-24 任意本地文件读，风险 R6）。"""
    root_dir = os.path.dirname(os.path.abspath(main_tex_path))
    seen, stack, depth = set(), [os.path.abspath(main_tex_path)], 0
    while stack:
        cur = stack.pop()
        if cur in seen or depth > TexConfig.MAX_INPUT_DEPTH:
            continue
        seen.add(cur)
        depth += 1
        try:
            text = open(cur, 'r', encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue  # 读取问题交由 resolve_inputs/convert_tex 报错
        for m in re.finditer(r'\\(?:input|include)\{(.+?)\}', text):
            ref = m.group(1).strip()
            if os.path.isabs(ref) or os.path.splitdrive(ref)[0]:
                raise TexConversionError(f"拒绝绝对路径 \\input 引用: {m.group(1)}")
            if not ref.endswith('.tex'):
                ref += '.tex'
            child = os.path.normpath(os.path.join(os.path.dirname(cur), ref))
            if not os.path.isfile(child):
                child = os.path.normpath(os.path.join(root_dir, ref))
            if os.path.commonpath([root_dir, child]) != root_dir:
                raise TexConversionError(f"拒绝越界 \\input 引用: {m.group(1)}")
            stack.append(child)


def _extract_latex_title(main_tex_path: str) -> str | None:
    """花括号计数提取 \\title{…}，规避怪癖 Q2（首个 H1 是 Abstract）。"""
    try:
        text = open(main_tex_path, 'r', encoding='utf-8', errors='ignore').read()
    except OSError:
        return None
    m = re.search(r'\\title\{', text)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(text) and depth:
        depth += 1 if text[i] == '{' else (-1 if text[i] == '}' else 0)
        i += 1
    return text[m.end():i - 1].strip() or None


async def run_tex_workflow(doc_id, path, db):
    """任务链：tex/zip → ocr_markdown（跳过 OCR API）→ Basic Insight。
    签名匹配 task_manager 的 task_func(doc_id, *args, db=...) 调用约定。"""
    try:
        db.update_document_ocr(doc_id, "processing")
        if path.lower().endswith(".zip"):
            md = convert_tex_zip(path, path + "_src")
            title = _extract_latex_title(_find_main_tex(path + "_src"))
        else:
            md = convert_tex(path)
            title = _extract_latex_title(path)
        cleaned = clean_ocr_markdown(md)      # 复用现有字段清洗（已验证兼容）
        title = title or extract_title_from_markdown(md)
        db.update_document_ocr(doc_id, "completed", markdown=cleaned, raw=md, title=title)
        cfg = ConfigService(db).get_extract_config()
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
    except Exception as e:
        print(f"[TexWorkflow] CRITICAL ERROR: {e}")
        db.update_document_ocr(doc_id, "failed")
        raise e                                # 交由 task_hub 重试（MAX_RETRIES=3）
