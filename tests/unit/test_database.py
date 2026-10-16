import os
import unittest
import sqlite3
import sys
import json

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_db, remove_db_files  # noqa: E402
add_backend_to_sys_path()

from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = make_temp_db()
        self.db = Database(self.db_path)

    def tearDown(self):
        remove_db_files(self.db_path)

    def test_add_get_document(self):
        doc_id = self.db.add_document("test.pdf", "orig/path", "stored/path")
        doc = self.db.get_document(doc_id)
        self.assertEqual(doc['filename'], "test.pdf")
        self.assertEqual(doc['ocr_status'], "pending")

    def test_config_crud(self):
        self.db.set_config("TEST_KEY", "VALUE")
        val = self.db.get_config("TEST_KEY")
        self.assertEqual(val, "VALUE")
        
        # Override
        self.db.set_config("TEST_KEY", "NEW_VALUE")
        self.assertEqual(self.db.get_config("TEST_KEY"), "NEW_VALUE")

    def test_delete_document(self):
        doc_id = self.db.add_document("del.pdf", "o", "s")
        success = self.db.delete_document(doc_id)
        self.assertTrue(success)
        self.assertIsNone(self.db.get_document(doc_id))

    def test_get_all_documents_with_metadata_join(self):
        # 1. Add doc
        doc_id = self.db.add_document("test.pdf", "/raw/path", "/stored/path")
        
        # 2. Add 'Basic Insight' metadata
        insight = {"journal_or_conference": "Nature", "date": "2023"}
        self.db.add_document_metadata(doc_id, "Basic Insight", json.dumps(insight))
        
        # 3. Get all docs and check JOIN result
        docs = self.db.get_all_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['basic_insight_json'], json.dumps(insight))
        self.assertEqual(docs[0]['id'], doc_id)


class TestDoiColumnsMigration(unittest.TestCase):
    """Phase 1：doi/doi_source/bibtex 列迁移与写入。"""

    def setUp(self):
        self.db_path = make_temp_db()
        self.db = Database(self.db_path)

    def tearDown(self):
        remove_db_files(self.db_path)

    def test_new_db_has_doi_columns_null_by_default(self):
        doc_id = self.db.add_document("a.pdf", "o", "s")
        doc = self.db.get_document(doc_id)
        for col in ("doi", "doi_source", "bibtex"):
            self.assertIn(col, doc)
            self.assertIsNone(doc[col])
        # get_all_documents（SELECT d.*）同样暴露新列
        row = self.db.get_all_documents()[0]
        self.assertIsNone(row["doi"])

    def test_update_document_doi_dynamic_set(self):
        doc_id = self.db.add_document("a.pdf", "o", "s")

        # (场景, update kwargs, 期望列值)：同一 doc 上按序叠加
        steps = [
            ("仅 doi", {"doi": "10.1234/abc"},
             {"doi": "10.1234/abc", "doi_source": None}),
            ("doi + source", {"doi_source": "crossref"},
             {"doi": "10.1234/abc", "doi_source": "crossref"}),
            ("bibtex", {"bibtex": "@article{x}"}, {"bibtex": "@article{x}"}),
            ("全 None → no-op", {},
             {"doi": "10.1234/abc", "doi_source": "crossref"}),
        ]
        for name, kwargs, expected in steps:
            with self.subTest(scenario=name):
                self.db.update_document_doi(doc_id, **kwargs)
                doc = self.db.get_document(doc_id)
                for col, value in expected.items():
                    if value is None:
                        self.assertIsNone(doc[col])
                    else:
                        self.assertEqual(doc[col], value)

    def test_legacy_db_without_doi_columns_gets_migrated(self):
        """模拟 Phase 1 之前的旧库：无 doi 列 → 开库即补列且数据不丢。"""
        legacy_path = make_temp_db(prefix="ac_test_legacy")
        try:
            conn = sqlite3.connect(legacy_path)
            conn.execute('''
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    original_path TEXT,
                    stored_path TEXT,
                    title TEXT,
                    authors TEXT,
                    ocr_status TEXT DEFAULT 'pending',
                    ocr_markdown TEXT,
                    ocr_raw TEXT,
                    metadata_json TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute(
                "INSERT INTO documents (filename, title) VALUES ('old.pdf', 'Old')")
            conn.commit()
            conn.close()

            # 旧库无新列
            conn = sqlite3.connect(legacy_path)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
            conn.close()
            self.assertNotIn("doi", cols)

            # 开库触发迁移
            db = Database(legacy_path)
            conn = sqlite3.connect(legacy_path)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(documents)")}
            conn.close()
            for col in ("doi", "doi_source", "bibtex"):
                self.assertIn(col, cols)

            # 旧数据完好，新列可写
            doc = db.get_document(1)
            self.assertEqual(doc["title"], "Old")
            self.assertIsNone(doc["doi"])
            db.update_document_doi(1, doi="10.1234/abc", doi_source="crossref")
            self.assertEqual(db.get_document(1)["doi"], "10.1234/abc")
        finally:
            remove_db_files(legacy_path)

if __name__ == "__main__":
    unittest.main()
