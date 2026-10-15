import sqlite3
import os
import threading
from contextlib import contextmanager
from utils.text_processor import parse_structured_ocr_content

try:
    from backend.constants import DBConfig
except ImportError:
    from constants import DBConfig

class Database:
    _write_lock = threading.Lock()

    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=DBConfig.TIMEOUT)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @contextmanager
    def safe_write(self):
        """线程安全的写操作"""
        with Database._write_lock:
            conn = self.get_connection()
            try:
                cursor = conn.cursor()
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def init_db(self):
        with self.safe_write() as cursor:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER,
                    label TEXT,
                    content_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doc_id) REFERENCES documents (id)
                )
            ''')

            self._ensure_columns(cursor, "documents", {
                "doi": "TEXT",
                "doi_source": "TEXT",   # 'crossref' | 'llm' | NULL
                "bibtex": "TEXT",
            })

            # Phase 3：提取维度定义（label UNIQUE；id 为稳定键，label 可改名）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS extraction_dimensions (
                    id TEXT PRIMARY KEY,
                    label TEXT UNIQUE NOT NULL,
                    prompt TEXT NOT NULL,
                    system_prompt TEXT DEFAULT '',
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Phase 3：metadata 行关联维度（可空，旧行 NULL；Basic Insight 不填）
            self._ensure_columns(cursor, "document_metadata", {
                "dimension_id": "TEXT",
            })

    def _ensure_columns(self, cursor, table: str, columns: dict) -> None:
        """幂等加列（Phase 1 迁移）：已存在则跳过；只加列不删不改类型。"""
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def add_document_metadata(self, doc_id, label, content_json, dimension_id=None):
        with self.safe_write() as cursor:
            cursor.execute('INSERT INTO document_metadata (doc_id, label, content_json, dimension_id) VALUES (?, ?, ?, ?)',
                         (doc_id, label, content_json, dimension_id))
            return cursor.lastrowid

    def get_document_metadata(self, doc_id):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM document_metadata WHERE doc_id = ? ORDER BY created_at DESC', (doc_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_metadata(self, metadata_id):
        with self.safe_write() as cursor:
            cursor.execute('DELETE FROM document_metadata WHERE id = ?', (metadata_id,))

    def delete_metadata_by_dimension(self, doc_id, dimension_id):
        """Phase 3：force 重跑前清理该文档该维度的旧结果。"""
        with self.safe_write() as cursor:
            cursor.execute('DELETE FROM document_metadata WHERE doc_id = ? AND dimension_id = ?',
                           (doc_id, dimension_id))

    def update_document_doi(self, doc_id, doi=None, doi_source=None, bibtex=None):
        """Phase 1：动态 SET 写入 doi/doi_source/bibtex（仿 update_document_ocr）。"""
        with self.safe_write() as cursor:
            updates, params = [], []
            if doi is not None:
                updates.append("doi = ?")
                params.append(doi)
            if doi_source is not None:
                updates.append("doi_source = ?")
                params.append(doi_source)
            if bibtex is not None:
                updates.append("bibtex = ?")
                params.append(bibtex)
            if not updates:
                return
            params.append(doc_id)
            cursor.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = ?", params)

    def get_config(self, key, default=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM configs WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_config(self, key, value):
        with self.safe_write() as cursor:
            cursor.execute('INSERT OR REPLACE INTO configs (key, value) VALUES (?, ?)', (key, value))

    def add_document(self, filename, original_path, stored_path):
        with self.safe_write() as cursor:
            cursor.execute('''
                INSERT INTO documents (filename, original_path, stored_path)
                VALUES (?, ?, ?)
            ''', (filename, original_path, stored_path))
            return cursor.lastrowid

    def update_document_ocr(self, doc_id, status, markdown=None, raw=None, title=None, metadata_json=None):
        with self.safe_write() as cursor:
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

    def delete_document(self, doc_id):
        with self.safe_write() as cursor:
            cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            return cursor.rowcount > 0

    def get_document(self, doc_id):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
            row = cursor.fetchone()
            if not row:
                return None
            doc = dict(row)
            doc["ocr_structured_json"] = parse_structured_ocr_content(doc.get("ocr_markdown"))
            return doc

    def get_all_documents(self):
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT d.*, m.content_json as basic_insight_json
                FROM documents d
                LEFT JOIN (
                    SELECT doc_id, content_json
                    FROM document_metadata
                    WHERE label = 'Basic Insight'
                    GROUP BY doc_id
                    HAVING MAX(created_at)
                ) m ON d.id = m.doc_id
                ORDER BY d.added_at DESC
            ''')
            documents = [dict(row) for row in cursor.fetchall()]
            for doc in documents:
                doc["ocr_structured_json"] = parse_structured_ocr_content(doc.get("ocr_markdown"))
            return documents
