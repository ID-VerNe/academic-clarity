# Phase 3 实施方案：借鉴 litrev-extract 框架模式增强元数据提取能力

> 分支 `feature/extraction-framework`｜本文档只读代码后撰写，不修改任何项目源码
> 约束（agents.md）：测试先行、全套绿后合 main；新服务文件 ≤200 行单一职责；配置走 ConfigService；前端走 `src/api/client.ts`；LLM JSON 渲染深度 ≤5；新测试入 `tests/{unit,integration,security,system}/`，UUID 隔离、动态路径发现

---

## 1. 目标与范围

把 litrev-extract（`paper-tools/litrev-extract`）的三个机制搬进 academic-clarity **现有代码**，不 vendor：

1. **提示词模板化**：提取维度（label + prompt）从"一次性请求参数"升级为 DB 可管理实体，SettingsModal 可增删改。
2. **批量提取**：对库内多文档跑同一维度，任务入现有任务队列（并发 + 重试 + 死信全部复用）。
3. **报告导出**：跨文档汇总导出 CSV / Markdown（litrev postproc 的最小有用子集）。

**明确不做**：不 vendor litrev-extract（与现有"自定义维度提取"重叠，且引入第二套 LLM 编排违反 DRY）；不引入 `litrev.yaml` / YAML 配置体系（项目用 DB 配置 + ConfigService）；不引入 litrev CLI；不实现 postproc 插件注册系统（`postproc/registry.py:46` 的 `@register_post_processor` + `discover_processors`）；不引入 pandas / openai / tqdm 依赖（python_embed 无 pip，导出一律用 stdlib `csv`）；不做 multimodal 逐图提取。

---

## 2. litrev 源码分析（均已对照源码验证）

### 2.1 `config.py` — 声明式配置 + 宽松校验
`ConfigLoader.from_file`（`config.py:219`）解析 `litrev.yaml` 为 `ReviewConfig`；`_validate_config`（`config.py:117`）收集式校验（project/models/prompts/input 必填）；`_resolve_env_var`（`config.py:92`）支持 `$VAR`。**借鉴**：维度定义结构化 + 保存前集中校验。**不搬**：YAML 文件发现机制（`search_paths`，`config.py:216`）——项目配置已在 DB。

### 2.2 `pipeline.py` — 并发、重试、不可重试错误
- `initialize_queue`（`pipeline.py:197`）：文档 × prompt 笛卡尔积建任务；`state_manager.is_completed` 命中即跳过（`pipeline.py:246`）——**断点续跑的核心**。
- `run`（`pipeline.py:294`）：`ThreadPoolExecutor(max_workers=min(max_workers, len(queue)))`，`wait(FIRST_COMPLETED)` 饱和提交。
- `_safe_process`（`pipeline.py:375`）返回 terminal 布尔；`NonRetriableError`（`pipeline.py:46`，auth/400/缺文件）不浪费重试。
- `_handle_failure`（`pipeline.py:542`）：线性退避 `min(retry_count * retry_delay_base, 60)`，超 `max_retries`（默认 10）判死；失败任务 rotate 回队列前部附近优先重试。
**项目已有更好等价物**：任务队列（10 worker、`MAX_RETRIES=3`、`RETRY_BACKOFF=[1,5,30]`、死信队列），见 §3。

### 2.3 `state.py` — 断点续跑状态机
`StateManager`（`state.py:24`）：JSON 文件、`(model_alias, task_id)` 二级键、`task_id = f"{relative_path}|{prompt_def.id}|{model_alias}"`（`models.py:204`）；`mark_success/mark_failed/is_completed/get_failed_ids/reset_failed`（`state.py:126-260`）；tmp+rename 原子写、`flush_interval=50` 批量落盘；损坏state备份后重跑（`state.py:94`）。
**项目等价物更强**：结果即状态——`document_metadata` 行存在 ≡ litrev state success。无需第二份状态文件。

