# Phase 2 实施方案与风险文档：know 知识层集成

**日期**: 2026-10-14
**分支**: `feature/knowledge-layer`（测试先行，全套绿后才能合 `main`，agents.md §1）
**约束**: 不改 `backend/vendor/know/` 一字；适配层 `knowledge_service.py` ≤200 行；配置走 ConfigService；前端走 `src/api/client.ts`
**上游依据**: `plans/integrate-paper-tools.md` §4 Phase 2；`paper-tools/.plan/knowledge-layer-master-plan.md` §3/§4/§4.5

---

## 1. 目标与范围

**目标**：把 paper-tools `know` 的段落级 claim + 内容哈希锚点知识层接入 academic-clarity，使 Reader/ChatSidebar 能给出**可回原文的引用**（`cite://` 锚点），Dashboard 能跨库做概念检索。

**范围（含）**：
- ingest：OCR 完成且 Basic Insight 就绪的文档 → claims + sha1-8 锚点 → 独立知识库
- search：`GET /knowledge/search`（FTS5 + CJK LIKE 兜底）
- claims API：`GET /knowledge/papers`、按篇 claims 查询
- 前端：Dashboard 知识库搜索入口；ChatSidebar「引用模式」（先检索逐字引文再携引文作答）

**范围（不含）**：wikilinks 维护、社区检测、Obsidian 兼容、concepts/ 懒创建页（master plan §"显式排除"同样排除；`know.concept()` 不移植）、`know flag` CLI 的 note 参数（只做标记语义）。

---

## 2. 组件源码分析（全部对照 `paper-tools/know/` 实证）

### 2.1 config.py — schema 全貌（187 行）

- `SCHEMA_SQL`（config.py:18-54）：`papers(paper_id PK, title, authors, year INTEGER, project, source_rel, ocr_version, doi, identity_status)`；`claims(claim_id PK AUTOINCREMENT, paper_id FK, concept, quote, anchor, heading_path, model, prompt_id, conflicting, rank)`。`_clean_schema()`（config.py:57-63）把占位 `UNIQUE(paper_id, field_placeholder)` 删掉——**claims 无业务唯一键**，幂等靠调用方 dedup。
- 两张 FTS 表：`claims_fts`（`tokenize='unicode61'`，英文分词）+ `claims_fts_cjk`（`tokenize='trigram'`，CJK 子串，仅 ≥3 字符有效），均 `content_rowid='rowid'`。
- `init_db(db_path)`（config.py:66-71）：裸 `sqlite3.connect`，**无 WAL、无 busy_timeout**（适配层需补 `PRAGMA busy_timeout`，见 §3.2）。
- `insert_claim`（config.py:98-115）：插 claims 后同步插两张 FTS 表（显式传 rowid）。
- `search_claims`（config.py:118-180）：先 FTS 双表 MATCH（`ORDER BY rank`），`sqlite3.OperationalError` 裸吞（config.py:146,161——FTS 语法错误的查询自动落 LIKE）；最后 **LIKE 兜底** `concept LIKE ? OR quote LIKE ?`（config.py:164-171），参数化拼接 `%term%`；按 claim_id 合并去重，`[:limit]` 截断。**注意：LIKE 路径不过滤 `%`/`_` 通配符，查询串含 `%` 会放大匹配（功能问题非注入）**。
- **依赖实证：know 五个模块零第三方依赖**（仅 stdlib：os/sys/json/re/sqlite3/hashlib/unicodedata/difflib/datetime）。集成方案 §5 风险表"know 需 pyyaml"的说法不成立——`pyproject.toml` 声明了 pyyaml 但源码无 import。python_embed 可直接运行。

### 2.2 anchors.py — 分段与 sha1-8 锚点（136 行）

- `paragraphize`（anchors.py:48-62）：按 `\n` 切行，跳空行与 `^#{1,6}\s` 标题行，每行 `_normalize`（NFKC + 空白折叠，anchors.py:22-24）。**一行=一段落**，不做跨行合并。
- `anchor_id`（anchors.py:65-73）：`'p' + sha1(NFKC归一化文本)[:8]`，共 9 字符；空白差异不改变 id（test_anchors.py:90-100 钉死）。
- `rematch`（anchors.py:92-115）：归一化后精确子串 → MATCHED(1.0)；否则滑窗 `_window_best`（anchors.py:76-89，步长 `nq//4`）difflib ratio：**≥0.85 MATCHED，0.60–0.85 BROKEN，<0.60 UNMATCHED**。阈值被 TestRematchThresholds（test_anchors.py:128-175）与 mutation_test.py:31-33 钉死。
- `classify_fragmented`（anchors.py:118-136）：按 `...` 切片，逐片 rematch，取最差片作为绑定结果（list 型字段经 `coerce_quote` 以 ` ... ` 连接，anchors.py:27-45）。
- **Phase 0 实测锚点稳定性**（master plan §3，line 84）：同 PDF 两次 DeepSeek-OCR，全行 sha1-8 集合重合 94.3%，真实内容漂移 <5% 且全部 ratio ≥0.95；章节结构 14/14 一致。→ 主锚点内容哈希、回退模糊重匹配、`heading_path` 作辅助轴。

