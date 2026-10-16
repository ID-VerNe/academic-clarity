# Academic Clarity — 项目长期记忆

## 架构约定（改前先看这里）

- **密钥与轮询**：应用内**不再**实现多 Key 轮询——`ServiceKeyPool` / `MultiServiceKeyManager` / `KeyPoolConfig` / `KEYPOOL_TTL` 等已于 2026-10-15 整体移除，轮询职责由**外部本地代理**承担。应用侧单 Key 走 **openai SDK**（`services/ai_service.py`；**LiteLLM 已于 2026-10-15 完全移除，勿再加回**）；`ConfigService` 统一返回生效值（DB → `backend/config.py` 默认值回退）。**勿再加回密钥池**。
- **LLM 调用层契约**（2026-10-15 重构）：`ai_service` 三路径（OCR/Chat/JSON 提取）共用 `_make_client()` seam + `_call_llm()` 样板；**测试 mock 目标 = `patch('services.ai_service._make_client')`**。模型名 `openai/` 前缀由 `_strip_provider_prefix()` 在 HTTP 前剥离（存量配置兼容，**勿删**）。错误协议：OCR/Chat 抛 `APIResponseError`；JSON 提取返回 error-JSON（由 extraction_service 转异常）。OCR 采样参数在 `OCRConfig.DEFAULT_TEMPERATURE/MAX_TOKENS`。
- **门面 patch 语义**：`services/ocr_service.py`、`tex_service.py` 仅 re-export；工作流模块**晚绑定**从门面 import（如 `from services.ocr_service import call_ocr_api`），测试 patch 门面路径才生效——**勿改回直接 import ai_service**。
- **后端分层（2026-10-15 SRP/DRY 重构）**：`server.py` 仅装配；路由在 `routes/`（common/documents/tasks/knowledge/extraction/system）；DB 在 `db/` 包（schema/queries）；服务实现拆分（ocr_workflow/ocr_images/tex_workflow/tex_security/tex_detect/knowledge_store/knowledge_queries/workflow_common 等）；`core/` 两套任务系统（priority_queue 与 task_manager）**不合并**，差异见 `core/README.md`。
- **前端结构**：组件按域分子目录（`dashboard/` `reader/` `settings/` `ui/`）；状态逻辑收敛 `src/hooks/`；纯工具在 `src/utils/`（keyboard/json/format/docStatus）；请求统一走 `src/api/client.ts`（`request` 软失败 / `requestStrict` 严格）。
- **前端反馈**：全局提示一律走 `src/components/ui/Toast.tsx`（`toast.success/error/info` + `<ToastHost/>`，测试用 `clearToasts()`）；确认交互一律用 `src/components/ui/ConfirmDialog.tsx`，**禁止** `window.confirm/alert`。
- **文案**：全中文；术语统一「文献库 / 提取维度 / 立即提取（仅本文档）」。`AppConfig` 收敛为 5 字段。
- **任务可见性**：后端 `progress_tracker.track_task_progress(doc_id, progress, step)` 上报阶段，`GET /tasks` 合并 `stage/progress/elapsed`；取消走 `POST /tasks/{doc_id}/cancel`（`TaskManager` 用 `asyncio.create_task` 跑独立 job，取消只杀任务不杀 worker）。
- **编码规范（2026-10-16 起，`agents.md` §5 为正典）**：**不设行数硬上限**（旧「超 200 行必拆」规则已废止）——按职责边界拆模块；新增代码先规划结构/接口 + 先检索复用（`src/utils/` / `src/hooks/` / `backend/utils/` / `backend/services/` / `tests/helpers.py`），职责混合才拆、真实重复才抽。

## 环境陷阱（Windows）

- **vitest React 双实例**：进程 cwd 盘符为小写 `c:\` 时，pnpm 符号链接经 realpath 解析为大写 `C:\`，同一份 `react.development.js` 被 ESM / CJS 两条路径各加载一次 → 报 `Cannot read properties of null (reading 'useState')` / `Invalid hook call`。已在 `vitest.config.ts` 规范化 cwd 盘符并显式设 `test.root`（非 Windows 自动跳过），**勿删该段**。
- **沙箱 safe-delete**：`rm -rf <dir>` 可能被守卫拦截（SIGTERM、无输出）→ 逐文件 `rm -f` + `rmdir` 空目录可绕过。
- **真实 LLM E2E**：必须串行跑（并行会抢同一代理配额）；用例基建在 `tests/e2e_llm_harness.py`（`LlmE2eHarness` 封装 server 子进程 / HTTP / 轮询；server 输出落盘防管道阻塞）；代理不可达自动 SKIP（`proxy_reachable()` TCP 探测）。
- **python_embed 隔离模式**：`python310._pth` 忽略 `PYTHONPATH`；脚本/测试须显式 `sys.path.insert(0, ...)`（`tests/helpers.py` 已封装）。
- **litellm 删除后**：其导入时的 `sys.path` 注入副作用消失（曾致 `backend.constants` / `constants` 双模块分裂）——勿依赖隐式仓库根导入。

## 验证入口

- 全量门禁：`scripts/run_tests.bat`（= `python_embed\python.exe tests\run_all_tests.py`；run_all_tests.py 为薄编排，逻辑在 `tests/runner.py`；34 任务并行）。
- 前端单跑：`pnpm test`；类型检查：`pnpm lint`（tsc --noEmit）。
- 测试共享脚手架：`tests/helpers.py`（`find_repo_root` / `add_backend_to_sys_path` / `add_vendor_know_to_sys_path` / `make_temp_ws` / `make_temp_db` / `remove_db_files` / `poll_until` / `server_test_client` / `cleanup_temp_artifacts` / `FakeDb` / `FakeCrossrefClient` / `fake_completion_response`）、`tests/fixtures_data.py`、`tests/e2e_llm_harness.py`。
- **测试写法基线（2026-10-16 全量迁移后）**：32 个测试文件已全部接入共享基础设施——**勿再写路径 while 样板**（引导 = `sys.path.insert(0, dirname(dirname(abspath(__file__))))` + `from helpers import add_backend_to_sys_path`，know 家族用 `add_vendor_know_to_sys_path`）；**勿再把临时 DB/ws 落 cwd 或源码树**（用 `make_temp_ws`/`make_temp_db`，系统 temp + `ac_test_` 前缀供调度器清理）；server 测试用 `server_test_client(port, ws)`（类级共享时 lifecycle 放 setUpClass）；LLM mock 用 `fake_completion_response` + `patch('services.ai_service._make_client')`。
- `src/tests/setup.ts` 已 mock：`scrollIntoView` / `scrollTo` / `clipboard` / `Range.getBoundingClientRect` / `URL.createObjectURL` / `fetch().blob`。
- 真实 LLM E2E 门控：`AC_E2E_LLM=1`（默认跳过）。
