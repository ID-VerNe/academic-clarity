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
        print(f"[Core] Active workspace set to: {path}")

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    initial_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(BASE_DIR), "workspace_default")
    state.initialize(initial_path)
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
    # 任务队列显示：正在处理的，或者虽然标为 completed 但还没出 Markdown 结果的异常件
    return [d for d in docs if d['ocr_status'] in ['pending', 'processing']]

@app.post("/workspace/sync")
async def sync_workspace(background_tasks: BackgroundTasks):
    """
    全自动同步引擎：
    1. 扫描物理新文件入库。
    2. 发现所有“不完整”的文档（缺 Markdown 或 缺 Basic Insight）。
    3. 强制推入后台队列自动补全。
    """
    # 物理同步
    state.workspace_service.scan_and_sync()
    
    docs = state.db.get_all_documents()
    triggered_count = 0
    
    for d in docs:
        doc_id = d['id']
        filename = d['filename']
        stored_path = d.get('stored_path')
        
        if not stored_path or not os.path.exists(stored_path):
            continue

        # 检查是否需要处理
        metadata = state.db.get_document_metadata(doc_id)
        has_basic_insight = any(m['label'] == 'Basic Insight' for m in metadata)
        has_markdown = bool(d.get('ocr_markdown'))
        
        # 补全逻辑：只要没有 Markdown，或者有了 Markdown 但还没提取基础洞察，就跑全流程
        if not has_markdown or not has_basic_insight or d['ocr_status'] in ['pending', 'failed']:
            background_tasks.add_task(run_full_ocr_workflow, doc_id, stored_path, state.db)
            triggered_count += 1
            print(f"[Auto-Pilot] Enqueued recovery/new task for: {filename}")
    
    return {"success": True, "total_scanned": len(docs), "auto_triggered": triggered_count}

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
async def add_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
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
    background_tasks.add_task(run_full_ocr_workflow, doc_id, dest_path, state.db)
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
        raise HTTPException(status_code=400, detail="OCR not completed")
    
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
async def reprocess_document(doc_id: int, background_tasks: BackgroundTasks):
    doc = state.db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404)
    background_tasks.add_task(run_full_ocr_workflow, doc_id, doc['stored_path'], state.db)
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
    initial_port = int(sys.argv[1]) if len(sys.argv) > 1 else 38391
    # 尝试 5 个连续端口，处理 EACCES 冲突
    for port in range(initial_port, initial_port + 5):
        try:
            print(f"[Core] Starting production server on port {port}...")
            # uvicorn.run 在某些环境下可能在 bind 失败时直接退出，
            # 我们通过 socket 预检来确保端口可用
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', port))
            sock.close()
            
            uvicorn.run(app, host="127.0.0.1", port=port)
            break
        except OSError:
            print(f"[Warn] Port {port} unavailable, skipping...")
            continue
