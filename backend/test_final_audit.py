import os
import sys
import threading
import unittest
import uuid
import time
import shutil

# Ensure the backend directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import Database
from utils.security import secure_filename

class TestSecurityAndConcurrency(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(BASE_DIR, f"test_audit_{uuid.uuid4().hex}.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def tearDown(self):
        # Try to clean up
        for _ in range(5):
            try:
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                # Also try to remove WAL/SHM files
                for ext in ["-wal", "-shm"]:
                    if os.path.exists(self.db_path + ext):
                        os.remove(self.db_path + ext)
                break
            except PermissionError:
                time.sleep(0.2)

    def test_path_sanitization(self):
        print("\n[Test] Path Sanitization...")
        test_cases = [
            ("../../etc/passwd", "passwd"),
            ("document.pdf", "document.pdf"),
            ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
            ("./relative/path/file.txt", "file.txt"),
            ("中文文件名.pdf", "中文文件名.pdf"),
        ]
        
        for input_name, expected in test_cases:
            result = secure_filename(input_name)
            self.assertNotIn("..", result)
            self.assertNotIn("/", result)
            self.assertNotIn("\\", result)
            print(f"  Passed: {input_name} -> {result}")

    def test_database_concurrency(self):
        print("\n[Test] Database Concurrency (WAL & Timeout)...")
        db = Database(self.db_path)
        
        # Check if WAL is enabled
        with db.get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
            print(f"  Journal Mode is WAL: OK")

        # Test concurrent writes
        errors = []
        def worker(worker_id):
            try:
                for i in range(20):
                    db.set_config(f"key_{worker_id}_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(errors), 0, f"Concurrency errors found: {errors}")
        print(f"  Concurrent writes (100 ops) finished without locks: OK")

if __name__ == "__main__":
    unittest.main()
