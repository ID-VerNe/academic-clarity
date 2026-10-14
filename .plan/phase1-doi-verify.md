# Phase 1 实施方案与风险文档：pdf-doi-toolkit DOI 权威校验集成
- **分支**：`feature/doi-verify`（独立 feature 分支，全套测试绿后才可合 `main`，`agents.md` §1）｜**上游方案**：`plans/integrate-paper-tools.md` Phase 1｜**组件版本**：`pdf_doi_toolkit 1.1.0`（`__init__.py:23`）｜ 2026-10-14 ｜ 断言均对照真实源码/实测，未验证处已标注

---

## 1. 目标与范围

**要解决的问题**：当前流水线为 上传 PDF → DeepSeek-OCR → `ocr_markdown` → LLM "Basic Insight" 提取（`backend/services/ocr_service.py:163-190`）→ DB。LLM 提取的 DOI 存在幻觉风险（该 prompt 的 DOI 指令无 schema 约束，且输出字段清单里没有 `doi` 键，见 §2.6）。本阶段用 CrossRef 权威数据校验/更正 DOI，并提供 BibTeX 获取。
**范围（In Scope）**：① DOI 校验——以 LLM 已提取的 `title` + `authors`（+ LLM DOI，若有）查 CrossRef，按标题相似度 + 作者验证定权威 DOI；② BibTeX——对确认的 DOI 走 content negotiation（`Accept: application/x-bibtex`）拉取并缓存；③ DB 加 `doi`/`doi_source`/`bibtex` 三列 + 幂等迁移、新 API 端点、前端「验证 DOI」「复制 BibTeX」入口。

**范围外（Out of Scope）**：不集成 scihub 下载（法律风险）；不做 PDF 文件重命名（vendor 的 `rename_matched()`/`simple_rename_pipeline` 均以改文件名为目标）；不重新解析 PDF 提标题（已有 `ocr_markdown`，§2.1）；不用 x-mol.net 兜底（`xmol.py`，非官方 API，R9）；不做模糊文件名兜底（`fuzzy.py` 解析文件名，本项目输入是 DB 元数据）。

---

## 2. 组件源码分析（`paper-tools/pdf-doi-toolkit/pdf_doi_toolkit/`，11 个 .py 全部通读）

### 2.1 依赖实测结论（已在 `python_embed` 3.10.11 执行）

| 验证项 | 结论 |
|---|---|
| 整包 import | ✅ 纯 stdlib（urllib/json/re/threading/concurrent.futures/unicodedata），v1.1.0 |
| PDF 库 | ✅ `fitz` 可用；❌ `pypdf`/`PyPDF2`/`pdfminer` 均缺失（无 pip/uv，不能装） |
| `title_extractor.py` 依赖 | **不用任何 PDF 解析库**；`title_extractor.py:83` 用 subprocess 调 `["uv","run","python","ocr_cli.py",...]` 唤起外部 DeepSeek-OCR 项目 |
| 命名空间包导入 / sqlite 版本 | ✅ `from vendor.pdf_doi_toolkit import CrossRefClient` 无需 `__init__.py`（PEP 420，模拟 `backend/vendor/` 结构实测）；sqlite 3.40.1（≥3.35，支持 `DROP COLUMN`，回滚可行） |

**关键设计结论**：`title_extractor.py` 在本项目**不可用也不需使用**——它依赖 `uv` + 外部 DeepSeek-OCR 目录（`title_extractor.py:162-192` 探测必然失败返回 `ocr_dir_not_found`），而本项目标题来自 LLM Basic Insight。适配层只 import `CrossRefClient` 与 utils 纯函数，**不 import** `DOIMatcher`/`PDFScanner`/`TitleExtractor`/`XMolFallback`/`simple_rename_pipeline`，vendor 依赖面最小化（抗漂移，R7）。

### 2.2 `CrossRefClient` API 面（`crossref.py`）

| 成员 | 位置 | 行为 | 返回 |
|---|---|---|---|
| 构造 | `:44-52` | `CrossRefClient(user_agent=None, max_retries=None, concurrency=None, request_delay=None, timeout=None)`，全部可外部注入 | — |
| `search_by_title` | `:59-94` | `GET {base}?query.title={title}&rows=3`（`:200-202`）；`expected_author` 仅供 `_pick_best` 加权 | `{"doi","author","title","note"}`，note ∈ ok/no_results/no_good_match/retries_exhausted |
| `search_by_doi` | `:96-121` | `GET {base}/{doi}`，DOI 直接字符串拼接（`:107`） | 成功 note=ok；**任何异常都吞掉**返回 `{"doi","note":str(e)[:60]}` |
| `_request` | `:204-225` | 429→指数退避重试；**非 429 的 HTTPError 直接 raise**（`:214-215`）；URLError/OSError/TimeoutError→重试，耗尽返回 None | JSON 或 None |

