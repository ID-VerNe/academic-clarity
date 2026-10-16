import os
import sys
import threading
import unittest

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_db, remove_db_files  # noqa: E402
add_backend_to_sys_path()

from database import Database
from utils.security import secure_filename
from services.doi_service import _assert_safe_url, DoiServiceError, fetch_bibtex

class TestSecurityAndConcurrency(unittest.TestCase):
    def setUp(self):
        # 临时 DB 落系统 temp（ac_test_ 前缀，调度器可清理）
        self.db_path = make_temp_db("ac_test_audit")

    def tearDown(self):
        remove_db_files(self.db_path)

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

    def test_wal_mode_enabled(self):
        # 行为分段：WAL 日志模式检查
        print("\n[Test] WAL Journal Mode...")
        db = Database(self.db_path)

        with db.get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
            print(f"  Journal Mode is WAL: OK")

    def test_concurrent_writes_no_locks(self):
        # 行为分段：并发写无锁错误
        print("\n[Test] Database Concurrency (WAL & Timeout)...")
        db = Database(self.db_path)

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


class TestDoiSsrF(unittest.TestCase):
    """Phase 1：DOI 服务 SSRF 防线。

    威胁模型：LLM 返回的 DOI 不可信，若直接拼进 URL 可把请求导向
    内网/恶意主机。防线 = URL 主机名字面量白名单（_assert_safe_url）
    + quote(safe='') 全编码。本类验证两层都不可绕过。
    """

    BLOCKED = [
        "http://api.crossref.org/works/10.1234/abc",             # 非 https
        "https://evil.com/works/10.1234/abc",                    # 异机
        "https://api.crossref.org.evil.com/works/10.1234/abc",   # 后缀混淆
        "https://api.crossref.org@evil.com/works/10.1234/abc",   # userinfo 戏法
        "https://user:pass@api.crossref.org/works/10.1234/abc",  # 带凭据
        "https://127.0.0.1/works/10.1234/abc",                   # 回环
        "https://localhost/works/10.1234/abc",                   # 本机名
        "https://169.254.169.254/latest/meta-data/",             # 云元数据
        "ftp://api.crossref.org/works/10.1234/abc",              # 异协议
        "https://API.CROSSREF.ORG/works/10.1234/abc",            # 大写主机名（应放行）
    ]

    def test_host_whitelist(self):
        for url in self.BLOCKED:
            with self.subTest(url=url):
                if url.endswith("API.CROSSREF.ORG/works/10.1234/abc"):
                    _assert_safe_url(url)  # 大小写不敏感 → 放行
                else:
                    with self.assertRaises(DoiServiceError):
                        _assert_safe_url(url)

    def test_crafted_doi_cannot_redirect_request(self):
        """恶意 DOI（含 @ / .. / 反斜杠）经 quote(safe='') 后主机不变；
        含 ?/# 的则被 DOI_RE 直接拒（fetch_bibtex 抛 DoiServiceError）。"""
        from unittest.mock import patch, MagicMock

        class _Db:
            def get_config(self, k, d=""):
                return d

        # 通过 DOI_RE 的载荷：验证 quote 后主机仍为 api.crossref.org
        pass_through = ["10.1234/@evil.com", "10.1234/..%2F..%2Fetc",
                        "10.1234/a\\b", "10.1234/x#y".replace("#", "")]
        for doi in pass_through:
            with self.subTest(doi=doi):
                resp = MagicMock()
                resp.read.return_value = b"@article{x}"
                resp.__enter__.return_value = resp
                resp.__exit__.return_value = False
                with patch("urllib.request.urlopen", MagicMock(return_value=resp)) as m:
                    fetch_bibtex(doi, db=_Db())
                    req = m.call_args[0][0]
                    self.assertEqual(req.host, "api.crossref.org")
                    self.assertTrue(req.full_url.startswith(
                        "https://api.crossref.org/works/"))

        # 含 ? / # 的载荷：DOI_RE 拒绝 → DoiServiceError，根本不出网
        for doi in ["10.1234/abc?redirect=https://evil.com",
                    "10.1234/abc#frag"]:
            with self.subTest(doi=doi):
                with patch("urllib.request.urlopen") as m:
                    with self.assertRaises(DoiServiceError):
                        fetch_bibtex(doi, db=_Db())
                    self.assertFalse(m.called)


if __name__ == "__main__":
    unittest.main()
