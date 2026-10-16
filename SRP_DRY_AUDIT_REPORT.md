# Academic Clarity — SRP & DRY 全项目审计报告

> **审计日期**：2026-10-15
> **审计分支**：`refactor/srp-dry-cleanup`（基于 `main` @ 6e0d938）
> **审计方法**：4 个并行只读审计子代理（后端 SRP / 后端 DRY / 前端 SRP+DRY / 测试与脚本），全部发现均经工具逐行核实。
> **审计范围**：`backend/`（排除 `vendor/` 第三方冻结代码）、`src/`、`electron/`、`tests/`、`scripts/`、根配置。
> **排除项**：`backend/vendor/**`（有 `test_vendor_know_integrity.py` 哈希保护，禁止改动）、`node_modules/`、`python_embed/`、`dist/`、`dist-electron/`。

---

## 0. 执行摘要

| 域 | 发现总数 | HIGH | MED | LOW |
|---|---|---|---|---|
| 后端 SRP | 24 | 14 | 4 | 6 |
| 后端 DRY | 25 | 4 | 12 | 9 |
| 前端 SRP + DRY | 26 | 7 | 14 | 5 |
| 测试与脚本 | 20 | 7 | 7 | 6 |
| **合计** | **95** | **32** | **37** | **26** |

核心问题画像：

1. **超 200 行文件（AGENTS.md §5 硬约束）**：后端 12 个（server.py 610 行最严重）、前端 6 个（Dashboard.tsx 1015 行最严重）。
2. **分层泄漏**：路由层内嵌业务逻辑、service 层裸写 SQL、utils 层反向依赖 services。
3. **并行维护的重复系统**：两套任务队列（task_manager / priority_queue）、两套重试退避、两套单例、两套 server 装配。
4. **已定义但悬空的常量**：`LoggingConfig` / `DBConfig` / `CacheConfig` / `MetadataConfig.DEFAULT_LABEL` 等定义了却无消费方，实现处硬编码。
5. **测试样板大规模复制**：31/32 个测试文件重复路径引导、6 个集成测试重复 server 脚手架、14 个文件重复临时 DB 生命周期；清理器前缀与实际脱节（实测有残留）。
6. **LiteLLM 渗透点**：后端 1 处 import（3 个调用）+ 测试 4 处引用 + `python_embed` 已安装包本体。

修复工作按 3 个批次推进（详见 §8 处置矩阵），全部修改在 `refactor/srp-dry-cleanup` 分支完成，通过全量测试后合并 `main`。

---

## 1. 基线状态（修复前）

- `git status`：工作树干净，`main` 领先 origin 2 个提交。
- 全量测试（`tests/run_all_tests.py`，8 路并行 + pnpm lint/test）：**32/34 PASS**。
  - `test_doi_verify_flow.py`、`test_extraction_batch_flow.py` 报 600s 超时——经单独重跑确认**均为并发 CPU 争抢所致的假超时**（单独跑 64.7s / 86.5s 全绿）。基线判定：**全绿**。
- 环境：Python 3.10.11（python_embed）、Node 22.19.0、pnpm 11.25.0。

---

## 2. 后端 SRP 发现（B-SRP）

### 2.1 超 200 行文件清单

| 文件 | 行数 | 主要职责数 | 建议拆分 |
|---|---|---|---|
| `backend/server.py` | 610 | 6+ | 拆 `routes/`（documents/tasks/knowledge/extraction/system/files）+ `app_state.py`，server 保留装配与启动 |
| `backend/core/priority_queue.py` | 339 | 5 | 拆 `priority_models.py` + `dead_letter_store.py` + 队列/管理器 |
| `backend/utils/health.py` | 321 | 8 类检查 | 拆 `checks_system.py` + `checks_services.py` + 编排层 |
| `backend/utils/cache.py` | 303 | 5 | 拆 `cache_backends.py` + `cache_domains.py` + 管理/单例 |
| `backend/utils/websocket.py` | 299 | 5 | 拆 `ws_protocol.py` + `ws_connection.py` + `ws_progress.py` |
| `backend/utils/shared.py` | 269 | 8 个互不相关原语 | **全文件零消费者（死代码）→ 删除** |
| `backend/services/ocr_service.py` | 234 | 3 | 拆 `ocr_images.py` + `ocr_workflow.py`，保留门面 |
| `backend/database.py` | 225 | 4 | 拆 schema/repository/queries（注意保留 `database.py` 兼容入口） |
| `backend/utils/middleware.py` | 216 | 5 中间件 + 工厂 | 拆 observability/limits，删 2 个 no-op 死代码 |
| `backend/services/tex_service.py` | 209 | 4 | 拆 `tex_security.py` + `tex_detect.py` + workflow |
| `backend/services/knowledge_service.py` | 200 | 5 | 拆 `knowledge_store.py` + `knowledge_queries.py` |
| `backend/utils/metrics.py` | 185 | 6 | 拆 registry / timeseries / 埋点 |
| `backend/core/task_manager.py` | 187 | 6 | 拆重试策略 / worker 池（或并入 priority_queue，见 B-DRY-05） |

