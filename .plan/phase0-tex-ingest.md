# Phase 0 实施方案与风险文档：tex2txt 摄入（LaTeX → ocr_markdown）

**日期**: 2026-10-14 ｜ **分支**: `feature/tex-ingest`（全测试绿后才可合 `main`，agents.md §1）
**上游总方案**: `plans/integrate-paper-tools.md` §4 Phase 0（本文档是其展开）｜ **组件源**: `paper-tools/tex2txt/src/tex2txt/`（8 个 `.py`，纯 stdlib 零依赖）。所有组件行为断言均已对照源码逐行验证，推测处标"未验证"；本阶段零 vendor 修改。

## 1. 目标与范围

**做什么**
- vendor 进 `backend/vendor/tex2txt/`，经薄适配层 `backend/services/tex_service.py` 暴露：`convert_tex(main_tex_path) -> str`（单 `.tex`，自动展开 `\input`/`\include`）、`convert_tex_zip(zip_path, dest_dir) -> str`（arXiv 源码包 → 探测主 `.tex` → Markdown）。
- `POST /documents/add`、`/workspace/sync`、`/documents/{id}/reprocess` 按扩展名分流：`.pdf` 走现有 `run_full_ocr_workflow`；`.tex/.zip` 走新 `run_tex_workflow`——**跳过 OCR API**，直接写 `ocr_markdown` 并触发 Basic Insight。
- 前端放开 `.tex/.zip` 上传，并修复现存"Import 按钮无文件输入框"缺陷（§3.7）。

**不做什么（明确排除）**
- 排除 `gui.py`（tkinter）、`cli.py`、`__main__.py`：只用库 API（`resolve_inputs` + `process_tex`，经 `__init__.py:7-31` 再导出）。
- 不改 `documents` 表结构（无迁移）；不引入新依赖（tex2txt 纯 stdlib，`python_embed` 直接可用）；不做 DOI 校验（Phase 1）/知识层（Phase 2）；不处理 `.bib` 内容；非 UTF-8 编码只给明确错误，不做 latin-1 转码兜底（风险 R2）。

## 2. 组件源码分析（已逐行验证）

### 2.1 模块清单

| 文件 | 职责 | vendor？ |
|---|---|---|
| `__init__.py` | 再导出 `resolve_inputs`/`protect_environments`/`process_tex`/`PROTECTED_ENVS`（:7-31） | ✅ |
| `processor.py` | `process_tex(text)` 流水线编排（:46-105） | ✅ |
| `resolver.py` | `\input`/`\include` 递归展开（:29-80） | ✅ |
| `transforms.py` | 12 个可组合文本变换 | ✅ |
| `environment.py` | 环境保护/还原，`PROTECTED_ENVS`（:18-27） | ✅ |
| `cli.py` / `gui.py` / `__main__.py` | CLI / tkinter GUI / `python -m` 垫片 | ❌ 入口，不拷贝 |

> ⚠️ `__main__.py:6` 在 **import 时即执行 `main()`**：vendor 目录不得包含它，任何代码禁止 `import tex2txt.__main__`。

### 2.2 `process_tex` 流水线（processor.py:46-105，14 步）