默认参数（`config.py:8-13`，实测）：`CROSSREF_BASE_URL="https://api.crossref.org/works"`；`MAX_RETRIES=5`；`REQUEST_DELAY=0.35s`；`TIMEOUT=15s`；`USER_AGENT="PDF-DOI-Toolkit/1.0"`（**无 mailto**，R4）。

### 2.3 作者验证与相似度（实测行为）

- `utils.authors_match`（`utils.py:30-70`）三级策略：① 规范化后互相包含；② 姓氏相等（容忍中间名缩写）；③ 姓氏字符集相似度 ≥ `AUTHOR_MATCH_CHAR_THRESHOLD=0.7`（`config.py:20`，`:65-68`）。`normalize_author`（`:11-27`）做 NFC + 统一连字符 + 去空格小写，**不去音符**。
- 实测：`Kutalek/Kutálek=True`、`J. Smith/John Smith=True`、`Gonzalez/González=True`、`Wei Zhou/Wonil Nam=False`、`Lee/Li=False`；**误判**：`Zhang/Chang=True`、`Wang/Wong=True`（R8）。
- **重要缺口（R10）**：`_pick_best` 初始 `best_score=-1`，词重叠为 0 的条目也会被返回（`crossref.py:260,270-271,286-287`）——"标题零相关也可能返回 DOI"，适配层必须自建标题门槛（§3.2 `_title_overlap`）。
- `fuzzy.py` 澄清：任务书中"fuzzy.py 相似度算法"实为 `FilenameParser`（从 PDF 文件名解析 author/year/keywords，`fuzzy.py:42-56`），与文本相似度无关；真正的模糊评分在 `matcher.py:450-487`（作者 50 + 年份 30/20 + 关键词覆盖 20；阈值 70 自动 / 40 人工，`config.py:23-24`）——本项目不用。

### 2.4 BibTeX 能力：**不存在，需适配层新增**

全目录 grep `bibtex|Accept|mailto`：仅 `xmol.py:204` 有 `accept: application/json`；`crossref.py` 只发 `User-Agent` 头（`:111,207`）——**无 content negotiation、无 BibTeX、无 mailto**，`fetch_bibtex` 由适配层自实现（§3.2）。

### 2.5 可复用入口评估

| vendor 入口 |  verdict | 原因 |
|---|---|---|
| `CrossRefClient.search_by_title / search_by_doi` | ✅ 核心复用 | 纯网络，参数可注入 |
| `utils.authors_match / strip_supplement / normalize_author` | ✅ 复用 | 纯函数 |
| `DOIMatcher._check_one`（`matcher.py:158-220`） | ⚠️ 只借鉴逻辑 | 绑定 scanner entry 结构与磁盘缓存；其"作者不匹配则剥 `.s001` 重查"在适配层简化复刻 |
| `DOICache`（`cache.py`）/ `simple_rename_pipeline`（`__init__.py:51-82`） | ❌ | 前者缓存键是 PDF 文件名（本项目缓存落 `documents.bibtex` 列）；后者内含文件重命名，超范围 |
| `PDFScanner`/`TitleExtractor`/`XMolFallback`/`ScienceDirectHandler` | ❌ | 分别绑定 paper-tools 目录结构/外部 OCR/第三方 API/文件名格式 |

### 2.6 项目侧输入的现实（影响适配层）

- Basic Insight prompt（`ocr_service.py:163-182`）**未把 `doi` 列入输出字段**（只有 title/authors/journal_or_conference/date/abstract/keywords/summary）；仅因 `ai_service.py:204-205` 在 prompt 含 "DOI" 时追加一句指令，LLM **可能**返回 `doi` 键——适配层必须容忍缺失。另：`documents.authors` 列（`database.py:55`）经 grep 证实**从未被后端写入**，作者输入只能取自 Basic Insight JSON 的 `authors` 字段（缺失时退化为"仅标题匹配"，§4 `no_author_to_verify`）。

---

## 3. 项目侧改动清单（逐文件）

### 3.1 `backend/vendor/pdf_doi_toolkit/`（新增，逐字拷贝）

