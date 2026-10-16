"""/tasks 系列（B-SRP-01，拆分自 server.py）。"""
from fastapi import APIRouter, Depends

from app_state import state
from core.priority_queue import priority_task_hub
from routes.common import _broadcast_doc_updated, get_doc_or_404
from utils.websocket import progress_tracker

router = APIRouter()


@router.get("/tasks")
async def list_active_tasks():
    if not state.db: return []
    docs = state.db.get_all_documents()
    active = [d for d in docs if d['ocr_status'] in ['pending', 'processing']]
    # 合并流水线阶段快照（UX-26）：stage / progress / elapsed
    for d in active:
        stage = progress_tracker.get_stage(d['id'])
        if stage:
            d['stage'] = stage['stage']
            d['progress'] = stage['progress']
            d['elapsed'] = stage['elapsed']
    return active


@router.post("/tasks/{doc_id}/cancel")
async def cancel_active_task(doc_id: int, doc: dict = Depends(get_doc_or_404)):
    """取消排队中/运行中的文档任务（UX-26）。状态回落为 failed，可重新处理。"""
    hit = await state.task_hub.cancel_task(doc_id)
    if priority_task_hub:
        try:
            hit = (await priority_task_hub.cancel_by_doc_id(doc_id)) or hit
        except Exception as e:
            print(f"[TaskHub] priority cancel skipped: {e}")

    if hit or doc['ocr_status'] in ['pending', 'processing']:
        state.db.update_document_ocr(doc_id, "failed")
        try:
            await progress_tracker.track_task_failure(doc_id, "已取消")
        except Exception:
            pass
        await _broadcast_doc_updated(doc_id)
        return {"success": True, "doc_id": doc_id}

    return {"success": False, "doc_id": doc_id, "message": "任务已结束，无需取消"}


@router.get("/tasks/stats")
async def get_task_stats():
    return {
        "standard": state.task_hub.get_stats(),
        "priority": priority_task_hub.get_stats() if priority_task_hub else {}
    }


@router.get("/tasks/dead-letters")
async def get_dead_letters():
    """获取死信队列"""
    if priority_task_hub:
        return priority_task_hub.queue.get_dead_letters()
    return {}


@router.post("/tasks/dead-letters/{task_id}/retry")
async def retry_dead_letter(task_id: str):
    """重试死信任务"""
    if priority_task_hub:
        task = priority_task_hub.queue.retry_dead_letter(task_id)
        if task:
            await priority_task_hub.queue.enqueue(task)
            return {"success": True, "message": f"Task {task_id} requeued"}
    return {"success": False, "message": "Task not found"}
