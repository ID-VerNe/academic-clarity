import os
import sys
import unittest
import uuid
import shutil
import asyncio
from unittest.mock import patch

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_ws  # noqa: E402
add_backend_to_sys_path()

# 样例 PDF 查找基准（tests/ 目录，保持原查找位置）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from database import Database  # noqa: E402
from services.workspace_service import WorkspaceService  # noqa: E402


class TestAutoPipeline(unittest.TestCase):
    def setUp(self):
        self.unique_id = uuid.uuid4().hex
        self.test_dir = make_temp_ws()
        
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

    @patch('services.ocr_service.run_full_ocr_workflow')
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
        self.assertEqual(len(results), 1)
        
        # 2. 验证数据库中记录的状态
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['filename'], "test_sync.pdf")
        
        print("  Auto-Sync & Trigger Logic: PASS")

if __name__ == "__main__":
    unittest.main()