拷贝源目录全部 **11 个 .py**（README 结构清单漏列 `cache.py`/`title_extractor.py`，以实际目录为准）：`__init__.py`、`cache.py`、`config.py`、`crossref.py`、`fuzzy.py`、`matcher.py`、`scanner.py`、`sciencedirect.py`、`title_extractor.py`、`utils.py`、`xmol.py`。**不拷** `tests.py`/`demo.py`/`pyproject.toml`/`README.md`/`__pycache__`；拷贝后 `diff -r` 校验一致（验收项）；`backend/vendor/` 永不修改（agents.md）。导入（实测通过）：`from vendor.pdf_doi_toolkit import CrossRefClient`（`server.py:21` 已将 `backend/` 加入 `sys.path`，测试侧 `tests/` 已有动态路径发现样板）。

### 3.2 `backend/services/doi_service.py`（新增，≤200 行，适配层）

```python
"""CrossRef DOI 权威校验适配器。vendor 逐字拷贝不修改；网络调用全部
域名白名单 + timeout + 有限重试 + 失败降级（标记 unverified，不抛断流水线）。"""
import json, re, urllib.request, urllib.error, urllib.parse
from services.config_service import ConfigService

CROSSREF_HOST = "api.crossref.org"
CROSSREF_WORKS = "https://api.crossref.org/works"
DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s?#]+$")     # 防 URL 注入（R1）
TITLE_OVERLAP_MIN = 0.6                             # 自建标题门槛（R10）
class DoiServiceError(Exception): ...

def _client(db):
    """CrossRefClient：UA 注入 mailto（R4）、压底重试参数（R2）。"""
    cfg = ConfigService(db).get_crossref_config()   # 见 3.3
    ua = f"AcademicClarity/1.0 (mailto:{cfg['mailto']})" if cfg["mailto"] else "AcademicClarity/1.0"
    from vendor.pdf_doi_toolkit import CrossRefClient
    return CrossRefClient(user_agent=ua, max_retries=cfg["max_retries"],
                          timeout=cfg["timeout"], request_delay=0.35)

def _assert_safe_url(url: str):
    """SSRF 防线：仅允许 https + api.crossref.org 字面量主机名。"""
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or (p.hostname or "").lower() != CROSSREF_HOST:
        raise DoiServiceError(f"blocked non-crossref url: {url}")

def normalize_doi(raw: str):
    """去 https://doi.org/ 前缀、剥 .sNNN；不过 DOI_RE 返回 None。"""
    if not raw: return None
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", raw.strip(), flags=re.I)
    from vendor.pdf_doi_toolkit.utils import strip_supplement
    d = strip_supplement(d).strip()
    return d if DOI_RE.match(d) else None

def _title_overlap(query: str, cr_title: str) -> float:
    """查询标题词在 CrossRef 标题中的覆盖率（补 vendor 缺口 R10）。"""
    q = {w for w in re.split(r"\W+", (query or "").lower()) if len(w) > 2}
    if not q: return 0.0
    t = {w for w in re.split(r"\W+", (cr_title or "").lower()) if len(w) > 2}
    return len(q & t) / len(q)

def verify_doi(title: str, authors: str, llm_doi: str, db=None) -> dict:
    """→ {"status": verified|corrected|mismatch|unverified, "doi": str|None, "score": int,
         "source": crossref|llm|unverified, "cr_author"/"cr_title": str|None, "note": str}"""
    llm_norm = normalize_doi(llm_doi or "")
    src_llm = {"status": "unverified", "doi": llm_norm, "score": 0,
               "source": "llm" if llm_norm else "unverified"}
    if not title:
        return {**src_llm, "note": "no_title"}
    try:
        res = _client(db).search_by_title(title, authors or None)   # 可能 raise（R5）
    except Exception as e:                       # 网络失败 / 非 429 HTTPError
        return {**src_llm, "note": f"crossref_error: {str(e)[:60]}"}
    cr_doi = normalize_doi(res.get("doi") or "")
    overlap = _title_overlap(title, res.get("title") or "")
    if not cr_doi or overlap < TITLE_OVERLAP_MIN:
        return {**src_llm, "note": res.get("note") or "no_good_match"}
    from vendor.pdf_doi_toolkit.utils import authors_match
    author_ok = bool(authors) and authors_match(authors, res.get("author") or "")
    score = int(50 * overlap) + (50 if author_ok else 0)
    if authors and not author_ok:                # 作者不符 → 绝不改写 DOI
        return {"status": "mismatch", "doi": llm_norm or cr_doi, "score": score,
                "source": "llm", "cr_author": res.get("author"),
                "cr_title": res.get("title"), "note": "author_mismatch"}
    status = "verified" if (not llm_norm or llm_norm.lower() == cr_doi.lower()) else "corrected"
    return {"status": status, "doi": cr_doi, "score": score, "source": "crossref",
            "cr_author": res.get("author"), "cr_title": res.get("title"),
            "note": "no_author_to_verify" if not authors else "ok"}

def fetch_bibtex(doi: str, db=None) -> str:
    """content negotiation：Accept: application/x-bibtex（vendor 无此能力，§2.4）。"""
    d = normalize_doi(doi or "")
    if not d: raise DoiServiceError("invalid doi")
    url = f"{CROSSREF_WORKS}/{urllib.parse.quote(d, safe='')}"   # safe='' 防 ../
    _assert_safe_url(url)
    cfg = ConfigService(db).get_crossref_config()
    req = urllib.request.Request(url, headers={
        "Accept": "application/x-bibtex",
        "User-Agent": f"AcademicClarity/1.0 (mailto:{cfg['mailto']})"})
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as e:
        raise DoiServiceError(f"crossref bibtex HTTP {e.code}")
    except Exception as e:
        raise DoiServiceError(f"crossref bibtex error: {str(e)[:60]}")

def verify_document(db, doc_id: int) -> dict:
    """task 链入口：读 Basic Insight → verify_doi → 落库。"""
    metas = db.get_document_metadata(doc_id)
    insight = next((m for m in metas if m["label"] == "Basic Insight"), None)
    if not insight: return {"status": "unverified", "note": "no_basic_insight"}
    data = json.loads(insight["content_json"])
    result = verify_doi(data.get("title") or "", data.get("authors") or "",
                        data.get("doi") or "", db)
    db.update_document_doi(doc_id, doi=result["doi"], doi_source=result["source"])
    return result
```
配套 `ConfigService.get_crossref_config()`（`backend/services/config_service.py`，遵循 agents.md §5 配置集中；`CROSSREF_MAILTO` 可选，留空用无 mailto UA 仅降速不错败，R4；写入复用现有 `POST /configs?key=...&value=...`，`server.py:317-320`，无需新配置 UI）：

