import os
import sys
import unittest
import shutil
from unittest.mock import patch

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (  # noqa: E402
    add_backend_to_sys_path,
    make_temp_ws,
    poll_until,
    server_test_client,
)
add_backend_to_sys_path()


class TestApiUploadFlow(unittest.TestCase):
    def setUp(self):
        # server_test_client 内部伪造 argv 并触发 lifespan 启动 TaskHub
        # worker，否则入队的任务永远不会被执行，mock 不会被调用
        self.ws = make_temp_ws()
        self._cm = server_test_client(38392, self.ws)
        self.client, self.state = self._cm.__enter__()

    def tearDown(self):
        self._cm.__exit__(None, None, None)
        shutil.rmtree(self.ws, ignore_errors=True)

    @patch('routes.documents.run_full_ocr_workflow')
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
        physical_path = os.path.join(self.ws, "api_test.pdf")
        self.assertTrue(os.path.exists(physical_path), "File was not copied!")

        # 4. 验证后台任务是否被调用
        poll_until(lambda: mock_ocr.called, timeout=5.0)
        self.assertTrue(mock_ocr.called)
        print("  API Upload Flow Logic: PASS")

    def test_reprocess_api_logic(self):
        """验证重新处理接口"""
        doc_id = self.state.db.add_document("retry.pdf", "o", os.path.join(self.ws, "retry.pdf"))
        # 创建一个空文件
        with open(os.path.join(self.ws, "retry.pdf"), "w") as f: f.write("m")

        with patch('routes.documents.run_full_ocr_workflow') as mock_ocr:
            response = self.client.post(f"/documents/{doc_id}/reprocess")
            self.assertEqual(response.status_code, 200)
            poll_until(lambda: mock_ocr.called, timeout=5.0)
            self.assertTrue(mock_ocr.called)
        print("  API Reprocess Endpoint: PASS")

if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