### 2.4 `templates.py` — `{content}` 占位符渲染
`render`（`templates.py:137`）：先截断（`content_truncation`）再 `template.replace("{content}", text)`，未知占位符原样保留。
**有意分歧**：项目的 `call_json_extraction_api` 是 `f"{prompt_instructions}\n\nCONTENT:\n{md_content}"`（`ai_service.py:222`），prompt 里写 `{content}` 会原样泄露——维度 prompt 必须按项目约定书写（见 §4.2 校验）。

### 2.5 `postproc/` — 聚合 / CSV / 报告
- `aggregate.py:116`：`rglob("*.json")` + **按 prompt 名长度降序匹配文件名后缀**（`aggregate.py:110`）——靠文件名反推语义，是脆弱点（改名/碰撞即错）。
- `export_csv.py:158`：pandas `DataFrame.to_csv`；`_find_keys`（`stats.py:44`）dot-notation 递归取值（深度上限 10）；`enrich_from` 跨 prompt join 元数据（`export_csv.py:191`）；跳过 `"not reported"/"null"/""` 哨兵值。
- `report_md.py:268`：`{{value_counts/count_true/mean/count "prompt" "field"}}` 模板命令，`re.sub` 回调渲染。
**借鉴**：聚合→导出两段式；**不搬**：文件名解析聚合（项目用 SQL JOIN）、pandas、模板命令引擎（用简化 Markdown 报告）。

### 2.6 `llm_handler.py` — key 轮询 + 滑窗限流
`RateLimiter`（`llm_handler.py:31`，deque 滑窗）+ 每 key 一个 client 轮询（`get_client:194`）+ `is_retriable`（`llm_handler.py:209`：429/5xx/连接错误可重试，401/403/400 不可）；`response_format` 被主动丢弃（`llm_handler.py:262`，Claude 兼容代理不接收）。
**项目已有更强等价物**：`core/api_key_manager` 的 `ServiceKeyPool`（per-key `max_concurrent/rpm_limit/tpm_limit`，`config_service.py:32-54`），`ai_service._call_with_key_pool`（`ai_service.py:42`）已封装等待/报错/重试。**不新写限流器**。

---

## 3. 机制映射表

| litrev 机制（源码位置） | 项目等价物（已验证） | 处置 |
|---|---|---|
| `litrev.yaml` + `ConfigLoader`（`config.py:186`） | `ConfigService` + DB `configs`/新表 `extraction_dimensions` | 借鉴"声明式+校验"，落 DB；不引 YAML |
| `PromptDef` name/id/system_prompt/user_template（`models.py:124`） | `extraction_dimensions` 行：`label`=name、`prompt`=user_template 变体、`system_prompt` 可选 | 搬"维度可管理"；不搬 `{content}` 占位符 |
| `TemplateManager.render`（`templates.py:137`） | `call_json_extraction_api` 的 `prompt + "\n\nCONTENT:\n" + md`（`ai_service.py:222`） | 复用现有拼接 |
| `Pipeline` 线程池并发（`pipeline.py:330`） | `priority_task_hub` 10 workers（`constants.py:25` `DEFAULT_CONCURRENCY=10`） | 复用，BACKGROUND 优先级 |
| `StateManager.is_completed`（`state.py:126`） | `document_metadata.dimension_id` 存在性检查 | 复用+扩展（新增列） |
| `--reset/--resume-failed`（`cli/run_cmd.py:64`） | 批量 `force=true`：先删旧结果再入队；死信队列重试端点（`server.py:226`） | 复用 |
| `NonRetriableError` + 重试（`pipeline.py:46,582`） | worker 抛异常 → 队列 `requeue_with_delay`（`priority_queue.py:322`），3 次后死信 | 复用（参数更保守，合适） |
| `aggregate`（`postproc/aggregate.py:116`） | SQL `JOIN document_metadata/documents` 查询 | 复用（比文件名解析可靠） |
| `export_csv`（`postproc/export_csv.py:158`） | 新 `extraction_export.build_csv`（stdlib csv） | 借鉴+加固（公式注入/BOM） |
| `report_md`（`postproc/report_md.py:271`） | 新 `extraction_export.build_markdown`（每文档一节） | 借鉴最小子集 |
| `LLM_API_KEY/BASE_URL/MODEL_NAME`（`models.py:78`，`llm_handler.py:155`） | `ConfigService.get_extract_config()`（`config_service.py:94`） | 复用 |
| `RateLimiter` 滑窗 + key 轮询（`llm_handler.py:31,194`） | `ServiceKeyPool` + `_call_with_key_pool`（`ai_service.py:42`）；批量侧加进程内信号量（§4.2） | 复用+轻量兜底 |
| `ReaderFactory`（`readers/base.py:24`，PDF 需外部预处理） | 输入恒为 `documents.ocr_markdown` | 不搬 |
| CLI `litrev run/postproc` + 插件 registry（`registry.py:46`） | 无 | **不搬**（不做 CLI/插件系统） |
| multimodal 逐图任务（`pipeline.py:252`） | 无场景 | 不搬 |

