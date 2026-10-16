"""路由层共享依赖与 helper（B-DRY-21/22/23）。

- doc 校验 Depends：get_doc_or_404 / get_doc_with_markdown_or_400
  （/chat 的软失败因 doc_id 在请求体，仍由端点自行处理）
- server_error：500 包装
- _broadcast_doc_updated：文档 "updated" 广播（3 处共用）
"""
from fastapi import HTTPException

from app_state import state
from utils.websocket import ws_manager


def get_doc_or_404(doc_id: int) -> dict:
    doc = state.db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def get_doc_with_markdown_or_400(doc_id: int) -> dict:
    doc = state.db.get_document(doc_id)
    if not doc or not doc.get("ocr_markdown"):
        raise HTTPException(status_code=400)
    return doc


def server_error(e: Exception) -> HTTPException:
    """统一 500 包装：raise server_error(e)"""
    return HTTPException(status_code=500, detail=str(e))


async def _broadcast_doc_updated(doc_id: int) -> None:
    await ws_manager.send_document_update("updated", doc_id, state.db.get_document(doc_id))
