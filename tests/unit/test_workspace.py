import os
import sys
import asyncio
import unittest
import uuid
import shutil

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_ws  # noqa: E402
add_backend_to_sys_path()

from database import Database
from services.workspace_service import WorkspaceService

class TestWorkspaceSync(unittest.TestCase):
    def setUp(self):
        self.unique_id = uuid.uuid4().hex
        # 临时 workspace 目录落系统 temp（ac_test_ 前缀，调度器可清理）
        self.test_dir = make_temp_ws()
        self.db_path = os.path.join(self.test_dir, f"test_db_{self.unique_id}.db")
        self.db = Database(self.db_path)
        self.service = WorkspaceService(self.test_dir, self.db)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_auto_scan_new_pdfs(self):
        # 1. 模拟物理放入两个 PDF
        file1 = os.path.join(self.test_dir, "paper1.pdf")
        file2 = os.path.join(self.test_dir, "paper2.pdf")
        with open(file1, "w") as f: f.write("%PDF-1.4 mock content")
        with open(file2, "w") as f: f.write("%PDF-1.4 mock content")

        # 2. 执行同步
        results = self.service.scan_and_sync()
        
        # 3. 验证 DB 中是否增加了两条记录
        self.assertEqual(len(results), 2)
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 2)
        filenames = [d['filename'] for d in docs]
        self.assertIn("paper1.pdf", filenames)
        self.assertIn("paper2.pdf", filenames)

    def test_idempotent_sync(self):
        # 验证重复同步不会增加冗余记录
        file1 = os.path.join(self.test_dir, "only_one.pdf")
        with open(file1, "w") as f: f.write("%PDF-1.4 mock content")
        
        self.service.scan_and_sync() # 第一次
        results = self.service.scan_and_sync() # 第二次
        
        self.assertEqual(len(results), 0)
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 1)

    def test_async_scan_new_pdfs(self):
        """测试异步扫描功能能正确检测新增的PDF"""
        file1 = os.path.join(self.test_dir, "async_paper1.pdf")
        file2 = os.path.join(self.test_dir, "async_paper2.pdf")
        with open(file1, "w") as f: f.write("%PDF-1.4 mock content")
        with open(file2, "w") as f: f.write("%PDF-1.4 mock content")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self.service.async_scan_and_sync())
        finally:
            loop.close()

        self.assertEqual(len(results), 2)
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 2)
        filenames = [d['filename'] for d in docs]
        self.assertIn("async_paper1.pdf", filenames)
        self.assertIn("async_paper2.pdf", filenames)

    def test_async_idempotent_sync(self):
        """测试异步扫描的幂等性 - 重复调用不会创建重复记录"""
        file1 = os.path.join(self.test_dir, "async_idempotent.pdf")
        with open(file1, "w") as f: f.write("%PDF-1.4 mock content")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.service.async_scan_and_sync())
            results = loop.run_until_complete(self.service.async_scan_and_sync())
        finally:
            loop.close()

        self.assertEqual(len(results), 0)
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 1)

if __name__ == "__main__":
    unittest.main()
