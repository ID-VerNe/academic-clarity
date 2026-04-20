import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, patch
from io import BytesIO
import json
import uuid
import shutil

# --- Path Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_chat_api
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown

class TestAcademicClarityIntegration(unittest.TestCase):
    def setUp(self):
        # 1. 设置独立的测试数据库和工作区
        self.test_workspace = os.path.join(BASE_DIR, f"test_workspace_integration_{uuid.uuid4().hex}")
        if not os.path.exists(self.test_workspace):
            os.makedirs(self.test_workspace)
        
        self.db_path = os.path.join(self.test_workspace, f"test_library_{uuid.uuid4().hex}.db")
        if os.path.exists(self.db_path): os.remove(self.db_path)
        
        self.db = Database(self.db_path)
        
        # 2. 设置测试 PDF 路径
        self.test_pdf = r"C:\Users\VerNe\Downloads\Documents\academic-clarity\workspace\10_48550-arxiv_2103_12553.pdf"
        
        # 3. 初始配置测试
        self.db.set_config("DEEPSEEK_API_KEY", "test_key_placeholder")
        self.db.set_config("API_BASE", "https://api.siliconflow.cn/v1")
        self.db.set_config("MODEL_NAME", "deepseek-ai/DeepSeek-V3")

    def tearDown(self):
        # 清理测试数据库
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                for ext in ["-wal", "-shm"]:
                    if os.path.exists(self.db_path + ext):
                        os.remove(self.db_path + ext)
            except:
                pass
        # 清理工作区目录
        if os.path.exists(self.test_workspace):
            try:
                shutil.rmtree(self.test_workspace)
            except:
                pass

    def test_workflow_full_pipeline_mocked(self):
        """
        验证全流程逻辑：数据库记录 -> OCR 流程触发 -> 状态更新 -> JSON 提取
        (使用 Mock 模拟 LLM 响应，确保逻辑正确)
        """
        print("\n[Integration Test] Starting Full Workflow (Mocked)...")
        
        # 准备 Mock 数据
        mock_ocr_md = "# Test Paper Title\nThis is a sample abstract with a formula: $E=mc^2$."
        mock_json_meta = json.dumps({
            "title": "Test Paper Title",
            "authors": ["Author One", "Author Two"],
            "abstract": "This is a sample abstract.",
            "keywords": ["AI", "OCR"]
        })

        # 创建文档记录
        doc_id = self.db.add_document("test_file.pdf", self.test_pdf, self.test_pdf)
        self.assertEqual(self.db.get_document(doc_id)['ocr_status'], 'pending')

        # 运行异步全流程 (Mocking AI calls)
        async def run_mocked_ocr():
            with patch('services.ocr_service.call_ocr_api', return_value=mock_ocr_md), \
                 patch('services.ocr_service.call_json_extraction_api', return_value=mock_json_meta):
                await run_full_ocr_workflow(doc_id, self.test_pdf, self.db)

        asyncio.run(run_mocked_ocr())

        # 验证结果
        updated_doc = self.db.get_document(doc_id)
        print(f"  Status updated to: {updated_doc['ocr_status']}")
        self.assertEqual(updated_doc['ocr_status'], 'completed')
        self.assertEqual(updated_doc['title'], 'Test Paper Title')
        self.assertIn('$E=mc^2$', updated_doc['ocr_markdown'])
        
        # 验证 JSON 提取
        meta_data = json.loads(updated_doc['metadata_json'])
        self.assertEqual(meta_data['authors'][0], "Author One")
        print("  Workflow Logic Verified OK.")

    def test_ai_chat_logic(self):
        """
        验证 AI 问答逻辑
        """
        print("\n[Integration Test] AI Chat Logic...")
        
        # 准备环境：假设已有一个提取好的文档
        mock_context = "# Introduction\nDeep learning is a subset of machine learning."
        doc_id = self.db.add_document("chat.pdf", "path", "path")
        self.db.update_document_ocr(doc_id, "completed", markdown=mock_context)
        
        api_config = {
            "api_key": "test",
            "api_base": "test",
            "model_name": "test"
        }

        async def run_mocked_chat():
            with patch('services.ai_service.completion') as mock_comp:
                # 模拟 LiteLLM 的响应结构
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "AI Response based on context."
                mock_comp.return_value = mock_response
                
                response = await call_chat_api("What is deep learning?", mock_context, api_config)
                self.assertEqual(response, "AI Response based on context.")

        asyncio.run(run_mocked_chat())
        print("  AI Chat Logic Verified OK.")

    def test_path_existence(self):
        """
        验证用户指定的测试 PDF 路径是否真的存在
        """
        print(f"\n[Validation] Checking PDF source: {self.test_pdf}")
        self.assertTrue(os.path.exists(self.test_pdf), f"PDF file not found at {self.test_pdf}")
        print("  PDF Path found OK.")

if __name__ == "__main__":
    unittest.main()
