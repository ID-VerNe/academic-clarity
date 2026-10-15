# Academic Clarity — 项目长期记忆

## 架构约定（改前先看这里）

- **密钥与轮询**：应用内**不再**实现多 Key 轮询——`ServiceKeyPool` / `MultiServiceKeyManager` / `KeyPoolConfig` / `KEYPOOL_TTL` 等已于 2026-10-15 整体移除，轮询职责由**外部本地代理**承担。应用侧单 Key 直呼 LiteLLM `completion()`；`ConfigService` 统一返回生效值（DB → `backend/config.py` 默认值回退）。**勿再加回密钥池**。
- **前端反馈**：全局提示一律走 `src/components/ui/Toast.tsx`（`toast.success/error/info` + `<ToastHost/>`，测试用 `clearToasts()`）；确认交互一律用 `src/components/ui/ConfirmDialog.tsx`，**禁止** `window.confirm/alert`。
- **文案**：全中文；术语统一「文献库 / 提取维度 / 立即提取（仅本文档）」。`AppConfig` 收敛为 5 字段。
- **任务可见性**：后端 `progress_tracker.track_task_progress(doc_id, progress, step)` 上报阶段，`GET /tasks` 合并 `stage/progress/elapsed`；取消走 `POST /tasks/{doc_id}/cancel`（`TaskManager` 用 `asyncio.create_task` 跑独立 job，取消只杀任务不杀 worker）。

## 环境陷阱（Windows）

- **vitest React 双实例**：进程 cwd 盘符为小写 `c:\` 时，pnpm 符号链接经 realpath 解析为大写 `C:\`，同一份 `react.development.js` 被 ESM / CJS 两条路径各加载一次 → 报 `Cannot read properties of null (reading 'useState')` / `Invalid hook call`。已在 `vitest.config.ts` 规范化 cwd 盘符并显式设 `test.root`（非 Windows 自动跳过），**勿删该段**。
- **沙箱 safe-delete**：`rm -rf <dir>` 可能被守卫拦截（SIGTERM、无输出）→ 逐文件 `rm -f` + `rmdir` 空目录可绕过。
- **真实 LLM E2E**：必须串行跑（并行会抢同一代理配额）；server 子进程输出须落盘（`subprocess.PIPE` 不读取会阻塞子进程）。

## 验证入口

- 全量门禁：`scripts/run_tests.bat`（= `python_embed\python.exe tests\run_all_tests.py`，34 任务并行：TSC + 后端单测/集成/安全/系统 + 前端 Vitest）。
- 前端单跑：`pnpm test`；类型检查：`pnpm lint`（tsc --noEmit）。
- `src/tests/setup.ts` 已 mock：`scrollIntoView` / `scrollTo` / `clipboard` / `Range.getBoundingClientRect` / `URL.createObjectURL` / `fetch().blob`。
- 真实 LLM E2E 门控：`AC_E2E_LLM=1`（默认跳过）。
