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
import shutil

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import (  # noqa: E402
    add_backend_to_sys_path,
    make_temp_ws,
    server_test_client,
)
add_backend_to_sys_path()

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
    # 类级共享 TestClient：lifespan（worker 启动）只跑一次，
    # 每测试仍独立 workspace + state.initialize 隔离。
    @classmethod
    def setUpClass(cls):
        cls.ws = make_temp_ws()
        cls._cm = server_test_client(38395, cls.ws)
        cls.client, cls.state = cls._cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._cm.__exit__(None, None, None)
        shutil.rmtree(cls.ws, ignore_errors=True)

    def setUp(self):
        # 每测试独立 workspace（系统 temp，ac_test_ 前缀）
        self.test_ws = make_temp_ws()
        self.state.initialize(self.test_ws)
        doc_id = self.state.db.add_document("s.pdf", "/raw/s.pdf",
                                            os.path.join(self.test_ws, "s.pdf"))
        self.state.db.update_document_ocr(doc_id, "completed", markdown=OCR_MD,
                                          title="P2P Energy Trading Survey")
        self.state.db.add_document_metadata(doc_id, "Basic Insight", INSIGHT)
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