| 步 | 调用（位置） | 效果 |
|---|---|---|
| 0 | `_extract_body`（:31-43） | 截取 `\begin{document}`…`\end{document}`；**两者都无则全文保留**（:36-39） |
| 1 | `remove_comments`（transforms.py:138-144） | 删非转义 `%` 到行尾（`\%` 经 `\x00PERCENT\x00` 保护后还原） |
| 2 | `protect_environments`（environment.py:40-101） | 栈匹配最外层受保护环境 → 占位符 `\x00BLOCK_N\x00`（:92） |
| 3 | `process_abstract`（transforms.py:155-169） | abstract → `# Abstract\n\n…` |
| 4 | `remove_metadata`（transforms.py:172-176 + :59-67） | 删 `\maketitle`、`\bibliography{…}`、`\bibliographystyle{…}`、IEEE 元数据 |
| 5 | `process_sections`（transforms.py:179-186） | `part/chapter/section→#`、`subsection→##`…`subparagraph→#####`（映射表 :48-56） |
| 6 | `process_formatting`（transforms.py:189-199） | `\textbf→**`、`\textit/\emph→*`、`\textsf/\texttt/\textsc→去壳` |
| 7-8 | `process_citations`（:202-210）+ `process_footnotes`（:213-221） | `\cite→[citation]`、`\ref→[ref]`、`\label→[label]`、`\pageref`、`\eqref`；`\footnote{…}→" (…) "` 行内化 |
| 9 | `process_lists`（:224-250） | itemize→`- `、enumerate→`1. ` |
| 10 | `process_special_chars`（:12-45, :147-152） | `\&→&`、`\textemdash→—` 等 33 项；`~→空格`（:151 全文替换） |
| 11 | `_remove_remaining_commands`（:260-303） | 花括号计数删 `\title/\author/\thanks`、间距/字号命令；**不删** `\documentclass`、`\usepackage` |
| 12-14 | 还原环境（processor.py:96-97）→ `_cleanup_whitespace`（:253-257）→ 占位符兜底（:103） | 占位符替换回原始 LaTeX；`\n{3,}→\n\n`、strip；`re.sub(r'\x00[A-Z_]+\d+\x00','',…)` |

### 2.3 `resolve_inputs` 行为（resolver.py:29-80）

- 路径解析（`_resolve_path` :18-26）：ref 补 `.tex` 后缀（:21-22）；**绝对路径 ref 原样返回**（:23-24）；否则相对当前文件目录 normpath。
- **root_dir 回退**（:72-75）：相对当前文件找不到时，用 `os.path.join(root_dir, 'dummy.tex')` 再试（借 `dirname` 取 root_dir，模拟 LaTeX 搜索路径）；root_dir 默认主文件目录（:49-50）。
- **循环检测**（:52-55）：`seen` 为绝对路径集，命中返回 `''`。**怪癖：`seen` 跨递归共享（:76 引用传递），同一文件被 `\input` 两次（含非循环的菱形引用）第二次展开为 `''`——会丢内容。**
- 缺文件（:57-59）：stderr 警告后返回 `''`，不抛异常。编码（:61）：`encoding='utf-8'` 严格模式、**无回退**，非 UTF-8 抛 `UnicodeDecodeError` 冒泡。每层 `\input` 一次 Python 递归，数百文件长链有 `RecursionError` 风险（未验证阈值）。

### 2.4 环境保护/还原（environment.py:40-101）

- `PROTECTED_ENVS`（:18-27）24 项：`figure/figure*`、`table/table*`、`tikzpicture`、`algorithm/algorithmic`、`equation/align/gather/multline/alignat/flalign`（含 `*`）、`subfigure/subfig` 等；`_ensure_set`（:30-37）补无星名。
- 栈匹配（:64-70）：`\end{X}` 仅当栈顶同名才配对；只取不重叠的最外层（:77-80）。被保护块全程原样保留、第 12 步还原——**输出 Markdown 中会残留 `\includegraphics{…}`、`\begin{tabular}…`、`$…$` 等原始 LaTeX**（vendor 设计即如此）。

### 2.5 输出形态与项目侧兼容性（已核实）

典型输出：`# Abstract` → `# 1. Introduction`（H1–H5 层级）、`[citation]`/`[ref]` 字面 token、受保护环境为原始 LaTeX。

- `clean_ocr_markdown`（text_processor.py:3-32）兼容性：ref/det 标签清理对 tex 输出无匹配（空操作）；`\coloneqq` 等 3 个替换无害；`\n\s*#`→`\n#` 仅规范标题缩行；空行压缩幂等。**结论：可直接复用，tex 分支无需改 `text_processor.py`。** `parse_structured_ocr_content`（text_processor.py:34-105）对无 `title/text` 标签的纯 Markdown 返回空 blocks（现有单测 `test_parse_structured_ocr_content_ignores_plain_markdown` 即此断言），`MarkdownViewer`（src/components/reader/MarkdownViewer.tsx:19,74,105）无 blocks 时回退渲染原始 `content`——**Reader 渲染 tex 输出无需改动**。