```python
def get_crossref_config(self):
    return {"mailto": self._get_val("CROSSREF_MAILTO", "CROSSREF_MAILTO", ""),
            "timeout": self._get_val_int("CROSSREF_TIMEOUT", "CROSSREF_TIMEOUT", 10),
            "max_retries": self._get_val_int("CROSSREF_MAX_RETRIES", "CROSSREF_MAX_RETRIES", 2)}
```

### 3.3 `backend/database.py`（修改）

1) `init_db()` 的 `safe_write` 块（`database.py:39-73`）末尾追加幂等迁移：

```python
def _migrate_document_doi_columns(self, cursor):
    cursor.execute("PRAGMA table_info(documents)")
    cols = {row[1] for row in cursor.fetchall()}
    for name in ("doi", "doi_source", "bibtex"):
        if name not in cols:
            cursor.execute(f"ALTER TABLE documents ADD COLUMN {name} TEXT")
```

2) 新增写入方法（仿 `update_document_ocr` 动态 SET，`database.py:111-131`）：

```python
def update_document_doi(self, doc_id, doi=None, doi_source=None, bibtex=None):
    with self.safe_write() as cursor:
        updates, params = [], []
        if doi is not None: updates.append("doi = ?"); params.append(doi)
        if doi_source is not None: updates.append("doi_source = ?"); params.append(doi_source)
        if bibtex is not None: updates.append("bibtex = ?"); params.append(bibtex)
        if not updates: return
        params.append(doc_id)
        cursor.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = ?", params)
```

`get_document`/`get_all_documents` 用 `SELECT *`（`database.py:141,155`），新列自动进 API 响应，**无需改查询**；note 不落库（验收以 doi/doi_source 为准）。
### 3.4 `backend/server.py`（修改，新增 2 端点，仿 `server.py:371-388` 风格）

```python
@app.post("/documents/{doc_id}/doi/verify")
async def verify_document_doi(doc_id: int):
    doc = state.db.get_document(doc_id)
    if not doc or not doc.get('ocr_markdown'):
        raise HTTPException(status_code=400)
    try:
        from services.doi_service import verify_document
        result = verify_document(state.db, doc_id)      # 同步纯网络，~秒级
        await ws_manager.send_document_update("updated", doc_id, state.db.get_document(doc_id))
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{doc_id}/bibtex")
async def get_document_bibtex(doc_id: int):
    doc = state.db.get_document(doc_id)
    if not doc: raise HTTPException(status_code=404)
    if doc.get("bibtex"): return {"bibtex": doc["bibtex"]}      # DB 缓存优先
    if not doc.get("doi"): raise HTTPException(status_code=400, detail="no verified doi")
    try:
        from services.doi_service import fetch_bibtex
        bib = fetch_bibtex(doc["doi"], state.db)
        state.db.update_document_doi(doc_id, bibtex=bib)        # 缓存，避免重复请求
        return {"bibtex": bib}
    except DoiServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```
