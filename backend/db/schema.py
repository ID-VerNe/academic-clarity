"""db.schema — DDL、列迁移与连接 pragma（B-SRP-10 拆分）。

WAL 与 busy_timeout 统一接入 DBConfig（B-DRY-20）；pragma 只在
连接工厂执行一次（去除原 init_db 内的重复 WAL 执行）。
"""
try:
    from backend.constants import DBConfig
except ImportError:
    from constants import DBConfig


def apply_pragmas(conn) -> None:
    """连接级 pragma：WAL（DBConfig.WAL_MODE）与 busy_timeout（DBConfig.BUSY_TIMEOUT）。"""
    if DBConfig.WAL_MODE:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={DBConfig.BUSY_TIMEOUT}")


def create_schema(cursor) -> None:
    """建表 + 幂等迁移（原 init_db 的 DDL 部分）。"""
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

    _ensure_columns(cursor, "documents", {
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
    _ensure_columns(cursor, "document_metadata", {
        "dimension_id": "TEXT",
    })


def _ensure_columns(cursor, table: str, columns: dict) -> None:
    """幂等加列（Phase 1 迁移）：已存在则跳过；只加列不删不改类型。"""
    cursor.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for name, ddl in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
