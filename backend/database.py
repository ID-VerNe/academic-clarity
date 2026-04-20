import sqlite3
import os

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        # Set busy timeout to 30,000ms
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        # Enable WAL mode
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Ensure WAL mode is active
            cursor.execute("PRAGMA journal_mode=WAL")
            # 配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # 文献表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
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
            
            # 兼容性升级
            cursor.execute("PRAGMA table_info(documents)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'ocr_raw' not in columns:
                cursor.execute("ALTER TABLE documents ADD COLUMN ocr_raw TEXT")
            if 'metadata_json' not in columns:
                cursor.execute("ALTER TABLE documents ADD COLUMN metadata_json TEXT")
                
            conn.commit()

    def get_config(self, key, default=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM configs WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_config(self, key, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO configs (key, value) VALUES (?, ?)', (key, value))
            conn.commit()

    def add_document(self, filename, original_path, stored_path):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents (filename, original_path, stored_path)
                VALUES (?, ?, ?)
            ''', (filename, original_path, stored_path))
            return cursor.lastrowid

    def update_document_ocr(self, doc_id, status, markdown=None, raw=None, title=None, metadata_json=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            updates = ["ocr_status = ?"]
            params = [status]
            
            if markdown: 
                updates.append("ocr_markdown = ?")
                params.append(markdown)
            if raw:
                updates.append("ocr_raw = ?")
                params.append(raw)
            if title:
                updates.append("title = ?")
                params.append(title)
            if metadata_json:
                updates.append("metadata_json = ?")
                params.append(metadata_json)
                
            params.append(doc_id)
            sql = f"UPDATE documents SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            
    def delete_document(self, doc_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_document(self, doc_id):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_documents(self):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM documents ORDER BY added_at DESC')
            return [dict(row) for row in cursor.fetchall()]
