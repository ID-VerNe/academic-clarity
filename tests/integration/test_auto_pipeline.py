import os
import sys
import unittest
import uuid
import shutil
import asyncio
from unittest.mock import patch, MagicMock

# Add backend to path for imports
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
from services.workspace_service import WorkspaceService

class TestAutoPipeline(unittest.TestCase):
    def setUp(self):
        self.unique_id = uuid.uuid4().hex
        self.test_dir = os.path.join(BASE_DIR, f"test_auto_ws_{self.unique_id}")
        os.makedirs(self.test_dir)
        
        # 准备一个真实的 PDF 文件用于测试（从根目录 workspace 拷贝）
        self.src_pdf = os.path.join(os.path.dirname(BASE_DIR), "workspace", "10_48550-arxiv_2103_12553.pdf")
        if os.path.exists(self.src_pdf):
            shutil.copy(self.src_pdf, os.path.join(self.test_dir, "test_sync.pdf"))
        else:
            # 如果源不存在，创建一个 mock pdf
            with open(os.path.join(self.test_dir, "test_sync.pdf"), "w") as f: f.write("%PDF-1.4 mock")

        self.db_path = os.path.join(self.test_dir, f"test_db_{self.unique_id}.db")
        self.db = Database(self.db_path)
        self.service = WorkspaceService(self.test_dir, self.db)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('services.workspace_service.run_full_ocr_workflow')
    def test_sync_automatically_triggers_ocr(self, mock_ocr_workflow):
        """
        验证切换工作区后，扫描到的新文件能自动触发 OCR 任务挂载。
        """
        # 模拟异步任务调度
        mock_ocr_workflow.return_value = asyncio.Future()
        mock_ocr_workflow.return_value.set_result(None)

        print(f"\n[Test] Running Auto-Sync Pipeline for: {self.test_dir}")
        
        # 执行同步
        results = self.service.scan_and_sync()
        
        # 1. 验证文件已入库
        self.assertEqual(results["added"], 1)
        # 2. 验证 OCR 任务已被逻辑触发 (triggered_ocr 计数)
        self.assertEqual(results["triggered_ocr"], 1)
        
        # 3. 验证数据库中记录的状态
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['filename'], "test_sync.pdf")
        
        print("  Auto-Sync & Trigger Logic: PASS")

if __name__ == "__main__":
    unittest.main()
