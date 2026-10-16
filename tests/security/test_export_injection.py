"""导出注入安全测试（Phase 3 方案 §6 / 风险 R3）。

威胁模型：提取结果来自 LLM（可被论文内容间接影响），导出物直接进
Excel/Sheets/Markdown 渲染器。防线：
- CSV 公式注入：= + - @ \\t \\r 前缀单元格加 ' 中和（OWASP CSV Injection）
- Markdown 结构注入：换行/竖线破坏报告结构
- Content-Disposition 文件名：../ 路径穿越 / 引号换行头注入
"""
import os
import sys
import csv
import io
import unittest

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path  # noqa: E402
add_backend_to_sys_path()

from services import extraction_export as ee  # noqa: E402

DIM = {"id": "sec1", "label": "Security", "prompt": "P"}


class TestCsvFormulaInjection(unittest.TestCase):
    PAYLOADS = [
        "=cmd|'/C calc'!A0",
        "=HYPERLINK(\"http://evil.example\",\"click\")",
        "+1+1",
        "-1+1",
        "@SUM(1+1)",
        "\t=1+1",
        "\r=1+1",
        "=1+1\n=2+2",
    ]

    def test_payloads_neutralized_in_output(self):
        rows = [{"doc_id": 1, "filename": "p.pdf", "title": "T", "created_at": "t",
                 "data": {"payload": p}} for p in self.PAYLOADS]
        text = ee.build_csv(DIM, rows)
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        col = parsed[0].index("payload")
        for i, payload in enumerate(self.PAYLOADS, start=1):
            cell = parsed[i][col]
            self.assertTrue(cell.startswith("'"),
                            f"未中和: {payload!r} → {cell!r}")
            # 中和后仍是原文本（除 ' 前缀），不丢数据
            self.assertEqual(cell, "'" + payload)

    def test_no_bare_dangerous_lead_in_any_cell(self):
        rows = [{"doc_id": "=1", "filename": "+2", "title": "@3", "created_at": "-4",
                 "data": {"a": "=x", "b": "\ty"}}]
        text = ee.build_csv(DIM, rows)
        parsed = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        for cell in parsed[1]:
            if cell:
                self.assertNotIn(cell[0], "=+-@\t\r",
                                 f"裸危险前缀未中和: {cell!r}")


class TestMarkdownStructureInjection(unittest.TestCase):
    def test_newlines_and_pipes_do_not_break_report(self):
        rows = [{"doc_id": 1, "filename": "a.pdf", "title": "T",
                 "created_at": "t",
                 "data": {"attack": "value\n\n# Fake Heading\n| fake | table |"}}]
        md = ee.build_markdown(DIM, rows)
        # 伪造标题/表格不产生真实结构（\n 已转 <br>）
        self.assertNotIn("\n# Fake Heading", md)
        self.assertNotIn("\n| fake |", md)
        self.assertIn("<br>", md)
        # 真实结构仍完好：H1 仅在首行、每文档一个 H2、无注入的第二个 H1
        self.assertTrue(md.startswith("# 导出报告：Security"))
        self.assertEqual(md.count("\n# "), 0)
        self.assertEqual(md.count("\n## "), 1)


class TestContentDispositionFilename(unittest.TestCase):
    PAYLOADS = [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "a\"; evil=\"x",
        "a\nb",
        "a\r\nContent-Type: text/html",
        "  ",
        "a;b;c",
    ]

    def test_path_traversal_and_header_injection_sanitized(self):
        for payload in self.PAYLOADS:
            with self.subTest(payload=payload):
                name = ee.safe_filename(payload, "csv")
                self.assertNotIn("/", name)
                self.assertNotIn("\\", name)
                self.assertNotIn('"', name)
                self.assertNotIn("\n", name)
                self.assertNotIn("\r", name)
                self.assertNotIn(";", name)
                self.assertTrue(name.endswith(".csv"))

    def test_empty_label_fallback(self):
        self.assertEqual(ee.safe_filename(None, "md"), "export.md")


if __name__ == "__main__":
    unittest.main()
