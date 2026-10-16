"""extraction_export 单测（Phase 3 方案 §6）。

覆盖：flatten_record（标量/嵌套/None/列表）、sanitize_csv_cell、
build_csv（BOM/列并集排序/逗号引号换行转义）、build_markdown
（换行/竖线净化、分文档节、空结果集）、safe_filename。
"""
import os
import sys
import csv
import io
import json
import unittest

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path  # noqa: E402
add_backend_to_sys_path()

from services import extraction_export as ee  # noqa: E402

DIM = {"id": "abc123", "label": "Methodology", "prompt": "Extract the method."}

ROWS = [
    {"doc_id": 1, "filename": "a.pdf", "title": "Alpha", "created_at": "2026-10-15 08:00:00",
     "data": {"method": "X", "score": 1, "nested": {"k": "v"}, "tags": ["a", "b"]}},
    {"doc_id": 2, "filename": "b.pdf", "title": "Beta", "created_at": "2026-10-15 08:01:00",
     "data": {"method": "Y, with comma", "extra": "line1\nline2"}},
]


class TestFlattenRecord(unittest.TestCase):
    def test_scalars_and_none(self):
        self.assertEqual(ee.flatten_record({"a": 1, "b": 2.5, "c": None, "d": True}),
                         {"a": "1", "b": "2.5", "c": "", "d": "True"})

    def test_nested_compact_json(self):
        out = ee.flatten_record({"m": {"k": "v"}, "l": ["a", "b"]})
        self.assertEqual(out["m"], '{"k":"v"}')
        self.assertEqual(out["l"], '["a","b"]')

    def test_empty(self):
        self.assertEqual(ee.flatten_record({}), {})
        self.assertEqual(ee.flatten_record(None), {})


class TestSanitizeCsvCell(unittest.TestCase):
    def test_dangerous_prefixes_neutralized(self):
        for payload in ["=cmd|'/C calc'!A0", "+1", "-1", "@SUM(A1)", "\tX", "\rX"]:
            self.assertEqual(ee.sanitize_csv_cell(payload), "'" + payload)

    def test_safe_values_untouched(self):
        for v in ["hello", "1", "中文", "", None, "a=b"]:
            self.assertEqual(ee.sanitize_csv_cell(v),
                             "" if v is None else str(v))


class TestBuildCsv(unittest.TestCase):
    def test_bom_and_parseable(self):
        text = ee.build_csv(DIM, ROWS)
        self.assertTrue(text.startswith("\ufeff"))
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        self.assertEqual(parsed[0], ["doc_id", "filename", "title", "created_at",
                                     "extra", "method", "nested", "score", "tags"])

    def test_union_columns_and_missing_cells_empty(self):
        text = ee.build_csv(DIM, ROWS)
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        row1, row2 = parsed[1], parsed[2]
        self.assertEqual(len(row1), len(parsed[0]))
        # row2 无 nested/score/tags → 空；row1 无 extra → 空
        idx = {c: i for i, c in enumerate(parsed[0])}
        self.assertEqual(row1[idx["extra"]], "")
        self.assertEqual(row2[idx["nested"]], "")

    def test_comma_quote_newline_escaped(self):
        rows = [{"doc_id": 1, "filename": 'q".pdf', "title": "T",
                 "created_at": "t", "data": {"v": 'he said "hi", ok\nnext'}}]
        text = ee.build_csv(DIM, rows)
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        self.assertEqual(parsed[1][-1], 'he said "hi", ok\nnext')

    def test_empty_rows_header_only(self):
        text = ee.build_csv(DIM, [])
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        self.assertEqual(len(parsed), 1)


class TestBuildMarkdown(unittest.TestCase):
    def test_structure_and_metadata(self):
        md = ee.build_markdown(DIM, ROWS)
        self.assertIn("# 导出报告：Methodology", md)
        self.assertIn("- dimension_id: `abc123`", md)
        self.assertIn("- 文档数: 2", md)
        self.assertIn("## a.pdf", md)
        self.assertIn("## b.pdf", md)
        self.assertIn("- **method**: X", md)
        self.assertIn('- **nested**: {"k":"v"}', md)

    def test_newline_and_pipe_sanitized(self):
        rows = [{"doc_id": 1, "filename": "a|b.pdf", "title": "T\nline",
                 "created_at": "t", "data": {"v": "x|y\nz"}}]
        md = ee.build_markdown(DIM, rows)
        self.assertIn("## a\\|b.pdf", md)
        self.assertIn("- **title**: T<br>line", md)
        self.assertIn("- **v**: x\\|y<br>z", md)

    def test_empty_rows(self):
        md = ee.build_markdown(DIM, [])
        self.assertIn("_无提取结果_", md)


class TestSafeFilename(unittest.TestCase):
    def test_sanitizes_and_keeps_chinese(self):
        self.assertEqual(ee.safe_filename("方法 提取", "csv"), "方法_提取.csv")

    def test_empty_fallback(self):
        self.assertEqual(ee.safe_filename("", "md"), "export.md")


if __name__ == "__main__":
    unittest.main()
