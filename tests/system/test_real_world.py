import os
import sys
import asyncio
import json
import time
import uuid
import shutil

# --- Path Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
current = BASE_DIR
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current: break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_chat_api

async def run_real_integration_test():
    print("====================================================")
    print("   REAL ENVIRONMENT INTEGRATION TEST (NON-MOCK)     ")
    print("====================================================")

    # 1. 初始化测试环境
    test_ws = os.path.join(BASE_DIR, f"real_test_workspace_{uuid.uuid4().hex}")
    if not os.path.exists(test_ws): os.makedirs(test_ws)
    
    db_path = os.path.join(test_ws, f"real_test_{uuid.uuid4().hex}.db")
    if os.path.exists(db_path): os.remove(db_path)
    db = Database(db_path)

    try:
        # 2. 配置 API Keys (从原始配置中恢复)
        # OCR 使用硅基流动
        db.set_config("DEEPSEEK_API_KEY", "sk-amxyrkodwpvxguiumotfrgjirqstfqmghmiytbdvhriejtve")
        db.set_config("API_BASE", "https://api.siliconflow.cn/v1")
        db.set_config("MODEL_NAME", "openai/deepseek-ai/DeepSeek-OCR")

        # JSON 提取使用本地接口
        db.set_config("EXTRACT_API_KEY", "sk-copilot-sdk-default")
        db.set_config("EXTRACT_API_BASE", "http://localhost:37210/v1")
        db.set_config("EXTRACT_MODEL_NAME", "gpt-4.1")

        # 3. 指定 PDF 文件
        pdf_path = r"C:\Users\VerNe\Downloads\Documents\academic-clarity\workspace\10_48550-arxiv_2103_12553.pdf"
        if not os.path.exists(pdf_path):
            print(f"\n[SKIP] Real-world test skipped: PDF not found at {pdf_path}")
            return

        # 4. 执行全链路 OCR + JSON 提取        print(f"[Phase 1] Starting Real OCR for: {os.path.basename(pdf_path)}")
        doc_id = db.add_document(os.path.basename(pdf_path), pdf_path, pdf_path)
        
        start_time = time.time()
        await run_full_ocr_workflow(doc_id, pdf_path, db)
        duration = time.time() - start_time
        
        # 5. 验证结果
        doc = db.get_document(doc_id)
        print("\n[Final Results]")
        print(f"- Status: {doc['ocr_status']}")
        print(f"- Title: {doc['title']}")
        print(f"- Markdown Length: {len(doc['ocr_markdown']) if doc['ocr_markdown'] else 0} chars")
        print(f"- JSON Metadata: {doc['metadata_json'][:200]}...")
        print(f"- Total Time: {duration:.2f} seconds")

        if doc['ocr_status'] == 'completed':
            print("\n[SUCCESS] ALL SYSTEMS GO: Real-world test passed.")
        else:
            print("\n[FAILURE] TEST FAILED: Workflow did not reach 'completed' state.")

    except Exception as e:
        print(f"\n[ERROR] CRITICAL ERROR during test: {e}")
    finally:
        # Cleanup
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                for ext in ["-wal", "-shm"]:
                    if os.path.exists(db_path + ext):
                        os.remove(db_path + ext)
            except: pass
        if os.path.exists(test_ws):
            shutil.rmtree(test_ws, ignore_errors=True)

if __name__ == "__main__":
    asyncio.run(run_real_integration_test())
