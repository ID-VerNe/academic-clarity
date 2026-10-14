"""doi_service 单元测试（Phase 1）。

mock 边界：
- verify_doi：patch services.doi_service._client（不打真网络）
- fetch_bibtex：patch urllib.request.urlopen（module 级，doi_service 同引）
- _client/ConfigService：FakeDb 提供 get_config（backend 无 config.py，
  ConfigService.defaults 为 None，全部走字面默认值）

覆盖：normalize / overlap / SSRF / verified / corrected / mismatch /
no_author / no_title / crossref_error / low_overlap / bibtex 成败 /
verify_document 落库。
"""
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch, MagicMock

# 动态路径发现定位 backend/
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from services.doi_service import (  # noqa: E402
    DoiServiceError,
    _assert_safe_url,
    _client,
    _title_overlap,
    fetch_bibtex,
    normalize_doi,
    verify_doi,
    verify_document,
)


class FakeDb:
    """最小 db 桩：仅实现 ConfigService 需要的 get_config。"""

    def __init__(self, configs=None):
        self.configs = configs or {}

    def get_config(self, key, default=""):
        return self.configs.get(key, default)


class FakeClient:
    """CrossRefClient 桩：返回预置 search_by_title 结果或抛错。"""

    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def search_by_title(self, title, expected_author=None):
        self.calls.append((title, expected_author))
        if self.exc:
            raise self.exc
        return self.result


class TestNormalizeDoi(unittest.TestCase):
    def test_strips_doi_org_prefixes(self):
        self.assertEqual(
            normalize_doi("https://doi.org/10.1234/abc"), "10.1234/abc")
        self.assertEqual(
            normalize_doi("http://dx.doi.org/10.1234/abc"), "10.1234/abc")
        self.assertEqual(
            normalize_doi("DOI:10.1234/abc"), "10.1234/abc")
        self.assertEqual(normalize_doi("  10.1234/abc  "), "10.1234/abc")

    def test_strips_supplement_suffix(self):
        self.assertEqual(
            normalize_doi("10.1021/acs.analchem.5c01686.s001"),
            "10.1021/acs.analchem.5c01686")

    def test_rejects_invalid(self):
        for bad in ["", None, "not-a-doi", "10.123/abc",  # 注册号段不足 4 位
                    "10.1234/abc?query=1", "10.1234/abc#frag"]:
            self.assertIsNone(normalize_doi(bad), f"should reject: {bad!r}")


class TestTitleOverlap(unittest.TestCase):
    def test_full_and_partial(self):
        self.assertEqual(_title_overlap("Deep Learning", "Deep Learning"), 1.0)
        # "on" 仅 2 字母被过滤 → 分母 3，覆盖 2
        self.assertEqual(
            _title_overlap("Deep Learning on Graphs", "Deep Learning"), 2 / 3)
        self.assertEqual(_title_overlap("Deep Learning", "Something Else"), 0.0)

    def test_empty_query_returns_zero(self):
        self.assertEqual(_title_overlap("", "anything"), 0.0)
        self.assertEqual(_title_overlap("a an of", "a an of"), 0.0)  # 全短词


class TestAssertSafeUrl(unittest.TestCase):
    def test_accepts_crossref_https(self):
        # 不抛即过
        _assert_safe_url("https://api.crossref.org/works/10.1234/abc")

    def test_rejects_non_https(self):
        with self.assertRaises(DoiServiceError):
            _assert_safe_url("http://api.crossref.org/works/10.1234/abc")

    def test_rejects_other_hosts(self):
        for url in [
            "https://evil.com/works/10.1234/abc",
            "https://api.crossref.org.evil.com/works/10.1234/abc",
            "https://api.crossref.org@evil.com/works/10.1234/abc",  # userinfo 戏法
            "https://127.0.0.1/works/10.1234/abc",
            "https://localhost/works/10.1234/abc",
        ]:
            with self.assertRaises(DoiServiceError, msg=url):
                _assert_safe_url(url)


