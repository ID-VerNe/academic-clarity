"""Phase 3：提取维度、批量提取与结果导出（B-SRP-01，拆分自 server.py）。"""
import asyncio
import urllib.parse

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app_state import state
from core.priority_queue import priority_task_hub, TaskPriority
from services import extraction_export, extraction_service

router = APIRouter()


class DimensionRequest(BaseModel):
    id: str = ""
    label: str
    prompt: str
    system_prompt: str = ""
    enabled: bool = True


class BatchExtractRequest(BaseModel):
    dimension_id: str
    doc_ids: list[int] = []      # 空 = 全部候选文档
    force: bool = False


@router.get("/extraction/dimensions")
async def list_extraction_dimensions():
    return {"dimensions": extraction_service.list_dimensions(state.db)}


@router.post("/extraction/dimensions")
async def save_extraction_dimension(req: DimensionRequest):
    try:
        dim = extraction_service.save_dimension(state.db, req.model_dump())
    except extraction_service.DimensionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True, "dimension": dim}


@router.delete("/extraction/dimensions/{dimension_id}")
async def delete_extraction_dimension(dimension_id: str):
    if not extraction_service.delete_dimension(state.db, dimension_id):
        raise HTTPException(status_code=404)
    return {"success": True}


@router.post("/extraction/batch")
async def run_batch_extraction(req: BatchExtractRequest):
    dim = extraction_service.get_dimension(state.db, req.dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="dimension not found")
    if not dim["enabled"]:
        # fail-fast：worker 也会拒绝停用维度，但入队后重试耗尽才失败，
        # 用户看到「已入队」却无结果——直接在端点拒绝（与 worker 检查一致）
        raise HTTPException(status_code=400, detail="dimension disabled")
    to_run, skipped = await asyncio.to_thread(
        extraction_service.select_batch_candidates, state.db,
        req.dimension_id, req.doc_ids or None, req.force)
    if req.force:                       # 先清旧行再入队（litrev --reset 等价物）
        for doc_id in to_run:
            state.db.delete_metadata_by_dimension(doc_id, req.dimension_id)
    queued = 0
    for doc_id in to_run:               # BACKGROUND：不与交互式 reprocess 争抢
        ok = await priority_task_hub.add_task(
            doc_id, extraction_service.run_dimension_extraction, req.dimension_id,
            priority=TaskPriority.BACKGROUND, force=req.force)
        if ok is not None:
            queued += 1
    return {"success": True, "queued": queued, "skipped": len(skipped)}


@router.get("/documents/export")
async def export_dimension_results(dimension_id: str, format: str = "csv"):
    dim = extraction_service.get_dimension(state.db, dimension_id)
    if not dim:
        raise HTTPException(status_code=404, detail="dimension not found")
    if format not in ("csv", "md"):
        raise HTTPException(status_code=400, detail="format must be csv or md")
    rows = await asyncio.to_thread(extraction_service.collect_export_rows,
                                   state.db, dimension_id)
    if format == "csv":
        text = extraction_export.build_csv(dim, rows)
        media = "text/csv; charset=utf-8"
    else:
        text = extraction_export.build_markdown(dim, rows)
        media = "text/markdown; charset=utf-8"
    fname = extraction_export.safe_filename(dim["label"], format)
    return Response(content=text, media_type=media, headers={
        "Content-Disposition":
            f"attachment; filename={fname}; "
            f"filename*=UTF-8''{urllib.parse.quote(fname)}"})
