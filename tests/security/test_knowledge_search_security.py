"""know 知识层检索安全测试（Phase 2，方案 §5.3 安全用例）。

威胁模型：q 直接进 vendor config.search_claims 的 FTS MATCH 与
LIKE。防线 = 全参数化（vendor config.py:139-171 实证）+ FTS 语法
错误 OperationalError 裸吞落 LIKE（config.py:146/161）+ 端点层
超长/空查询 400。本类验证注入/畸形 FTS/通配符/超长四类载荷下
claims 表无损、不 500、不 OOM。
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
    os.path.join(os.path.dirname(__file__), f"test_ws_know_sec_{unique_id}"))
if not os.path.exists(module_ws):
    os.makedirs(module_ws)

sys.argv = [sys.argv[0], "38395", module_ws]

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

OCR_MD = """# Paper

## Abstract
P2P 交易瓶颈在于各 agent 需顺序更新账本。
We review market designs for peer-to-peer energy trading.
"""

INSIGHT = json.dumps({
    "title": "P2P Energy Trading Survey", "authors": "Wei Zhou",
    "abstract": "本文综述 P2P 能源交易的市场机制与瓶颈。",
    "keywords": ["P2P trading"], "doi": "",
})


class TestKnowledgeSearchSecurity(unittest.TestCase):
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
            os.path.join(os.path.dirname(__file__),
                         f"test_ws_know_sec_case_{uuid.uuid4().hex}"))
        os.makedirs(self.test_ws, exist_ok=True)
        state.initialize(self.test_ws)
        doc_id = state.db.add_document("s.pdf", "/raw/s.pdf",
                                       os.path.join(self.test_ws, "s.pdf"))
        state.db.update_document_ocr(doc_id, "completed", markdown=OCR_MD,
                                     title="P2P Energy Trading Survey")
        state.db.add_document_metadata(doc_id, "Basic Insight", INSIGHT)
        resp = self.client.post(f"/knowledge/ingest/{doc_id}")
        self.assertEqual(resp.status_code, 200)
        self.doc_id = doc_id

    def tearDown(self):
        shutil.rmtree(self.test_ws, ignore_errors=True)

    def _claim_count(self):
        from services.knowledge_service import _conn
        conn = _conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        finally:
            conn.close()

    # ── SQL 注入 ────────────────────────────────────────────

    def test_sql_injection_payloads_harmless(self):
        before = self._claim_count()
        payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE claims; --",
            "交易' UNION SELECT 1,2,3 --",
            "\" OR \"\"=\"",
            "'; DELETE FROM papers; --",
        ]
        for q in payloads:
            with self.subTest(q=q):
                resp = self.client.get("/knowledge/search", params={"q": q})
                self.assertIn(resp.status_code, (200, 400))
                if resp.status_code == 200:
                    self.assertIsInstance(resp.json()["results"], list)
                # 表结构/数据无损
                self.assertEqual(self._claim_count(), before)
        # 显式确认表还在
        self.assertGreaterEqual(self._claim_count(), 1)

    # ── FTS 畸形语法 ────────────────────────────────────────

    def test_malformed_fts_syntax_no_500(self):
        payloads = ['"未闭合短语', "NEAR(", "AND OR", "^", "*",
                    "a AND", "OR b", "NOT", "((", "))"]
        for q in payloads:
            with self.subTest(q=q):
                resp = self.client.get("/knowledge/search", params={"q": q})
                self.assertIn(resp.status_code, (200, 400))
                self.assertIsInstance(resp.json().get("results", []), list)

    # ── LIKE 通配符（文档化行为：可能放大匹配，不崩）────────

    def test_like_wildcards_no_crash(self):
        for q in ["%", "_", "%_%", "%%%"]:
            with self.subTest(q=q):
                resp = self.client.get("/knowledge/search", params={"q": q})
                self.assertEqual(resp.status_code, 200)
                self.assertIsInstance(resp.json()["results"], list)

    # ── 超长查询 ────────────────────────────────────────────

    def test_super_long_query_400_no_oom(self):
        # 载荷 6 万 ASCII 字符：远超服务端 200 门槛即被拒，不触达 FTS/LIKE。
        # （httpx TestClient 的 URL 组件上限约 65535 字符；CJK 会被
        # percent-encode 成 9 字节 3 倍膨胀，故用 ASCII 载荷。门槛在
        # 200，任何 >200 的载荷走的都是同一条拒绝路径。）
        resp = self.client.get("/knowledge/search",
                               params={"q": "x" * 60000})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "query too long")
        # 正常查询仍可用
        ok = self.client.get("/knowledge/search", params={"q": "交易"})
        self.assertEqual(ok.status_code, 200)
        self.assertGreaterEqual(len(ok.json()["results"]), 1)

    def test_empty_and_whitespace_query_400(self):
        for q in ["", "   "]:
            with self.subTest(q=q):
                resp = self.client.get("/knowledge/search", params={"q": q})
                self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
