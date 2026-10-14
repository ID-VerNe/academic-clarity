"""vendor/know 完整性基线测试（Phase 2）。

vendor 逐字拷贝禁改；本测试对 5 个 .py 算 sha256 钉基线。
任何 vendor 变更 = 整包替换 + 重新记基线（agents.md §6）。
基线来源：paper-tools@176ac7b1ec7ddc52cc05ada7a84b08c072bb6339
（know/ 目录，diff -q 逐字校验通过）。
"""
import os
import sys
import unittest
import hashlib

current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
VENDOR_KNOW = os.path.join(current, "backend", "vendor", "know")

BASELINE = {
    "anchors.py": "bfe7b2d7eca70b179ffcc7789d11b849a3a8c97d8d2d2fb86e277bf73aebe60a",
    "config.py": "4a5a0844ca740762fd0d322dd98ec285638d0b72e55f6558f70c3724efe4697a",
    "derive.py": "20db7d0a99657584423154b110862ec2fcdc98100167ab43f5ab0a5fe331f053",
    "identity.py": "7308156fa84b6e355cceb3415f22a4f94b1e8125da7f4e8b1aef547cb28e9764",
    "know.py": "548bd1e49debc0287079370131d64bdbbe8c881edd62c28cdb6c7cac44067795",
}

EXPECTED_FILES = set(BASELINE)


class TestVendorKnowIntegrity(unittest.TestCase):
    def test_exactly_five_modules_no_pycache(self):
        entries = set(os.listdir(VENDOR_KNOW))
        self.assertEqual(entries, EXPECTED_FILES,
                         f"vendor/know 应恰含 5 个 .py，实含: {sorted(entries)}")
        self.assertNotIn("__pycache__", entries)

    def test_sha256_baseline(self):
        for name, expected in BASELINE.items():
            with self.subTest(module=name):
                path = os.path.join(VENDOR_KNOW, name)
                self.assertTrue(os.path.exists(path), f"missing {name}")
                digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
                self.assertEqual(digest, expected,
                                 f"{name} 与基线不符——vendor 被改动？"
                                 f"若是 intentional 升级，整包替换并重记基线")

    def test_zero_third_party_imports(self):
        """know 五模块零第三方依赖（仅 stdlib）——python_embed 可直接运行。"""
        stdlib_ok = {"os", "sys", "json", "re", "sqlite3", "hashlib",
                     "unicodedata", "difflib", "datetime", "shutil", "argparse",
                     "pathlib", "typing", "collections", "functools", "itertools",
                     "textwrap", "dataclasses"}
        for name in BASELINE:
            src = open(os.path.join(VENDOR_KNOW, name), encoding="utf-8").read()
            for line in src.splitlines():
                line = line.strip()
                if line.startswith("import "):
                    mod = line.split()[1].split(".")[0]
                elif line.startswith("from ") and " import " in line:
                    mod = line.split()[1].split(".")[0]
                else:
                    continue
                if mod in ("anchors", "config", "derive", "identity", "know"):
                    continue  # 包内互引
                self.assertIn(mod, stdlib_ok,
                              f"{name} 引入非 stdlib 依赖: {mod}")


if __name__ == "__main__":
    unittest.main()
