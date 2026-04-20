import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, patch
import json
import uuid
import shutil

# --- Path Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_chat_api

class TestAcademicClarityIntegration(unittest.TestCase):
    def setUp(self):
        # 1. 设置独立的测试数据库和工作区
        self.unique_id = uuid.uuid4().hex
        self.test_workspace = os.path.join(BASE_DIR, f"test_workspace_int_{self.unique_id}")
        if not os.path.exists(self.test_workspace):
            os.makedirs(self.test_workspace)
        
        # 2. 生成 Mock PDF 文件
        self.test_pdf = os.path.join(self.test_workspace, "integration_test.pdf")
        with open(self.test_pdf, "wb") as f:
            f.write(b"%PDF-1.4 mock content")

        self.db_path = os.path.join(self.test_workspace, f"test_library_{self.unique_id}.db")
        self.db = Database(self.db_path)
        
        # 3. 初始配置测试
        self.db.set_config("DEEPSEEK_API_KEY", "test_key")
        self.db.set_config("API_BASE", "https://api.siliconflow.cn/v1")
        self.db.set_config("MODEL_NAME", "deepseek-ai/DeepSeek-V3")

    def tearDown(self):
        # 清理
        if os.path.exists(self.test_workspace):
            shutil.rmtree(self.test_workspace, ignore_errors=True)

    def test_workflow_full_pipeline_mocked(self):
        """
        验证全流程：DB入库 -> OCR触发 -> 状态更新 -> 多维元数据提取 (Mocked API)
        """
        print("\n[Integration Test] Starting Full Workflow (Mocked)...")
        
        mock_ocr_md = "# Test Paper\nFormula: $E=mc^2$."
        mock_json_meta = json.dumps({"title": "Test Paper", "authors": ["AI"]})

        doc_id = self.db.add_document("test_file.pdf", self.test_pdf, self.test_pdf)

        async def run_mocked_ocr():
            # 模拟 fitz.open 因为是 mock pdf
            with patch('fitz.open') as mock_fitz, \
                 patch('services.ocr_service.call_ocr_api', return_value=mock_ocr_md), \
                 patch('services.ocr_service.call_json_extraction_api', return_value=mock_json_meta):
                
                # 模拟 PDF 页数
                mock_doc = MagicMock()
                mock_doc.__len__.return_value = 1
                mock_page = MagicMock()
                mock_page.get_pixmap.return_value.tobytes.return_value = b"img_data"
                mock_doc.__getitem__.return_value = mock_page
                mock_fitz.return_value = mock_doc
                
                await run_full_ocr_workflow(doc_id, self.test_pdf, self.db)

        asyncio.run(run_mocked_ocr())

        # 验证
        updated_doc = self.db.get_document(doc_id)
        self.assertEqual(updated_doc['ocr_status'], 'completed')
        
        metadata_list = self.db.get_document_metadata(doc_id)
        self.assertGreater(len(metadata_list), 0)
        self.assertEqual(metadata_list[0]['label'], "Basic Insight")
        
        print("  Full Pipeline Logic: PASS")

    def test_ai_chat_logic(self):
        """验证 AI 问答逻辑"""
        print("\n[Integration Test] AI Chat Logic...")
        mock_context = "# Intro\nAI is cool."
        doc_id = self.db.add_document("chat.pdf", "path", "path")
        self.db.update_document_ocr(doc_id, "completed", markdown=mock_context)
        
        async def run_mocked_chat():
            with patch('services.ai_service.completion') as mock_comp:
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Response"
                mock_comp.return_value = mock_response
                
                response = await call_chat_api("Hi", mock_context, {"api_key":"k", "api_base":"b", "model_name":"m"})
                self.assertEqual(response, "Response")

        asyncio.run(run_mocked_chat())
        print("  AI Chat Logic: PASS")

if __name__ == "__main__":
    unittest.main()
