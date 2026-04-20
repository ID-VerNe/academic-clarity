import os
import sys
import unittest
import uuid
import shutil

# Add backend to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "backend"))
if BACKEND_PATH not in sys.path: sys.path.insert(0, BACKEND_PATH)

from database import Database
from services.workspace_service import WorkspaceService

class TestWorkspaceSync(unittest.TestCase):
    def setUp(self):
        self.unique_id = uuid.uuid4().hex
        self.test_dir = os.path.join(BASE_DIR, f"test_workspace_{self.unique_id}")
        os.makedirs(self.test_dir)
        
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
        self.assertEqual(results["added"], 2)
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
        
        self.assertEqual(results["added"], 0)
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 1)

if __name__ == "__main__":
    unittest.main()
