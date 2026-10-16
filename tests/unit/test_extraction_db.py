"""Phase 3 DB 迁移测试：extraction_dimensions 表 + document_metadata.dimension_id。

覆盖：新库建表/列、add_document_metadata 带/不带 dimension_id、
delete_metadata_by_dimension、label UNIQUE 约束、旧库开库即迁移
（历史行 dimension_id 为 NULL、Basic Insight 数据无损）。
"""
import os
import sys
import sqlite3
import unittest
import json

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_db, remove_db_files  # noqa: E402
add_backend_to_sys_path()

from database import Database  # noqa: E402


class TestExtractionDb(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.db = Database(self.db_path)

    def tearDown(self):
        remove_db_files(self.db_path)

    def test_new_db_has_dimension_table_and_column(self):
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='extraction_dimensions'").fetchone()
            self.assertIsNotNone(row)
            cols = [r[1] for r in conn.execute(
                "PRAGMA table_info(document_metadata)").fetchall()]
            self.assertIn("dimension_id", cols)

    def test_add_metadata_with_and_without_dimension_id(self):
        doc_id = self.db.add_document("a.pdf", "o", "s")
        # 不带 dimension_id（Basic Insight 既有调用路径零改动）
        mid1 = self.db.add_document_metadata(doc_id, "Basic Insight",
                                             json.dumps({"title": "T"}))
        # 带 dimension_id（Phase 3 批量提取）
        mid2 = self.db.add_document_metadata(doc_id, "Methodology",
                                             json.dumps({"method": "X"}),
                                             dimension_id="dim123")
        rows = {r["id"]: r for r in self.db.get_document_metadata(doc_id)}
        self.assertIsNone(rows[mid1]["dimension_id"])
        self.assertEqual(rows[mid2]["dimension_id"], "dim123")

    def test_delete_metadata_by_dimension(self):
        doc_id = self.db.add_document("a.pdf", "o", "s")
        self.db.add_document_metadata(doc_id, "D1", "{}", dimension_id="dimA")
        self.db.add_document_metadata(doc_id, "D2", "{}", dimension_id="dimB")
        self.db.add_document_metadata(doc_id, "Basic Insight", "{}")  # 无维度行
        self.db.delete_metadata_by_dimension(doc_id, "dimA")
        labels = {r["label"] for r in self.db.get_document_metadata(doc_id)}
        self.assertEqual(labels, {"D2", "Basic Insight"})

    def test_dimension_label_unique_constraint(self):
        with self.db.safe_write() as cursor:
            cursor.execute("INSERT INTO extraction_dimensions (id, label, prompt) "
                           "VALUES ('a', 'Method', 'p')")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.safe_write() as cursor:
                cursor.execute("INSERT INTO extraction_dimensions (id, label, prompt) "
                               "VALUES ('b', 'Method', 'q')")

    def test_legacy_db_migrated_on_open(self):
        """模拟 Phase 3 之前的旧库：无维度表、document_metadata 无 dimension_id。"""
        legacy_path = make_temp_db(prefix="ac_test_legacy")
        try:
            conn = sqlite3.connect(legacy_path)
            conn.execute('''
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT, original_path TEXT, stored_path TEXT,
                    title TEXT, authors TEXT,
                    ocr_status TEXT DEFAULT 'pending',
                    ocr_markdown TEXT, ocr_raw TEXT, metadata_json TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE TABLE document_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER, label TEXT, content_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute("INSERT INTO documents (filename, title) VALUES ('old.pdf', 'Old')")
            conn.execute("INSERT INTO document_metadata (doc_id, label, content_json) "
                         "VALUES (1, 'Basic Insight', '{\"title\": \"OldT\"}')")
            conn.commit()
            conn.close()

            db = Database(legacy_path)          # 开库即迁移
            rows = db.get_document_metadata(1)
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]["dimension_id"])       # 旧行 NULL
            self.assertEqual(json.loads(rows[0]["content_json"])["title"], "OldT")
            # 新表可用 + 迁移后可写带维度行
            with db.safe_write() as cursor:
                cursor.execute("INSERT INTO extraction_dimensions (id, label, prompt) "
                               "VALUES ('x', 'L', 'P')")
            db.add_document_metadata(1, "Dim", "{}", dimension_id="x")
            rows = db.get_document_metadata(1)
            self.assertEqual({r["dimension_id"] for r in rows}, {None, "x"})
        finally:
            remove_db_files(legacy_path)


if __name__ == "__main__":
    unittest.main()