### 3.5 触发点：Basic Insight 之后的 task 链（`backend/services/ocr_service.py`）

在 `ocr_service.py:188-192` 的 Basic Insight `try/except` 块**之后**、`if failed_pages:`（`:194`）之前插入：

```python
# Phase 1: CrossRef DOI 权威校验（失败不阻断主流水线，降级 unverified）
try:
    from services.doi_service import verify_document
    verify_document(db, doc_id)
except Exception as e:
    print(f"[TaskHub] DOI Verify skipped: {e}")
```

**为何不用 `task_hub.add_task` 再排队**：`task_manager.py:69-70` 对同一 `doc_id` 在 `active_task_ids` 中直接 skip，而 OCR worker 执行 `task_func` 期间该 id 仍在集合内（`:102-104` 才 discard）——同 doc_id 二次入队必被拒。直接同步调用最简；最坏耗时 ≈ 7s（R2 参数）。`/workspace/sync` 重跑 OCR 时自动带上校验（`server.py:236-254`）。

### 3.6 前端（4 个文件）

- `src/types/index.ts`：`Document` 加 `doi?: string | null; doi_source?: 'llm'|'crossref'|'unverified'; bibtex?: string | null;`；新增 `export interface DoiVerification { status: 'verified'|'corrected'|'mismatch'|'unverified'; doi: string|null; score: number; source: 'llm'|'crossref'|'unverified'; note?: string; }`。`src/api/client.ts`（统一 client，agents.md §5）加两法：`verifyDoi(docId)` → `POST /documents/${docId}/doi/verify`；`getBibtex(docId)` → `GET /documents/${docId}/bibtex`（均 `getBaseUrl()` + `res.json()`，与现有方法同构）。
- `src/components/reader/MetadataPanel.tsx`：props 加 `docId?: number; onVerified?: () => void;`；当 `label === 'Basic Insight'` 且 metadata 含 `doi` 时，标题行下渲染按钮行：「验证 DOI」（调 `api.verifyDoi` → 展示 `result.status`/`source`，成功回调 `onVerified?.()` 刷新）与「复制 BibTeX」（调 `api.getBibtex` → `navigator.clipboard.writeText`，失败提示 note）。两个 `onClick` 必须补 Vitest（agents.md §6）。
- `src/components/reader/ChatSidebar.tsx:142`：`<MetadataPanel ... docId={docId} onVerified={fetchMetadata} />`（`docId` 为现有 prop，`:20`）。`ReaderToolbar.tsx` 本阶段**不改**（按钮集中 MetadataPanel，避免 Reader 布局回归；总方案的工具栏按钮降级为后续增强）。
---

## 4. 数据流与状态机

```
PDF ─► OCR ─► ocr_markdown ─► LLM Basic Insight(title/authors/doi?) ─► verify_document(db, id)
   ↑ 自动触发：ocr_service 尾部同步调用        ↑ 手动触发：POST /documents/{id}/doi/verify
   ▼  verify_doi(title, authors, llm_doi) 四分支：
   ├─ CrossRef 200 + 标题覆盖≥0.6 + 作者匹配 ─► verified(llm_doi 一致/缺失) 或 corrected(不一致)；doi=权威值，source=crossref
   ├─ CrossRef 200 + 标题覆盖≥0.6 + 作者不符 ─► mismatch，doi 保留 llm_doi，cr_author 入 note
   ├─ CrossRef 200 + 标题覆盖<0.6 或 DOI 非法 ─► unverified，doi 保留 llm_doi
   └─ 网络失败/超时/429耗尽/无结果/无 title ───► unverified，doi 保留 llm_doi
   ▼  documents.doi / doi_source 写入；bibtex 按需经 GET /documents/{id}/bibtex 拉取并缓存
```

`doi_source` 取值语义（`documents.doi_source` 列）：

| 值 | 含义 | 何时写入 |
|---|---|---|
| `crossref` | DOI 已被 CrossRef 权威确认（verified/corrected） | source=crossref |
| `llm` | DOI 仅来自 LLM，未获权威确认（mismatch / 断网但 LLM 有值） | source=llm |
| `unverified` | 无 DOI（LLM 没提取 + 校验失败），列留 NULL | source=unverified |