### 2.3 derive.py — 输入假设与 existence gate（190 行）

- 输入形状（derive.py:114-123）：`{prompt_group: {claim_group: {..., evidence_quotes: {field: quote|null}}}}`，**三级嵌套**，引文只在 `evidence_quotes` 叶子里。
- **existence gate**（derive.py:130-133）：`status != MATCHED` 的 claim 直接 `continue` 丢弃——不编造、不降级。null quote 视为"无论文"跳过（derive.py:126-129，Phase 1.0 finding 3）。
- `_resolve_anchor`（derive.py:151-167）：先精确子串找段，否则取全段落最佳滑窗 ratio 的段，返回其 anchor；全不命中返回哨兵 `p00000000`。
- `_resolve_heading_path`（derive.py:170-190）：与锚定同款的片段匹配逻辑，返回 `"## III. METHOD > ### A. Concept"` 形章节链；找不到返回 `""`。
- **关键输入假设**：文件命名 `{paper_id}_v2_{model}.json`，OCR md 在 `{ocr_dir}/{paper_id}/{paper_id}.md` 或平铺（derive.py:69-86, know.py:215-220）。这是 paper-tools 的目录约定，**本项目没有也不打算造这个目录**——这是 §3.2 新写 ingester 的根本原因。
- master plan §4.5（line 119,135）：v2 prompt 改造后真实命中率 90.5%（语料 A）/96.1%（语料 B）；**未改造 prompt 的字段 95.6% 无逐字引文**（§4，line 106）。

### 2.4 identity.py — 三层身份映射（162 行）

- `resolve_doi(doi_map_entry, metadata_doi)`（identity.py:105-131）→ `(doi, status)`：`clean`（doi_map 命中且非 `.fmatter`）/ `fmatter_trap`（DOI 以 `.fmatter` 结尾 → 压制为 `""`）/ `unresolved`（两侧都无真 DOI）/ `unresolved_meta`（doi_map 无但 metadata 带真 DOI——**记录但不晋升为权威**）。
- `_is_real_doi`（identity.py:96-102）：必须匹配 `^10\.\d{4,9}/`。
- `build_identity`（identity.py:134-162）：读 `doi_map.json` + `{paper_id}_metadata_{alias}.json` 目录。**本项目无 doi_map 文件**；Phase 2 直接以 `resolve_doi({}, basic_insight.doi)` 调用：LLM 抽的 DOI 一律落 `unresolved_meta`（记录+标注），等 Phase 1 CrossRef 校验落地后再提供 clean 层。这正是三层信任顺序在本项目的形态。
- 测试覆盖 test_identity.py:61-105：四家族状态、`.fmatter` 绝不外泄、"not reported" 清洗为 `""`。

### 2.5 know.py — CLI 结构（500 行）

- `ingest(ocr_dir, derived_dir, db_path, kb_dir, doi_map_path, metadata_dir, ...)`（know.py:169-267）：扫 `*_v2_*.json` → 逐篇 `derive.derive()` → `config.insert_paper`（UPSERT，config.py:74-95）→ 按 `(concept_key, quote)` dedup 后 `config.insert_claim` → 写 markdown 页 + `log.md` + `catalog.md`。`paper_count` 返回。
- `_write_paper_page`（know.py:57-95）：`knowledge-base/papers/{paper_id}.md`，frontmatter 带 doi/title/authors/year/project/source_rel/ocr_version/identity_status；claim 行内嵌 `cite://{paper_id}/{anchor}`。
- `search(db_path, concept, limit=10)`（know.py:299-305）= `config.search_claims` 薄包装；`validate`（know.py:274-296）查孤儿 claim + catalog/papers 目录存在性；`flag`（know.py:308-318）只把 `conflicting` 置 `'flagged'`，**绝不删行**（信任链）。
- `_main`（know.py:400-493）：ingest/validate/search/flag/concept 五命令；`concept` 要求跨 ≥2 篇才建页（know.py:345-349），本方案不移植。
- **幂等语义**：`_existing_claim_keys`（know.py:158-164）按 `(concept, quote)` 去重 → 重 ingest 不复制。**但它不重绑锚点**：re-OCR 后同 quote 命中新段落时，旧 anchor 行不会更新——这正是风险 R1 要在适配层解决的缺口（know.ingest 本身不调用）。