### 2.6 已知怪癖与适配策略

| # | 怪癖 | 源码依据 | 适配策略 |
|---|---|---|---|
| Q1 | 无 `\begin{document}` 时全文处理，`\documentclass`/`\usepackage` 残入输出 | processor.py:36-39；transforms.py:260-303 无对应模式 | 单测固化现状，不额外清洗 |
| Q2 | 首个 H1 恒为 `# Abstract`（步 3 先于步 5），`extract_title_from_markdown` 会把标题取成 "Abstract" | transforms.py:155-169 vs :179-186；text_processor.py:112 | workflow 用 `\title{…}` 花括号计数提取标题（§3.4） |
| Q3 | 同一文件二次 `\input` 展开为 `''`（菱形引用丢内容） | resolver.py:52-55, :76 | 接受为上游局限；单测固化 |
| Q4 | 绝对路径 `\input{C:/…/x.tex}` 原样读取任意本地文件 | resolver.py:23-24 | 适配层前置校验拒绝（§3.4，风险 R6） |
| Q5 | `\section{Title \textbf{x}}` 非贪婪正则截断，残留半个命令 | transforms.py:184、:191-193 | 接受；不 vendor 内修复 |
| Q6 | `\bibitem{…}`、`$…$`、`\[…\]`、tabular 原样残留 | transforms.py 无对应模式；environment.py:88-99 | 接受（Reader 当普通文本渲染） |
| Q7 | 非 UTF-8 直接 `UnicodeDecodeError` | resolver.py:61 | 转 `TexConversionError`，doc failed（R2） |
| Q8/Q9 | 缺 `\input` 文件仅 stderr 警告静默丢内容；`__main__.py` import 即执行 CLI | resolver.py:57-59；`__main__.py:6` | 接受（可选记 warning 计数）；vendor 不含该文件（§3.1） |

## 3. 项目侧改动清单（逐文件）

### 3.1 新增 `backend/vendor/tex2txt/`（逐字拷贝，永不修改）
拷贝 `__init__.py`、`processor.py`、`resolver.py`、`transforms.py`、`environment.py` 共 5 个文件；删 `__pycache__/`；不放 `cli.py`/`gui.py`/`__main__.py`/`pyproject.toml`。包内为绝对 import（`from tex2txt.resolver import …`），`backend/vendor` 入 `sys.path` 由适配层在 import 时完成（§3.4），测试运行器无需改（`tests/run_all_tests.py` 只把 `backend/` 放入 `PYTHONPATH`）。验收：与源目录 `diff -r` 逐字一致。

### 3.2 `backend/constants.py`：新增 `TexConfig`（沿用 `OCRConfig` :8-14 常量类模式）
```python
class TexConfig:
    MAX_MAIN_TEX_BYTES = 5 * 1024 * 1024      # 单 .tex 上限（R3）
    MAX_ZIP_BYTES = 100 * 1024 * 1024         # zip 本身上限
    MAX_ZIP_TOTAL_BYTES = 300 * 1024 * 1024   # 解压总上限（防 zip 炸弹）
    MAX_INPUT_DEPTH = 50                      # \input 图遍历深度上限
    MAIN_TEX_NAME_HINTS = ("main", "paper", "article", "root", "ms", "manuscript", "tex")
```

### 3.3 新增 `backend/services/prompts.py`（DRY：提取 ocr_service.py:163-182 内联 prompt）
`default_prompt` 原样移入 `BASIC_INSIGHT_PROMPT` 常量；`ocr_service.py` 唯一改动：`from services.prompts import BASIC_INSIGHT_PROMPT` 替换内联字符串（行为不变，`tests/unit/test_ocr_service.py` 回归保护）。