**离线降级行为**：任何网络异常 → `status=unverified`、保留 LLM 原值、`doi_source` 相应降档；OCR 主流水线仍为 `completed`（`ocr_service.py:197/201` 不受影响）；UI 显示"未校验"徽标而非报错弹窗。`GET /documents` 随 `SELECT *` 带出三列，Dashboard/Reader 无需改查询。
---

## 5. 测试计划（`tests/{unit,integration,security,system}/`，UUID 隔离 + 动态路径发现，`run_tests.bat` 并行）

### 5.1 `tests/unit/test_doi_service.py`（新增，mock `urllib.request.urlopen`，零真实网络）

| 用例 | mock 场景 | 断言 |
|---|---|---|
| `test_crossref_200_verified` / `_corrected` | items 标题词高度重叠 + 第一作者匹配；后者 llm_doi 与权威不一致 | verified（doi=CrossRef 值，score≥75）/ corrected（doi 被更正），source=crossref |
| `test_author_mismatch_keeps_llm` | 标题匹配但作者完全不符 | status=mismatch，doi=llm_doi，**不被改写** |
| `test_title_overlap_below_threshold` | items 标题与查询零词重叠（R10 回归） | status=unverified（vendor 仍返回 doi，适配层必须拒） |
| `test_crossref_404` / `_timeout` | `HTTPError(404)` / `URLError(TimeoutError)` | status=unverified，note 含 crossref_error，**不 raise** |
| `test_crossref_429_then_ok` | 第一次 429、第二次 200 | 重试后 verified |
| `test_no_author_to_verify` | authors="" | status=verified/corrected 且 note=no_author_to_verify |
| `test_llm_doi_missing` | Basic Insight JSON 无 doi 键 | 正常查询，不 KeyError |
| `test_normalize_doi` | `https://doi.org/10.1/a.b`、`10.1/a.b.s001`、`not-a-doi`、`10.1/x@evil` | 前两个归一成功，后两个 None |
| `test_fetch_bibtex_ok` / `_404_timeout` | 200 + `Accept: application/x-bibtex` / HTTPError/URLError | 前者返回字符串且**断言请求头 Accept 值**；后者抛 `DoiServiceError`（端点层转 502） |
| `test_client_params` | — | `_client(db)` UA 含 mailto、max_retries=2、timeout=10（覆盖 vendor 默认） |

### 5.2 `tests/unit/test_database.py`（追加，旧库迁移）

`test_migration_adds_doi_columns`：裸 sqlite 建**旧 schema** documents 表 + 插 1 行 → `Database(path)` 触发迁移 → `PRAGMA table_info` 含三列、旧行完好、`update_document_doi` 可写可读；`test_migration_idempotent`：连续两次 `Database(path)` 不报错、列不重复。

### 5.3 `tests/security/test_final_audit.py`（追加 SSRF 用例）

- `test_bibtex_url_domain_allowlist`：`_assert_safe_url` 对 `http://api.crossref.org/...`、`https://evil.com/`、`https://api.crossref.org.evil.com/`、`https://127.0.0.1/`、`https://api.crossref.org@evil.com/` 全部拒绝，仅精确 `https://api.crossref.org` 放行。
- `test_doi_regex_rejects_injection`：`normalize_doi("10.1/../../etc")`、`"10.1/x@evil.com"`、`"10.1/x?y=1"` 返回 None（堵 `crossref.py:107` 拼接入侵路径）；`test_fetch_bibtex_never_calls_non_crossref`：mock urlopen 记录 URL，断言 host 恒为 `api.crossref.org`。

### 5.4 `tests/integration/test_doi_verify_flow.py`（新增，提取→校验→落库全链）

- `Database(uuid.db)` + `verify_document`：预置 Basic Insight（LLM 错 DOI）→ patch `doi_service._client` 返回权威 DOI → 断言 `documents.doi == 权威值`、`doi_source == 'crossref'`；离线分支（`_client` 抛 `URLError`）→ 断言 `doi_source == 'llm'`、DB 行仍在、无异常外泄。
- API 层（仿 `tests/integration/test_api_upload_flow.py` 的 `sys.argv` 欺骗 + `TestClient` 生命周期）：`POST /documents/{id}/doi/verify` 200 且响应含 result；`GET /documents/{id}/bibtex` 无 doi 时 400、有缓存时二次请求不触发网络（mock 计数断言）。

### 5.5 `tests/system/test_doi_real_network.py`（新增，**可选/默认跳过**）

`@unittest.skipUnless(os.environ.get("DOI_NETWORK_TESTS") == "1", ...)`；真实 DOI（如 `10.1038/nature11704`）验证 `fetch_bibtex` 返回含 `@article`；对 workspace 内真实 PDF 的 Basic Insight 跑端到端。CI 不跑，人工验收跑一次。

