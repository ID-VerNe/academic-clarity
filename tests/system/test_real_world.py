"""真实环境冒烟测试（非 mock）：全链路 OCR + 关键结果断言。

- 入口为脚本式，由 run_all_tests.py 串行调度；也可独立执行。
- 无 test/key.json 或无测试 PDF 时打印 [SKIP] 并以 0 退出。
- PDF：环境变量 AC_TEST_PDF 优先，缺省 workspace/10_48550-arxiv_2103_12553.pdf。
- 密钥仅从 test/key.json 读取，严禁打印/复制其内容。
"""
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
ROOT_DIR = current
BACKEND_PATH = os.path.join(ROOT_DIR, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

KEY_FILE = os.path.join(ROOT_DIR, "test", "key.json")
DEFAULT_PDF = os.path.join(ROOT_DIR, "workspace", "10_48550-arxiv_2103_12553.pdf")

from database import Database
from services.ocr_service import run_full_ocr_workflow


def _load_key():
    """读取本机 LLM 配置（字段：key/url/model-ocr/model-llm）；内容严禁外泄。"""
    if not os.path.exists(KEY_FILE):
        return None
    with open(KEY_FILE, encoding="utf-8") as f:
        return json.load(f)


async def run_real_integration_test(key, pdf_path):
    print("====================================================")
    print("   REAL ENVIRONMENT INTEGRATION TEST (NON-MOCK)     ")
    print("====================================================")

    # 1. 初始化测试环境
    test_ws = os.path.join(BASE_DIR, f"real_test_workspace_{uuid.uuid4().hex}")
    os.makedirs(test_ws, exist_ok=True)
    db_path = os.path.join(test_ws, f"real_test_{uuid.uuid4().hex}.db")
    db = Database(db_path)
    exit_code = 1

    try:
        # 2. 配置 API Keys（来自 test/key.json，不落日志）
        db.set_config("DEEPSEEK_API_KEY", key["key"])
        db.set_config("API_BASE", key["url"] + "/v1")
        db.set_config("MODEL_NAME", "openai/" + key["model-ocr"])
        db.set_config("EXTRACT_API_KEY", key["key"])
        db.set_config("EXTRACT_API_BASE", key["url"] + "/v1")
        db.set_config("EXTRACT_MODEL_NAME", "openai/" + key["model-llm"])

        # 3. 执行全链路 OCR + JSON 提取
        print(f"[Phase 1] Starting Real OCR for: {os.path.basename(pdf_path)}")
        doc_id = db.add_document(os.path.basename(pdf_path), pdf_path, pdf_path)

        start_time = time.time()
        await run_full_ocr_workflow(doc_id, pdf_path, db)
        duration = time.time() - start_time

        # 4. 验证结果（关键结果必须断言，失败即非零退出）
        doc = db.get_document(doc_id)
        markdown = (doc.get("ocr_markdown") or "") if doc else ""
        print("\n[Final Results]")
        print(f"- Status: {doc['ocr_status'] if doc else '<no doc>'}")
        print(f"- Title: {doc['title'] if doc else '<no doc>'}")
        print(f"- Markdown Length: {len(markdown)} chars")
        print(f"- JSON Metadata: {(doc.get('metadata_json') or '')[:200] if doc else ''}...")
        print(f"- Total Time: {duration:.2f} seconds")

        assert doc is not None, "document row missing after workflow"
        assert doc["ocr_status"] == "completed", f"workflow did not reach 'completed' (got {doc['ocr_status']})"
        assert markdown.strip(), "OCR markdown is empty"

        print("\n[SUCCESS] ALL SYSTEMS GO: Real-world test passed.")
        exit_code = 0
    except Exception as e:
        print(f"\n[FAILURE] TEST FAILED: {type(e).__name__}: {e}")
        exit_code = 1
    finally:
        # Cleanup
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                for ext in ["-wal", "-shm"]:
                    if os.path.exists(db_path + ext):
                        os.remove(db_path + ext)
            except OSError:
                pass
        if os.path.exists(test_ws):
            shutil.rmtree(test_ws, ignore_errors=True)
    return exit_code


if __name__ == "__main__":
    key = _load_key()
    if not key:
        print(f"[SKIP] Real-world test skipped: {KEY_FILE} not found.")
        sys.exit(0)
    pdf_path = os.environ.get("AC_TEST_PDF") or DEFAULT_PDF
    if not os.path.exists(pdf_path):
        print(f"[SKIP] Real-world test skipped: PDF not found at {pdf_path}")
        sys.exit(0)
    sys.exit(asyncio.run(run_real_integration_test(key, pdf_path)))