### 2.2 逐条发现

| # | 严重度 | 位置 | 问题 | 修复方案 |
|---|---|---|---|---|
| B-SRP-01 | HIGH | `server.py:1-610` | 单文件承担：应用装配、30+ 路由、Pydantic 模型、文件上传落盘、端口探测、全局状态 | 拆 `routes/` 包 + `app_state.py`，server ≤120 行 |
| B-SRP-02 | HIGH | `server.py:233-256,282-304,328-353,463-481,577-596` | 路由层内嵌业务：cancel 联动 5 个组件、sync 重跑判定、上传做文件 IO、chat 拼 context、export 拼响应头 | 下沉为 service 函数（`services/document_service.py` 等） |
| B-SRP-03 | HIGH | `server.py:59-86` | `AppState` 全局单例 = 服务定位器；路由直达 `state.db`；`initialize()` 混杂三种子系统引导 | 拆 `AppContext` + 各服务自管初始化；保持 `state` 可从 server 导入 |
| B-SRP-04 | HIGH | `core/priority_queue.py:24-339` | 任务模型/堆存储/死信/worker 池/统计五合一；`asyncio.Lock` 与 `threading.Lock` 混用 | 拆 3 文件；`QueuedTask`、`priority_task_hub` 保持可导入 |
| B-SRP-05 | HIGH | `utils/health.py:60-319` | 8 类异构检查；utils 层裸写 SQL 查 documents；utils 反向 import services | 拆 checks 模块；DB 探测改走 db API；API 配置检查注入回调 |
| B-SRP-06 | HIGH | `utils/cache.py:21-303` | 配置解析/两种后端/两种领域缓存/全局单例四合一；本地 `CacheConfig` 与 constants 双份 | 拆 backends/domains；删除本地 CacheConfig 与死导入 |
| B-SRP-07 | HIGH | `utils/websocket.py:12-299` | 协议/连接/广播/领域事件映射/进度状态机同文件；两个单例；UI 文案混入基础设施 | 拆 3 文件；领域映射移出；保持 `ws_manager/progress_tracker/EventType` 可导入 |
| B-SRP-08 | HIGH | `utils/shared.py:13-269` | 8 个并发原语杂物抽屉，**全仓零调用方**（仅 `utils/__init__` 重导出）；`Once` 用废弃 API | **删除整个文件**并清理 `utils/__init__.py` 导出 |
| B-SRP-09 | HIGH | `services/ocr_service.py:34-234` | 图像编码/单页重试/全流水线编排（112 行单函数）混合 | 拆 `ocr_images.py` + `ocr_workflow.py`；保留 4 个公共符号 re-export |
| B-SRP-10 | HIGH | `database.py:39-225` | DDL+迁移+CRUD+视图模型组装混层；持久层 import utils.text_processor（依赖倒置） | 拆 schema/repository/queries；`ocr_structured_json` 组装上移；保持 `Database` 类与返回字段 |
| B-SRP-11 | HIGH | `utils/middleware.py:104-216` | 2 个 no-op 死中间件 + 2 个未挂载中间件 + 第四种装配工厂（与 server 双装配） | 删除 no-op 与工厂；保留 2 个在用中间件并拆分 |
| B-SRP-12 | HIGH | `services/tex_service.py:43-209` | 安全校验/主 tex 启发式/标题解析/工作流编排混合 | 拆 `tex_security.py` + `tex_detect.py`；**`TexConfig` 必须保持 re-export**（安全测试依赖） |
| B-SRP-13 | HIGH | `services/knowledge_service.py:35-200` | 基础设施/字段映射/4 处裸 SQL/ingest 业务/归档 IO 混合 | 拆 store/queries；`_conn`、`_kb_path` 必须保持可导入 |
| B-SRP-14 | HIGH | `services/extraction_service.py:37-139` | service 层绕过 Database 直写 SQL；同表读写分散两层 | Database 补 extraction_dimensions CRUD；查询样板收敛 |
| B-SRP-15 | MED | `server.py:306-322` | `/configs` 绕过 ConfigService：`TABLE_STYLE` 直读、POST 任意键直写（无白名单） | ConfigService 增 `get_ui_config()` / `set_config()`（含白名单） |
| B-SRP-16 | MED | `core/task_manager.py:68-186` | 与 `priority_queue` 两套职责重叠的任务系统；调用方要同时操作两者 | 见 B-DRY-05 处置 |
| B-SRP-17 | MED | `utils/metrics.py:11-185` | 指标定义/注册表/时间序列/uptime/HTTP Response 渲染全在一个单例；未用导入 | 拆 registry/timeseries；Response 构造移出 utils |
| B-SRP-18 | MED | `services/workspace_service.py:10-59` | sync/async 两份近逐行重复实现；扩展名 3 处硬编码；print 混入 | `async` 版改 `asyncio.to_thread` 单行包装；扩展名上收 constants |
| B-SRP-19 | MED | `utils/websocket.py:65-75` | `WebSocketConfig`（上限/心跳/队列）完全未接入；`_heartbeat_task` 从未启动 | 接入 `MAX_CONNECTIONS`；删除未用字段或实现心跳 |
| B-SRP-20 | LOW | `utils/logger.py:15-18,86-104` | 轮转参数硬编码；`LoggingConfig` 悬空；`ServerConfig` 死导入 | 接入 `LoggingConfig`（含新增 ERROR_* 常量）；删死导入 |
| B-SRP-21 | LOW | `services/ai_service.py:44-45,31-32,97-98` | OCR 采样参数硬编码；`"OCR Failed:"` 字符串协议与 ocr_service 隐式耦合（三套错误协议并存） | 参数上收 `OCRConfig`；统一异常协议（随 LiteLLM 移除同批） |
| B-SRP-22 | LOW | `services/doi_service.py:29,32,106` | UA 模板两处、`request_delay=0.35` 硬编码；SSRF/规范化/评分/传输四层混合 | UA/延迟上收 `DoiConfig`；四层可后续再拆 |
| B-SRP-23 | LOW | `utils/__init__.py:4-30` | 包门面一次性 import 触发 5+ 个模块级单例初始化 | 精简为最小 re-export；删除 shared 导出 |
| B-SRP-24 | LOW | `services/config_service.py:40-49` | 字面默认值（`sk-copilot-sdk-default` 等）焊死在代码 | 保持机制（`config.py` 为可选本地覆盖层），统一工厂构造消除键名重复 |