### 3.4 新增 `backend/services/tex_service.py`（≤200 行；超限则将 `run_tex_workflow` 拆入 `tex_workflow.py`）

```python
import os, re, sys, zipfile

try:
    from backend.constants import TexConfig, MetadataConfig
except ImportError:
    from constants import TexConfig, MetadataConfig

# vendor 加载：backend/vendor 入 sys.path（包内为绝对 import，禁改 vendor）
_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from tex2txt.resolver import resolve_inputs      # vendor API（__init__.py:7-31 亦再导出）
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
```

zip-slip 防护与 arXiv 主 `.tex` 探测：

```python
def _safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    """zip-slip 防护：逐条校验全部条目后才 extractall（tests/security 专项）。"""
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
    """arXiv 源码包主 .tex 探测启发式：\\documentclass(+100) > 被其它 .tex
    \\input 次数×10 > \\begin{document}(+5) > 常见文件名(+3) > 路径更浅(-2/层)。
    最高分且含 \\documentclass 者胜出，否则抛错（不静默产出错内容）。"""
    tex_files = []
    for root, dirs, files in os.walk(dest_dir):
        dirs[:] = [d for d in dirs if d != "__MACOSX"]
        tex_files += [os.path.join(root, f) for f in files if f.lower().endswith(".tex")]
    if not tex_files:
        raise TexConversionError("zip 中未找到 .tex 文件")
    texts = {}
    for p in tex_files:
        try: texts[p] = open(p, encoding='utf-8', errors='ignore').read()
        except OSError: texts[p] = ""
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
    """arXiv 源码包 → Markdown。dest_dir 由调用方提供（{workspace}/<name>.zip_src）。"""
    if os.path.getsize(zip_path) > TexConfig.MAX_ZIP_BYTES:
        raise TexConversionError("zip 文件超过大小上限")
    os.makedirs(dest_dir, exist_ok=True)
    _safe_extract_zip(zip_path, dest_dir)
    return convert_tex(_find_main_tex(dest_dir))
```

安全预检与任务链：

```python
def _validate_input_refs(main_tex_path: str) -> None:
    """镜像 resolver.py:18-26/72-75 的解析语义遍历 \\input 图，拒绝绝对路径
    与越出 root_dir 的 ref（对应 resolver.py:23-24 任意本地文件读，风险 R6）。"""
    root_dir = os.path.dirname(os.path.abspath(main_tex_path))
    seen, stack, depth = set(), [os.path.abspath(main_tex_path)], 0
    while stack:
        cur = stack.pop()
        if cur in seen or depth > TexConfig.MAX_INPUT_DEPTH:
            continue
        seen.add(cur); depth += 1
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
    签名匹配 task_manager.py:102 的 task_func(doc_id, *args, db=...) 调用约定。"""
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
            metadata_json = await call_json_extraction_api(cleaned, cfg, BASIC_INSIGHT_PROMPT)
            db.add_document_metadata(doc_id, MetadataConfig.DEFAULT_LABEL, metadata_json)
        except Exception as e:
            print(f"[TexWorkflow] Basic Insight Stage Error: {e}")  # 不阻断主链路（对齐 ocr_service.py:191-192）
    except Exception as e:
        print(f"[TexWorkflow] CRITICAL ERROR: {e}")
        db.update_document_ocr(doc_id, "failed")
        raise e                                # 交由 task_hub 重试（MAX_RETRIES=3）
```

