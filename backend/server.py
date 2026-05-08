import os
import sys
import shutil
import urllib.parse
import uvicorn
import asyncio
import time
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

try:
    from backend.constants import SecurityConfig, ServerConfig, LoggingConfig, MetricsConfig, WebSocketConfig
except ImportError:
    from constants import SecurityConfig, ServerConfig, LoggingConfig, MetricsConfig, WebSocketConfig

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_chat_api
from utils.security import secure_filename
from services.config_service import ConfigService
from services.workspace_service import WorkspaceService
from core.task_manager import task_hub
from utils.logger import core_logger, api_logger, task_logger, db_logger, key_logger, get_logger
from utils.metrics import metrics, MetricsMiddleware
from utils.health import health_checker
from utils.cache import init_cache, get_cache
from utils.websocket import ws_manager, progress_tracker, EventType
from core.priority_queue import priority_task_hub, TaskPriority

class AppState:
    def __init__(self):
        self.workspace_path = ""
        self.db = None
        self.workspace_service = None
        self.use_multi_key = False
        self.ocr_multi_key = False
        self.llm_multi_key = False
        self.task_hub = task_hub
        self.start_time = time.time()

    def initialize(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        self.workspace_path = path
        self.db = Database(os.path.join(path, "library.db"))
        self.workspace_service = WorkspaceService(path, self.db)
        config_service = ConfigService(self.db)
        pool_status = config_service.initialize_key_pools()
        self.ocr_multi_key = pool_status.get("ocr", False)
        self.llm_multi_key = pool_status.get("llm", False)
        self.use_multi_key = self.ocr_multi_key or self.llm_multi_key

        init_cache()

        metrics.set_app_info(
            version="1.0.0",
            workspace=path,
            multi_key_enabled=str(self.use_multi_key)
        )

        core_logger.info(f"Application initialized", workspace=path, multi_key=self.use_multi_key)
        print(f"[Core] Active workspace: {path}")
        print(f"[Core] OCR multi-key: {'enabled' if self.ocr_multi_key else 'disabled'}")
        print(f"[Core] LLM multi-key: {'enabled' if self.llm_multi_key else 'disabled'}")

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    initial_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(BASE_DIR), "workspace_default")
    state.initialize(initial_path)

    await task_hub.start_workers(state)

    core_logger.info("Application startup complete", uptime_start=state.start_time)

    yield

    await task_hub.shutdown()
    core_logger.info("Application shutdown complete")

app = FastAPI(title="Academic Clarity Backend", lifespan=lifespan)

app.middleware("http")(MetricsMiddleware(lambda scope, receive, send: None))