### 5.6 前端 Vitest

`src/components/reader/MetadataPanel.test.tsx` 追加：「验证 DOI」点击 → `api.verifyDoi` 被调、状态徽标渲染；「复制 BibTeX」点击 → clipboard 写入成功/失败分支；无 `docId` 或无 doi 字段时按钮不渲染。事件处理器 100% 覆盖（agents.md §6）。
---

## 6. 风险登记表

| # | 风险 | 等级 | 事实依据 | 对策 |
|---|---|---|---|---|
| R1 | **SSRF**：`search_by_doi` 把 DOI 直接拼 URL（`crossref.py:107`），恶意 DOI 可试图改主机/路径 | 高 | 源码实测 | `DOI_RE` 白名单 + `normalize_doi` 前置；BibTeX 用 `quote(safe='')` + `_assert_safe_url` 主机名字面量校验；§5.3 专项测试 |
| R2 | **CrossRef 限流**：vendor 默认 5 次重试 × 0.35s + 指数退避，单查询最坏 ~45s，阻塞 task worker | 高 | `config.py:10-13`、`crossref.py:75-76,227-230` 实测 | 适配层强制 `max_retries=2, timeout=10, delay=0.35`（最坏 ~7s）；单文档同步串行一次查询 |
| R3 | **离线/内网环境**：CrossRef 不可达 | 高 | — | 全链路 try/except → `unverified` 降级；OCR 主流程仍 completed；UI 显示"未校验" |
| R4 | **mailto 缺失**：vendor UA 无 mailto（`config.py:8`），CrossRef 礼貌池降速（不错败） | 中 | grep 证实 | `CROSSREF_MAILTO` 走 ConfigService 注入 UA；留空也可用 |
| R5 | **非 429 HTTPError 直接 raise**（`crossref.py:214-215`），异常穿透 task worker 触发 3 次重试 + 死信（`task_manager.py:109-115`） | 高 | 源码实测 | 调用处与 `verify_doi` 内部双重 try/except；单测覆盖 404/超时不外抛 |
| R6 | **迁移破坏旧库**：用户已有 `library.db` 无新列 | 中 | — | `PRAGMA table_info` 幂等 ALTER；旧库升级单测（§5.2）；WAL 下 ALTER 秒级；sqlite 3.40.1 可 `DROP COLUMN` 回退 |
| R7 | **vendor 漂移**：paper-tools 后续演进导致行为变化 | 中 | — | vendor 只进不出整包替换；适配层只依赖 `CrossRefClient` + 3 个 utils 纯函数（§2.1）；拷贝后 `diff -r` 验收 |
| R8 | **作者名大小写/缩写/罗马化误判**：`authors_match` 宽松策略实测 `Zhang/Chang=True`、`Wang/Wong=True`（`Gonzalez/González=True` 是期望行为） | 中 | §2.3 实测 | **作者不匹配时绝不改写 DOI**（mismatch 交人工）；标题覆盖 ≥0.6 是硬门槛，作者匹配只作加分 |
| R9 | x-mol 兜底依赖第三方非官方 API，随时可变 | 低（已规避） | `xmol.py:6-13` | Phase 1 不使用、不 import |
| R10 | **vendor 标题零相关也返回 DOI**：`_pick_best` 初始分 -1，0 词重叠即入选（`crossref.py:260-287`） | 高 | 源码实测 | 适配层自建 `_title_overlap ≥ 0.6` 硬门槛；专测用例（§5.1） |
| R11 | Basic Insight JSON 无 `doi`/`authors` 键 | 中 | §2.6 源码分析 | 适配层 `.get()` 容错；无作者时 note=no_author_to_verify |
| R12 | `documents.authors` 列从未被写入（grep 证实无赋值点） | 低 | §2.6 | 作者输入只取 Basic Insight JSON，不依赖该列 |
| R13 | 许可证：paper-tools 无显式 license，本项目 GPLv3 | 低 | 总方案 §5 | 均为本人仓库；vendor 前补 license 声明（后续统一处理） |

---

## 7. 验收标准（可勾选）

