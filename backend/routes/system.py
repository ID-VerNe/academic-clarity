"""/health、/metrics、/configs、/ws、/files（B-SRP-01 / B-SRP-15，拆分自 server.py）。

/configs 读写统一走 ConfigService（get_ui_config / set_config 白名单）。
"""
import os
import urllib.parse

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from app_state import state
from services.config_service import ConfigService
from utils.cache import get_cache
from utils.health import health_checker
from utils.logger import api_logger
from utils.metrics import metrics
from utils.websocket import EventType, ws_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket端点 - 支持实时任务进度推送"""
    await websocket.accept()
    client_id = websocket.client

    try:
        await ws_manager.connect(websocket)
        api_logger.info(f"WebSocket client connected", client=str(client_id))

        while True:
            try:
                data = await websocket.receive_text()
                message = ws_manager.WSMessage.from_json(data)

                if message.event == EventType.HEARTBEAT:
                    await ws_manager.send(websocket, EventType.HEARTBEAT, {"pong": True})

            except WebSocketDisconnect:
                break
            except Exception as e:
                api_logger.error(f"WebSocket error", error=str(e), client=str(client_id))
                break

    finally:
        await ws_manager.disconnect(websocket)
        api_logger.info(f"WebSocket client disconnected", client=str(client_id))


@router.get("/files/{filename}")
async def serve_file(filename: str):
    api_logger.debug(f"Serving file", filename=filename)
    decoded_filename = urllib.parse.unquote(filename)

    if '..' in decoded_filename or decoded_filename.startswith('/') or decoded_filename.startswith('\\'):
        raise HTTPException(status_code=400, detail="Invalid filename: path traversal detected")

    if os.path.splitdrive(decoded_filename)[0]:
        raise HTTPException(status_code=400, detail="Invalid filename: drive letters not allowed")

    normalized_workspace = os.path.normpath(state.workspace_path)
    normalized_file_path = os.path.normpath(os.path.join(normalized_workspace, decoded_filename))

    common = os.path.commonpath([normalized_workspace, normalized_file_path])
    if common != normalized_workspace:
        raise HTTPException(status_code=403, detail="Access denied: file outside workspace")

    if not os.path.exists(normalized_file_path) or not os.path.isfile(normalized_file_path):
        raise HTTPException(status_code=404, detail="File not found")

    if os.path.getsize(normalized_file_path) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    return FileResponse(
        normalized_file_path,
        media_type='application/pdf',
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )


@router.get("/health")
async def health():
    """基础健康检查"""
    return {"status": "ok", "workspace": state.workspace_path}


@router.get("/health/detailed")
async def detailed_health():
    """详细健康检查 - 检查所有组件"""
    result = await health_checker.run_all_checks(state)
    status_code = 200 if result["status"] == "healthy" else 503 if result["status"] == "unhealthy" else 200
    return JSONResponse(content=result, status_code=status_code)


@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus指标端点"""
    return metrics.get_prometheus_metrics()


@router.get("/metrics/summary")
async def metrics_summary():
    """指标摘要"""
    return {
        "uptime_seconds": metrics.get_uptime(),
        "tasks_in_progress": state.task_hub.get_stats().get("active_tasks", 0),
        "tasks_queued": state.task_hub.get_stats().get("queued_tasks", 0),
        "websocket_connections": ws_manager.get_connection_count(),
        "cache_stats": get_cache().cache.get_stats() if hasattr(get_cache(), 'cache') else {}
    }


@router.get("/configs")
async def get_configs():
    # 返回「生效值」（DB → config.py 默认值），供 UI 判断配置完整性（UX-32）
    return ConfigService(state.db).get_ui_config(state.workspace_path)


@router.post("/configs")
async def set_config(key: str = Query(...), value: str = Query(...)):
    if not ConfigService(state.db).set_config(key, value):
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")
    return {"success": True}