---

## 4. 项目侧改动清单

### 4.1 DB schema 与迁移（`backend/database.py`）

两处变更，均**向前兼容、幂等**：

```python
def init_db(self):
    with self.safe_write() as cursor:
        # ...现有三张表 CREATE TABLE IF NOT EXISTS 不动...
        self._migrate(cursor)

def _migrate(self, cursor):
    # 新库/旧库统一：补建维度表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS extraction_dimensions (
            id TEXT PRIMARY KEY,
            label TEXT UNIQUE NOT NULL,
            prompt TEXT NOT NULL,
            system_prompt TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # document_metadata 增加维度外键（可空，旧行 NULL）
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(document_metadata)").fetchall()]
    if 'dimension_id' not in cols:
        cursor.execute("ALTER TABLE document_metadata ADD COLUMN dimension_id TEXT")
```

`add_document_metadata` 加可选参（向后兼容，`ocr_service.py:190` 调用点零改动）：

```python
def add_document_metadata(self, doc_id, label, content_json, dimension_id=None):
    with self.safe_write() as cursor:
        cursor.execute('INSERT INTO document_metadata (doc_id, label, content_json, dimension_id) VALUES (?, ?, ?, ?)',
                       (doc_id, label, content_json, dimension_id))
        return cursor.lastrowid
```

设计决策：**新表而非 `configs` JSON blob**——JSON 方案是读-改-写，维度管理并发有丢失更新风险，且无法用 `UNIQUE(label)` 约束与 SQL 过滤导出；新表方案迁移零风险（`init_db` 每次启动都跑，`IF NOT EXISTS` + `PRAGMA` 守卫）。`document_metadata.dimension_id` 而非仅按 label 关联：label 可改名/重名，id 才是稳定键（对应 litrev `PromptDef.id` vs `name` 的分工，`models.py:126`）。

### 4.2 新服务 `backend/services/extraction_service.py`（≤200 行）

