"""database — SQLite 持久层门面（B-SRP-10 拆分）。

DDL/迁移/pragma 在 db/schema.py；列表/详情查询与视图组装在 db/queries.py；
本模块保留 Database 类（连接管理、safe_write、CRUD、fetch 工具），
方法签名与返回字段对既有调用方保持不变。
"""
import json
import sqlite3
import threading
from contextlib import contextmanager

from db.queries import get_all_documents as _query_all_documents
from db.queries import get_document as _query_document
from db.schema import apply_pragmas, create_schema

try:
    from backend.constants import DBConfig, MetadataConfig
except ImportError:
    from constants import DBConfig, MetadataConfig


class Database:
    _write_lock = threading.Lock()

    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=DBConfig.TIMEOUT)
        apply_pragmas(conn)   # WAL + busy_timeout（B-DRY-20，仅此一处执行）
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
            create_schema(cursor)

    # ── fetch 工具（B-DRY-11：查询样板统一在此）────────────────

    def fetch_all(self, sql, params=()):
        """查询多行 → list[dict]（row_factory + dict(row) 样板收敛）。"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def fetch_one(self, sql, params=()):
        """查询单行 → dict | None。"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def _update_columns(self, table, row_id, fields):
        """动态 SET 更新（B-DRY-10）：None 值跳过；全 None → no-op。"""
        updates, params = [], []
        for column, value in fields.items():
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value)
        if not updates:
            return
        params.append(row_id)
        with self.safe_write() as cursor:
            cursor.execute(f"UPDATE {table} SET {', '.join(updates)} WHERE id = ?", params)

    # ── document_metadata ──────────────────────────────────────

    def add_document_metadata(self, doc_id, label, content_json, dimension_id=None):
        with self.safe_write() as cursor:
            cursor.execute('INSERT INTO document_metadata (doc_id, label, content_json, dimension_id) VALUES (?, ?, ?, ?)',
                         (doc_id, label, content_json, dimension_id))
            return cursor.lastrowid

    def get_document_metadata(self, doc_id):
        return self.fetch_all(
            'SELECT * FROM document_metadata WHERE doc_id = ? ORDER BY created_at DESC', (doc_id,))

    def delete_metadata(self, metadata_id):
        with self.safe_write() as cursor:
            cursor.execute('DELETE FROM document_metadata WHERE id = ?', (metadata_id,))

    def delete_metadata_by_dimension(self, doc_id, dimension_id):
        """Phase 3：force 重跑前清理该文档该维度的旧结果。"""
        with self.safe_write() as cursor:
            cursor.execute('DELETE FROM document_metadata WHERE doc_id = ? AND dimension_id = ?',
                           (doc_id, dimension_id))

    def get_basic_insight(self, doc_id):
        """最新 Basic Insight 的解析结果（B-DRY-13：label 查找 + JSON 容错）。

        无行 / JSON 损坏 / 非对象 → None（不抛）；label 走 MetadataConfig。
        """
        row = self.fetch_one(
            'SELECT content_json FROM document_metadata WHERE doc_id = ? AND label = ? '
            'ORDER BY created_at DESC LIMIT 1', (doc_id, MetadataConfig.DEFAULT_LABEL))
        if not row:
            return None
        try:
            data = json.loads(row["content_json"])
        except (json.JSONDecodeError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    # ── configs ────────────────────────────────────────────────

    def get_config(self, key, default=None):
        row = self.fetch_one('SELECT value FROM configs WHERE key = ?', (key,))
        return row["value"] if row else default

    def set_config(self, key, value):
        with self.safe_write() as cursor:
            cursor.execute('INSERT OR REPLACE INTO configs (key, value) VALUES (?, ?)', (key, value))

    # ── documents ──────────────────────────────────────────────

    def add_document(self, filename, original_path, stored_path):
        with self.safe_write() as cursor:
            cursor.execute('''
                INSERT INTO documents (filename, original_path, stored_path)
                VALUES (?, ?, ?)
            ''', (filename, original_path, stored_path))
            return cursor.lastrowid

    def update_document_ocr(self, doc_id, status, markdown=None, raw=None, title=None, metadata_json=None):
        fields = {"ocr_status": status, "ocr_markdown": markdown, "ocr_raw": raw,
                  "title": title, "metadata_json": metadata_json}
        self._update_columns("documents", doc_id,
                             {k: v for k, v in fields.items() if v})

    def update_document_doi(self, doc_id, doi=None, doi_source=None, bibtex=None):
        """Phase 1：动态 SET 写入 doi/doi_source/bibtex（仿 update_document_ocr）。"""
        self._update_columns("documents", doc_id,
                             {"doi": doi, "doi_source": doi_source, "bibtex": bibtex})

    def delete_document(self, doc_id):
        with self.safe_write() as cursor:
            cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            return cursor.rowcount > 0

    def get_document(self, doc_id):
        with self.get_connection() as conn:
            return _query_document(conn, doc_id)

    def get_all_documents(self):
        with self.get_connection() as conn:
            return _query_all_documents(conn)

    # ── extraction_dimensions CRUD（B-SRP-14，供 extraction_service）──

    def list_dimensions(self):
        return self.fetch_all("SELECT * FROM extraction_dimensions ORDER BY created_at, id")

    def get_dimension(self, dimension_id):
        return self.fetch_one("SELECT * FROM extraction_dimensions WHERE id = ?", (dimension_id,))

    def save_dimension(self, dimension_id, label, prompt, system_prompt, enabled):
        """upsert；label 冲突抛 sqlite3.IntegrityError（由 service 层转领域异常）。"""
        with self.safe_write() as cursor:
            cursor.execute('''
                INSERT INTO extraction_dimensions
                    (id, label, prompt, system_prompt, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    label=excluded.label, prompt=excluded.prompt,
                    system_prompt=excluded.system_prompt, enabled=excluded.enabled,
                    updated_at=CURRENT_TIMESTAMP
            ''', (dimension_id, label, prompt, system_prompt, enabled))

    def delete_dimension(self, dimension_id):
        with self.safe_write() as cursor:
            cursor.execute("DELETE FROM extraction_dimensions WHERE id = ?", (dimension_id,))
            return cursor.rowcount > 0