### 2.6 CJK LIKE 兜底（Gap 5 修复）与 84 测试覆盖地图

- 兜底在 config.py:164-171（参数化 LIKE，拼接 `%term%`）。master plan §2 F2（line 53）实测：trigram 与 unicode61 两表对 `MATCH '交易'` 均返 0。
- 测试清点（grep 实证）：`def test_` 共 85 处，其中 test_know_cli.py:453 `test_identity_upgrade_on_reingest` 是**模块级函数、引用 `self.tmp`，unittest discover 永不收集**（死代码，移植时丢弃或包进 TestCase）。实际收集 = 84，与 master plan §4.5 line 147 的"84 测试"吻合：
  - test_anchors.py 27（coerce/paragraphize/anchor_id/rematch 阈值钉死/fragmented）
  - test_derive.py 10（claim 形状、null 跳过、existence gate 空 OCR 全丢、坏 quote 不 matched）
  - test_identity.py 13（paper_id/status 四家族/resolve_doi/not-reported 清洗/build_identity）
  - test_know_cli.py 23（ingest 落库/页/log、identity 流 DOI、fmatter 压制、幂等、search、flag、backfill、corpus B 四家族+project+合并 catalog、validate）
  - test_schema.py 11（四表存在、heading_path 列、**2 字符 CJK 返行（test_schema.py:83-86）**、3 字符/英文仍通、无匹配返 0）
  - mutation_test.py：5 个变异体 4 kill + 1 equivalent（sha1→md5 只验确定性不验算法，等价变异杀不掉——诚实缺口）。

---

## 3. 项目侧改动清单（逐文件）

### 3.1 `backend/vendor/know/` — 拷贝范围决策

**拷贝 5 个 `.py`**：`know.py / anchors.py / derive.py / identity.py / config.py`（逐字，禁改；删 `__pycache__`）。
**不拷贝**：`pyproject.toml`、`uv.lock`、`.venv/`、`tests/`、`mutation_test.py`。理由：tests/fixtures 属于测试资产，按 agents.md §6 归 `tests/` 且需改造路径发现；mutation_test.py 会**原地改写被变异文件**（mutation_test.py:72-79），对着 vendor 跑等于破坏 vendor。
**fixtures 另拷**：`know/tests/fixtures/`（10 个文件：5 md + 5 json，含 `corpus_b/` 8 个）→ `tests/unit/fixtures/know/`。fixtures 只读共享，天然并行安全。

### 3.2 `backend/services/knowledge_service.py`（新建，≤200 行）

函数签名与骨架：

```python
# import: anchors, config, derive, identity（均 from vendor.know 或 vendor 路径）
KNOW_DB_NAME = "index.sqlite"          # {workspace}/knowledge/index.sqlite
PROMPT_ID_PARA = "basic-insight-v1"    # 段落级锚定
PROMPT_ID_SECT = "basic-insight-v1~section"  # 章节级锚定（无逐字引文的等价降级）

def init_store(workspace_path: str) -> None:
    """lifespan/workspace 切换时调用：建 {workspace}/knowledge/ + init_db + busy_timeout。"""

def ingest_document(doc_id: int, db) -> dict:
    """返回 {paper_id, claims, rebound, section_level, skipped_reason?}。"""

def search(query: str, limit: int = 10) -> list[dict]:
    """config.search_claims + JOIN papers 带出 title/doi；paper_id='doc:{id}' 回填 doc_id。"""

def get_paper_claims(paper_id: str) -> list[dict]:
    """单篇 claims（按 claim_id）。"""
```

核心流程 `ingest_document`：
1. 取文档：`db.get_document(doc_id)` → `ocr_markdown`；Basic Insight 取 `db.get_document_metadata(doc_id)` 中**最新一条 `label=='Basic Insight'`**（`MetadataConfig.DEFAULT_LABEL`，constants.py:39）解析 `content_json`。**注意：`documents.metadata_json` 列是死列**——ocr_service.py:190 写的是 `document_metadata` 表，不要读错源。
2. 分段：`paras = anchors.paragraphize(ocr_md)`；`paras_with_path = derive._paragraphs_with_path(ocr_md)`（**vendor 私有函数，由移植测试钉死签名**；不重写以免双份逻辑漂移）。
3. 逐字段产 claim（Basic Insight → claims 映射）：

