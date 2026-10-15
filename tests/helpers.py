"""
Academic Clarity — Shared Test Infrastructure

统一提供：路径引导、临时资源生命周期、server TestClient 脚手架、轮询工具。

约定：
- 所有新建临时资源必须使用 "ac_test_" 前缀（调度器清理器依赖此前缀）。
- 临时 DB / workspace 默认落系统 temp 目录，避免污染仓库。
- 各测试文件引导样板（4 行）：

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from helpers import add_backend_to_sys_path
    add_backend_to_sys_path()
"""

import contextlib
import json
import os
import shutil
import socket
import sys
import tempfile
import time
import uuid

# ---------------------------------------------------------------- 路径引导


def find_repo_root(start=None):
    """从 start（默认调用方目录）向上查找含 backend/ 的仓库根；找不到返回 None。"""
    current = os.path.abspath(start or os.getcwd())
    while current:
        if os.path.exists(os.path.join(current, "backend")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None


def add_backend_to_sys_path(start=None):
    """动态发现 backend/ 并注入 sys.path；返回 backend 绝对路径。"""
    root = find_repo_root(start)
    if not root:
        raise RuntimeError("backend/ not found upward from: %s" % (start or os.getcwd()))
    backend = os.path.join(root, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    return backend


def add_vendor_know_to_sys_path(start=None):
    """在 backend 路径之上再注入 backend/vendor/know（know 移植测试专用）。"""
    backend = add_backend_to_sys_path(start)
    vendor_know = os.path.join(backend, "vendor", "know")
    if vendor_know not in sys.path:
        sys.path.insert(0, vendor_know)
    return vendor_know


# ---------------------------------------------------------------- 临时资源

# 统一前缀 + 历史前缀（清理兼容，勿在新代码中使用历史前缀）
TEMP_PREFIXES = (
    "ac_test_",
    "test_db_",
    "test_workspace_",
    "test_audit_",
    "test_ws_api_",
    "test_ws_tex",
    "test_ws_doi",
    "test_ws_know",
    "test_ws_know_sec",
    "test_ws_ext",
    "test_tex_unit_",
    "test_tex_sec_",
    "test_auto_ws_",
    "real_test_workspace_",
)


def make_temp_ws(prefix="ac_test_ws", base_dir=None):
    """创建唯一临时 workspace 目录（默认系统 temp），返回绝对路径。"""
    base = base_dir or tempfile.gettempdir()
    path = os.path.join(base, f"{prefix}_{uuid.uuid4().hex}")
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def make_temp_db(prefix="ac_test_db", base_dir=None):
    """返回唯一临时 SQLite 路径（文件尚未创建）。"""
    base = base_dir or tempfile.gettempdir()
    return os.path.abspath(os.path.join(base, f"{prefix}_{uuid.uuid4().hex}.db"))


def remove_db_files(db_path, retries=3):
    """删除 DB 及其 -wal/-shm 旁文件；Windows 句柄占用时短暂重试。"""
    for suffix in ("", "-wal", "-shm"):
        target = db_path + suffix
        for _ in range(retries):
            if not os.path.exists(target):
                break
            try:
                os.remove(target)
                break
            except PermissionError:
                time.sleep(0.2)
            except OSError:
                break


def _matches(name):
    return any(name.startswith(p) for p in TEMP_PREFIXES)


def _remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            os.remove(path)
        except OSError:
            pass


def cleanup_temp_artifacts(roots):
    """递归清理 roots 下匹配 TEMP_PREFIXES 的条目（系统 temp 只扫一层）。

    返回删除条目数。供调度器与手动清理复用。
    """
    removed = 0
    system_temp = os.path.abspath(tempfile.gettempdir())
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        root_abs = os.path.abspath(root)
        if root_abs == system_temp:
            for name in os.listdir(root_abs):
                if _matches(name):
                    _remove_path(os.path.join(root_abs, name))
                    removed += 1
            continue
        for dirpath, dirnames, filenames in os.walk(root_abs, topdown=True):
            for name in list(dirnames):
                if _matches(name):
                    _remove_path(os.path.join(dirpath, name))
                    dirnames.remove(name)
                    removed += 1
            for name in filenames:
                if _matches(name):
                    _remove_path(os.path.join(dirpath, name))
                    removed += 1
    return removed


# ---------------------------------------------------------------- 通用工具


def poll_until(predicate, timeout=15.0, interval=0.1):
    """轮询 predicate() 直至为真；超时返回 False。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def free_port():
    """获取一个空闲本地端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def seed_document(db, filename="paper.pdf", markdown="", insight=None, status="completed"):
    """建文档 → 置 OCR 状态/markdown → 可选写 Basic Insight。返回 doc_id。"""
    doc_id = db.add_document(filename, f"/orig/{filename}", f"/stored/{filename}")
    if markdown or status != "pending":
        db.update_document_ocr(doc_id, status, markdown=markdown or None)
    if insight is not None:
        db.add_document_metadata(doc_id, "Basic Insight", json.dumps(insight))
    return doc_id


# ---------------------------------------------------------------- server 脚手架


@contextlib.contextmanager
def server_test_client(port, module_ws):
    """伪 argv → 导入 server → TestClient lifespan → state 重指向。

    yield (client, state)。退出时关闭 lifespan（不删除 workspace）。
    注意：argv 必须在首次 `import server` 之前设置（本函数内部完成）。
    """
    old_argv = sys.argv
    sys.argv = [old_argv[0] if old_argv else "test", str(port), module_ws]
    try:
        from fastapi.testclient import TestClient  # noqa: E402
        import server as server_module  # noqa: E402

        server_module.state.initialize(module_ws)
        cm = TestClient(server_module.app)
        client = cm.__enter__()
        try:
            yield client, server_module.state
        finally:
            cm.__exit__(None, None, None)
    finally:
        sys.argv = old_argv


class FakeDb:
    """仅实现 get_config 的最小 DB 替身（doi_service / config_service 依赖）。"""

    def __init__(self, values=None):
        self.values = values or {}

    def get_config(self, key, default=None):
        return self.values.get(key, default)

    def set_config(self, key, value):
        self.values[key] = value
