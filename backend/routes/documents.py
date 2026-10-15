"""/documents 系列 + 上传落盘 + /workspace/sync（B-SRP-01，拆分自 server.py）。
_queue_workflow 在本模块 globals 查找 run_*_workflow（测试 patch 目标即本模块）。"""
import asyncio
import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app_state import state
from constants import FileConfig
from core.priority_queue import priority_task_hub, TaskPriority
from core.task_manager import task_hub
from routes.common import _broadcast_doc_updated, get_doc_or_404, get_doc_with_markdown_or_400, server_error
from services import knowledge_service
from services.config_service import ConfigService
from services.ocr_service import run_full_ocr_workflow
from services.tex_service import run_tex_workflow
from utils.logger import api_logger, task_logger
from utils.security import secure_filename
from utils.websocket import ws_manager

router = APIRouter()
SUPPORTED_EXTS = FileConfig.SUPPORTED_EXTS   # B-DRY-17：单一来源 constants.FileConfig


def _queue_workflow(doc_id, stored_path):
    """按扩展名分流到 OCR 或 tex 工作流（/documents/add、/workspace/sync、/reprocess 共用）"""
    ext = os.path.splitext(stored_path)[1].lower()
    if ext == ".pdf":
        return run_full_ocr_workflow
    if ext in (".tex", ".zip"):
        return run_tex_workflow
    raise ValueError(f"unsupported extension: {ext}")


class MetadataRequest(BaseModel):
    label: str
    prompt: str


@router.get("/documents")
async def list_documents():
    return state.db.get_all_documents()


@router.post("/documents/add")
async def add_document(file: UploadFile = File(...)):
    filename = secure_filename(file.filename)
    dest_path = os.path.join(state.workspace_path, filename)
    counter = 1
    while os.path.exists(dest_path):
        name, ext = os.path.splitext(filename)
        dest_path = os.path.join(state.workspace_path, f"{name}_{counter}{ext}")
        counter += 1

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    ext = os.path.splitext(dest_path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail="Unsupported file type")

    doc_id = state.db.add_document(filename, "uploaded", dest_path)
    await task_hub.add_task(doc_id, _queue_workflow(doc_id, dest_path), dest_path)

    doc = state.db.get_document(doc_id)
    await ws_manager.send_document_update("added", doc_id, doc)

    api_logger.log_api_call("/documents/add", "POST", 201, 0)
    return {"success": True, "doc_id": doc_id}


@router.get("/documents/{doc_id}/pdf")
async def get_document_pdf(doc_id: int):
    doc = state.db.get_document(doc_id)
    if doc and doc.get('stored_path') and os.path.exists(doc['stored_path']):
        if doc['stored_path'].lower().endswith('.pdf'):
            return FileResponse(doc['stored_path'], media_type='application/pdf')
        raise HTTPException(status_code=404, detail="Not a PDF document")
    raise HTTPException(status_code=404)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    doc = state.db.get_document(doc_id)
    if doc:
        if os.path.exists(doc['stored_path']):
            try: os.remove(doc['stored_path'])
            except: pass
        state.db.delete_document(doc_id)
        # Phase 2 知识层联动（R4）：知识库是派生投影，删文档即删知识行；
        # 失败不影响文档删除本身（可删 knowledge/ 全量重建）。
        try:
            await asyncio.to_thread(knowledge_service.forget_paper, doc_id)
        except Exception as e:
            print(f"[Knowledge] forget_paper skipped: {e}")
        await ws_manager.send_document_update("deleted", doc_id)
        return {"success": True}
    return {"success": False}


@router.get("/documents/{doc_id}/metadata")
async def get_document_metadata_list(doc_id: int):
    return state.db.get_document_metadata(doc_id)


@router.post("/documents/{doc_id}/metadata/extract")
async def trigger_custom_extraction(doc_id: int, request: MetadataRequest,
                                    doc: dict = Depends(get_doc_with_markdown_or_400)):
    config_service = ConfigService(state.db)
    extract_api_config = config_service.get_extract_config()
    try:
        from services.ai_service import call_json_extraction_api
        metadata_json = await call_json_extraction_api(doc['ocr_markdown'], extract_api_config, request.prompt)
        state.db.add_document_metadata(doc_id, request.label, metadata_json)
        return {"success": True, "label": request.label}
    except Exception as e:
        raise server_error(e)


@router.post("/documents/{doc_id}/reprocess")
async def reprocess_document(doc_id: int, priority: str = "normal",
                             doc: dict = Depends(get_doc_or_404)):
    priority_map = {
        "critical": TaskPriority.CRITICAL,
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "low": TaskPriority.LOW
    }
    task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)
    try:
        workflow = _queue_workflow(doc_id, doc['stored_path'])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {doc.get('filename')}")

    if priority_task_hub and task_priority.value < TaskPriority.NORMAL.value:
        await priority_task_hub.add_task(doc_id, workflow, doc['stored_path'],
                                         priority=task_priority, force=True)
        task_logger.log_task("queued_priority", doc_id, priority=task_priority.name)
    else:
        await task_hub.add_task(doc_id, workflow, doc['stored_path'], force=True)
        task_logger.log_task("queued", doc_id)

    return {"success": True}


@router.post("/documents/{doc_id}/doi/verify")
async def verify_document_doi(doc_id: int,
                              doc: dict = Depends(get_doc_with_markdown_or_400)):
    try:
        from services.doi_service import verify_document
        result = verify_document(state.db, doc_id)      # 同步纯网络，~秒级
        await _broadcast_doc_updated(doc_id)
        return {"success": True, "result": result}
    except Exception as e:
        raise server_error(e)


@router.get("/documents/{doc_id}/bibtex")
async def get_document_bibtex(doc_id: int, doc: dict = Depends(get_doc_or_404)):
    if doc.get("bibtex"):
        return {"bibtex": doc["bibtex"]}      # DB 缓存优先
    if not doc.get("doi"):
        raise HTTPException(status_code=400, detail="no verified doi")
    try:
        from services.doi_service import fetch_bibtex, DoiServiceError
        bib = fetch_bibtex(doc["doi"], state.db)
        state.db.update_document_doi(doc_id, bibtex=bib)        # 缓存，避免重复请求
        return {"bibtex": bib}
    except DoiServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/workspace/sync")
async def sync_workspace():
    await state.workspace_service.async_scan_and_sync()
    docs = state.db.get_all_documents()
    triggered = 0
    for d in docs:
        metadata = state.db.get_document_metadata(d['id'])
        has_basic = any(m['label'] == 'Basic Insight' for m in metadata)
        has_markdown = bool(d.get('ocr_markdown'))

        if not has_markdown or not has_basic or d['ocr_status'] in ['pending', 'failed']:
            stored_path = d.get('stored_path')
            if stored_path and os.path.exists(stored_path):
                try:
                    workflow = _queue_workflow(d['id'], stored_path)
                except ValueError:
                    continue  # 不支持的后缀跳过
                await task_hub.add_task(d['id'], workflow, stored_path)
                await ws_manager.send_document_update("updated", d['id'])
                triggered += 1

    return {"success": True, "triggered": triggered}