| Basic Insight 字段（ocr_service.py:163-182 的 prompt 产物） | claims.concept | claims.quote | model / prompt_id |
|---|---|---|---|
| title | `basic_insight.title` | 标题串 | `academic-clarity` / 按锚定级别 |
| authors | `basic_insight.authors` | 逗号串 | 同上 |
| journal_or_conference | `basic_insight.venue` | 场馆串 | 同上 |
| date | `basic_insight.date` | 年份串 | 同上 |
| abstract | `basic_insight.abstract` | 摘要串 | 同上 |
| keywords（list） | `basic_insight.keywords` | `", ".join` | 同上 |
| summary | `basic_insight.summary` | 字符串或 list→`" ... "` 连接（借 anchors.coerce_quote 语义） | 同上 |

4. **两级锚定策略（quote 缺失的等价处理，替代 existence gate 的硬丢弃）**：
   - **T1 段落级**：`status, ratio = anchors.classify_fragmented(quote, paras)`，`MATCHED` → `anchor = derive._resolve_anchor(...)`、`heading_path = derive._resolve_heading_path(...)`，`prompt_id=PROMPT_ID_PARA`。
   - **T2 章节级（本项目主力路径）**：Basic Insight 是 LLM 转述，Phase 0.5 已证 95.6% 字段逐字锚不中。对 `status != MATCHED` 的字段，**不丢弃**（丢弃=知识层只剩个位数 claim），而是降级：在 `paras_with_path` 里找 `heading_path` 含 `abstract`/`摘要`（大小写不敏感）的首段作锚；找不到则取文档首段。`prompt_id=PROMPT_ID_SECT`，UI 层对该级 claim 标注"章节级转述"。**锚永远指向真实存在的段落（可解析、非编造）；被标注的是文本粒度，不是锚真实性。**
   - OCR 完全无正文段（`paras == []`）：整篇 skip，记 `skipped_reason='no_paragraphs'`。
5. 身份：`doi, st = identity.resolve_doi({}, insight.get("doi") or "")`；`paper_id = f"doc:{doc_id}"`（**固定 schema，不用 DOI 作主键**——DOI 未经验证会变，主键必须对 re-ingest 稳定；DOI 只进 `papers.doi`）。`papers` 行：title 取 `documents.title` 或 insight.title 或 filename；year 从 date 抽 4 位数字（无则 NULL）；authors JSON 序列化；`ocr_version` 填 `"deepseek-ocr-v1"`；`identity_status=st`。
6. **幂等 + 重绑（补 know.ingest 的缺口，风险 R1 的对策）**：对每个计算出的 claim，查 `(paper_id, concept, quote)` 是否已存在：
   - 不存在 → `config.insert_claim`；
   - 存在且 anchor 不同 → `UPDATE claims SET anchor=?, heading_path=? WHERE ...`（**重绑**，`rebound += 1`，写 log.md）；
   - 存在且 anchor 相同 → 跳过。
   - T2 兜底保证任何 quote 都有可解析锚 → **结构上不产生死 claim**；T1 退化为 T2 时 quote 文本不变、锚迁移，log.md 留痕。
7. 归档：`{kb}/papers/{paper_id}.md`（frontmatter + claims + `cite://doc:{id}/{anchor}` 锚表，复刻 know.py:32-54 模板）+ `{kb}/log.md` 追加（ingest/rebind 条目）。
8. 连接卫生：`init_store` 后执行 `PRAGMA busy_timeout=30000`（vendor `init_db` 没设，FastAPI 线程池并发 ingest 会 `database is locked`）；写路径用项目级 `threading.Lock` 单线程化（knowledge DB 单写者）。

### 3.3 `backend/server.py`（改）

- **存储初始化时机**：`AppState.initialize`（server.py:49-73）末尾加 `knowledge_service.init_store(path)`。**实证覆盖两种入口**：冷启动走 `lifespan`（server.py:77-79，`sys.argv[2]` 为 workspace）；切换工作区时 electron/main.ts:122-135 先 `killPythonBackend()` 再以新 workspace 重启进程 → 同样落到 `state.initialize`。**不需要额外的 workspace 切换钩子**。
- 新端点（`state.db`/`state.workspace_path` 模式照抄现有处理器）：
  - `POST /knowledge/ingest/{doc_id}`：文档存在且 `ocr_markdown` 非空才 ingest；`await asyncio.to_thread(knowledge_service.ingest_document, doc_id, state.db)`（**同步 CPU 活必须进线程池**，照 workspace_service.py:37-44 先例）；400/404/500 语义照抄 server.py:371-388。
  - `GET /knowledge/search?q=&limit=`：`q` 必填非空；`asyncio.to_thread` 包 `search()`；返回行带 `doc_id`（从 `paper_id` 拆）。
  - `GET /knowledge/papers`：papers + claim 计数，Dashboard/搜索来源。
