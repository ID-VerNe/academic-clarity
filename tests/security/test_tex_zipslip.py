"""tex zip-slip / 路径安全专项测试（Phase 0 一票否决项）。

恶意 zip（../ 穿越、绝对路径、盘符、符号链接、zip 炸弹、深层穿越）
与恶意 .tex（绝对路径 \\input 读本地文件）必须全部拒绝。
"""
import os
import sys
import unittest
import shutil
import zipfile

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_ws  # noqa: E402
add_backend_to_sys_path()

from services.tex_service import (  # noqa: E402
    TexConversionError,
    _safe_extract_zip,
    convert_tex,
    TexConfig,
)


class TestTexZipSlip(unittest.TestCase):
    def setUp(self):
        # 临时目录落系统 temp（ac_test_ 前缀，调度器可清理）
        self.tmp = make_temp_ws("ac_test_tex_sec")
        self.dest = os.path.join(self.tmp, "dest")
        os.makedirs(self.dest)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_zip(self, name, entries):
        """entries: list of (arcname, content) 或 (arcname, content, external_attr)"""
        path = os.path.join(self.tmp, name)
        with zipfile.ZipFile(path, "w") as zf:
            for entry in entries:
                if len(entry) == 3:
                    arcname, content, attr = entry
                    zi = zipfile.ZipInfo(arcname)
                    zi.external_attr = attr
                    zf.writestr(zi, content)
                else:
                    zf.writestr(entry[0], entry[1])
        return path

    def test_parent_traversal_entry_rejected(self):
        zip_path = self._make_zip("slip1.zip", [("../evil.tex", "pwned")])
        with self.assertRaises(TexConversionError) as ctx:
            _safe_extract_zip(zip_path, self.dest)
        self.assertIn("zip-slip", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil.tex")))

    def test_absolute_path_entry_rejected(self):
        for i, arc in enumerate(["/etc/evil.tex", "C:/Windows/evil.tex", "\\\\srv\\evil.tex"]):
            zip_path = self._make_zip(f"abs{i}.zip", [(arc, "pwned")])
            with self.assertRaises(TexConversionError):
                _safe_extract_zip(zip_path, self.dest)

    def test_symlink_entry_not_materialized(self):
        # external_attr 高 16 位 0o120000 = 符号链接
        zip_path = self._make_zip("symlink.zip", [
            ("link.tex", "/etc/passwd", (0o120777 << 16)),
        ])
        with self.assertRaises(TexConversionError):
            _safe_extract_zip(zip_path, self.dest)
        self.assertFalse(os.path.islink(os.path.join(self.dest, "link.tex")))

    def test_zip_bomb_rejected(self):
        big = "A" * 1024
        entries = [(f"filler_{i}.txt", big) for i in range(400)]  # ~400KB
        zip_path = self._make_zip("bomb.zip", entries)
        old = TexConfig.MAX_ZIP_TOTAL_BYTES
        TexConfig.MAX_ZIP_TOTAL_BYTES = 100 * 1024
        try:
            with self.assertRaises(TexConversionError) as ctx:
                _safe_extract_zip(zip_path, self.dest)
            self.assertIn("总量超限", str(ctx.exception))
        finally:
            TexConfig.MAX_ZIP_TOTAL_BYTES = old

    def test_deep_nested_traversal_rejected(self):
        zip_path = self._make_zip("deep.zip", [("a/b/../../../../evil.tex", "pwned")])
        with self.assertRaises(TexConversionError):
            _safe_extract_zip(zip_path, self.dest)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil.tex")))

    def test_absolute_input_ref_no_file_leak(self):
        """恶意 .tex 借绝对路径 \\input 读任意本地文件，必须拒绝且内容不外泄。"""
        secret = os.path.join(self.tmp, "secret.txt")
        with open(secret, "w", encoding="utf-8") as f:
            f.write("SECRET-MARKER-XYZ\n")
        evil = os.path.join(self.tmp, "evil.tex")
        with open(evil, "w", encoding="utf-8") as f:
            f.write("\\begin{document}\n"
                    f"\\input{{{secret.replace(os.sep, '/')}}}\n"
                    "\\end{document}\n")
        with self.assertRaises(TexConversionError):
            convert_tex(evil)
        # 即使异常路径也确认内容未进入任何输出
        try:
            out = convert_tex(evil)
        except TexConversionError:
            out = ""
        self.assertNotIn("SECRET-MARKER-XYZ", out)


if __name__ == "__main__":
    unittest.main()
