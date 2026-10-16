"""tex 上传分流与全流程集成测试（Phase 0）。

骨架使用共享 helpers：server_test_client（每测试独立 workspace + lifespan
启动 worker）；TEX 夹具取自 fixtures_data；轮询替代定长 sleep。
"""
import os
import sys
import unittest
import shutil
import json

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (  # noqa: E402
    add_backend_to_sys_path,
    make_temp_ws,
    poll_until,
    server_test_client,
)
add_backend_to_sys_path()
from fixtures_data import TEX_FIXTURE  # noqa: E402
from unittest.mock import patch, AsyncMock  # noqa: E402


class TestTexUploadFlow(unittest.TestCase):
    def setUp(self):
        # 每测试独立 workspace（agents.md §3 并行隔离）；server_test_client
        # 内部触发 lifespan 启动 TaskHub worker
        self.ws = make_temp_ws()
        self._cm = server_test_client(38392, self.ws)
        self.client, self.state = self._cm.__enter__()

    def tearDown(self):
        self._cm.__exit__(None, None, None)
        shutil.rmtree(self.ws, ignore_errors=True)

    def _upload(self, filename, content):
        return self.client.post(
            "/documents/add",
            files={"file": (filename, content, "application/octet-stream")},
        )

    @patch('routes.documents.run_full_ocr_workflow', new_callable=AsyncMock)
    @patch('routes.documents.run_tex_workflow', new_callable=AsyncMock)
    def test_upload_tex_routes_to_tex_workflow(self, mock_tex, mock_ocr):
        resp = self._upload("paper.tex", TEX_FIXTURE.encode("utf-8"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertTrue(os.path.exists(os.path.join(self.ws, "paper.tex")))

        ok = self._wait_for(lambda: mock_tex.called)
        self.assertTrue(ok, "tex workflow was never called")
        self.assertFalse(mock_ocr.called, "OCR workflow must not run for .tex")
        args = mock_tex.call_args[0]
        self.assertEqual(args[1], os.path.join(self.ws, "paper.tex"))

    @patch('routes.documents.run_full_ocr_workflow', new_callable=AsyncMock)
    @patch('routes.documents.run_tex_workflow', new_callable=AsyncMock)
    def test_upload_zip_routes_to_tex_workflow(self, mock_tex, mock_ocr):
        import zipfile
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("main.tex", TEX_FIXTURE)
        resp = self._upload("src.zip", buf.getvalue())
        self.assertEqual(resp.status_code, 200)

        ok = self._wait_for(lambda: mock_tex.called)
        self.assertTrue(ok, "tex workflow was never called for .zip")
        self.assertFalse(mock_ocr.called, "OCR workflow must not run for .zip")
        self.assertEqual(
            mock_tex.call_args[0][1], os.path.join(self.ws, "src.zip")
        )

    @patch('routes.documents.run_full_ocr_workflow', new_callable=AsyncMock)
    @patch('routes.documents.run_tex_workflow', new_callable=AsyncMock)
    def test_upload_unsupported_ext_rejected(self, mock_tex, mock_ocr):
        resp = self._upload("evil.exe", b"MZ fake binary")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.ws, "evil.exe")))
        self.assertFalse(mock_tex.called)
        self.assertFalse(mock_ocr.called)

    def test_full_tex_flow_completed(self):
        """真实 run_tex_workflow（仅 mock LLM）：completed + markdown 含 # +
        Basic Insight 落库 + title 来自 \\title{} 而非 'Abstract'。
        patch 在上传前激活，避免 worker 抢跑未 patch 的真实 LLM 调用。"""
        mock_llm = AsyncMock(
            return_value=json.dumps({"title": "Real Title", "authors": "A, B"})
        )
        with patch("services.tex_service.call_json_extraction_api", new=mock_llm):
            resp = self._upload("full.tex", TEX_FIXTURE.encode("utf-8"))
            self.assertEqual(resp.status_code, 200)
            doc_id = resp.json()["doc_id"]

            def pipeline_done():
                doc = state.db.get_document(doc_id) or {}
                if doc.get("ocr_status") != "completed":
                    return False
                metas = state.db.get_document_metadata(doc_id)
                return any(m["label"] == "Basic Insight" for m in metas)

            self.assertTrue(self._wait_for(pipeline_done), "tex pipeline did not finish")

            doc = state.db.get_document(doc_id)
            self.assertEqual(doc["ocr_status"], "completed")
            self.assertIn("#", doc["ocr_markdown"])
            self.assertIn("# Introduction", doc["ocr_markdown"])
            self.assertEqual(doc["title"], "Real Title")  # 非 "Abstract"（Q2 规避）

            metas = state.db.get_document_metadata(doc_id)
            basic = [m for m in metas if m["label"] == "Basic Insight"]
            self.assertEqual(len(basic), 1)
            self.assertEqual(json.loads(basic[0]["content_json"])["title"], "Real Title")
            self.assertTrue(mock_llm.called)
            # LLM 输入显式前置标题行（tex markdown 不含标题）；存储 markdown 不变
            llm_md = mock_llm.call_args[0][0]
            self.assertTrue(llm_md.startswith("# Real Title"),
                            f"LLM input should carry title: {llm_md[:60]!r}")
            self.assertNotIn("Real Title", doc["ocr_markdown"])

    @patch('routes.documents.run_full_ocr_workflow', new_callable=AsyncMock)
    @patch('routes.documents.run_tex_workflow', new_callable=AsyncMock)
    def test_workspace_sync_routes_tex(self, mock_tex, mock_ocr):
        tex_path = os.path.join(self.ws, "scanned.tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(TEX_FIXTURE)

        resp = self.client.post("/workspace/sync")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["triggered"], 1)

        ok = self._wait_for(lambda: mock_tex.called)
        self.assertTrue(ok, "sync did not queue tex workflow")
        self.assertEqual(mock_tex.call_args[0][1], tex_path)
        # OCR workflow 不得对该 .tex 文档被调用
        for call in mock_ocr.call_args_list:
            self.assertNotIn("scanned.tex", str(call))


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
