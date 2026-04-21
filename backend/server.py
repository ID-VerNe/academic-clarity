import os
import sys
import shutil
import uvicorn
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

# --- Path Configuration ---
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

    def initialize(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        self.workspace_path = path
        self.db = Database(os.path.join(path, "library.db"))
        self.workspace_service = WorkspaceService(path, self.db)
        print(f"[Core] Active workspace: {path}")

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 初始化物理路径
    initial_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(BASE_DIR), "workspace_default")
    state.initialize(initial_path)
    
    # 2. 启动 10 并发任务中枢
    await task_hub.start_workers(state)
    
    yield

app = FastAPI(title="Academic Clarity Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/files/{filename}")
async def serve_file(filename: str):
    file_path = os.path.join(state.workspace_path, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404)

# --- Schemas ---
class ChatRequest(BaseModel):
    doc_id: int
    query: str

class MetadataRequest(BaseModel):
    label: str
    prompt: str

# --- API Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok", "workspace": state.workspace_path}

@app.get("/tasks")
async def list_active_tasks():
    if not state.db: return []
    docs = state.db.get_all_documents()
    return [d for d in docs if d['ocr_status'] in ['pending', 'processing']]

@app.post("/workspace/sync")
async def sync_workspace():
    """
    全自动同步：扫描并推入 10 并发任务池
    """
    state.workspace_service.scan_and_sync()
    docs = state.db.get_all_documents()
    
    triggered = 0
    for d in docs:
        metadata = state.db.get_document_metadata(d['id'])
        has_basic = any(m['label'] == 'Basic Insight' for m in metadata)
        has_markdown = bool(d.get('ocr_markdown'))

        if not has_markdown or not has_basic or d['ocr_status'] in ['pending', 'failed']:
            stored_path = d.get('stored_path')
            if stored_path and os.path.exists(stored_path):
                # 推入 10 并发 Task Hub
                await task_hub.add_task(d['id'], run_full_ocr_workflow, stored_path)
                triggered += 1
    
    return {"success": True, "triggered": triggered}

@app.get("/configs")
async def get_configs():
    return {
        "DEEPSEEK_API_KEY": state.db.get_config("DEEPSEEK_API_KEY", ""),
        "API_BASE": state.db.get_config("API_BASE", "https://api.siliconflow.cn/v1"),
        "WORKSPACE_PATH": state.workspace_path,
        "TABLE_STYLE": state.db.get_config("TABLE_STYLE", "three-line")
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
    # 推入并行任务池
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
    # 强制重试
    await task_hub.add_task(doc_id, run_full_ocr_workflow, doc['stored_path'])
    return {"success": True}

@app.post("/chat")
async def chat_with_doc(request: ChatRequest):
    doc = state.db.get_document(request.doc_id)
    if not doc or not doc.get('ocr_markdown'):
        return {"response": "OCR results not available."}
    config_service = ConfigService(state.db)
    api_config = config_service.get_chat_config()
    try:
        response = await call_chat_api(request.query, doc['ocr_markdown'], api_config)
        return {"response": response}
    except Exception as e:
        return {"response": f"AI Error: {str(e)}"}

if __name__ == "__main__":
    initial_port = int(sys.argv[1]) if len(sys.argv) > 1 else 38392
    for port in range(initial_port, initial_port + 5):
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