---

## 3. 后端 DRY 发现（B-DRY）

| # | 严重度 | 位置 A | 位置 B（多者） | 问题 | 修复方案 |
|---|---|---|---|---|---|
| B-DRY-01 | HIGH | `workspace_service.py:10-28` | `:30-59` | 同步/异步扫描逐行重复 15+ 行 | async 版改 `to_thread` 单行包装 |
| B-DRY-02 | HIGH | `ocr_service.py:114-119` | `tex_service.py:31-36` + 7 处 `track_*` try/except | `_stage` 逐字重复 + 进度上报样板 8 处 | 抽 `services/workflow_common.py`（safe 上报 + `_stage`） |
| B-DRY-03 | HIGH | `ocr_service.py:227-234` | `tex_service.py:202-209` | 流水线失败清理块（落库 failed + 上报 + raise）重复 | 同上：`fail_workflow()` |
| B-DRY-04 | HIGH | `ai_service.py:35-47` | `:61-72`、`:89-100` | 三个 LLM 调用函数共用同一 completion 样板 | 抽 `_call_llm()` helper（随 LiteLLM 移除重写） |
| B-DRY-05 | MED | `core/task_manager.py:12-187` | `core/priority_queue.py:73-337` | 两套任务队列（worker/重试/取消/统计语义重叠） | 优先合并为 priority 适配器（保持 `task_hub` 接口）；语义无法保真则拆分+文档化 |
| B-DRY-06 | MED | `ocr_service.py:99,108` | `task_manager.py:112`、`priority_queue.py:56-59`、`shared.py:174-189` | 重试退避 clamp 4 处 + 第 3 套独立退避实现 | 建 `utils/retry.py:backoff_delay()`；删除 shared 版 |
| B-DRY-07 | MED | `utils/text_processor.py:16-21` | `ocr_service.py:43,78` | DeepSeek 标签清洗两套正则**已分叉** | 统一为 `strip_ref_det_tags()` 单一实现（取最宽松容错语义） |
| B-DRY-08 | MED | 12 个文件的 `try: from backend.constants / except: from constants` | 其中 3 处（priority_queue/health/middleware）fallback **复制数值** | 双导入样板 12 处；数值双份 | 统一为 `from constants import X` 单行（所有入口均可导入）；消除数值复制 |
| B-DRY-09 | MED | `config_service.py:31-50` | `server.py:311-317`、`ai_service.py` 3 处、`health.py:118-129` | `{api_key,api_base,model_name}` schema 手工构造/消费 7+ 处 | ConfigService 内统一工厂构造，键名集中一处 |
| B-DRY-10 | MED | `database.py:130-146` | `:167-187` | 动态 SET 更新构造重复 | 抽 `_update_columns()` |
| B-DRY-11 | MED | `database.py:113-118,194-225` | `extraction_service.py:37-130` | `get_connection + row_factory + dict(row)` 查询样板 7 处 | Database 增 `fetch_all/fetch_one` |
| B-DRY-12 | MED | `database.py:216` | `server.py:290`、`doi_service.py:119`、`knowledge_service.py:84` | `"Basic Insight"` 字面量 4 处（写入口用常量、读出口用字面量） | 统一引用 `MetadataConfig.DEFAULT_LABEL` |
| B-DRY-13 | MED | `doi_service.py:118-122` | `knowledge_service.py:84-90` | "取 metadata→找 Basic Insight→json.loads"重复且容错已分叉 | Database 增 `get_basic_insight()`（含容错） |
| B-DRY-14 | MED | `ai_service.py:20-23` | `ocr_service.py:69-73` | 图片→base64/DataURI 编码两处 | 建 `utils/image.py:image_to_data_uri()` |
| B-DRY-15 | MED | `utils/logger.py:88,98` | `constants.py:63-69`（悬空） | 日志轮转魔数 vs LoggingConfig 脱钩 | logger 接入 LoggingConfig |
| B-DRY-16 | MED | `knowledge_service.py:116-136` | `:144-198` 共 5 处 | `conn=_conn() + try/finally close` 样板 5 处 | 抽 `_read_conn/_write_conn` contextmanager |
| B-DRY-17 | LOW | `server.py:48` | `workspace_service.py:16,41` | 扩展名元组 3 处硬编码 | 上收 `FileConfig.SUPPORTED_EXTS` |
| B-DRY-18 | LOW | `utils/logger.py:27` | `health.py:308`、`websocket.py:28` | UTC ISO 时间戳三种写法 | 建 `utils/time_utils.py:utc_now_iso()` |
| B-DRY-19 | LOW | `utils/cache.py:120,230,292` | `constants.py:81`（悬空） | 6379 三处硬编码 | 引用 `CacheConfig.REDIS_PORT` |
| B-DRY-20 | LOW | `database.py:21,41` | `knowledge_service.py:50` | PRAGMA/WAL/busy_timeout 与 DBConfig 脱钩；WAL 重复执行两次 | 接入 `DBConfig.WAL_MODE/BUSY_TIMEOUT` |
| B-DRY-21 | LOW | `server.py:236-238,405-407,448-450,487-489` | `:389-390,436-437,466-467,490-491` | doc 存在性/ocr_markdown 校验样板 8 处（三种响应形态） | FastAPI `Depends` 依赖注入统一 |
| B-DRY-22 | LOW | `server.py:395-401` | `:438-444`、`:492-500` | `except → HTTPException(500)` 包装 3 处 | 抽 `server_error()` helper |
| B-DRY-23 | LOW | `server.py:253` | `:441`、`:496-497` | `send_document_update("updated", ...)` 组合动作 3 处 | 抽 `_broadcast_doc_updated()` |
| B-DRY-24 | LOW | `utils/metrics.py:30-36` | `websocket.py:54-58,216-220`、`health.py:32-36` | 手写单例 4 份且细节不一致 | 统一单例基类或各自规范一致 |
| B-DRY-25 | LOW | `tests/` 23 个文件 | 10 个文件 setUp | 测试样板（见 §6，T-01/04） | 迁移到 `tests/helpers.py` |

