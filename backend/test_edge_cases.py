import os
import sys
import unittest
import asyncio
import json
import shutil
import sqlite3
import uuid
from unittest.mock import MagicMock, patch
from io import BytesIO

# --- Path Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from database import Database
from services.ocr_service import run_full_ocr_workflow
from services.ai_service import call_json_extraction_api

class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.test_workspace = os.path.join(BASE_DIR, f"test_workspace_edge_{uuid.uuid4().hex}")
        if not os.path.exists(self.test_workspace):
            os.makedirs(self.test_workspace)
        
        self.db_path = os.path.join(self.test_workspace, f"test_library_edge_{uuid.uuid4().hex}.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        
        self.db = Database(self.db_path)
        self.db.set_config("DEEPSEEK_API_KEY", "test_key")

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                for ext in ["-wal", "-shm"]:
                    if os.path.exists(self.db_path + ext):
                        os.remove(self.db_path + ext)
            except:
                pass
        if os.path.exists(self.test_workspace):
            try:
                shutil.rmtree(self.test_workspace)
            except:
                pass

    def test_empty_pdf_handling(self):
        """1. Test handling of an empty (0-byte) PDF file."""
        empty_pdf_path = os.path.join(self.test_workspace, "empty.pdf")
        with open(empty_pdf_path, "wb") as f:
            pass
        
        doc_id = self.db.add_document("empty.pdf", empty_pdf_path, empty_pdf_path)
        
        # run_full_ocr_workflow should catch fitz.FileNotFoundError or similar and mark as failed
        asyncio.run(run_full_ocr_workflow(doc_id, empty_pdf_path, self.db))
        
        doc = self.db.get_document(doc_id)
        self.assertEqual(doc['ocr_status'], 'failed')

    def test_malformed_llm_json_response(self):
        """2. Test handling of corrupted/malformed LLM JSON responses."""
        api_config = {"api_key": "test", "api_base": "test", "model_name": "test"}
        
        async def run_test():
            with patch('services.ai_service.completion') as mock_comp:
                # Case 1: Non-JSON content
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "This is not JSON"
                mock_comp.return_value = mock_response
                
                res = await call_json_extraction_api("content", api_config, "prompt")
                data = json.loads(res)
                self.assertIn("error", data)
                self.assertEqual(data["error"], "Model returned invalid JSON")
                
                # Case 2: Timeout
                mock_comp.side_effect = asyncio.TimeoutError()
                res = await call_json_extraction_api("content", api_config, "prompt")
                data = json.loads(res)
                self.assertIn("error", data)
                self.assertTrue("timed out" in data["error"])

        asyncio.run(run_test())

    def test_database_field_size_limits(self):
        """3. Test database field size limits with very long markdown."""
        # Create a 5MB string
        large_markdown = "A" * (5 * 1024 * 1024) 
        doc_id = self.db.add_document("large.pdf", "path", "path")
        
        # Test updating with large content
        self.db.update_document_ocr(doc_id, "completed", markdown=large_markdown)
        
        doc = self.db.get_document(doc_id)
        self.assertEqual(len(doc['ocr_markdown']), 5 * 1024 * 1024)
        self.assertEqual(doc['ocr_markdown'], large_markdown)

    def test_rapid_multi_upload_concurrency(self):
        """4. Test rapid multi-upload concurrency to ensure DB integrity."""
        num_concurrent = 20
        
        async def concurrent_adds():
            # simulate adding documents in parallel
            # We use a wrapper since add_document is not async
            def add_sync(idx):
                return self.db.add_document(f"file_{idx}.pdf", f"path_{idx}", f"stored_{idx}")
            
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(None, add_sync, i) for i in range(num_concurrent)]
            return await asyncio.gather(*tasks)

        doc_ids = asyncio.run(concurrent_adds())
        
        self.assertEqual(len(doc_ids), num_concurrent)
        self.assertEqual(len(set(doc_ids)), num_concurrent) # all unique
        
        all_docs = self.db.get_all_documents()
        self.assertEqual(len(all_docs), num_concurrent)

if __name__ == "__main__":
    unittest.main()