- `/chat` 引用模式：`ChatRequest`（server.py:166-168）加可选 `quotes: list[str] | None`。`chat_with_doc`（server.py:415-428）分支：有 quotes → context = 逐条 `"[cite://{n}] {quote}"` 拼接（**只喂逐字引文，LLM 不许外溢**）；无 → 现有全量 `ocr_markdown`。system prompt 复用 ai_service.py:166 的"Answer based ONLY on the provided context"。
- 可选增强（recommended，非阻塞）：`ocr_service.py:163-182` 的 `default_prompt` 增补 `evidence_quotes` 逐字字段约定（know Phase 1.0 的同款修复，master plan §4 line 112）。**新增/重提取文档从此走 T1 段落级**；适配层对无该字段的旧数据自动走 T2，向前向后兼容。改 prompt 需回归 `tests/unit/test_ocr_service.py` 与 `test_auto_pipeline.py`。

### 3.4 前端（改）

- `src/types/index.ts`：加 `KnowledgeClaim { claim_id, paper_id, doc_id, concept, quote, anchor, heading_path, conflicting?, title, doi? }`、`KnowledgePaper { paper_id, doc_id, title, doi?, claim_count, identity_status }`。
- `src/api/client.ts`：加 `searchKnowledge(q, limit)`、`ingestKnowledge(docId)`、`getKnowledgePapers()`；`chat` 增第三参 `quotes?: string[]`（agents.md §5：禁裸 fetch）。
- `src/components/Dashboard.tsx`：筛选栏（Dashboard.tsx:169-221）加检索范围切换（文献 / 知识 Claims）；Claims 模式调 `api.searchKnowledge`，结果卡展示 quote 截断 + `heading_path` + 论文标题，点击 → `onSelectDoc` 进 Reader。**所有新控件必须有 Vitest 用例**（agents.md §6，照 Dashboard.test.tsx 模式）。
- `src/components/reader/ChatSidebar.tsx` + `src/components/Reader.tsx`：ChatSidebar 加「引用模式」开关（新 prop `citeMode`/`setCiteMode`，头部按钮）；Reader.tsx:85-100 的 `handleSend` 分支：citeMode 开 → 先 `api.searchKnowledge(query)`（可按当前 doc 过滤）取 top-k claims → `api.chat(doc.id, query, quotes)`，AI 消息尾部附 `cite://` 列表。无命中时提示"未找到可引用段落"而非裸答。ChatSidebar.test.tsx 补开关与发送链路用例。

### 3.5 不改动项（明确）

- `library.db` **零 schema 变更**（无 ALTER TABLE）；knowledge 库存 `{workspace}/knowledge/index.sqlite` + markdown 归档，物理隔离。
- `backend/database.py`、`ocr_service.py`（除可选 prompt 增强）、`task_manager.py`、`workspace_service.py` 不动。
- 不自动 ingest（不做任务链尾挂载）——Phase 2 只做显式 `POST /knowledge/ingest/{doc_id}`（Dashboard 卡片按钮触发），避免 OCR 高峰并发写知识库；自动化留待 Phase 2.5 评估。

---

## 4. 数据流与状态机

```
[上传 PDF] → OCR(DeepSeek) → documents.ocr_markdown
                              → Basic Insight → document_metadata(label='Basic Insight')
                                                  │
        POST /knowledge/ingest/{doc_id} ◄──────────┘（显式触发，OCR 完成后任意时刻可重跑）
              │
              ├─ anchors.paragraphize(ocr_md) ─────────► paras / paras_with_path
              ├─ Basic Insight 字段 × 7 ──► T1 classify_fragmented=MATCHED ? 段落级 : T2 章节级
              ├─ identity.resolve_doi({}, llm_doi) ────► papers.doi + identity_status(unresolved_meta)
              └─ insert/rebind ─► {workspace}/knowledge/index.sqlite + papers/{paper_id}.md + log.md

查询：GET /knowledge/search?q=交易
      → config.search_claims：FTS5(unicode61+trigram) → OperationalError/%/% 吞掉 → LIKE 兜底 → 合并去重
      → KnowledgeClaim[]（含 cite://doc:{id}/p{sha1_8} + heading_path）
引用模式：query → search top-k → quotes[] → POST /chat{quotes} → LLM 仅基于逐字引文作答 + 引用列表
回原文：cite:// 锚 → anchors.anchor_id 同款归一化在 paras 中重定位段落（UI 高亮/跳转）
```

re-ingest 状态机（幂等）：`新建 insert → 锚漂移 rebind(UPDATE) → 同锚 skip → 无正文 skip(留 log)`。无"删除 claim"状态（flag 才标 conflicting）。

---

