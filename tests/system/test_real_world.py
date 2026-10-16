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
import shutil

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path  # noqa: E402
ROOT_DIR = os.path.dirname(add_backend_to_sys_path())
from helpers import make_temp_db, make_temp_ws, remove_db_files  # noqa: E402

KEY_FILE = os.path.join(ROOT_DIR, "test", "key.json")
DEFAULT_PDF = os.path.join(ROOT_DIR, "workspace", "10_48550-arxiv_2103_12553.pdf")

from database import Database  # noqa: E402
from services.ocr_service import run_full_ocr_workflow  # noqa: E402


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
    test_ws = make_temp_ws("ac_test_ws_real")
    db_path = make_temp_db("ac_test_db_real")
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
        remove_db_files(db_path)
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
