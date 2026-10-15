"""/chat 与 /knowledge 知识层（B-SRP-01，拆分自 server.py）。

call_chat_api 必须在本模块模块级 import（测试 patch 目标即本模块）。
"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app_state import state
from routes.common import _broadcast_doc_updated, get_doc_or_404, server_error
from services import knowledge_service
from services.ai_service import call_chat_api
from services.config_service import ConfigService

router = APIRouter()


class ChatRequest(BaseModel):
    doc_id: int
    query: str
    quotes: list[str] | None = None   # Phase 2 引用模式：只喂逐字引文


@router.post("/chat")
async def chat_with_doc(request: ChatRequest):
    # doc_id 来自请求体而非路径，无法走 Depends；软失败语义保持（非 400）
    doc = state.db.get_document(request.doc_id)
    if not doc or not doc.get('ocr_markdown'):
        return {"response": "OCR results not available."}
    config_service = ConfigService(state.db)
    api_config = config_service.get_chat_config()
    # Phase 2 引用模式：只喂逐字引文（LLM 不许外溢，cite:// 编号可回查）；
    # 无 quotes → 现有全量 ocr_markdown。
    if request.quotes:
        context = "\n".join(f"[cite://{i + 1}] {q}"
                            for i, q in enumerate(request.quotes))
    else:
        context = doc['ocr_markdown']
    try:
        response = await call_chat_api(request.query, context, api_config)
        return {"response": response}
    except Exception as e:
        return {"response": f"AI Error: {str(e)}"}


# ---------- Phase 2：know 知识层 ----------

@router.post("/knowledge/ingest/{doc_id}")
async def ingest_knowledge(doc_id: int, doc: dict = Depends(get_doc_or_404)):
    if not doc.get('ocr_markdown'):
        raise HTTPException(status_code=400, detail="no ocr markdown")
    try:
        # 同步 CPU 活进线程池（照 workspace_service 先例）
        result = await asyncio.to_thread(
            knowledge_service.ingest_document, doc_id, state.db)
        await _broadcast_doc_updated(doc_id)
        return {"success": True, "result": result}
    except Exception as e:
        raise server_error(e)


@router.get("/knowledge/search")
async def search_knowledge(q: str, limit: int = 10):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="empty query")
    if len(q) > 200:                     # 超长查询防御（FTS/LIKE 均不 OOM）
        raise HTTPException(status_code=400, detail="query too long")
    rows = await asyncio.to_thread(knowledge_service.search, q.strip(),
                                   min(max(limit, 1), 100))
    return {"results": rows}


@router.get("/knowledge/papers")
async def list_knowledge_papers():
    rows = await asyncio.to_thread(knowledge_service.list_papers)
    return {"papers": rows}


@router.get("/knowledge/papers/{paper_id}/claims")
async def get_knowledge_paper_claims(paper_id: str):
    return {"claims": knowledge_service.get_paper_claims(paper_id)}