## 5. 测试计划

### 5.1 移植 know 84 测试 → `tests/unit/test_know_*.py`

| 源文件 | 目标 | 用例数 | 改造点 |
|---|---|---|---|
| test_anchors.py | `tests/unit/test_know_anchors.py` | 27 | ①路径发现改为 tests/unit/test_workspace.py:9-17 同款动态找 `backend/`，再 `sys.path.insert(0, backend/vendor/know)`；②fixtures 指向 `tests/unit/fixtures/know/`；无其他改动（纯函数、零 IO） |
| test_derive.py | `tests/unit/test_know_derive.py` | 10 | ①②；③**TestExistenceGate/TestWarningsManifest 把 `empty.md`/`bad.json` 写到 UUID 临时目录**（原版写测试同目录，破坏并行隔离，agents.md §3） |
| test_identity.py | `tests/unit/test_know_identity.py` | 13 | ①②；`tempfile.TemporaryDirectory` 已隔离，保留 |
| test_know_cli.py | `tests/unit/test_know_cli.py` | 23 | ①②；③丢弃模块级死函数 `test_identity_upgrade_on_reingest`（或包进 TestCase 并补 `self.tmp`）；④CLI 子进程用例（backfill/concept flag）用 `sys.executable` + `backend/vendor/know/know.py` 绝对路径 + `env KNOW_DB/KOW_KB`（原版靠 cwd，本项目 `python_embed` 直接跑文件路径，脚本目录自动入 sys.path，`import anchors` 可解析——**未验证：python_embed 下 subprocess 的 sys.executable 指向**，实现时以 `sys.executable` 为准并加 skipUnless） |
| test_schema.py | `tests/unit/test_know_schema.py` | 11 | ①②；CJK 两条即验收门槛（见 5.3） |
| mutation_test.py | **不移植** | — | 会原地改写 vendor 文件；其 5 个变异体由锚定测试阈值 + 新增 vendor 完整性测试替代 |

新增 `tests/unit/test_vendor_know_integrity.py`：对 `backend/vendor/know/*.py` 算 sha256 钉基线（防误改 vendor；变更=整包替换+重新记基线）。

### 5.2 新增适配层测试 `tests/unit/test_knowledge_service.py`

1. **ingest 全链路**：UUID workspace + 内存 `Database`，造 1 篇文档（ocr_markdown 含 `## Abstract`、`## III. METHOD` 两节共 6 段；Basic Insight 含 title/abstract/keywords）→ ingest → 断言：papers 1 行（`paper_id='doc:{id}'`、`identity_status='unresolved_meta'` 当 insight.doi 为真 DOI）；claims ≥7 行；每条 anchor 都能在 `anchors.paragraphize(ocr_md)` 的 anchor 集合中解析到（**锚可解析性不变量**）；markdown 页含 `cite://doc:`。
2. **T1 段落级**：insight 某字段值=OCR 原文逐字子串 → 该 claim `prompt_id=PROMPT_ID_PARA`、anchor=该段 sha1-8。
3. **T2 章节级**：abstract=LLM 转述 → claim `prompt_id=PROMPT_ID_SECT`、anchor=Abstract 节首段；无 abstract 标题时退文档首段。
4. **幂等**：连续 ingest 两次 → claims 行数不变。
5. **重绑（漂移）**：改 `ocr_markdown` 一段落约 5% 词（模拟 re-OCR 漂移，同 know Phase 0 量级）→ 再 ingest → claims 不增（同 concept+quote dedup），受影响 claim 的 anchor 变为新段 sha1-8（rebound≥1），log.md 含 rebind 条目。
6. **空 OCR**：ocr_markdown 仅标题 → skip + `skipped_reason='no_paragraphs'`，claims 0 行。
7. **search 回填**：search 结果含 `doc_id`（int）与 papers.title。
8. **并发写**：4 线程同时 ingest 不同 doc → 无 `database is locked`（busy_timeout + 单写锁生效）。

### 5.3 验收门槛用例（移植 + 新增，CJK 2 字符）

