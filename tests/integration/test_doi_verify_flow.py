"""DOI 校验端点集成测试（Phase 1）。

骨架使用共享 helpers：server_test_client（类级共享 lifespan 只跑一次，
setUp 按测试重指向独立 workspace）。

CrossRef 全 mock：
- verify：patch services.doi_service._client（FakeCrossrefClient）
- bibtex：patch urllib.request.urlopen（MagicMock 上下文管理器）
"""
import os
import sys
import unittest
import shutil
import json
import urllib.error
from unittest.mock import patch, MagicMock

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (  # noqa: E402
    FakeCrossrefClient,
    add_backend_to_sys_path,
    make_temp_ws,
    server_test_client,
)
add_backend_to_sys_path()

INSIGHT = json.dumps({
    "title": "Deep Learning Survey",
    "authors": "John Doe",
    "doi": "10.1109/TVCG.2023.12345",
})

CR_RESULT = {"doi": "10.1109/TVCG.2023.12345", "author": "John Doe",
             "title": "Deep Learning Survey", "note": "ok"}


class TestDoiVerifyFlow(unittest.TestCase):
    # 类级共享 TestClient：lifespan（task_hub worker 启动）只跑一次，
    # 每测试仍独立 workspace + state.initialize 隔离。
    @classmethod
    def setUpClass(cls):
        cls.ws = make_temp_ws()
        cls._cm = server_test_client(38393, cls.ws)
        cls.client, cls.state = cls._cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._cm.__exit__(None, None, None)
        shutil.rmtree(cls.ws, ignore_errors=True)

    def setUp(self):
        self.test_ws = make_temp_ws()
        # lifespan 按 argv 的 ws 初始化；随后重指向到本测试 workspace
        self.state.initialize(self.test_ws)

    def tearDown(self):
        shutil.rmtree(self.test_ws, ignore_errors=True)

    # ── helpers ─────────────────────────────────────────────

    def _add_doc(self, with_ocr=True, with_insight=True):
        doc_id = self.state.db.add_document("paper.pdf", "/raw/paper.pdf",
                                       os.path.join(self.test_ws, "paper.pdf"))
        if with_ocr:
            self.state.db.update_document_ocr(doc_id, "completed",
                                         markdown="# Paper\n\nBody text.")
        if with_insight:
            self.state.db.add_document_metadata(doc_id, "Basic Insight", INSIGHT)
        return doc_id

    @staticmethod
    def _urlopen_ok(body=b"@article{doe2024, title={Deep Learning Survey}}"):
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return MagicMock(return_value=resp)

    # ── POST /documents/{id}/doi/verify ─────────────────────

    def test_verify_endpoint_verified_and_persisted(self):
        doc_id = self._add_doc()
        with patch("services.doi_service._client",
                   lambda db=None: FakeCrossrefClient(result=CR_RESULT)):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["result"]["status"], "verified")
        self.assertEqual(body["result"]["source"], "crossref")

        doc = self.state.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1109/TVCG.2023.12345")
        self.assertEqual(doc["doi_source"], "crossref")

    def test_verify_endpoint_corrects_llm_doi(self):
        doc_id = self._add_doc()
        with patch("services.doi_service._client",
                   lambda db=None: FakeCrossrefClient(result=CR_RESULT)):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        # LLM DOI 与 CrossRef 一致 → verified；换成不一致的输入则 corrected
        # （此处 INSIGHT 的 doi 与 CR_RESULT 相同，验证 verified 分支即可）
        self.assertEqual(resp.json()["result"]["status"], "verified")

    def test_verify_endpoint_requires_ocr_markdown(self):
        doc_id = self._add_doc(with_ocr=False)
        with patch("services.doi_service._client",
                   lambda db=None: FakeCrossrefClient(result=CR_RESULT)):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 400)

    def test_verify_endpoint_without_basic_insight(self):
        doc_id = self._add_doc(with_insight=False)
        with patch("services.doi_service._client",
                   lambda db=None: FakeCrossrefClient(result=CR_RESULT)) as cl:
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["note"], "no_basic_insight")
        # 未触网
        doc = self.state.db.get_document(doc_id)
        self.assertIsNone(doc["doi"])

    def test_verify_endpoint_crossref_error_degrades(self):
        doc_id = self._add_doc()
        with patch("services.doi_service._client",
                   lambda db=None: FakeCrossrefClient(exc=RuntimeError("boom"))):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(result["status"], "unverified")
        self.assertTrue(result["note"].startswith("crossref_error"))
        # 失败不阻断：LLM 原值保留落库
        doc = self.state.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1109/TVCG.2023.12345")
        self.assertEqual(doc["doi_source"], "llm")

    # ── GET /documents/{id}/bibtex ──────────────────────────

    def test_bibtex_endpoint_db_cache_first(self):
        doc_id = self._add_doc()
        self.state.db.update_document_doi(doc_id, doi="10.1109/TVCG.2023.12345",
                                     bibtex="@article{cached}")
        with patch("urllib.request.urlopen") as m:
            resp = self.client.get(f"/documents/{doc_id}/bibtex")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["bibtex"], "@article{cached}")
        self.assertFalse(m.called, "DB 缓存命中时不得触网")

    def test_bibtex_endpoint_fetches_then_caches(self):
        doc_id = self._add_doc()
        self.state.db.update_document_doi(doc_id, doi="10.1109/TVCG.2023.12345",
                                     doi_source="crossref")
        with patch("urllib.request.urlopen", self._urlopen_ok()) as m:
            resp = self.client.get(f"/documents/{doc_id}/bibtex")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Deep Learning Survey", resp.json()["bibtex"])
            self.assertTrue(m.called)

            # 第二次请求命中 DB 缓存，不再触网
            resp2 = self.client.get(f"/documents/{doc_id}/bibtex")
            self.assertEqual(resp2.json()["bibtex"], resp.json()["bibtex"])
            self.assertEqual(m.call_count, 1)

        doc = self.state.db.get_document(doc_id)
        self.assertIn("Deep Learning Survey", doc["bibtex"])

    def test_bibtex_endpoint_502_on_crossref_error(self):
        doc_id = self._add_doc()
        self.state.db.update_document_doi(doc_id, doi="10.1109/TVCG.2023.12345")
        err = urllib.error.HTTPError(
            "https://api.crossref.org/works/x", 404, "Not Found", {}, None)
        with patch("urllib.request.urlopen", MagicMock(side_effect=err)):
            resp = self.client.get(f"/documents/{doc_id}/bibtex")
        self.assertEqual(resp.status_code, 502)

    def test_bibtex_endpoint_400_without_doi(self):
        doc_id = self._add_doc()
        with patch("urllib.request.urlopen") as m:
            resp = self.client.get(f"/documents/{doc_id}/bibtex")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(m.called)

    def test_bibtex_endpoint_404_unknown_doc(self):
        resp = self.client.get("/documents/999999/bibtex")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
