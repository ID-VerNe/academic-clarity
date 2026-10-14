import os
import unittest
import sqlite3
import sys
import uuid
import json

# Add backend to path for imports
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current: break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_db_{uuid.uuid4().hex}.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                # Also remove WAL files if they exist
                for ext in ["-wal", "-shm"]:
                    if os.path.exists(self.db_path + ext):
                        os.remove(self.db_path + ext)
            except:
                pass

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
        self.db_path = f"test_db_{uuid.uuid4().hex}.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        for suffix in ["", "-wal", "-shm"]:
            p = self.db_path + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

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

        # 仅 doi
        self.db.update_document_doi(doc_id, doi="10.1234/abc")
        doc = self.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1234/abc")
        self.assertIsNone(doc["doi_source"])

        # doi + source
        self.db.update_document_doi(doc_id, doi_source="crossref")
        doc = self.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1234/abc")
        self.assertEqual(doc["doi_source"], "crossref")

        # bibtex
        self.db.update_document_doi(doc_id, bibtex="@article{x}")
        doc = self.db.get_document(doc_id)
        self.assertEqual(doc["bibtex"], "@article{x}")

        # 全 None → no-op，不炸不清数据
        self.db.update_document_doi(doc_id)
        doc = self.db.get_document(doc_id)
        self.assertEqual(doc["doi"], "10.1234/abc")
        self.assertEqual(doc["doi_source"], "crossref")

    def test_legacy_db_without_doi_columns_gets_migrated(self):
        """模拟 Phase 1 之前的旧库：无 doi 列 → 开库即补列且数据不丢。"""
        legacy_path = f"test_db_legacy_{uuid.uuid4().hex}.db"
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
            for suffix in ["", "-wal", "-shm"]:
                p = legacy_path + suffix
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

if __name__ == "__main__":
    unittest.main()
