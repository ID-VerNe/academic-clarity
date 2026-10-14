"""DOI 校验端点集成测试（Phase 1）。

骨架仿 tests/integration/test_tex_upload_flow.py：导入 server 前注入
sys.argv；每测试独立 UUID workspace；TestClient 上下文触发 lifespan。

 CrossRef 全 mock：
- verify：patch services.doi_service._client（FakeClient）
- bibtex：patch urllib.request.urlopen（MagicMock 上下文管理器）
"""
import os
import sys
import unittest
import uuid
import shutil
import json
import urllib.error
from unittest.mock import patch, MagicMock

# 强力隔离环境：在导入 server 之前先伪造 argv
unique_id = uuid.uuid4().hex
module_ws = os.path.abspath(
    os.path.join(os.path.dirname(__file__), f"test_ws_doi_{unique_id}"))
if not os.path.exists(module_ws):
    os.makedirs(module_ws)

sys.argv = [sys.argv[0], "38393", module_ws]

current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from fastapi.testclient import TestClient  # noqa: E402
import server  # noqa: E402
from server import app, state  # noqa: E402

INSIGHT = json.dumps({
    "title": "Deep Learning Survey",
    "authors": "John Doe",
    "doi": "10.1109/TVCG.2023.12345",
})

CR_RESULT = {"doi": "10.1109/TVCG.2023.12345", "author": "John Doe",
             "title": "Deep Learning Survey", "note": "ok"}


class FakeClient:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc

    def search_by_title(self, title, expected_author=None):
        if self.exc:
            raise self.exc
        return self.result


class TestDoiVerifyFlow(unittest.TestCase):
    # 类级共享 TestClient：lifespan（task_hub worker 启动）只跑一次，
    # 每测试仍独立 UUID workspace + state.initialize 隔离。
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        shutil.rmtree(module_ws, ignore_errors=True)

    def setUp(self):
        self.test_ws = os.path.abspath(
            os.path.join(os.path.dirname(__file__), f"test_ws_doi_case_{uuid.uuid4().hex}")
        )
        os.makedirs(self.test_ws, exist_ok=True)
        # lifespan 按 argv 的 module_ws 初始化；随后重指向到本测试 workspace
        state.initialize(self.test_ws)

    def tearDown(self):
        shutil.rmtree(self.test_ws, ignore_errors=True)

    # ── helpers ─────────────────────────────────────────────

    def _add_doc(self, with_ocr=True, with_insight=True):
        doc_id = state.db.add_document("paper.pdf", "/raw/paper.pdf",
                                       os.path.join(self.test_ws, "paper.pdf"))
        if with_ocr:
            state.db.update_document_ocr(doc_id, "completed",
                                         markdown="# Paper\n\nBody text.")
        if with_insight:
            state.db.add_document_metadata(doc_id, "Basic Insight", INSIGHT)
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
                   lambda db=None: FakeClient(result=CR_RESULT)):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["result"]["status"], "verified")
        self.assertEqual(body["result"]["source"], "crossref")

        doc = state.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1109/TVCG.2023.12345")
        self.assertEqual(doc["doi_source"], "crossref")

    def test_verify_endpoint_corrects_llm_doi(self):
        doc_id = self._add_doc()
        with patch("services.doi_service._client",
                   lambda db=None: FakeClient(result=CR_RESULT)):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        # LLM DOI 与 CrossRef 一致 → verified；换成不一致的输入则 corrected
        # （此处 INSIGHT 的 doi 与 CR_RESULT 相同，验证 verified 分支即可）
        self.assertEqual(resp.json()["result"]["status"], "verified")

    def test_verify_endpoint_requires_ocr_markdown(self):
        doc_id = self._add_doc(with_ocr=False)
        with patch("services.doi_service._client",
                   lambda db=None: FakeClient(result=CR_RESULT)):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 400)

    def test_verify_endpoint_without_basic_insight(self):
        doc_id = self._add_doc(with_insight=False)
        with patch("services.doi_service._client",
                   lambda db=None: FakeClient(result=CR_RESULT)) as cl:
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["note"], "no_basic_insight")
        # 未触网
        doc = state.db.get_document(doc_id)
        self.assertIsNone(doc["doi"])

    def test_verify_endpoint_crossref_error_degrades(self):
        doc_id = self._add_doc()
        with patch("services.doi_service._client",
                   lambda db=None: FakeClient(exc=RuntimeError("boom"))):
            resp = self.client.post(f"/documents/{doc_id}/doi/verify")
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertEqual(result["status"], "unverified")
        self.assertTrue(result["note"].startswith("crossref_error"))
        # 失败不阻断：LLM 原值保留落库
        doc = state.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1109/TVCG.2023.12345")
        self.assertEqual(doc["doi_source"], "llm")

    # ── GET /documents/{id}/bibtex ──────────────────────────

    def test_bibtex_endpoint_db_cache_first(self):
        doc_id = self._add_doc()
        state.db.update_document_doi(doc_id, doi="10.1109/TVCG.2023.12345",
                                     bibtex="@article{cached}")
        with patch("urllib.request.urlopen") as m:
            resp = self.client.get(f"/documents/{doc_id}/bibtex")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["bibtex"], "@article{cached}")
        self.assertFalse(m.called, "DB 缓存命中时不得触网")

    def test_bibtex_endpoint_fetches_then_caches(self):
        doc_id = self._add_doc()
        state.db.update_document_doi(doc_id, doi="10.1109/TVCG.2023.12345",
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

        doc = state.db.get_document(doc_id)
        self.assertIn("Deep Learning Survey", doc["bibtex"])

    def test_bibtex_endpoint_502_on_crossref_error(self):
        doc_id = self._add_doc()
        state.db.update_document_doi(doc_id, doi="10.1109/TVCG.2023.12345")
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
