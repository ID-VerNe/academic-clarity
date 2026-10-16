"""knowledge_store — know 知识库基础设施（B-SRP-13 拆分）。

vendor/know 入 sys.path（平铺 import：import anchors，禁改 vendor）、
{workspace}/knowledge 定位、连接工厂（busy_timeout 走 DBConfig，B-DRY-20）
与读写 contextmanager（B-DRY-16：消除 conn=_conn()+try/finally 样板）。
全局状态 _WORKSPACE 由 init_store 记录；_kb_path 据此定位。
"""
import os
import sys
import threading
from contextlib import contextmanager

try:
    from backend.constants import DBConfig
except ImportError:
    from constants import DBConfig

# vendor/know 入 sys.path（平铺 import：import anchors，禁改 vendor）
_VENDOR_KNOW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor", "know")
if os.path.exists(_VENDOR_KNOW) and _VENDOR_KNOW not in sys.path:
    sys.path.insert(0, _VENDOR_KNOW)
import config as know_config  # noqa: E402

KNOW_DB_NAME = "index.sqlite"     # {workspace}/knowledge/index.sqlite

_write_lock = threading.Lock()    # knowledge DB 单写者
_WORKSPACE = None                 # init_store 记录；_kb_path 据此定位


def init_store(workspace_path: str) -> None:
    """lifespan/workspace 切换时调用：建 {workspace}/knowledge/ + init_db。"""
    global _WORKSPACE
    _WORKSPACE = workspace_path
    os.makedirs(_kb_path(), exist_ok=True)
    _conn().close()


def _kb_path() -> str:
    if not _WORKSPACE:
        raise RuntimeError("knowledge_store not initialized (call init_store)")
    return os.path.join(_WORKSPACE, "knowledge")


def _conn():
    """vendor init_db（幂等建表）+ busy_timeout（vendor 未设，防锁）。"""
    conn = know_config.init_db(os.path.join(_kb_path(), KNOW_DB_NAME))
    conn.execute(f"PRAGMA busy_timeout={DBConfig.BUSY_TIMEOUT}")
    return conn


@contextmanager
def _read_conn():
    """只读连接生命周期（conn=_conn() + try/finally close 样板收敛）。"""
    conn = _conn()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _write_conn():
    """单写锁 + 连接生命周期；commit 由调用方在块内显式执行。"""
    with _write_lock:
        conn = _conn()
        try:
            yield conn
        finally:
            conn.close()