```python
"""提取维度管理与批量提取（Phase 3，借鉴 litrev-extract 模式）。"""
import asyncio, json, uuid
from services.ai_service import call_json_extraction_api
from services.config_service import ConfigService

_LLM_SEMAPHORE = asyncio.Semaphore(3)   # 批量场景 LLM 并发兜底（详见风险 R2）

class DimensionError(Exception): ...

def validate_dimension(dim: dict) -> dict:
    """集中校验（借鉴 _validate_config 的收集式风格）。label≤50、prompt≤8000 非空；
    prompt 含 '{content}' 一律拒绝——项目约定为 prompt + CONTENT 后缀，见 ai_service.py:222。"""
    label = (dim.get('label') or '').strip()
    prompt = (dim.get('prompt') or '').strip()
    if not label or len(label) > 50: raise DimensionError('label 必填且 ≤50 字符')
    if not prompt or len(prompt) > 8000: raise DimensionError('prompt 必填且 ≤8000 字符')
    if '{content}' in prompt: raise DimensionError("prompt 不需要 '{content}'，文档内容会自动附加")
    return {'id': (dim.get('id') or '').strip(), 'label': label, 'prompt': prompt,
            'system_prompt': (dim.get('system_prompt') or '').strip(),
            'enabled': 1 if dim.get('enabled', True) else 0}

def list_dimensions(db) -> list: ...          # SELECT * ORDER BY created_at
def get_dimension(db, dimension_id) -> dict | None: ...

def save_dimension(db, dim: dict) -> dict:
    """upsert：id 空则生成 uuid4().hex[:12]；label 冲突（sqlite3.IntegrityError）→ DimensionError。"""

def delete_dimension(db, dimension_id) -> bool: ...   # 只删维度定义，不删已产生结果

def select_batch_candidates(db, dimension_id, doc_ids=None, force=False):
    """返回 (to_run, skipped)。跳过：ocr_status!='completed' 或 ocr_markdown 为空；
    已有 (doc_id, dimension_id) 结果（litrev is_completed 等价物，force 时跳过该检查）。"""

async def run_dimension_extraction(doc_id, dimension_id, db):
    """任务队列 worker 入口，签名匹配 task_func(doc_id, *args, db=...)（task_manager.py:102）。"""
    dim = get_dimension(db, dimension_id)
    if not dim or not dim['enabled']: raise DimensionError(f'dimension {dimension_id} 不存在或已停用')
    doc = db.get_document(doc_id)
    if not doc or not doc.get('ocr_markdown'): raise DimensionError(f'doc {doc_id} 无 OCR 文本')
    cs = ConfigService(db)
    pool_status = cs.initialize_key_pools()               # 与 run_full_ocr_workflow 同模式
    cfg = cs.get_extract_config()
    if pool_status.get('llm', False): cfg['_use_multi_key'] = True
    async with _LLM_SEMAPHORE:
        raw = await call_json_extraction_api(doc['ocr_markdown'], cfg, dim['prompt'])
    data = json.loads(raw)                                # 失败会抛异常 → 队列重试
    if isinstance(data, dict) and 'error' in data:
        raise DimensionError(f"extraction failed: {data['error']}")   # 单 key 路径返回错误 JSON，必须转异常
    db.add_document_metadata(doc_id, dim['label'], raw, dimension_id=dimension_id)

def collect_export_rows(db, dimension_id) -> list:
    """JOIN document_metadata/documents，返回 [{doc_id, filename, title, data(dict), created_at}]。"""
```

要点：
- **error JSON 转异常**是关键质量闸口：`call_json_extraction_api` 单 key 失败路径返回 `json.dumps({"error": ...})`（`ai_service.py:239,261-265`）而非抛错；不转换会把错误当成提取结果落库。
- **信号量**是 litrev `RateLimiter` 的轻量项目等价物：只在批量路径生效，不动 OCR/聊天链路；单 key 模式下把 LLM 并发压到 ≤3，多 key 模式下由 key 池的 per-key `max_concurrent/rpm/tpm` 主导。
- 断点续跑 = `select_batch_candidates` 的存在性检查；`force` 由端点在入队前删旧行实现（对应 litrev `--reset`，`cli/run_cmd.py:64`）。

### 4.3 新服务 `backend/services/extraction_export.py`（≤120 行）

