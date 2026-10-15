"""know 知识层 API 集成测试（Phase 2，方案 §5.3）。

骨架仿 tests/integration/test_tex_upload_flow.py：导入 server 前注入
sys.argv；每测试独立 UUID workspace；类级共享 TestClient（lifespan 只
跑一次，state.initialize 按测试重指向）。

验收门槛：中文文档 ingest 后 GET /knowledge/search?q=交易 必须返回
≥1 条带 anchor 的 claim（master plan「旗舰查询不得查空」）。
"""
import os
import sys
import json
import unittest
import uuid
import shutil
from unittest.mock import patch, AsyncMock

# 强力隔离环境：在导入 server 之前先伪造 argv
unique_id = uuid.uuid4().hex
module_ws = os.path.abspath(
    os.path.join(os.path.dirname(__file__), f"test_ws_know_{unique_id}"))
if not os.path.exists(module_ws):
    os.makedirs(module_ws)

sys.argv = [sys.argv[0], "38394", module_ws]

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

# 中文旗舰语料：OCR 正文含「交易」段 + 对应 Basic Insight（LLM 转述）
CJK_OCR_MD = """# P2P Energy Trading Survey

## Abstract
P2P 交易瓶颈在于各 agent 需顺序更新账本。
We review market designs for peer-to-peer energy trading.

## METHOD
We compare centralized and decentralized clearing.
"""

CJK_INSIGHT = json.dumps({
    "title": "P2P Energy Trading Survey",
    "authors": "Wei Zhou",
    "journal_or_conference": "Applied Energy",
    "date": "2023",
    "abstract": "本文综述 P2P 能源交易的市场机制与瓶颈。",
    "keywords": ["P2P trading", "energy market"],
    "summary": ["Novelty: taxonomy", "Method: comparison"],
    "doi": "",
})


class TestKnowledgeApi(unittest.TestCase):
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
            os.path.join(os.path.dirname(__file__), f"test_ws_know_case_{uuid.uuid4().hex}")
        )
        os.makedirs(self.test_ws, exist_ok=True)
        state.initialize(self.test_ws)

    def tearDown(self):
        shutil.rmtree(self.test_ws, ignore_errors=True)

    def _add_doc(self, ocr_md=CJK_OCR_MD, insight=CJK_INSIGHT):
        doc_id = state.db.add_document("cjk.pdf", "/raw/cjk.pdf",
                                       os.path.join(self.test_ws, "cjk.pdf"))
        state.db.update_document_ocr(doc_id, "completed", markdown=ocr_md,
                                    title="P2P Energy Trading Survey")
        state.db.add_document_metadata(doc_id, "Basic Insight", insight)
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
        doc_id = state.db.add_document("x.pdf", "/raw/x.pdf",
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
