import os
import sys
import shutil
import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- Path Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

# --- Modular Imports ---
from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_chat_api
from utils.security import secure_filename
from services.config_service import ConfigService
from services.workspace_service import WorkspaceService

# --- Workspace & DB Initialization ---
WORKSPACE_PATH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(BASE_DIR), "workspace_default")
if not os.path.exists(WORKSPACE_PATH):
    os.makedirs(WORKSPACE_PATH)

DB_PATH = os.path.join(WORKSPACE_PATH, "library.db")
db = Database(DB_PATH)

# --- Auto Sync on Startup ---
workspace_service = WorkspaceService(WORKSPACE_PATH, db)
workspace_service.scan_and_sync()

# --- App Initialization ---
app = FastAPI(title="Academic Clarity Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=WORKSPACE_PATH), name="workspace_files")

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
    return {"status": "ok", "workspace": WORKSPACE_PATH}

@app.post("/workspace/sync")
async def sync_workspace():
    results = workspace_service.scan_and_sync()
    return {"success": True, "results": results}

@app.get("/configs")
async def get_configs():
    return {
        "DEEPSEEK_API_KEY": db.get_config("DEEPSEEK_API_KEY", ""),
        "API_BASE": db.get_config("API_BASE", "https://api.siliconflow.cn/v1"),
        "WORKSPACE_PATH": WORKSPACE_PATH,
        "TABLE_STYLE": db.get_config("TABLE_STYLE", "three-line")
    }

@app.post("/configs")
async def set_config(key: str = Query(...), value: str = Query(...)):
    db.set_config(key, value)
    return {"success": True}

@app.get("/documents")
async def list_documents():
    return db.get_all_documents()

@app.post("/documents/add")
async def add_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    filename = secure_filename(file.filename)
    dest_path = os.path.join(WORKSPACE_PATH, filename)
    counter = 1
    while os.path.exists(dest_path):
        name, ext = os.path.splitext(filename)
        dest_path = os.path.join(WORKSPACE_PATH, f"{name}_{counter}{ext}")
        counter += 1
    
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    doc_id = db.add_document(filename, "uploaded", dest_path)
    background_tasks.add_task(run_full_ocr_workflow, doc_id, dest_path, db)
    return {"success": True, "doc_id": doc_id}

@app.get("/documents/{doc_id}/pdf")
async def get_document_pdf(doc_id: int):
    doc = db.get_document(doc_id)
    if doc and doc.get('stored_path') and os.path.exists(doc['stored_path']):
        return FileResponse(doc['stored_path'], media_type='application/pdf')
    raise HTTPException(status_code=404, detail="PDF not found")

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: int):
    doc = db.get_document(doc_id)
    if doc:
        if os.path.exists(doc['stored_path']): 
            os.remove(doc['stored_path'])
        db.delete_document(doc_id)
        return {"success": True}
    return {"success": False}

@app.get("/documents/{doc_id}/metadata")
async def get_document_metadata_list(doc_id: int):
    return db.get_document_metadata(doc_id)

@app.post("/documents/{doc_id}/metadata/extract")
async def trigger_custom_extraction(doc_id: int, request: MetadataRequest):
    doc = db.get_document(doc_id)
    if not doc or not doc.get('ocr_markdown'):
        raise HTTPException(status_code=400, detail="OCR not completed yet")
    
    config_service = ConfigService(db)
    extract_api_config = config_service.get_extract_config()
    
    try:
        from services.ai_service import call_json_extraction_api
        metadata_json = await call_json_extraction_api(doc['ocr_markdown'], extract_api_config, request.prompt)
        db.add_document_metadata(doc_id, request.label, metadata_json)
        return {"success": True, "label": request.label}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/metadata/{metadata_id}")
async def delete_metadata_entry(metadata_id: int):
    db.delete_metadata(metadata_id)
    return {"success": True}

@app.post("/documents/{doc_id}/reprocess")
async def reprocess_document(doc_id: int, background_tasks: BackgroundTasks):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not os.path.exists(doc['stored_path']):
        raise HTTPException(status_code=400, detail="Physical file missing, cannot reprocess")

    background_tasks.add_task(run_full_ocr_workflow, doc_id, doc['stored_path'], db)
    return {"success": True}

@app.post("/chat")
async def chat_with_doc(request: ChatRequest):
    doc = db.get_document(request.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.get('ocr_markdown'):
        return {"response": "I cannot answer questions about this document yet because OCR has not been completed."}

    config_service = ConfigService(db)
    api_config = config_service.get_chat_config()

    if not api_config["api_key"]:
        return {"response": "Error: DEEPSEEK_API_KEY is not configured in Settings."}

    try:
        response = await call_chat_api(request.query, doc['ocr_markdown'], api_config)
        return {"response": response}
    except Exception as e:
        return {"response": f"Error interacting with AI: {str(e)}"}

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 38391
    uvicorn.run(app, host="127.0.0.1", port=port)