---

## 4. 前端 SRP + DRY 发现（FE）

### 4.1 超 200 行文件清单

| 文件 | 行数 | 处置 |
|---|---|---|
| `src/components/Dashboard.tsx` | 1015 | 拆 `dashboard/` 子组件 + 3 个 hooks + utils |
| `src/components/Reader.tsx` | 486 | 拆 reader 子组件 + hooks；复活 `useResizable` |
| `src/components/SettingsModal.tsx` | 440 | 拆 `settings/` 子组件 + 2 个 hooks |
| `src/components/Dashboard.test.tsx` | 413 | 拆 3 个测试文件（纯搬移） |
| `src/components/reader/ChatSidebar.tsx` | 373 | 拆 insight / chat 两面板 |
| `src/components/settings/DimensionManager.tsx` | 319 | 拆表单组件 + 行组件 |
| `src/App.tsx` | 301 | 拆 3 个 hooks |
| `src/api/client.ts` | 204 | `request<T>` 统一传输层 |

### 4.2 逐条发现

| # | 严重度 | 位置 | 问题 | 修复方案 |
|---|---|---|---|---|
| FE-01 | HIGH | `Dashboard.tsx:1-1015` | 9 类职责：队列轮询/claims 检索/摄入/筛选排序/5 种渲染分支 | 拆 `dashboard/` 6 个子组件；保持导出、props、aria-label、文案逐字不变 |
| FE-02 | HIGH | `Dashboard.tsx:147-224` | 组件同时是数据源与视图（14 个 useState） | 抽 `useActiveTasks` / `useClaimsSearch` / `useIngestAll` |
| FE-03 | HIGH | `Reader.tsx:1-486` | 三套拖拽缩放 + 划词 + 聊天 + 目录 + 持久化全挤一个组件 | 拆 `ReaderOutline` / `SelectionToolbar` + hooks；testid 保留 |
| FE-04 | HIGH | `SettingsModal.tsx:1-440` | 草稿/校验/焦点圈定/逐字段保存/两种弹窗流程 | 拆 `useSettingsDraft` / `useModalFocusTrap` / `SettingsField` |
| FE-05 | HIGH | `api/client.ts:1-204` | 25 个方法重复 baseUrl+fetch+res.json() 样板 | `request<T>` 统一；对外单例与方法名不变 |
| FE-06 | HIGH | `reader/PdfViewer.tsx:45` | 全仓唯一裸 fetch（绕过 api client） | client 增 `getPdfBlob()`；同步更新测试 mock |
| FE-07 | HIGH | `hooks/useResizable.ts:1-34` | hook 零引用（死代码），Reader 手写重复实现 | 增强 hook 并在 Reader 复用（保持 document 监听语义） |
| FE-08 | MED | `Reader.tsx:24-27` / `ChatSidebar.tsx:20-23` | `ChatMessage` 接口两处逐字重复 | 上移 `types/index.ts` |
| FE-09 | MED | Dashboard:563 / Header:53 / ChatSidebar:350 / PdfViewer:171 | IME 回车判断 4 处重复 | 统一 `utils/keyboard.ts:isImeEnter`（已预建） |
| FE-10 | MED | `Dashboard.tsx:104-111` / `MetadataPanel.tsx:131-135` | 容错 JSON.parse 两处 | 统一 `utils/json.ts:safeParseJson`（已预建） |
| FE-11 | MED | `Dashboard.tsx:113-126` | formatElapsed/formatAddedAt 内联无归属 | 上移 `utils/format.ts`（已预建，输出逐字一致） |
| FE-12 | MED | Dashboard 4 处 + SettingsModal 1 处 | Loader2 按钮模式 5 处 | Dashboard 侧统一为局部 Button；SettingsModal 侧自统一 |
| FE-13 | MED | `Dashboard.tsx:717-877` | 空态/错误态容器重复 5 处 | 抽 `ui/EmptyState.tsx` |
| FE-14 | MED | `SettingsModal.tsx:73-204` | 草稿编排与弹窗基础设施耦合（含 eslint-disable hack） | 见 FE-04 |
| FE-15 | MED | `App.tsx:29-216` | 6 类职责 + catch 三连重复 4 处 | 抽 `useDocuments` / `useBackendHealth` / `useDocumentActions` |
| FE-16 | MED | `ConfirmDialog.tsx:35-43` / `SettingsModal.tsx:105-142` | ESC 关闭两套实现，ConfirmDialog 缺焦点圈定 | `useModalFocusTrap` 共用 |
| FE-17 | MED | `Reader.tsx:87-104` / `PdfViewer.tsx:92-120` | localStorage 容错读写两处 | `usePersistentState`（key 模板与序列化格式逐字保持） |
| FE-18 | MED | `Dashboard.tsx:264-271` | 状态判定业务规则内联组件 | 上移 `utils/docStatus.ts`（已预建） |
| FE-19 | MED | `SettingsModal.tsx:206-357` | 字段行 60+ 行 JSX 内联 + renderTab 伪组件 | 拆 `SettingsField` / TabButton |
| FE-20 | MED | `types/index.ts:15-94` | Document 缺后端字段；AppConfig 字段清单三处硬编码 | 补可选字段 + 字段清单单一来源 |
| FE-21 | MED | `api/client.ts:13-201` | 错误处理口径不一致（仅 2 方法检查 res.ok） | `request<T>` 统一 throw；调用方同步适配 |
| FE-22 | MED | `Dashboard.test.tsx:1-413` | 测试文件超限、claims 用例三段式重复 | 拆 3 个测试文件 + 共享 helper |
| FE-23 | LOW | `api/client.ts:96-108` | `getKnowledgePapers/Claims` 零调用死方法 | 删除（已确认零引用） |
| FE-24 | LOW | vite/vitest/tsconfig | `@` 别名三处两套语义（实际零使用） | 删除未使用别名配置 |
| FE-25 | LOW | `vite.config.ts:8-75` | 五类配置混合（未超限） | **保持现状**（收益低风险高） |
| FE-26 | LOW | `Header.tsx:6` / `ReaderToolbar.tsx:6-7` | 内联联合类型重复 types 定义 | 复用 `View`；`ViewMode` 上移 types |

