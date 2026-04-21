import os
import sys
import unittest
import uuid
import shutil
import time
from unittest.mock import patch, MagicMock

# 强力隔离环境：在导入 server 之前先伪造 argv
unique_id = uuid.uuid4().hex
test_ws = os.path.abspath(os.path.join(os.path.dirname(__file__), f"test_ws_api_{unique_id}"))
if not os.path.exists(test_ws): os.makedirs(test_ws)

# 将测试路径注入 sys.argv 欺骗 server.py 的初始化逻辑
sys.argv = [sys.argv[0], "38392", test_ws]

# Add backend to path for imports
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current: break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from fastapi.testclient import TestClient
import server
from server import app, state

class TestApiUploadFlow(unittest.TestCase):
    def setUp(self):
        # Ensure state is initialized for testing
        state.initialize(test_ws)
        self.client = TestClient(app)
        self.test_ws = test_ws

    def tearDown(self):
        # 注意：这里不能删，因为异步任务可能还在跑。
        # 实际清理交由 run_all_tests.py 的全局清理模式处理。
        pass

    @patch('server.run_full_ocr_workflow')
    def test_upload_api_logic(self, mock_ocr):
        """
        验证上传 API 是否正确保存文件并投递后台任务。
        """
        # 1. 准备 Mock PDF
        pdf_content = b"%PDF-1.4 mock"
        files = {"file": ("api_test.pdf", pdf_content, "application/pdf")}

        # 2. 发送请求
        response = self.client.post("/documents/add", files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        # 3. 验证物理文件
        physical_path = os.path.join(self.test_ws, "api_test.pdf")
        self.assertTrue(os.path.exists(physical_path), "File was not copied!")

        # 4. 验证后台任务是否被调用
        self.assertTrue(mock_ocr.called)
        print("  API Upload Flow Logic: PASS")

    def test_reprocess_api_logic(self):
        """验证重新处理接口"""
        doc_id = state.db.add_document("retry.pdf", "o", os.path.join(self.test_ws, "retry.pdf"))
        # 创建一个空文件
        with open(os.path.join(self.test_ws, "retry.pdf"), "w") as f: f.write("m")

        with patch('server.run_full_ocr_workflow') as mock_ocr:
            response = self.client.post(f"/documents/{doc_id}/reprocess")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mock_ocr.called)
        print("  API Reprocess Endpoint: PASS")

if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