```python
def flatten_record(obj: dict) -> dict:
    """顶层键打平为列：标量转 str；dict/list → json.dumps(compact, ensure_ascii=False)。
    缺失键留空（借鉴 export_csv 的列并集思路，去掉字段配置与哨兵值复杂性）。"""

def sanitize_csv_cell(v) -> str:
    """CSV 公式注入防护：以 = + - @ \\t \\r 开头的字符串加 ' 前缀（Excel/Sheets 公式执行防护）。"""

def build_csv(dimension: dict, rows: list) -> str:
    """io.StringIO + csv.writer(QUOTE_MINIMAL, lineterminator='\\r\\n')；
    表头 = doc_id, filename, title, created_at, <打平列并集排序>；输出加 UTF-8 BOM（Windows Excel 中文）。"""

def md_escape(v) -> str:
    """Markdown 值净化：\\n→'<br>'，'|'→'\\\\|'，去首尾空白。"""

def build_markdown(dimension: dict, rows: list) -> str:
    """# 导出报告：{label} + 元信息行（dimension_id / 文档数 / 导出时间）
    + 每文档 '## {filename}' 一节，'- **key**: value' 列表（不用宽表格，长文本不破坏结构）。"""
```

### 4.4 `backend/server.py` 新端点（沿用现有 `BaseModel` 风格）

```python
class DimensionRequest(BaseModel):
    id: str = ""
    label: str
    prompt: str
    system_prompt: str = ""
    enabled: bool = True

class BatchExtractRequest(BaseModel):
    dimension_id: str
    doc_ids: list[int] = []     # 空 = 全部候选文档
    force: bool = False

@app.get("/extraction/dimensions")                    # 列表
@app.post("/extraction/dimensions")                   # save_dimension（校验失败 400）
@app.delete("/extraction/dimensions/{dimension_id}")  # 404 if 不存在

@app.post("/extraction/batch")
async def run_batch_extraction(req: BatchExtractRequest):
    dim = extraction_service.get_dimension(state.db, req.dimension_id)
    if not dim: raise HTTPException(404)
    to_run, skipped = extraction_service.select_batch_candidates(
        state.db, req.dimension_id, req.doc_ids or None, req.force)
    if req.force:
        for doc_id in to_run:
            state.db.delete_metadata_by_dimension(doc_id, req.dimension_id)
    queued = 0
    for doc_id in to_run:
        ok = await priority_task_hub.add_task(
            doc_id, extraction_service.run_dimension_extraction, req.dimension_id,
            priority=TaskPriority.BACKGROUND, force=req.force)
        if ok is not None: queued += 1
    return {"success": True, "queued": queued, "skipped": len(skipped)}

@app.get("/documents/export")                         # ?dimension_id=&format=csv|md
async def export_documents(dimension_id: str, format: str = "csv"):
    dim = extraction_service.get_dimension(state.db, dimension_id)
    if not dim or format not in ("csv", "md"): raise HTTPException(404)
    rows = extraction_service.collect_export_rows(state.db, dimension_id)
    text = extraction_export.build_csv(dim, rows) if format == "csv" else extraction_export.build_markdown(dim, rows)
    safe = re.sub(r'[^\w\u4e00-\u9fff-]', '_', dim['label'])   # 文件名消毒，防 header 注入
    return Response(content=text, media_type="text/csv; charset=utf-8" if format=="csv" else "text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={safe}.{format}; filename*=UTF-8''{quote(safe)}.{format}"})
```

需在 `database.py` 补 `delete_metadata_by_dimension(doc_id, dimension_id)`（force 重跑前清理，与 `delete_metadata` 同风格，+6 行）。

### 4.5 前端

| 文件 | 改动 |
|---|---|
| `src/types/index.ts` | 新增 `ExtractionDimension { id, label, prompt, system_prompt?, enabled, created_at, updated_at }`、`BatchRunResult { queued, skipped }` |
| `src/api/client.ts` | `getDimensions() / saveDimension(dim) / deleteDimension(id) / runBatch(dimensionId, docIds?, force?) / exportDimension(dimensionId, format) → Blob`（全部走现有 `getBaseUrl()` 模式） |
| `src/components/settings/DimensionManager.tsx`（新） | 维度列表 + 新增/编辑表单（label/prompt/system_prompt/enabled）+ 删除 + 「批量运行」「导出 CSV」「导出 MD」按钮；导出用 `URL.createObjectURL(blob)` 触发下载 |
| `src/components/SettingsModal.tsx` | `TabType` 增加 `'dimensions'`，tab 栏加按钮，内容区挂 `<DimensionManager />`（`SettingsModal.tsx:15,457-461` 同款模式） |
| `src/components/settings/DimensionManager.test.tsx`（新） |  Vitest/RTL 覆盖全部 handler（agents.md §6 100% 事件覆盖） |
| `src/components/SettingsModal.test.tsx`（已有） | 追加维度 tab 切换用例 |