### 3.5 `backend/server.py`（1 处导入 + 助手 + 3 处分流 + 1 处可选加固）
1. 导入区（:24 后）加 `from services.tex_service import run_tex_workflow`；新增模块级助手：
```python
SUPPORTED_EXTS = (".pdf", ".tex", ".zip")

def _queue_workflow(doc_id, stored_path):
    """按扩展名分流到 OCR 或 tex 工作流（/documents/add、/workspace/sync、/reprocess 共用）"""
    ext = os.path.splitext(stored_path)[1].lower()
    if ext == ".pdf":
        return run_full_ocr_workflow
    if ext in (".tex", ".zip"):
        return run_tex_workflow
    raise ValueError(f"unsupported extension: {ext}")
```
2. `POST /documents/add`（:326-346）：落盘后校验扩展名 ∈ `SUPPORTED_EXTS`，否则 `HTTPException(400, "Unsupported file type")`；:340 改为 `await task_hub.add_task(doc_id, _queue_workflow(doc_id, dest_path), dest_path)`（保留现有 `secure_filename`/防覆盖 `_counter` 逻辑不动）。
3. `POST /workspace/sync`（:242-250）：:250 改用 `_queue_workflow(d['id'], stored_path)`——否则 `.tex` 文档会被误送 `fitz.open` 而 failed。
4. `POST /documents/{doc_id}/reprocess`（:405-411）：同样改用 `_queue_workflow`。
5. （可选加固）`GET /documents/{doc_id}/pdf`（:348-353）：非 `.pdf` 的 `stored_path` 返回 404，避免 `.tex` 被以 `application/pdf` 吐出（:161）。

### 3.6 `backend/services/workspace_service.py`（2 行）
:16 与 :41 的 `f.lower().endswith('.pdf')` 同步改为 `f.lower().endswith(('.pdf', '.tex', '.zip'))`；幂等性依赖 `filename` 去重（:18），不受影响。

### 3.7 前端
- **`src/components/Dashboard.tsx`（必修，含已验证的现存缺陷）**：全文检索证实 `fileInputRef`（:44）已声明、按钮 onClick 调用 `fileInputRef.current?.click()`（:159），**但整个文件没有任何 `<input type="file">` 挂载该 ref**（唯一 `<input>` 是 :172 搜索框）——当前"Import PDF"按钮点击无反应。本阶段补齐：
```tsx
<input ref={fileInputRef} type="file" accept=".pdf,.tex,.zip" className="hidden" onChange={handleFileChange} />
```
  :163 按钮文案 `Import PDF` → `Import PDF / LaTeX`。`Dashboard.test.tsx` 补用例：存在 `accept=".pdf,.tex,.zip"` 的文件输入（满足 agents.md §6 事件处理器全覆盖）。
- **`src/components/Reader.tsx`（小改）**：:30 `viewMode` 初值按扩展名分流——`.tex/.zip` 默认 `'markdown'`，否则默认 `'split'`（否则 PdfViewer 对 `.tex` 请求 `/files/<name>.tex`，而 server.py:161 一律以 `application/pdf` 返回，左侧窗格必坏）：
```tsx
const [viewMode, setViewMode] = useState<'split' | 'pdf' | 'markdown'>(
  /\.(tex|zip)$/i.test(doc.filename) ? 'markdown' : 'split'
);
```
- **`src/api/client.ts`：无需改动**——`uploadDocument(file)`（:59-65）为通用 FormData 提交，`.tex/.zip` 走同一 `POST /documents/add`（已核实，特此排除）。

## 4. 数据流与状态机

```
PDF 路（现状）: upload .pdf → db.add_document(..., "uploaded", dest)  [ocr_status 默认 'pending']
  → task_hub.add_task(doc_id, run_full_ocr_workflow, dest_path) → fitz 渲染 → DeepSeek-OCR API 逐页并发
  → clean_ocr_markdown → call_json_extraction_api → document_metadata('Basic Insight') → ocr_status='completed'

TeX 路（新增）: upload .tex/.zip → db.add_document(..., "uploaded", dest)  ['pending']
  → task_hub.add_task(doc_id, run_tex_workflow, dest_path)
  → [.zip] _safe_extract_zip → _find_main_tex ；[.tex] 直接用
  → resolve_inputs + process_tex（纯本地，零网络零 key）→ clean_ocr_markdown
  → update_document_ocr('completed', markdown, raw=展开后 LaTeX, title=\title{…})
  → call_json_extraction_api → document_metadata('Basic Insight')
```