- 移植 test_schema.py:83-86 `test_two_char_cjk_returns_rows`（`search_claims(conn, "交易")` > 0）。
- **项目场景验收**：`tests/integration/test_knowledge_api.py` 中，造中文文档（ocr_markdown 含"P2P 交易瓶颈在于各 agent 需顺序更新"段 + 对应 Basic Insight），ingest 后 `GET /knowledge/search?q=交易` **必须返回 ≥1 条带 anchor 的 claim**（master plan §"Phase 1 验收测试"：用户的旗舰查询不得查空）。同文件再测 3 字符（交易瓶颈）、英文（attack）、无匹配（不存在的词xyz）返 0 不崩。
- **API 集成测试**（照 tests/integration/test_api_upload_flow.py:10-31 的 argv 注入 + `state.initialize(test_ws)` + TestClient lifespan 模式）：
  1. `POST /knowledge/ingest/{doc_id}` → 200 + claims>0；无 ocr_markdown → 400；不存在 doc → 404。
  2. `GET /knowledge/search?q=交易` → 200，行含 claim_id/anchor/heading_path/doc_id。
  3. `GET /knowledge/papers` → 含该 paper + claim_count。
  4. `/chat` quotes 模式：带 quotes → 200 且 mock LLM 收到的 context 只含引文（patch `server.call_chat_api` 断言入参）。
  5. **重复 ingest 幂等**：两次 POST → claims 计数不变。
- **安全用例**（`tests/security/test_final_audit.py` 追加或独立 `test_knowledge_search_security.py`）：
  - `q="' OR 1=1 --"`、`q='"; DROP TABLE claims; --'`、`q="交易' UNION SELECT 1"` → 200/400，**claims 表行数不变**（参数化 + FTS 语法错误落 LIKE，实证 config.py:146/161）。
  - FTS 畸形语法：`q='"未闭合短语'`、`q='NEAR('`、`q='AND OR'` → 不 500（OperationalError 被吞）。
  - LIKE 通配：`q='%'`、`q='_'` → 不崩、不返回全表当异常（文档化为已知行为：可能放大匹配）。
  - 超长 q（10 万字符）→ 400 或截断，不 OOM。
- **前端**：Dashboard.test.tsx 加 Claims 模式渲染+点击跳转用例；ChatSidebar.test.tsx 加引用模式开关+带 quotes 发送用例（agents.md §6：100% 事件处理器覆盖）。

### 5.4 运行方式

`.\python_embed\python.exe tests/unit/test_know_anchors.py` 单跑；`run_tests.bat` 全量（并行安全：所有测试用 UUID 临时 DB/workspace，fixtures 只读）。

---

## 6. 风险登记表

| # | 风险 | 概率/影响 | 事实依据 | 对策 |
|---|---|---|---|---|
| R1 | **re-OCR 锚点失效** | 高 / 中 | Phase 0 实测漂移 <5%（master plan §3 line 84）：每次重 OCR 约 ≤5% 段落换哈希；know.ingest 无重绑机制（§2.5） | 适配层 rebind UPDATE + log 留痕（§3.2-6）；T2 兜底保证锚永可解析；验收：漂移 5% 重 ingest 后死 claim=0、rebound 与漂移段数一致；`ocr_version` 字段记录 OCR 代次 |
| R2 | **FTS5 CJK 2 字符返空** | 已实测 / 高 | master plan F2：trigram 与 unicode61 对 `交易` 均返 0；config.py LIKE 兜底是唯一修复 | 兜底已随 vendor 带入；作为**合并门槛**（§5.3）；FTS 畸形串吞 OperationalError 已有测试 |
| R3 | **规模性能（10000 篇/年）** | 中 / 中 | master plan §1（line 21）：~10,000 篇/年、单项目上千篇；当前层内 84 篇 172 claims（line 146）。外推 10k 篇 × ~7 claim ≈ 70k claims | FTS5 70k 行 ms 级；**LIKE 兜底是全表扫描**（无索引可走 `%x%`），2 字符 CJK 查询 ~70k 行扫描约几十 ms，可接受；markdown 归档 10k×~5KB≈50MB。**未验证：>5k 篇实测延迟**，移交前用 2000 篇合成数据压测 search p99 |
| R4 | **双库一致性**（library.db vs knowledge/index.sqlite） | 中 / 中 | 知识库是派生投影，无外键/事务跨库 | 知识库**永远可从 library.db 全量重建**（删 `knowledge/` 再逐篇 ingest）；文档删除时同步删知识行（§3.3 列出删除端点或文档内联处理——**实现决策：`DELETE /documents/{id}` 时调 `knowledge_service.forget_paper(doc_id)`**）；启动时可选跑 `know.validate` 等价检查 |
| R5 | **vendor 漂移/腐化** | 低 / 高 | vendor 逐字拷贝；上游 know 仍在演进 | vendor 只进不出；升级=整目录替换 + 重跑 §5.1 全套 + 重记 sha256 基线（test_vendor_know_integrity）；适配层只 import 公共 API + 3 个私有函数（`derive._paragraphs_with_path`、`derive._resolve_anchor`、`derive._resolve_heading_path`），私有依赖由移植测试钉死 |
| R6 | **引用幻觉**（无逐字引文不得编造） | 高 / 高 | Phase 0.5：95.6% 字段无逐字引文；Basic Insight 是 LLM 转述 | T1/T2 分级 + `prompt_id` 后缀标记；UI 明示"章节级转述"；`/chat` quotes 模式只喂逐字引文；existence gate 永不制造 MATCHED；`identity_status=unresolved_meta` 明示 DOI 未核验 |
| R7 | **LLM DOI 幻觉进知识库** | 高 / 低 | LLM 提取 DOI 不可信（总方案 §1） | DOI 一律走 `resolve_doi({}, ...)` → `unresolved_meta`，等 Phase 1 CrossRef 校验提供 clean 层；`.fmatter` 陷阱逻辑随 vendor 免费获得 |
| R8 | **python_embed 运行时** | 低 / 高 | 无 pip；know 五模块零三方依赖（§2.1 实证） | 无需安装任何东西；子进程 CLI 用例的 `sys.executable` 行为**未验证**，以 skipUnless 保护 |