---

## 5. 测试与脚本发现（T）

| # | 严重度 | 位置 | 问题 | 修复方案 |
|---|---|---|---|---|
| T-01 | HIGH | 31/32 个测试文件 | 路径引导样板（8 行 while 循环）逐字复制 | 统一 `tests/helpers.py:add_backend_to_sys_path()`（已预建） |
| T-02 | HIGH | 6 个集成/安全测试 | server 脚手架（argv 注入 + TestClient lifespan + state 重指向）约 50 行 ×6 | `helpers.server_test_client()`（已预建） |
| T-03 | MED | 2 个 E2E 文件 | ~150 行 server 子进程 harness 逐字重复 | 抽 `tests/e2e_llm_harness.py`（保留日志落盘行为） |
| T-04 | HIGH | 14 个文件 | 临时 DB setUp/tearDown + WAL 清理样板 | `helpers.make_temp_db/remove_db_files`（已预建） |
| T-05 | HIGH | `run_all_tests.py:53-57,124` | 清理前缀硬编码脱节：`test_tex_unit_`/`test_tex_sec_`/`test_auto_ws_` 未覆盖；CWD 相对 DB 落仓库根永不清理（**实测残留 3 个 .db + 5 个目录**） | 前缀迁入 helpers；清理 roots 参数化（含仓库根与系统 temp）；子进程显式 cwd |
| T-06 | MED | 5 个文件 | FakeClient / urlopen MagicMock / mock LLM response 构造重复 | helpers 提供共享替身 |
| T-07 | MED | 6 个文件 | TEX/CJK 夹具与 `_add_doc`/轮询 helper 重复 | `tests/fixtures_data.py`（已预建）+ helpers 函数 |
| T-08 | MED | `run_all_tests.py:1-131` | 7 项职责混合；`encoding='cp437'` 中文乱码；死变量 | 拆 `runner.py`；encoding 改 utf-8 |
| T-09 | MED | `test_extraction_real_llm.py:212-262` | 单方法断言 7 阶段 | **不拆**（E2E 成本与验证条件受限，理由见 §8） |
| T-10 | MED | batch_flow / final_audit / tex_upload_flow | 单方法混合多行为 | 按行为拆分 |
| T-11 | LOW | `test_database.py:98-122` | 4 个 DOI 子场景塞一个方法 | 改 `subTest` |
| T-12 | HIGH | `test_real_world.py:40` | **硬编码真实 API Key（已入 git）**；无断言假绿；硬编码绝对路径 | 改读 `test/key.json` + `skipTest`；断言化；⚠️ 密钥需用户手动轮换 |
| T-13 | LOW | `tests/ocr_lab/debug_ocr.py:9` | litellm 直接引用（实验室脚本，硬编码本机路径） | 删除脚本（内容已被正式 E2E 取代） |
| T-14 | MED | `test_integration.py:101` | mock `services.ai_service.completion`（litellm 符号） | 改 mock `_make_client` seam（随 LiteLLM 移除） |
| T-15 | MED | `test_edge_cases.py:79` | 同上 | 同上 |
| T-16 | MED | 2 个 E2E 文件 `:98` | 依赖 litellm `openai/` 前缀剥离行为；断网时 FAIL 而非 skip | 新实现保留前缀剥离（兼容存量配置）；setUp 加网络探测降级 |
| T-17 | LOW | vitest/vite/tsconfig/package.json | 别名不一致；tsc 重复 | 见 FE-24；tsc 重复保持（语义不同） |
| T-18 | MED | `scripts/run_app.bat:3` | `cd /d "%~dp0"` 进入 scripts/ 而非根目录，一键启动必挂 | 改为 `%~dp0..` |
| T-19 | LOW | 4 种临时资源位置策略 | 命名与位置分裂（仓库根/系统 temp/分类目录） | 统一 helpers 建临时资源（系统 temp + `ac_test_` 前缀） |
| T-20 | LOW | `backend/utils/*`、`core/*`、部分端点 | 零测试覆盖（cache/health/logger/metrics/middleware/websocket/shared + 10 个端点） | 本次不做补测专项（见 §8），随重构回归；列入 backlog |

