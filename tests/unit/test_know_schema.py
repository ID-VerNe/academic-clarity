"""know.config schema + FTS5 CJK 移植测试（Phase 2，源 test_schema.py 11 例）。

peer-review Gap 5：2 字符 CJK 查询必须返行——FTS5 trigram/unicode61
对 '交易' 均返 0，唯一修复是 config.search_claims 的 LIKE 兜底。
改造点：路径发现改为动态找 backend/ + backend/vendor/know；
其余逐一保持原样（含原始 INSERT 不走 FTS 同步、专测 LIKE 兜底）。
"""
import os
import sys
import sqlite3
import unittest
import tempfile

# 动态路径发现定位 backend/
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
VENDOR_KNOW = os.path.join(current, "backend", "vendor", "know")
if os.path.exists(VENDOR_KNOW) and VENDOR_KNOW not in sys.path:
    sys.path.insert(0, VENDOR_KNOW)

from config import init_db, SCHEMA_SQL, search_claims  # noqa: E402


class TestSchemaTables(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.tmp.close()
        self.conn = init_db(self.tmp.name)

    def tearDown(self):
        self.conn.close()
        os.remove(self.tmp.name)

    def test_papers_table_exists(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='papers'")
        self.assertIsNotNone(cur.fetchone())

    def test_claims_table_exists(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='claims'")
        self.assertIsNotNone(cur.fetchone())

    def test_claims_fts_exists(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='claims_fts'")
        self.assertIsNotNone(cur.fetchone())

    def test_claims_fts_cjk_exists(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='claims_fts_cjk'")
        self.assertIsNotNone(cur.fetchone())

    def test_claims_has_heading_path_column(self):
        cur = self.conn.execute("PRAGMA table_info(claims)")
        cols = [row[1] for row in cur.fetchall()]
        self.assertIn("heading_path", cols)

    def test_claims_has_ocr_version_column(self):
        cur = self.conn.execute("PRAGMA table_info(papers)")
        cols = [row[1] for row in cur.fetchall()]
        self.assertIn("ocr_version", cols)


class TestFTS5CJKTwoCharQuery(unittest.TestCase):
    """peer-review Gap 5: 2-char CJK query must return rows.
    The shipped trigram+unicode61 tables returned 0 for '交易'.
    This is the flagship fix.
    """
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.tmp.close()
        self.conn = init_db(self.tmp.name)
        self.conn.execute(
            "INSERT INTO papers (paper_id, title, authors, year, project, "
            "source_rel, ocr_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("doi:test", "Title", '["Author"]', 2020, "proj", "rel", "v1"),
        )
        self.conn.execute(
            "INSERT INTO claims (paper_id, concept, quote, anchor, heading_path, "
            "model, prompt_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("doi:test", "P2P交易瓶颈", "逐字引文交易", "pabcdefgh", "II. INTRO",
             "gemini", "v1"),
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        os.remove(self.tmp.name)

    def test_two_char_cjk_returns_rows(self):
        results = search_claims(self.conn, "交易")
        self.assertGreater(len(results), 0,
                           "2-char CJK query '交易' must return rows (Gap 5 fix)")

    def test_three_char_cjk_still_works(self):
        results = search_claims(self.conn, "交易瓶颈")
        self.assertGreater(len(results), 0)

    def test_english_token_works(self):
        results = search_claims(self.conn, "P2P")
        self.assertGreater(len(results), 0)

    def test_no_match_returns_empty(self):
        results = search_claims(self.conn, "不存在的词xyz")
        self.assertEqual(len(results), 0)


class TestHeadingPathStored(unittest.TestCase):
    """Gap 4: heading_path stored per claim for relocation detection."""
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.tmp.close()
        self.conn = init_db(self.tmp.name)

    def tearDown(self):
        self.conn.close()
        os.remove(self.tmp.name)

    def test_heading_path_round_trips(self):
        self.conn.execute(
            "INSERT INTO papers (paper_id, title, authors, year, project, "
            "source_rel, ocr_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("doi:h", "T", '["A"]', 2020, "p", "r", "v1"),
        )
        self.conn.execute(
            "INSERT INTO claims (paper_id, concept, quote, anchor, heading_path, "
            "model, prompt_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("doi:h", "c", "q", "pxxxxxxxx", "## III. METHOD > ### A. Concept",
             "m", "p"),
        )
        self.conn.commit()
        cur = self.conn.execute(
            "SELECT heading_path FROM claims WHERE paper_id=?", ("doi:h",))
        row = cur.fetchone()
        self.assertEqual(row[0], "## III. METHOD > ### A. Concept")


if __name__ == "__main__":
    unittest.main()