状态机（`documents.ocr_status` 真实取值；注意 server.py:339 的第二参 `"uploaded"` 是 `original_path` 字面量而非状态）：
```
pending ──► processing ──► completed （Basic Insight 失败仍 completed，Dashboard 显示 'partial'）
   │             └──► failed ──► task_hub 自动重试 ≤3 次（RETRY_BACKOFF=[1,5,30]）
```
与 PDF 路差异：① 无 OCR 网络阶段，转换在 worker 内同步完成；② 失败原因为编码/空输出/zip 非法/探测失败，经 `TexConversionError` 面向用户；③ `ocr_raw` 存展开后的完整 LaTeX。注意 `update_document_ocr`（database.py:111-131）对空串不更新（真值判断），故 `convert_tex` 必须对空输出抛错而非写空。`/workspace/sync`（server.py:236-254）会对"无 markdown/无 Basic Insight/pending/failed"文档重排队，tex 文档亦在列，故 :250 必须分流（§3.5-3）。

## 5. 测试计划（unittest；UUID 临时目录；动态路径发现定位 `backend/`）

> 骨架沿用：向上遍历找 `backend/` 并 `sys.path.insert`（tests/unit/test_workspace.py:8-17）；临时数据 `uuid.uuid4().hex` 命名，`tearDown` 清理含 `-wal/-shm`（tests/security/test_final_audit.py:28-41）。适配层自行把 `backend/vendor` 入 `sys.path`，测试无需额外配置。

### 5.1 `tests/unit/test_tex_service.py`（新增）
`test_convert_basic_sections_and_formatting`（`\section{Intro}`→`# Intro`、`\textbf{x}`→`**x**`）；`test_body_extraction_drops_preamble`；`test_no_document_environment_keeps_all`（固化 Q1）；`test_input_expansion_sibling_and_subdir`（含无扩展名 ref）；`test_root_dir_fallback`（resolver.py:72-75）；`test_cyclic_input_terminates`（a→b→a 不死循环）；`test_diamond_input_second_expansion_empty`（固化 Q3）；`test_missing_input_warns_and_continues`；`test_non_utf8_raises_tex_conversion_error`（Q7/R2 回归）；`test_empty_output_raises`；`test_protected_environment_restored_verbatim`（equation 原样）；`test_citations_and_footnotes_placeholders`（`[citation]`、`(n)`）；`test_absolute_input_ref_rejected`（R6 回归）；`test_oversized_main_tex_rejected`（R3）；`test_find_main_tex_heuristics`（多候选打分 + 无 `\documentclass` 抛错）；`test_convert_tex_zip_happy_path`（zip 含 `#` 标题）；`test_extract_latex_title_brace_counting`（`\title{A \textbf{B} C}`→`A \textbf{B} C`，Q2 回归）。

### 5.2 `tests/security/test_tex_zipslip.py`（新增，Phase 0 一票否决项）
`test_parent_traversal_entry_rejected`（`../evil.tex` 拒绝且 dest 外不存在该文件）；`test_absolute_path_entry_rejected`（`/etc/evil.tex`、`C:/Windows/evil.tex`）；`test_symlink_entry_not_materialized`（`external_attr` 高 16 位 `0o120000` → 拒绝；即便放行也 `assertFalse(os.path.islink(...))`）；`test_zip_bomb_rejected`（解压总量超限）；`test_deep_nested_traversal_rejected`（`a/b/../../../../evil.tex`）；`test_absolute_input_ref_no_file_leak`（恶意 `.tex` 绝对 `\input` → 拒绝且目标内容不出现在输出）。

