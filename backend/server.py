import os
import sys
import shutil
import urllib.parse
import uvicorn
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

try:
    from backend.constants import SecurityConfig, ServerConfig
except ImportError:
    from constants import SecurityConfig, ServerConfig

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_chat_api
from utils.security import secure_filename
from services.config_service import ConfigService
from services.workspace_service import WorkspaceService
from core.task_manager import task_hub

class AppState:
    def __init__(self):
        self.workspace_path = ""
        self.db = None
        self.workspace_service = None
        self.use_multi_key = False
        self.ocr_multi_key = False
        self.llm_multi_key = False

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
        print(f"[Core] Active workspace: {path}")
        print(f"[Core] OCR multi-key: {'enabled' if self.ocr_multi_key else 'disabled'}")
        print(f"[Core] LLM multi-key: {'enabled' if self.llm_multi_key else 'disabled'}")

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    initial_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(BASE_DIR), "workspace_default")
    state.initialize(initial_path)

    await task_hub.start_workers(state)

    yield

app = FastAPI(title="Academic Clarity Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=SecurityConfig.ALLOWED_ORIGINS,
    allow_origin_regex=SecurityConfig.ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/files/{filename}")
async def serve_file(filename: str):
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

@app.get("/health")
async def health():
    return {"status": "ok", "workspace": state.workspace_path}

@app.get("/tasks")
async def list_active_tasks():
    if not state.db: return []
    docs = state.db.get_all_documents()
    return [d for d in docs if d['ocr_status'] in ['pending', 'processing']]

@app.get("/tasks/stats")
async def get_task_stats():
    return task_hub.get_stats()

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
    return key_manager.get_all_stats()

@app.post("/configs/multi-keys/ocr")
async def update_ocr_keys(ocr_keys: str = Query(...)):
    state.db.set_config("OCR_API_KEYS", ocr_keys)
    config_service = ConfigService(state.db)
    pool_status = config_service.initialize_key_pools()
    state.ocr_multi_key = pool_status.get("ocr", False)
    state.use_multi_key = state.ocr_multi_key or state.llm_multi_key
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
async def reprocess_document(doc_id: int):
    doc = state.db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404)
    await task_hub.add_task(doc_id, run_full_ocr_workflow, doc['stored_path'], force=True)
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
