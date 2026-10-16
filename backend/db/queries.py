"""db.queries — 列表/详情查询与视图组装（B-SRP-10 拆分）。

ocr_structured_json 视图字段组装在此（持久层不再 import text_processor）；
Basic Insight label 走 MetadataConfig 参数绑定（B-DRY-12），
LEFT JOIN + HAVING 语义与原实现一致。
"""
import sqlite3

from utils.text_processor import parse_structured_ocr_content

try:
    from backend.constants import MetadataConfig
except ImportError:
    from constants import MetadataConfig


def get_document(conn, doc_id):
    """单文档详情 + ocr_structured_json 视图字段。"""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    if not row:
        return None
    doc = dict(row)
    doc["ocr_structured_json"] = parse_structured_ocr_content(doc.get("ocr_markdown"))
    return doc


def get_all_documents(conn):
    """全量列表 + 最新 Basic Insight 回填 + ocr_structured_json 视图字段。"""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, m.content_json as basic_insight_json
        FROM documents d
        LEFT JOIN (
            SELECT doc_id, content_json
            FROM document_metadata
            WHERE label = ?
            GROUP BY doc_id
            HAVING MAX(created_at)
        ) m ON d.id = m.doc_id
        ORDER BY d.added_at DESC
    ''', (MetadataConfig.DEFAULT_LABEL,))
    documents = [dict(row) for row in cursor.fetchall()]
    for doc in documents:
        doc["ocr_structured_json"] = parse_structured_ocr_content(doc.get("ocr_markdown"))
    return documents