### 5.3 `tests/integration/test_tex_upload_flow.py`（新增，仿 test_api_upload_flow.py:9-39 骨架）
前置：`sys.argv = [sys.argv[0], "38392", uuid_ws]` 后再 `import server`；`state.initialize(test_ws)`；`TestClient(app)` 上下文触发 lifespan 启动 worker。
`test_upload_tex_routes_to_tex_workflow`（`@patch('server.run_tex_workflow')`；POST `.tex`→200、文件落盘、mock 收到 dest_path、OCR workflow 未被调用）；`test_upload_zip_routes_to_tex_workflow`；`test_upload_unsupported_ext_rejected`（`.exe`→400）；`test_full_tex_flow_completed`（patch `services.tex_service.call_json_extraction_api`；轮询至 `completed`；`ocr_markdown` 含 `#`；`document_metadata` 有 `label='Basic Insight'` 行；`title` 等于 `\title{…}` 而非 "Abstract"）；`test_workspace_sync_routes_tex`（workspace 放 `.tex`；POST `/workspace/sync` → tex workflow 被调用、OCR workflow 未对该 doc 调用）。`tests/system/` 另加可选真实 arXiv zip 用例（`@unittest.skipUnless(os.environ.get("AC_NETWORK"), …)` 默认跳过）。前端：`Dashboard.test.tsx`/`Reader.test.tsx` 补 §3.7 用例。执行：`run_tests.bat`（并行+自动清理）+ `pnpm build` + `pnpm test`。

## 6. 风险登记表

| # | 风险 | 严重度 | 缓解 | 检测手段 |
|---|---|---|---|---|
| R1 | **zip-slip**：恶意 zip `../` 条目写出 workspace | **高** | `_safe_extract_zip` 逐条校验（绝对路径/盘符/`commonpath`/符号链接/总量上限），通过才 `extractall` | security 5 个对抗用例（§5.2）红→绿门禁 |
| R2 | 非 UTF-8 `.tex` 触发 `UnicodeDecodeError` 任务 failed | 中 | 适配层转 `TexConversionError` 明确消息；可重试；latin-1 兜底列后续 | unit 回归；system 真实包抽样 |
| R3 | 巨型 tex/zip 拖慢 worker 或 OOM | 中 | `TexConfig` 三级大小上限，超限即 failed 不拖队列 | unit 超大文件用例；worker 并发下耗时观测 |
| R4 | 主 `.tex` 探测失败/探错（多 `\documentclass` 特刊包） | 中 | 启发式打分 + 失败即抛错（用户可见原因，不静默错内容） | unit 多候选 fixture；system 人工抽检 |
| R5 | **vendor 与上游漂移**（paper-tools 更新失同步） | 中 | vendor 只进不出；升级=整包替换+`diff -r` 审查；适配层隔离全部定制 | 合入前 `git diff --stat backend/vendor` 须为空（除首拷） |
| R6 | 恶意 `.tex` 借绝对路径 `\input` 读任意本地文件并经 Basic Insight 外发至 LLM API | 中 | `_validate_input_refs` 前置遍历拒绝绝对/越界 ref；与 PDF 路"内容上云"同构信任模型下边际风险有界 | security 用例；ref 遍历与 vendor 语义一致性单测 |
| R7 | 输出与 `clean_ocr_markdown`/Reader 不兼容（`\bibitem`、`$…$`、tabular 残留） | 低 | 已验证兼容（§2.5）：clean 为空操作、MarkdownViewer 回退原始 markdown | unit 固化断言；integration 断言含 `#`；人工目检 |
| R8 | 首个 H1 为 `# Abstract` 污染 `documents.title` | 低 | `_extract_latex_title` 花括号计数提取（Q2） | unit + integration 断言 title≠"Abstract" |
| R9 | `\input` 菱形引用丢内容（vendor 语义局限） | 低 | 文档化 + 单测固化；不 vendor 内修复 | unit 固化断言（防未来误改 vendor） |
| R10 | `xxx.zip_src` 解压目录残留 workspace 占空间 | 低 | 与 PDF 同目录策略一致；总量上限约束；删文档仅删 `stored_path`（现状） | 人工检查；后续可加清理任务 |

## 7. 验收标准（可勾选）