范围控制：**不改** `ChatSidebar.tsx` 现有单文档提取表单（避免范围蔓延）；维度下拉快选列入后续可选增强。

### 4.6 批量任务与队列协调

- 走 `priority_task_hub`（`PriorityTaskManager`，lifespan 已启动，`server.py:82-83`），`TaskPriority.BACKGROUND`：批量提取不与交互式 `reprocess`（CRITICAL/HIGH）争抢。
- 入队前 `select_batch_candidates` 已过滤无 OCR 文本的文档；正在 OCR（`processing`）的文档不在候选内。极端竞态（枚举时 OCR 刚完成）下该文档本轮跳过，下轮批量自然覆盖。
- **已知限制**：队列按 `doc_id` 去重（`priority_queue.py:285`）——同一文档正在跑维度 A 时，维度 B 的批量任务会被跳过（返回 `skipped`）。UI 提示"每文档同时只运行一个提取任务"。
- 进度观测：`GET /tasks/stats`（`server.py:212`）已含 priority 统计；死信可通过 `GET /tasks/dead-letters`（`server.py:219`）查看与重试。worker 不推 WS（与 `run_full_ocr_workflow` 现状一致），前端轮询刷新。

---

## 5. 数据流与状态机

```
[维度定义] SettingsModal → POST /extraction/dimensions → validate_dimension
                                                    → extraction_dimensions 行
[批量入队] 「批量运行」→ POST /extraction/batch → select_batch_candidates
        → (force? 删旧结果) → priority_task_hub(BACKGROUND) 每 doc 一任务
[worker]  run_dimension_extraction(doc_id, dimension_id, db)
        → ConfigService.get_extract_config() + key 池 → Semaphore(3)
        → call_json_extraction_api(ocr_markdown, cfg, dim.prompt)
        → 解析；{"error":...} → 抛异常
[落库]    add_document_metadata(doc_id, label, raw_json, dimension_id)
[导出]    GET /documents/export → collect_export_rows(JOIN) → flatten → CSV/MD → Blob 下载
```

状态机（单 doc × 单维度）：`未提取 → 排队中 → 运行中 → 已提取(metadata 行)`；运行中异常 → `重试等待(backoff 1s/5s/30s)`，3 次后 → `死信`（可在死信端点重试）；已提取状态下再次批量 → `跳过`（= litrev `is_completed`），`force` → 删行重回 `未提取`。批量整体语义：**部分失败不阻塞其余文档**（逐 doc 独立重试，对应 litrev `_safe_process` 的逐任务隔离，`pipeline.py:375`）。

---

## 6. 测试计划

**unit**
- `tests/unit/test_extraction_db.py`：迁移——手工按旧 schema 建库（无 `dimension_id`、无维度表）→ `Database(path)` → 断言新列存在、旧 `document_metadata` 行 `dimension_id IS NULL`、`Basic Insight` 读取正常；`extraction_dimensions` CRUD；`add_document_metadata` 带/不带 `dimension_id`。
- `tests/unit/test_extraction_service.py`：`validate_dimension`（空 label / 空 prompt / 超长 / 含 `{content}` 拒绝）；`save_dimension` upsert 与 label 唯一冲突 → `DimensionError`；`select_batch_candidates`（无 markdown 排除、已完成跳过、force 包含、`doc_ids` 过滤）；`run_dimension_extraction` mock `call_json_extraction_api` 三条路径——正常 JSON 落库、返回 `{"error":...}` 抛异常、抛 `APIKeyPoolExhaustedError` 传播（供队列重试）。
- `tests/unit/test_extraction_export.py`：`flatten_record`（标量/嵌套/缺列/列表）；CSV 转义（含逗号、引号、换行、`=cmd|'/C calc'!A0`、`+1`、`-1`、`@SUM`、Tab 前缀全部被 `'` 中和；BOM 存在）；Markdown 换行/竖线净化；空结果集输出仅表头/空节。

