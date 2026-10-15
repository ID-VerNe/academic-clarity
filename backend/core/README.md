# core 任务系统语义边界

`core/` 下并存两套任务执行系统，职责不同，**当前不做合并**（B-SRP-16 / B-DRY-05 处置结论）。

## 1. task_hub（task_manager.py + task_retry.py）

- 结构：单一 `asyncio.Queue` + worker 池，FIFO，无优先级。
- 去重：`active_task_ids`（同一 doc 在队/在跑则跳过入队）。
- 重试：失败后非阻塞调度（独立 `asyncio.Task` 睡退避表 `TaskConfig.RETRY_BACKOFF`），
  失败次数按 doc 记入 `failed_task_ids`，达到 `MAX_RETRIES` 后拒绝重新入队（`force=True` 强制）。
- 取消（UX-26）：`cancel_task(doc_id)` —— 运行中取消任务的 asyncio.Task，排队中打
  `cancelled_task_ids` 标记由 worker 丢弃；状态回落到 failed。
- 消费方：`/documents/add`、`/workspace/sync`、`/reprocess`（普通优先级）、
  `/tasks/{id}/cancel`、`/tasks/stats`。

## 2. priority_task_hub（priority_queue.py + priority_manager.py + priority_models.py + dead_letter_store.py）

- 结构：`heapq` 优先队列（`TaskPriority`），支持延迟执行（`scheduled_at`）。
- 去重：按 doc 只保留高优先级任务（低优先级入队会替换已有低优任务）。
- 重试：`requeue_with_delay` 按 `QueuedTask.get_retry_delay()`（同一退避表）重入堆；
  重试耗尽进死信（`DeadLetterStore`，`threading.Lock`），可经 `/tasks/dead-letters/{id}/retry` 重投。
- 取消：`cancel_by_doc_id(doc_id)` 仅覆盖排队任务。
- 消费方：`/reprocess`（critical/high）、`/extraction/batch`（BACKGROUND）。

## 为什么暂不合并

合并为一个系统需要同时保真以下语义，且缺少测试覆盖（`/tasks/cancel`、`/tasks/stats` 无自动化测试）：

1. 重试语义不同：task_hub 的失败计数按 doc 累计并**阻止**重新入队（force 例外）；
   priority hub 的重试计数挂在任务对象上，耗尽后进**死信**且可手动重投。
2. 去重语义不同：task_hub 按"在队/在跑"跳过；priority hub 按优先级替换。
3. 取消语义不同：task_hub 可取消运行中任务（需要 `_running` 的 asyncio.Task 句柄）；
   priority hub 只取消排队任务。
4. 失败可见性不同：task_hub 暴露 `failed_task_details`（供 `/tasks/stats` 与
   `/health/detailed` 消费）；priority hub 暴露死信明细。

合并的前提：先把上述 4 条语义写成可执行测试（含 `/tasks/cancel`、`/tasks/stats`），
再以 priority hub 为底座实现 task_hub 适配器，逐条对照测试迁移。