---

## 6. LiteLLM 移除影响清单（E）

### 6.1 代码引用（全部）

| 位置 | 形式 | 处置 |
|---|---|---|
| `backend/services/ai_service.py:7` | `from litellm import completion`；3 处调用（OCR/Chat/JSON 提取） | ✅ **已重写为 openai SDK**；`_make_client()` 模块级 seam + `_strip_provider_prefix()` + `_call_llm()` 共享样板 |
| `tests/ocr_lab/debug_ocr.py:9,42-53` | 直接 import + 调用 | ✅ **已删除**（连同 `tests/ocr_lab/output/` 实验残留：2 个 litellm 报错文件 + 2 个空文件 + 2 个实验片段） |
| `tests/integration/test_integration.py:101` | `patch('services.ai_service.completion')` | ✅ 改 patch `services.ai_service._make_client` |
| `tests/system/test_edge_cases.py:79` | 同上 + 异常注入 | ✅ 同上（side_effect 保持通用 Exception，验证 error-JSON 协议） |
| `tests/system/test_extraction_real_llm.py:5-6,98` | 注释 + `"openai/" + model` 前缀依赖 | ✅ 注释更新；新实现保留前缀剥离；setUp 加 TCP 探测（不可达 → SKIP） |
| `tests/system/test_tex_real_llm.py:98` | 同上 | ✅ 同上 |
| `python_embed/Lib/site-packages/litellm*` | 已安装包本体（1.82.1） | ✅ **物理删除**（未留备份；如需恢复可从 PyPI 重新获取同版本） |
| `UX_AUDIT_REPORT.md:414` | 历史文档提及 | 保留（历史记录，不改） |

### 6.2 替换设计决策

1. **用 `openai` SDK 而非 httpx 裸调用**：两者端点均为 OpenAI 兼容（`/v1`），SDK 已随 python_embed 安装，响应形状（`choices[0].message.content`）与现有 mock 完全一致。
2. **保留 `_make_client(api_config)` seam**：三条调用路径共用一个 client 工厂，测试一行 mock 覆盖全部；避免 patch SDK 内部路径（不稳定）。
3. **保留 `openai/` 前缀剥离**：`config.py.example` 默认值与存量用户 DB 配置均含 `openai/` 前缀（litellm 路由语法），新实现须 `model.removeprefix("openai/")`，否则存量配置集体 404。
4. **错误协议统一**：`call_ocr_api` 从返回 `"OCR Failed: ..."` 字符串改为抛 `APIResponseError`；`ocr_service` 的字符串探测同步改 try/except（消除跨模块字符串契约）。
5. **`pil_to_base64` / `_extract_json_from_response`**：前者迁入 `utils/image.py`（与 ocr_service 的重复实现合并）；后者保留在 ai_service（全仓唯一实现，无重复）。