**integration**
- `tests/integration/test_extraction_batch_flow.py`（沿用 `test_api_upload_flow.py` 的 `sys.argv` 注入 + `TestClient` + lifespan 启 worker 模式）：mock `services.extraction_service.call_json_extraction_api` 返回合法 JSON → `POST /extraction/batch` → 等待 worker → 断言每 doc 一条 `dimension_id` 正确的 metadata；二次批量全部 `skipped`；`force=true` 重跑（旧行被替换）。
- LLM 失败重试与部分失败：`mock.patch.object(constants.TaskConfig, 'RETRY_BACKOFF', [0,0,0])` 加速 → mock 恒失败 → 等待 → 断言 `priority_task_hub` 死信出现该 doc、其余 doc 不受影响；`GET /documents/export` 对空维度 404、对 `format=xml` 400/404。
- 端到端导出：2 文档不同结构 JSON → CSV 列并集正确、MD 每文档一节。

**security**
- `tests/security/test_export_injection.py`：公式注入单元格中和回归；`Content-Disposition` 文件名含 `../`、引号、换行时被消毒（路径穿越/头注入）。

**前端**：`DimensionManager.test.tsx` 覆盖新增/保存/删除/批量运行/导出 CSV/导出 MD 全部 `onClick`；`SettingsModal.test.tsx` 覆盖维度 tab 切换。

**回归门槛**：`run_tests.bat` 全绿 + `pnpm build` 通过方可合 `main`（agents.md §1）。

---

## 7. 风险登记表

| # | 风险 | 等级 | 对策 |
|---|---|---|---|
| R1 | 范围蔓延成"干脆 vendor litrev" | 高 | §3 映射表证明每个机制已有等价物；litrev 依赖 openai/pandas/tqdm 而 python_embed 无 pip（未验证可装）——vendor 实际不可行；验收只认三模式，插件系统/YAML/CLI 明确不做 |
| R2 | 批量打爆 LLM 限流 | 高 | 多 key 模式下 `ServiceKeyPool` per-key `max_concurrent/rpm/tpm` + `acquire_key` 等待自动分摊（`ai_service.py:42-83`）；`extraction_service` 模块级 `Semaphore(3)` 兜底（含单 key 模式）；失败自动重试进死信不丢任务 |
| R3 | 导出注入（CSV 公式执行 / MD 结构破坏 / 文件名头注入） | 高 | `sanitize_csv_cell` 对 `= + - @ \t \r` 前缀加 `'`；`md_escape` 处理换行与竖线；导出文件名 `re.sub` 消毒；`tests/security/test_export_injection.py` 专项回归 |
| R4 | 维度 prompt 随意改导致提取质量回归 | 中 | prompt 存 DB 可改但不自动触发重跑（skip 语义）；编辑 UI 明示"修改不会自动重新提取"；导出报告头带 `dimension_id` + `updated_at` + prompt 长度便于追溯；`force` 才重跑 |
| R5 | DB 配置迁移失败/数据丢失 | 中 | 只加表加可空列，`CREATE TABLE IF NOT EXISTS` + `PRAGMA table_info` 守卫幂等；`safe_write` 写锁 + WAL；单测覆盖旧库升级路径；回滚无需 down migration（§9） |
| R6 | 错误 JSON 被当成功结果落库 | 中 | `run_dimension_extraction` 强制检查 `{"error":...}` 并转异常；单测三条路径覆盖（单 key 失败返回错误串是 `ai_service.py:239` 既有行为，易漏） |
| R7 | 同文档多维度批量互相跳过（队列按 doc_id 去重） | 低 | 文档化为已知限制；响应体返回 `skipped` 计数，UI 提示；需要时用户对第二维度再点一次批量 |
| R8 | 批量枚举期 OCR 竞态 | 低 | 候选查询要求 `ocr_status='completed'` 且 markdown 非空；竞态文档本轮跳过、下轮覆盖，无数据错误 |