class TestClientConfig(unittest.TestCase):
    def test_ua_injects_mailto_and_compresses_retries(self):
        fake = FakeDb({"CROSSREF_MAILTO": "dev@example.com",
                       "CROSSREF_TIMEOUT": "7", "CROSSREF_MAX_RETRIES": "1"})
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch("vendor.pdf_doi_toolkit.CrossRefClient", fake_ctor):
            client = _client(fake)
        self.assertIsNotNone(client)
        self.assertIn("mailto:dev@example.com", captured["user_agent"])
        self.assertEqual(captured["max_retries"], 1)   # vendor 默认 5 → 压到 1
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(captured["request_delay"], 0.35)

    def test_ua_without_mailto(self):
        captured = {}

        def fake_ctor(**kwargs):
            captured.update(kwargs)
            return MagicMock()

        with patch("vendor.pdf_doi_toolkit.CrossRefClient", fake_ctor):
            _client(FakeDb())
        self.assertEqual(captured["user_agent"], "AcademicClarity/1.0")
        self.assertNotIn("mailto", captured["user_agent"])
        self.assertEqual(captured["max_retries"], 2)   # 字面默认
        self.assertEqual(captured["timeout"], 10)


class TestVerifyDoi(unittest.TestCase):
    CR_RESULT = {"doi": "10.1109/TVCG.2023.12345", "author": "John Doe",
                 "title": "Deep Learning Survey", "note": "ok"}

    def _patch_client(self, result=None, exc=None):
        return patch("services.doi_service._client",
                     lambda db=None: FakeClient(result=result, exc=exc))

    # ── 主路径 ──────────────────────────────────────────────

    def test_verified_when_llm_doi_matches_crossref(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("Deep Learning Survey", "John Doe",
                           "10.1109/TVCG.2023.12345", db=FakeDb())
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["doi"], "10.1109/TVCG.2023.12345")
        self.assertEqual(r["source"], "crossref")
        self.assertEqual(r["score"], 100)  # overlap 1.0 → 50 + author 50
        self.assertEqual(r["note"], "ok")

    def test_verified_is_case_insensitive_on_doi(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("Deep Learning Survey", "John Doe",
                           "10.1109/TVCG.2023.12345".upper(), db=FakeDb())
        self.assertEqual(r["status"], "verified")

    def test_corrected_when_llm_doi_differs(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("Deep Learning Survey", "John Doe",
                           "10.9999/wrong.doi", db=FakeDb())
        self.assertEqual(r["status"], "corrected")
        self.assertEqual(r["doi"], "10.1109/TVCG.2023.12345")
        self.assertEqual(r["source"], "crossref")

    def test_verified_when_llm_doi_missing(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("Deep Learning Survey", "John Doe", "", db=FakeDb())
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["doi"], "10.1109/TVCG.2023.12345")

    def test_mismatch_when_authors_disagree_never_rewrites(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("Deep Learning Survey", "Wei Zhou",
                           "10.9999/wrong.doi", db=FakeDb())
        self.assertEqual(r["status"], "mismatch")
        self.assertEqual(r["doi"], "10.9999/wrong.doi")  # 保留 LLM 原值
        self.assertEqual(r["source"], "llm")
        self.assertEqual(r["note"], "author_mismatch")
        self.assertEqual(r["cr_author"], "John Doe")

    def test_no_author_verifies_with_note(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("Deep Learning Survey", "", "", db=FakeDb())
        self.assertEqual(r["status"], "verified")
        self.assertEqual(r["note"], "no_author_to_verify")
        self.assertEqual(r["score"], 50)  # 无作者加分

    # ── 降级路径 ────────────────────────────────────────────

    def test_no_title_short_circuits(self):
        with self._patch_client(self.CR_RESULT) as cl:
            r = verify_doi("", "John Doe", "10.9999/wrong.doi", db=FakeDb())
        self.assertEqual(r["status"], "unverified")
        self.assertEqual(r["note"], "no_title")
        self.assertEqual(r["doi"], "10.9999/wrong.doi")  # 保留 LLM 值
        self.assertEqual(r["source"], "llm")

    def test_no_title_with_invalid_llm_doi(self):
        with self._patch_client(self.CR_RESULT):
            r = verify_doi("", "John Doe", "garbage", db=FakeDb())
        self.assertIsNone(r["doi"])
        self.assertEqual(r["source"], "unverified")

    def test_crossref_error_degrades(self):
        with self._patch_client(exc=RuntimeError("boom")):
            r = verify_doi("Deep Learning Survey", "John Doe",
                           "10.1109/TVCG.2023.12345", db=FakeDb())
        self.assertEqual(r["status"], "unverified")
        self.assertTrue(r["note"].startswith("crossref_error"))
        self.assertEqual(r["doi"], "10.1109/TVCG.2023.12345")  # 保留 LLM 值

    def test_low_title_overlap_rejected(self):
        # CrossRef 返回的标题与查询几乎无关 → 不采信
        far = {"doi": "10.1109/TVCG.2023.12345", "author": "John Doe",
               "title": "Quantum Computing Today", "note": "ok"}
        with self._patch_client(far):
            r = verify_doi("Deep Learning Survey", "John Doe",
                           "10.1109/TVCG.2023.12345", db=FakeDb())
        self.assertEqual(r["status"], "unverified")
        self.assertEqual(r["note"], "low_title_overlap")

    def test_no_crossref_doi_uses_vendor_note(self):
        empty = {"doi": None, "author": None, "title": None, "note": "no_results"}
        with self._patch_client(empty):
            r = verify_doi("Deep Learning Survey", "John Doe", "", db=FakeDb())
        self.assertEqual(r["status"], "unverified")
        self.assertEqual(r["note"], "no_results")


class TestFetchBibtex(unittest.TestCase):
    def _urlopen_ok(self, body=b"@article{doe2024, title={X}}"):
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return MagicMock(return_value=resp)

    def test_success_sends_content_negotiation_headers(self):
        with patch("urllib.request.urlopen", self._urlopen_ok()) as m:
            bib = fetch_bibtex("10.1234/abc", db=FakeDb())
        self.assertEqual(bib, "@article{doe2024, title={X}}")
        req = m.call_args[0][0]
        self.assertEqual(req.get_header("Accept"), "application/x-bibtex")
        self.assertIn("AcademicClarity/1.0", req.get_header("User-agent"))
        # DOI 中的 / 必须 percent-encode（safe=''），否则路径歧义
        self.assertEqual(req.full_url,
                         "https://api.crossref.org/works/10.1234%2Fabc")

    def test_doi_with_slash_is_percent_encoded(self):
        with patch("urllib.request.urlopen", self._urlopen_ok()) as m:
            fetch_bibtex("10.1234/a/b", db=FakeDb())
        self.assertEqual(m.call_args[0][0].full_url,
                         "https://api.crossref.org/works/10.1234%2Fa%2Fb")

    def test_invalid_doi_raises(self):
        with self.assertRaises(DoiServiceError):
            fetch_bibtex("garbage", db=FakeDb())

    def test_http_error_becomes_service_error(self):
        err = urllib.error.HTTPError(
            "https://api.crossref.org/works/10.1234/abc", 404, "Not Found",
            {}, None)
        with patch("urllib.request.urlopen", MagicMock(side_effect=err)):
            with self.assertRaises(DoiServiceError) as ctx:
                fetch_bibtex("10.1234/abc", db=FakeDb())
        self.assertIn("404", str(ctx.exception))

    def test_network_error_becomes_service_error(self):
        with patch("urllib.request.urlopen",
                   MagicMock(side_effect=urllib.error.URLError("dns"))):
            with self.assertRaises(DoiServiceError):
                fetch_bibtex("10.1234/abc", db=FakeDb())


class TestVerifyDocument(unittest.TestCase):
    class DocDb(FakeDb):
        def __init__(self, metas, configs=None):
            super().__init__(configs)
            self.metas = metas
            self.updated = []

        def get_document_metadata(self, doc_id):
            return self.metas

        def update_document_doi(self, doc_id, doi=None, doi_source=None):
            self.updated.append((doc_id, doi, doi_source))

    def test_no_basic_insight_short_circuits(self):
        db = self.DocDb([{"label": "OCR Text", "content_json": "{}"}])
        r = verify_document(db, 1)
        self.assertEqual(r["status"], "unverified")
        self.assertEqual(r["note"], "no_basic_insight")
        self.assertEqual(db.updated, [])

    def test_persists_verified_result(self):
        import json
        metas = [{"label": "Basic Insight",
                  "content_json": json.dumps(
                      {"title": "Deep Learning Survey", "authors": "John Doe",
                       "doi": "10.1109/TVCG.2023.12345"})}]
        db = self.DocDb(metas)
        with patch("services.doi_service._client",
                   lambda db=None: FakeClient(
                       result=TestVerifyDoi.CR_RESULT)):
            r = verify_document(db, 42)
        self.assertEqual(r["status"], "verified")
        self.assertEqual(db.updated,
                         [(42, "10.1109/TVCG.2023.12345", "crossref")])


if __name__ == "__main__":
    unittest.main()