- [ ] `backend/vendor/tex2txt/` 含 5 个 `.py`，与源目录 `diff -r` 逐字一致；无 `__pycache__`/`cli.py`/`gui.py`/`__main__.py`/`pyproject.toml`
- [ ] `python_embed/python.exe -c "import sys; sys.path.insert(0,'backend/vendor'); import tex2txt; print(tex2txt.process_tex)"` 成功
- [ ] `python_embed/python.exe tests/unit/test_tex_service.py` 全绿（17 用例）
- [ ] `python_embed/python.exe tests/security/test_tex_zipslip.py` 全绿（zip-slip/绝对路径/符号链接/炸弹全部拒绝）
- [ ] `python_embed/python.exe tests/integration/test_tex_upload_flow.py` 全绿（分流、400、全流程 completed + Basic Insight）
- [ ] 上传 `.tex`：Reader 显示分节 Markdown，Dashboard completed，Basic Insight 有内容，`title` 为真实标题；上传 arXiv zip：探测到主 tex，Reader 显示全文，多章节 `\input` 包内容完整（除已知 Q3）
- [ ] 非 UTF-8 `.tex`：任务 failed 且错误信息可读（无裸 traceback 到 UI）
- [ ] `run_tests.bat` 全套绿；`pnpm build` + `pnpm test` 绿
- [ ] `git diff --stat -- backend/vendor` 仅含首次拷贝；`ocr_service.py` diff 仅 prompt 提取一行
- [ ] feature 分支合入 `main`（agents.md §1）

## 8. 回滚策略

1. 无 schema 变更、无迁移、无新配置项（不碰 `documents` 表与 ConfigService）→ 回滚即代码级回退。
2. 未合 main：`git checkout main` 后删 `feature/tex-ingest` 分支，全部改动消失。
3. 已合 main：`git revert <mergecommit>`（改动文件互不重叠：`backend/vendor/`、`services/tex_service.py|prompts.py`、`server.py`、`workspace_service.py`、`constants.py`、`Dashboard.tsx`、`Reader.tsx`，无冲突预期）。已产出的 `.tex/.zip` 文档记录保留无害（`ocr_markdown` 为静态文本，PDF 行为不变），需要时经 UI 删除；`*.zip_src` 目录可手工清理，不影响 DB。

## 9. 工作量估计（合计约 7 小时）

vendor 拷贝+diff+冒烟 0.5 ｜ `tex_service.py` 实现 2.0 ｜ server/workspace/constants/prompts 改动 1.0 ｜ unit 测试 1.5 ｜ security 测试 0.75 ｜ integration 测试 1.0 ｜ 前端+Vitest 0.75 ｜ 全量回归+手工验收 0.5

## 10. 实施顺序

1. `git checkout -b feature/tex-ingest`（从最新 main）。
2. 拷贝 5 个 vendor 文件 → `backend/vendor/tex2txt/`；删 `__pycache__`；`diff -r` 验证；import 冒烟。
3. `constants.py` 加 `TexConfig`；建 `services/prompts.py` 并改 `ocr_service.py` 一行；跑 `tests/unit/test_ocr_service.py` 确认无回归。
4. 实现 `backend/services/tex_service.py`（§3.4 骨架；严控 ≤200 行，超限拆 `tex_workflow.py`）。
5. 写 `tests/unit/test_tex_service.py`（§5.1）跑绿。
6. 写 `tests/security/test_tex_zipslip.py`（§5.2）跑绿（先红后绿，测试先行）。
7. 改 `server.py`（400 校验 + `_queue_workflow` 三处分流 + 导入）、`workspace_service.py`（两处扩展名）。
8. 写 `tests/integration/test_tex_upload_flow.py`（§5.3）跑绿。
9. 前端：`Dashboard.tsx` 补隐藏 file input + accept + 文案；`Reader.tsx` viewMode 分流；补 Vitest 用例；`pnpm build` + `pnpm test`。
10. 全量 `run_tests.bat`；手工验收：真实 `.tex` + arXiv zip 上传，Reader/Basic Insight/失败路径各目检一次。
11. 合入 `main`（agents.md §1）；在 `plans/integrate-paper-tools.md` Phase 0 验收项打勾。（后续可选）latin-1 转码兜底（R2）、`xxx.zip_src` 清理任务（R10）。