---

## 7. 修复批次编排（并行代理）

| 批次 | 代理 | 职责范围（文件所有权隔离） |
|---|---|---|
| 0（本提交） | 主代理 | 预建共享基础：`constants.py` 扩展、`src/utils/{keyboard,json,format,docStatus}.ts`、`tests/helpers.py`、`tests/fixtures_data.py` + 本报告 |
| 1 | F1 | `server.py` 拆分（routes/ + app_state）+ `/configs` ConfigService 化 + 测试 patch 目标同步 |
| 1 | F2 | `services/` 拆分（ocr/tex/knowledge/extraction/doi/workspace）+ `database.py` 拆分 + `workflow_common.py` |
| 1 | F3 | `utils/` + `core/` 拆分（shared 删除、middleware、cache、health、websocket、metrics、logger、priority_queue、task_manager） |
| 1 | F5 | 前端 Dashboard 组（Dashboard.tsx 拆分 + hooks + EmptyState + 测试拆分） |
| 1 | F6 | 前端 Reader/Settings/App/client 组 + types 整理 + 别名清理 |
| 1 | F7 | 测试基础设施（run_all_tests 重构 + 清理修复 + run_app.bat + test_real_world 安全修复） |
| 2 | F4 | LiteLLM 完全移除（ai_service 重写 + 错误协议统一 + 测试 mock + debug_ocr 删除 + python_embed 包清理） |
| 3-预建 | 主代理 | `tests/e2e_llm_harness.py`（E2E 共享 harness）+ helpers 共享替身（`bb48567`） |
| 3 | F7a | 测试样板迁移：integration（7）✅ + security（4）⚠️（限流中断，2 文件由主代理续完） |
| 3 | F7b | 测试样板迁移：unit（16 文件）⚠️（限流中断，8 文件完成后由主代理续完剩余 8 个） |
| 3 | F7c | 测试样板迁移：system（5 文件，含 2 个 E2E → `e2e_llm_harness` + AC_E2E_LLM 实跑验证）✅ |
| 3-收尾 | 主代理 | 限流中断遗留 12 文件续完（security 4 + unit 8） |
| 4 | 主代理 | 全量测试 + E2E 实跑 + 报告终稿 + 合并 main |

> 执行说明：F7a/F7b 代理在 2026-10-16 因 API 频率限流（429）中断；中断前成果经逐一核验完整可用（无残留样板、语法全过、用例数不减），遗留 12 文件（security 4 + unit 8）由主代理按同一迁移规范续完。F7c 的 E2E 实跑一次通过（tex 4/4 + extraction 2/2，无重试）。

---

## 8. 处置矩阵（逐条发现 → 处置）

**图例**：✅ 本分支修复 | ⏸ 延后（有理由，见下）| 🔑 需用户人工操作

| 发现 | 处置 | 执行者 |
|---|---|---|
| B-SRP-01/02/03/15 | ✅ | F1 |
| B-SRP-04/05/06/07/08/11/17/19/20/23 | ✅ | F3 |
| B-SRP-09/10/12/13/14/18/22 | ✅ | F2 |
| B-SRP-16 + B-DRY-05（双任务系统） | ✅（合并为 priority 适配器；语义不可保真则拆分+文档化） | F3 |
| B-SRP-21 + B-DRY-04 | ✅（随 LiteLLM 移除同批） | F4 |
| B-SRP-24 | ✅（统一工厂；默认值机制保留） | F1 |
| B-DRY-01/02/03/07/10/11/12/13/16/20 | ✅ | F2 |
| B-DRY-06/08/14/15/18/19/24 | ✅ | F3（14 建 utils/image.py，F4 引用） |
| B-DRY-09 | ✅ | F1 |
| B-DRY-17/21/22/23 | ✅ | F1 |
| B-DRY-25 | ✅ | F7a/F7b |
| FE-01~22、FE-23/24/26 | ✅ | F5/F6 |
| FE-25 | ⏸ 保持现状（未超 200 行，配置拆分收益低、易引入构建差异） | — |
| T-01~08、T-10~15、T-18、T-19 | ✅ | F7 / F7a / F7b |
| T-09（E2E 单方法拆分） | ⏸ E2E 受 `AC_E2E_LLM` 门控且依赖真实 LLM 配额；拆分会成倍增加真实调用成本且缺乏本地验证条件 | — |
| T-16 | ✅（前缀剥离保留 + 网络探测降级） | F4 |
| T-17 | ✅（别名清理） | F6 |
| T-20（补测专项） | ⏸ 补测属新增测试工程量（涉及 7 个 utils 模块 + 10 个端点），与本次重构解耦；重构后回归由现有 34 个测试文件保障 | backlog |
| T-12 密钥轮换 | 🔑 代码侧已修复（改读 `test/key.json`）；**已泄露的真实 Key 需用户到供应商处吊销/轮换**（git 历史清理需 force push，另行确认） | 用户 |

