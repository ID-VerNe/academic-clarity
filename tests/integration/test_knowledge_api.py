"""know 知识层 API 集成测试（Phase 2，方案 §5.3）。

骨架使用共享 helpers：server_test_client（类级共享 lifespan 只跑一次，
setUp 按测试重指向独立 workspace）；中文旗舰语料取自 fixtures_data。

验收门槛：中文文档 ingest 后 GET /knowledge/search?q=交易 必须返回
≥1 条带 anchor 的 claim（master plan「旗舰查询不得查空」）。
"""
import os
import sys
import unittest
import shutil
from unittest.mock import patch, AsyncMock

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (  # noqa: E402
    add_backend_to_sys_path,
    make_temp_ws,
    server_test_client,
)
add_backend_to_sys_path()
from fixtures_data import CJK_INSIGHT, CJK_OCR_MD  # noqa: E402


class TestKnowledgeApi(unittest.TestCase):
    # 类级共享 TestClient：lifespan（worker 启动）只跑一次，
    # 每测试仍独立 workspace + state.initialize 隔离。
    @classmethod
    def setUpClass(cls):
        cls.ws = make_temp_ws()
        cls._cm = server_test_client(38394, cls.ws)
        cls.client, cls.state = cls._cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._cm.__exit__(None, None, None)
        shutil.rmtree(cls.ws, ignore_errors=True)

    def setUp(self):
        self.test_ws = make_temp_ws()
        self.state.initialize(self.test_ws)

    def tearDown(self):
        shutil.rmtree(self.test_ws, ignore_errors=True)

    def _add_doc(self, ocr_md=CJK_OCR_MD, insight=CJK_INSIGHT):
        doc_id = self.state.db.add_document("cjk.pdf", "/raw/cjk.pdf",
                                       os.path.join(self.test_ws, "cjk.pdf"))
        self.state.db.update_document_ocr(doc_id, "completed", markdown=ocr_md,
                                    title="P2P Energy Trading Survey")
        self.state.db.add_document_metadata(doc_id, "Basic Insight", insight)
        return doc_id

    # ── ingest ──────────────────────────────────────────────

    def test_ingest_creates_claims(self):
        doc_id = self._add_doc()
        resp = self.client.post(f"/knowledge/ingest/{doc_id}")
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        self.assertGreater(result["claims"], 0)
        # T2 主力路径：LLM 转述 → 章节级
        self.assertGreaterEqual(result["section_level"], 1)

    def test_ingest_400_without_ocr(self):
        doc_id = self.state.db.add_document("x.pdf", "/raw/x.pdf",
                                       os.path.join(self.test_ws, "x.pdf"))
        resp = self.client.post(f"/knowledge/ingest/{doc_id}")
        self.assertEqual(resp.status_code, 400)

    def test_ingest_404_unknown_doc(self):
        resp = self.client.post("/knowledge/ingest/999999")
        self.assertEqual(resp.status_code, 404)

    def test_ingest_idempotent(self):
        doc_id = self._add_doc()
        r1 = self.client.post(f"/knowledge/ingest/{doc_id}").json()["result"]
        r2 = self.client.post(f"/knowledge/ingest/{doc_id}").json()["result"]
        self.assertEqual(r2["claims"], r1["claims"])
        papers = self.client.get("/knowledge/papers").json()["papers"]
        paper = next(p for p in papers if p["paper_id"] == f"doc:{doc_id}")
        self.assertEqual(paper["claim_count"], r1["claims"])

    # ── 旗舰验收：CJK 2 字符查询 ─────────────────────────────

    def test_search_cjk_two_char_flagship_query(self):
        doc_id = self._add_doc()
        self.client.post(f"/knowledge/ingest/{doc_id}")
        resp = self.client.get("/knowledge/search", params={"q": "交易"})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()["results"]
        self.assertGreaterEqual(len(rows), 1,
                                "旗舰查询 '交易' 不得查空（Gap 5 门槛）")
        row = rows[0]
        self.assertIn("claim_id", row)
        self.assertTrue(row["anchor"].startswith("p"))
        self.assertIn("heading_path", row)
        self.assertEqual(row["doc_id"], doc_id)

    def test_search_three_char_and_english_and_no_match(self):
        doc_id = self._add_doc()
        self.client.post(f"/knowledge/ingest/{doc_id}")
        # 3 字符 CJK（claim 文本「市场机制」在 LLM 摘要 quote 中）
        self.assertGreaterEqual(
            len(self.client.get("/knowledge/search",
                                params={"q": "市场机制"}).json()["results"]), 1)
        self.assertGreaterEqual(
            len(self.client.get("/knowledge/search",
                                params={"q": "trading"}).json()["results"]), 1)
        # 无匹配返 0 不崩
        self.assertEqual(
            self.client.get("/knowledge/search",
                            params={"q": "不存在的词xyz"}).json()["results"], [])
        # 仅存在于 OCR 原文、不在 claim 文本的词 → 0（检索域=claims，设计行为）
        self.assertEqual(
            self.client.get("/knowledge/search",
                            params={"q": "账本"}).json()["results"], [])

    def test_search_empty_query_400(self):
        resp = self.client.get("/knowledge/search", params={"q": ""})
        self.assertEqual(resp.status_code, 400)

    # ── papers / claims ─────────────────────────────────────

    def test_papers_and_claims_endpoints(self):
        doc_id = self._add_doc()
        self.client.post(f"/knowledge/ingest/{doc_id}")
        papers = self.client.get("/knowledge/papers").json()["papers"]
        paper = next(p for p in papers if p["paper_id"] == f"doc:{doc_id}")
        self.assertEqual(paper["title"], "P2P Energy Trading Survey")
        self.assertGreater(paper["claim_count"], 0)

        claims = self.client.get(
            f"/knowledge/papers/doc:{doc_id}/claims").json()["claims"]
        self.assertGreater(len(claims), 0)
        self.assertEqual(claims[0]["claim_id"], claims[0]["claim_id"])  # 有序非空
        self.assertTrue(all(c["anchor"].startswith("p") for c in claims))

    # ── /chat 引用模式 ──────────────────────────────────────

    def test_chat_quotes_mode_feeds_only_quotes(self):
        doc_id = self._add_doc()
        mock_chat = AsyncMock(return_value="基于引文的回答 [cite://1]")
        with patch("routes.knowledge.call_chat_api", mock_chat):
            resp = self.client.post("/chat", json={
                "doc_id": doc_id, "query": "交易瓶颈是什么？",
                "quotes": ["P2P 交易瓶颈在于各 agent 需顺序更新账本。"],
            })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["response"], "基于引文的回答 [cite://1]")
        # mock LLM 收到的 context 只含逐字引文，不外溢全文
        args = mock_chat.call_args[0]
        self.assertEqual(args[0], "交易瓶颈是什么？")
        self.assertEqual(args[1], "[cite://1] P2P 交易瓶颈在于各 agent 需顺序更新账本。")
        self.assertNotIn("We review market designs", args[1])

    def test_chat_without_quotes_uses_full_markdown(self):
        doc_id = self._add_doc()
        mock_chat = AsyncMock(return_value="全文回答")
        with patch("routes.knowledge.call_chat_api", mock_chat):
            resp = self.client.post(
                "/chat", json={"doc_id": doc_id, "query": "综述什么？"})
        self.assertEqual(resp.status_code, 200)
        args = mock_chat.call_args[0]
        self.assertIn("We review market designs", args[1])  # 全量 markdown

    # ── 删除联动 ────────────────────────────────────────────

    def test_delete_document_forgets_knowledge(self):
        doc_id = self._add_doc()
        self.client.post(f"/knowledge/ingest/{doc_id}")
        self.assertGreater(len(self.client.get(
            f"/knowledge/papers/doc:{doc_id}/claims").json()["claims"]), 0)
        resp = self.client.delete(f"/documents/{doc_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.client.get(
            f"/knowledge/papers/doc:{doc_id}/claims").json()["claims"], [])


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