app.add_middleware(
    CORSMiddleware,
    allow_origins=SecurityConfig.ALLOWED_ORIGINS,
    allow_origin_regex=SecurityConfig.ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
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

@app.get("/files/{filename}")
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

class ChatRequest(BaseModel):
    doc_id: int
    query: str

class MetadataRequest(BaseModel):
    label: str
    prompt: str

class PriorityRequest(BaseModel):
    doc_id: int
    priority: str = "normal"

@app.get("/health")
async def health():
    """基础健康检查"""
    return {"status": "ok", "workspace": state.workspace_path}

@app.get("/health/detailed")
async def detailed_health():
    """详细健康检查 - 检查所有组件"""
    result = await health_checker.run_all_checks(state)
    status_code = 200 if result["status"] == "healthy" else 503 if result["status"] == "unhealthy" else 200
    return JSONResponse(content=result, status_code=status_code)

@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus指标端点"""
    return metrics.get_prometheus_metrics()

@app.get("/metrics/summary")
async def metrics_summary():
    """指标摘要"""
    return {
        "uptime_seconds": metrics.get_uptime(),
        "tasks_in_progress": state.task_hub.get_stats().get("active_tasks", 0),
        "tasks_queued": state.task_hub.get_stats().get("queued_tasks", 0),
        "websocket_connections": ws_manager.get_connection_count(),
        "cache_stats": get_cache().cache.get_stats() if hasattr(get_cache(), 'cache') else {}
    }

@app.get("/tasks")
async def list_active_tasks():
    if not state.db: return []
    docs = state.db.get_all_documents()
    return [d for d in docs if d['ocr_status'] in ['pending', 'processing']]

@app.get("/tasks/stats")
async def get_task_stats():
    return {
        "standard": state.task_hub.get_stats(),
        "priority": priority_task_hub.get_stats() if priority_task_hub else {}
    }

@app.get("/tasks/dead-letters")
async def get_dead_letters():
    """获取死信队列"""
    if priority_task_hub:
        return priority_task_hub.queue.get_dead_letters()
    return {}

@app.post("/tasks/dead-letters/{task_id}/retry")
async def retry_dead_letter(task_id: str):
    """重试死信任务"""
    if priority_task_hub:
        task = priority_task_hub.queue.retry_dead_letter(task_id)
        if task:
            await priority_task_hub.queue.enqueue(task)
            return {"success": True, "message": f"Task {task_id} requeued"}
    return {"success": False, "message": "Task not found"}

@app.post("/workspace/sync")
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
                await task_hub.add_task(d['id'], run_full_ocr_workflow, stored_path)
                await ws_manager.send_document_update("updated", d['id'])
                triggered += 1

    return {"success": True, "triggered": triggered}

@app.get("/configs")
async def get_configs():
    return {
        "DEEPSEEK_API_KEY": state.db.get_config("DEEPSEEK_API_KEY", ""),
        "API_BASE": state.db.get_config("API_BASE", "https://api.siliconflow.cn/v1"),
        "WORKSPACE_PATH": state.workspace_path,
        "TABLE_STYLE": state.db.get_config("TABLE_STYLE", "three-line"),
        "USE_MULTI_KEY": state.use_multi_key,
        "OCR_MULTI_KEY": state.ocr_multi_key,
        "LLM_MULTI_KEY": state.llm_multi_key
    }

@app.get("/configs/multi-keys")
async def get_multi_key_stats():
    from core.api_key_manager import key_manager
    stats = key_manager.get_all_stats()

    for service, service_stats in stats.items():
        if "keys" in service_stats:
            for key_stats in service_stats["keys"]:
                key_prefix = key_stats.get("api_key", "")[:8]
                metrics.update_key_stats(
                    service=service,
                    key_prefix=key_prefix,
                    rpm_used=key_stats.get("rpm_used", 0),
                    rpm_limit=key_stats.get("rpm_limit", 60),
                    tpm_used=key_stats.get("tpm_used", 0),
                    tpm_limit=key_stats.get("tpm_limit", 100000),
                    is_healthy=key_stats.get("is_healthy", True)
                )

    return stats

@app.post("/configs/multi-keys/ocr")
async def update_ocr_keys(ocr_keys: str = Query(...)):
    state.db.set_config("OCR_API_KEYS", ocr_keys)
    config_service = ConfigService(state.db)
    pool_status = config_service.initialize_key_pools()
    state.ocr_multi_key = pool_status.get("ocr", False)
    state.use_multi_key = state.ocr_multi_key or state.llm_multi_key
    key_logger.log_key_pool("updated", "ocr")
    return {
        "success": True,
        "ocr_multi_key": state.ocr_multi_key,
        "ocr_pool": key_manager.get_pool("ocr").get_stats() if key_manager.get_pool("ocr") else []
    }

@app.post("/configs/multi-keys/llm")
async def update_llm_keys(llm_keys: str = Query(...)):
    state.db.set_config("LLM_API_KEYS", llm_keys)
    config_service = ConfigService(state.db)
    pool_status = config_service.initialize_key_pools()
    state.llm_multi_key = pool_status.get("llm", False)
    state.use_multi_key = state.ocr_multi_key or state.llm_multi_key
    key_logger.log_key_pool("updated", "llm")
    return {
        "success": True,
        "llm_multi_key": state.llm_multi_key,
        "llm_pool": key_manager.get_pool("llm").get_stats() if key_manager.get_pool("llm") else []
    }

@app.post("/configs")
async def set_config(key: str = Query(...), value: str = Query(...)):
    state.db.set_config(key, value)
    return {"success": True}

@app.get("/documents")
async def list_documents():
    return state.db.get_all_documents()

@app.post("/documents/add")
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

    doc_id = state.db.add_document(filename, "uploaded", dest_path)
    await task_hub.add_task(doc_id, run_full_ocr_workflow, dest_path)

    doc = state.db.get_document(doc_id)
    await ws_manager.send_document_update("added", doc_id, doc)

    api_logger.log_api_call("/documents/add", "POST", 201, 0)
    return {"success": True, "doc_id": doc_id}

@app.get("/documents/{doc_id}/pdf")
async def get_document_pdf(doc_id: int):
    doc = state.db.get_document(doc_id)
    if doc and doc.get('stored_path') and os.path.exists(doc['stored_path']):
        return FileResponse(doc['stored_path'], media_type='application/pdf')
    raise HTTPException(status_code=404)

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    doc = state.db.get_document(doc_id)
    if doc:
        if os.path.exists(doc['stored_path']):
            try: os.remove(doc['stored_path'])
            except: pass
        state.db.delete_document(doc_id)
        await ws_manager.send_document_update("deleted", doc_id)
        return {"success": True}
    return {"success": False}

@app.get("/documents/{doc_id}/metadata")
async def get_document_metadata_list(doc_id: int):
    return state.db.get_document_metadata(doc_id)

@app.post("/documents/{doc_id}/metadata/extract")
async def trigger_custom_extraction(doc_id: int, request: MetadataRequest):
    doc = state.db.get_document(doc_id)
    if not doc or not doc.get('ocr_markdown'):
        raise HTTPException(status_code=400)

    config_service = ConfigService(state.db)
    extract_api_config = config_service.get_extract_config()
    if state.llm_multi_key:
        extract_api_config['_use_multi_key'] = True

    try:
        from services.ai_service import call_json_extraction_api
        metadata_json = await call_json_extraction_api(doc['ocr_markdown'], extract_api_config, request.prompt)
        state.db.add_document_metadata(doc_id, request.label, metadata_json)
        return {"success": True, "label": request.label}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/documents/{doc_id}/reprocess")
async def reprocess_document(doc_id: int, priority: str = "normal"):
    doc = state.db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404)

    priority_map = {
        "critical": TaskPriority.CRITICAL,
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "low": TaskPriority.LOW
    }

    task_priority = priority_map.get(priority.lower(), TaskPriority.NORMAL)

    if priority_task_hub and task_priority.value < TaskPriority.NORMAL.value:
        await priority_task_hub.add_task(doc_id, run_full_ocr_workflow, doc['stored_path'],
                                         priority=task_priority, force=True)
        task_logger.log_task("queued_priority", doc_id, priority=task_priority.name)
    else:
        await task_hub.add_task(doc_id, run_full_ocr_workflow, doc['stored_path'], force=True)
        task_logger.log_task("queued", doc_id)

    return {"success": True}

@app.post("/chat")
async def chat_with_doc(request: ChatRequest):
    doc = state.db.get_document(request.doc_id)
    if not doc or not doc.get('ocr_markdown'):
        return {"response": "OCR results not available."}
    config_service = ConfigService(state.db)
    api_config = config_service.get_chat_config()
    if state.llm_multi_key:
        api_config['_use_multi_key'] = True
    try:
        response = await call_chat_api(request.query, doc['ocr_markdown'], api_config)
        return {"response": response}
    except Exception as e:
        return {"response": f"AI Error: {str(e)}"}

if __name__ == "__main__":
    initial_port = int(sys.argv[1]) if len(sys.argv) > 1 else ServerConfig.DEFAULT_PORT
    for port in range(initial_port, initial_port + ServerConfig.MAX_PORT_RANGE):
        try:
            print(f"[Core] Starting server on port {port}...")
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            uvicorn.run(app, host="127.0.0.1", port=port)
            break
        except OSError:
            continue