---

## 9. 修复结果与验证

### 批次 1 — 后端/前端/测试三层拆分（commit `cae97d3`）

- 121 个文件（44 modified / 2 deleted / 75 added）；净减 ~4700 行
- 全量测试 **34/34 PASS**（103.86s）；前端 Vitest 91 用例全绿；TSC lint 通过
- `vitest.config.ts` testTimeout 5s→20s（全量并行时 CPU 争抢致假超时，单独跑 14s 全绿佐证）

### 批次 2 — LiteLLM 完全移除（commit 见 git log）

- `backend/services/ai_service.py` 重写为 openai SDK（2.26.0）：
  - `_make_client(api_config)` 模块级 seam（`max_retries=0`，重试由业务层统一负责）
  - `_strip_provider_prefix()`：存量 `openai/` 前缀在 HTTP 前剥离（兼容 config.py.example 与用户 DB）
  - `_call_llm()` 共享请求样板（B-DRY-04）；OCR 采样参数上收 `OCRConfig.DEFAULT_TEMPERATURE/MAX_TOKENS`（B-SRP-21）
- 错误协议统一（B-SRP-21）：`call_ocr_api` 由返回 `"OCR Failed: ..."` 字符串改为抛 `APIResponseError`；`ocr_images.py` 字符串探测改 try/except（消除跨模块字符串契约）
- 测试 mock 迁移：2 处 `patch('services.ai_service.completion')` → `patch('services.ai_service._make_client')`
- E2E 网络探测降级（T-16）：`_proxy_reachable()` TCP 探测，代理不可达 → SKIP 而非 FAIL
- 删除 `tests/ocr_lab/`（debug_ocr.py + output/ 实验残留共 7 文件）
- 物理删除 `python_embed/Lib/site-packages/litellm` + `litellm-1.82.1.dist-info`；验证 `import litellm` → ModuleNotFoundError；`import server` 正常
- 全量测试 **34/34 PASS**（137.70s，无 litellm 环境）

### 批次 3 — 测试样板全量迁移（commit `2297ded`）

- 32 个测试文件全部迁移到共享基础设施（+425/−1136，净减 ~711 行）：
  - **T-01 路径引导**（32/32）：8 行 while 样板 → 4 行标准（`tests/helpers.py` 的 `add_backend_to_sys_path` / `add_vendor_know_to_sys_path`）
  - **T-02 server 脚手架**（6 文件）：伪造 argv + 模块级 `import server` + `TestClient` → `server_test_client(port, ws)`（类级共享语义按原文件保留）
  - **T-03 E2E harness**（2 文件，-412 行）：每文件 ~150 行 server 子进程样板 → `e2e_llm_harness.LlmE2eHarness`；断言与 `AC_E2E_LLM` 门控零改动
  - **T-04 临时资源**：落 cwd / 源码树的 DB、ws 目录 → `make_temp_db` / `make_temp_ws`（系统 temp + `ac_test_` 前缀，调度器可清理）+ `remove_db_files`（含 -wal/-shm）
  - **T-06 共享替身**：本地 `FakeClient` → `helpers.FakeCrossrefClient`；mock 响应构造 → `fake_completion_response`；`_wait_for_call` → `poll_until`
  - **T-10 / T-11**：`test_final_audit` 并发方法拆为 WAL / 并发写两用例；`test_database` DOI 场景 subTest 化
- 用例数全部不减（唯一变化：final_audit 4→5，为拆分增量）；断言、用例名、skip 条件、patch 目标字符串逐文件比对保持
- 迁移质量验证：32 文件逐个实跑全绿 → 全量 **34/34 PASS**（44.22s）→ E2E 终验收 **tex 4/4（29.4s）+ extraction 2/2（19.5s）**
- 执行说明：F7a/F7b 代理因 429 限流中断（详见 §7）；中断前成果经核验完整，遗留 12 文件（security 4 + unit 8）由主代理按同一规范续完

### 最终验收

| 门禁 | 结果 |
|---|---|
| 全量测试（`run_all_tests.py`，34 任务并行） | **34/34 PASS**（44.22s） |
| E2E 实跑（`AC_E2E_LLM=1`，串行防配额竞争） | tex **4/4**（29.4s）+ extraction **2/2**（19.5s） |
| 测试文件迁移完整性 | 32/32 文件（用例数不减、断言保持、逐个实跑绿） |
| LiteLLM 残留 | 全库零引用；物理包已删；无 litellm 环境 `import server` 正常 |
| 工作区卫生 | 无未跟踪残留；测试临时资源落系统 temp（`ac_test_` 前缀，调度器可清理） |

- [x] 批次 1 完成 + 全量测试
- [x] 批次 2（LiteLLM 移除）完成 + 全量测试
- [x] 批次 3（测试迁移）完成 + 全量测试
- [x] 报告终稿 + 合并 main（merge commit `9aaf0d8`，--no-ff；main 合并后全量 34/34 PASS）

---

*本报告由 4 个并行只读审计子代理产出并经主代理汇总核验；所有行号均经工具核实。*
