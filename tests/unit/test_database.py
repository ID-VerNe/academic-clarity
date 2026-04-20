import os
import unittest
import sqlite3
import sys
import uuid

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

if __name__ == "__main__":
    unittest.main()