- [ ] `backend/vendor/pdf_doi_toolkit/` 与源目录 `diff -r` 逐字一致，11 个 .py，无测试/演示文件；`backend/services/doi_service.py` ≤ 200 行，仅 import `CrossRefClient` + utils 纯函数
- [ ] LLM 提取**错** DOI 的 PDF：自动校验后 `documents.doi` = CrossRef 权威值、`doi_source='crossref'`；LLM 提取**对** DOI 的 PDF：`status=verified`，DOI 不变
- [ ] 断网/超时：`status=unverified`、`doi_source='llm'`（或 unverified）、OCR 流水线仍 `completed`、无异常弹窗
- [ ] 作者不匹配时 DOI **不被**改写（status=mismatch）
- [ ] `python_embed/python.exe` 跑 `tests/unit/test_doi_service.py`、`test_database.py`（迁移用例）、`tests/security/test_final_audit.py`（SSRF 用例）、`tests/integration/test_doi_verify_flow.py` 全绿
- [ ] `run_tests.bat` 并行全绿（system 网络用例默认跳过）
- [ ] 非 crossref 域名/IP/`@` 注入 URL 100% 被拒（security 测试证明）
- [ ] `pnpm build` 通过；MetadataPanel 新按钮 Vitest 事件处理器 100% 覆盖
- [ ] 旧版 `library.db`（无三列）打开后自动迁移，既有数据无损；`GET /documents/{id}/bibtex` 命中 DB 缓存时不发第二次网络请求

---

## 8. 回滚策略

| 层 | 回滚动作 | 代价 |
|---|---|---|
| 代码 | 分支未合 main → 删分支；已合 → `git revert` 合并提交 | 零 |
| vendor | `rm -rf backend/vendor/pdf_doi_toolkit/`（只进不出，无其他代码依赖） | 零 |
| DB | sqlite 3.40.1 ≥ 3.35，可 `ALTER TABLE documents DROP COLUMN doi/doi_source/bibtex`；不删亦无副作用（`SELECT *` 多三列 NULL） | 极低 |
| 配置 | `CROSSREF_MAILTO` 留空即回默认 UA 行为 | 零 |
| 前端 | revert `client.ts`/`types/index.ts`/`MetadataPanel.tsx`/`ChatSidebar.tsx` | 低 |
| 触发点 | 删除 `ocr_service.py` 尾部 6 行 try 块即恢复原流水线 | 零 |

**数据面不可逆点**：已被 `corrected` 覆盖的 LLM 原 DOI 不另存备份列（v1 取舍：CrossRef 权威值优先于 LLM 猜测）；如需审计，后续可在 `document_metadata` 追加 `label='DOI Verification'` 记录（本阶段不做）。
---

## 9. 工作量估计（合计约 1.5 人日，与总方案"约 1 天"一致含缓冲）

| 任务 | 工时 |
|---|---|
| vendor 拷贝 + diff 校验 + 导入验证 | 0.5h |
| `doi_service.py`（参数注入、标题门槛、BibTeX） | 3h |
| `database.py` 迁移 + `update_document_doi` + ConfigService 方法 | 1.5h |
| `server.py` 2 端点 + `ocr_service.py` 触发点 | 1h |
| 前端（types/client/MetadataPanel/ChatSidebar + Vitest） | 2.5h |
| 单测/安全/集成测试编写 | 3h |
| 联调 + 真实 PDF 端到端验收 + system 用例 | 1.5h |

---

## 10. 实施顺序
1. **建分支** `feature/doi-verify`（main 禁直推）。
2. **vendor 落地**：拷 11 个 .py 至 `backend/vendor/pdf_doi_toolkit/`，删 `__pycache__`，`diff -r` 校验，`python_embed` 验证 import。
3. **DB 先行**：`database.py` 加 `_migrate_document_doi_columns` + `update_document_doi`；写迁移单测（§5.2）跑绿。
4. **适配层**：新建 `doi_service.py` + `ConfigService.get_crossref_config()`；写 `tests/unit/test_doi_service.py`（§5.1）与 SSRF 用例（§5.3）跑绿。
5. **接线触发点**：`ocr_service.py` Basic Insight 后插 verify 块；写 `tests/integration/test_doi_verify_flow.py`（§5.4）跑绿。
6. **API 端点**：`server.py` 加 `/doi/verify` 与 `/bibtex`；补 API 集成断言跑绿。
7. **前端**：types → client → MetadataPanel 按钮 → ChatSidebar 传 props；补 Vitest；`pnpm build` 通过。
8. **全量回归**：`run_tests.bat` 并行全绿；system 网络用例人工跑一次（`DOI_NETWORK_TESTS=1`）。
9. **验收勾表（§7）→ 合 main**；合入后在 `plans/integrate-paper-tools.md` Phase 1 标注完成。

---

*所有 vendor 行为断言均可按 `路径:行号` 回溯源码复核；§2.1 依赖结论与 §2.3 作者匹配结论为 2026-10-14 在 `python_embed` 3.10.11 实测。*
