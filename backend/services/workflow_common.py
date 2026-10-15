"""workflow_common — 流水线编排通用原语（B-DRY-02/03）。

ocr / tex 工作流共用的进度上报样板与失败收尾：全部 safe_* 内部
吞掉上报异常（绝不影响主流程）；fail_workflow 保持「落库 failed →
安全上报 → 向上抛出」语义（交由 task_hub 重试）。
"""
from utils.websocket import progress_tracker


async def safe_stage(doc_id, progress, step):
    """流水线阶段上报（UX-26）。上报失败绝不影响主流程。"""
    try:
        await progress_tracker.track_task_progress(doc_id, progress, step)
    except Exception:
        pass


async def safe_start(doc_id, task_type="ocr"):
    """任务开始上报；失败绝不影响主流程。"""
    try:
        await progress_tracker.track_task_start(doc_id, task_type)
    except Exception:
        pass


async def safe_complete(doc_id):
    """任务完成上报；失败绝不影响主流程。"""
    try:
        await progress_tracker.track_task_complete(doc_id)
    except Exception:
        pass


async def safe_failure(doc_id, error):
    """任务失败上报；失败绝不影响主流程。"""
    try:
        await progress_tracker.track_task_failure(doc_id, error)
    except Exception:
        pass


async def fail_workflow(doc_id, db, exc, log_prefix="Workflow"):
    """流水线失败收尾：日志 → 落库 failed → 安全上报 → 原异常向上抛出。"""
    print(f"[{log_prefix}] CRITICAL ERROR: {exc}")
    db.update_document_ocr(doc_id, "failed")
    await safe_failure(doc_id, str(exc))
    raise exc