---

## 8. 验收标准

- [ ] `GET/POST/DELETE /extraction/dimensions` 可用；label 唯一、prompt 必填、`{content}` 拒绝，校验失败返回 400
- [ ] `POST /extraction/batch` 对 N 篇已完成文档入队并全部产出 metadata；已有结果跳过；`force=true` 替换旧结果
- [ ] 批量任务 BACKGROUND 优先级执行；LLM 并发 ≤3（信号量）；失败重试 ≤3 次后入死信，可在死信端点重试
- [ ] `GET /documents/export?format=csv` 返回 UTF-8(BOM) CSV，列并集正确，公式注入单元格被中和
- [ ] `format=md` 返回分文档报告，换行/竖线不破坏结构；空维度 404
- [ ] 旧库（含历史 `document_metadata`）升级后新列存在、旧行 `dimension_id` 为 NULL、Basic Insight 功能无损
- [ ] `tests/unit|integration|security` 新用例 + `run_tests.bat` 全绿；`pnpm build` 通过
- [ ] SettingsModal「Dimensions」tab：维度增删改、批量运行、导出按钮可用；全部事件 handler 有 Vitest 用例
- [ ] 全程在 `feature/extraction-framework` 分支；未 vendor 任何 litrev 代码；未新增第三方依赖（python_embed 直接可跑）
- [ ] 未引入 YAML 配置体系、litrev CLI、插件系统

---

## 9. 回滚策略

- 代码：整分支弃置即可，无 vendor 耦合、无共享协议变更。
- DB：变更全部向前兼容——新表 `extraction_dimensions` 与可空列 `document_metadata.dimension_id`；回滚旧代码后 `add_document_metadata(doc_id, label, json)` 仍工作，旧代码忽略新列。**无需 down migration**。
- 数据清理（可选，非必需）：`DROP TABLE extraction_dimensions;`（历史 metadata 行保留，仅失去维度关联）。
- 前端：`DimensionManager` 为新文件 + SettingsModal 增量挂载，revert 即净。

---

## 10. 工作量估计（约 1–1.5 人日）

| 项 | 工时 |
|---|---|
| DB 迁移 + 维度 DAO + `dimension_id` 参数 | 2h |
| `extraction_service.py`（校验/CRUD/候选/worker/信号量） | 2h |
| `extraction_export.py`（打平/CSV/MD/注入防护） | 1.5h |
| `server.py` 5 端点 | 1.5h |
| 前端（types/client/DimensionManager/SettingsModal 挂载） | 2h |
| 测试（unit×3 + integration×2 + security×1 + 前端×2） | 2.5h |
| 联调、全量测试、review | 1h |

---

## 11. 实施顺序

1. 建 `feature/extraction-framework` 分支（未绿不合 main）。
2. `database.py`：`_migrate` + `add_document_metadata(dimension_id)` + `delete_metadata_by_dimension` → 写 `tests/unit/test_extraction_db.py`（旧库升级用例先行）。
3. `extraction_service.py`：校验/CRUD/候选枚举 → 单测。
4. `run_dimension_extraction` worker + 信号量 → 单测（成功 / error-JSON / 异常三路径）。
5. `extraction_export.py` → 单测 + `tests/security/test_export_injection.py`。
6. `server.py` 端点 → `tests/integration/test_extraction_batch_flow.py`（含加速重试与死信用例）。
7. 前端：`types/index.ts` → `client.ts` → `DimensionManager.tsx`(+test) → `SettingsModal.tsx` tab(+test)。
8. `run_tests.bat` 全量 + `pnpm build` → 合 `main`。