---

## 7. 验收标准（可勾选）

- [ ] `backend/vendor/know/` 5 文件在位，sha256 基线测试通过，无 `__pycache__`
- [ ] §5.1 移植的 84 个 know 测试在 `python_embed` 下全绿
- [ ] `knowledge_service.py` ≤200 行；三个公共函数签名如 §3.2
- [ ] 单篇文档 ingest 后：claims 全部 anchor 可解析；markdown 页 + log.md 生成
- [ ] **`GET /knowledge/search?q=交易` 在含中文语料上返回 ≥1 条 claim**（CJK 2 字符门槛）
- [ ] 重复 ingest 幂等；5% 漂移重 ingest 后死 claim=0 且发生 rebind
- [ ] 注入/畸形 FTS/超长查询安全用例全过，claims 表无损
- [ ] Dashboard Claims 检索可点击进 Reader；ChatSidebar 引用模式可发送且引用列表可见；对应 Vitest 绿
- [ ] `library.db` 无 schema 变更；知识库删除后可从 library.db 完整重建
- [ ] `run_tests.bat` 全量绿 + `pnpm build` 过，才合 `main`

---

## 8. 回滚策略

1. **代码回滚**：本阶段零 DB 迁移、零 vendor 外部副作用 → `git revert` 该 feature 分支合并 commit 即完成（删除 `backend/vendor/know/`、`knowledge_service.py`、server/client/前端 diff、tests）。源语料（library.db、workspace PDF）从未被写。
2. **数据回滚**：知识库是纯派生数据 → 删 `{workspace}/knowledge/` 目录即完全回滚且无损（OCR/元数据不受影响）；重建=重新 ingest。
3. **分批提交**：vendor 拷贝 → 测试移植 → 适配层 → API → 前端，每步独立 commit，任一步失败 revert 到上一步，不影响已合内容。
4. 不回滚项：用户若已用引用模式产生过聊天记录，回滚后历史消息中的 `cite://` 文本失去解析后端——可接受（只读文本残留）。

---

## 9. 工作量估计

总方案估 1.5–2 天；按 master plan peer review Gap 1 的"时间估计 2x 上修"教训重估为 **3–4 人日**：

| 步骤 | 估计 |
|---|---|
| vendor 拷贝 + fixtures + 完整性基线测试 | 0.25d |
| 84 测试移植 + 路径/隔离改造 | 0.5–0.75d |
| `knowledge_service.py`（两级锚定 + rebind） | 0.75–1d |
| 3 端点 + /chat quotes + init_store | 0.5d |
| 前端（Dashboard 检索 + ChatSidebar 引用模式 + client/types + Vitest） | 0.75–1d |
| 新增单测/集成/安全/CJK 验收 + 全量跑绿 | 0.5–0.75d |

---

## 10. 实施顺序

0. `git checkout -b feature/knowledge-layer`（main 禁直提）
1. vendor 拷贝 + sha256 基线测试（红→绿）
2. 移植 84 测试（先红后绿，验证 vendor 在 python_embed 可用）
3. `knowledge_service.py` + `tests/unit/test_knowledge_service.py`（T1/T2/幂等/重绑/并发）
4. server.py 端点 + `/chat` quotes + `init_store` + `tests/integration/test_knowledge_api.py`
5. 前端三件套 + Vitest（`types` → `client` → Dashboard → ChatSidebar/Reader）
6. 安全用例 + CJK 2 字符验收 + （可选）Basic Insight prompt 增补 evidence_quotes 并回归 OCR 管线测试
7. `run_tests.bat` + `pnpm build` 全绿 → 合 main → 删分支

**关键路径**：步骤 3 的两级锚定设计是全部引用真实性的地基，先于任何前端工作完成并通过 §5.2 不变量测试。
