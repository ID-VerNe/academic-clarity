import sys
import os
import unittest

# Add backend to path for imports
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current: break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

# Updated import path after refactoring
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown, parse_structured_ocr_content

class TestTextProcessing(unittest.TestCase):
    def test_clean_ocr_markdown_removes_tags(self):
        # DeepSeek-OCR 格式: <|ref|>内容<|/ref|><|det|>坐标<|/det|>
        # 新逻辑：保留 ref 标签内的内容，删除 det 标签及坐标
        raw = "<|ref|>Title Text<|/ref|><|det|>1,2,3,4<|/det|> # Header"
        cleaned = clean_ocr_markdown(raw)
        self.assertEqual(cleaned, "Title Text # Header")

    def test_clean_ocr_markdown_replaces_latex(self):
        raw = r"\coloneqq \eqqcolon \approx"
        cleaned = clean_ocr_markdown(raw)
        self.assertEqual(cleaned, ":= =: ≈")

    def test_extract_title_from_markdown_h1(self):
        md = "# Actual Title\nSome content"
        title = extract_title_from_markdown(md)
        self.assertEqual(title, "Actual Title")

    def test_extract_title_from_markdown_fallback(self):
        md = "No H1 Header\nJust Text"
        title = extract_title_from_markdown(md)
        self.assertEqual(title, "No H1 Header")

    def test_parse_structured_ocr_content_parses_tagged_blocks(self):
        raw = "\n".join([
            "title",
            "A Review of P2P Energy Trading",
            "text Shama Naz Islam",
            "text Abstract: This paper reviews methods.",
            "sub_title",
            "1. Introduction",
            "text Distributed resources are growing."
        ])
        structured = parse_structured_ocr_content(raw)
        self.assertEqual(
            structured,
            {
                "version": 1,
                "blocks": [
                    {"type": "title", "text": "A Review of P2P Energy Trading"},
                    {"type": "text", "text": "Shama Naz Islam\nAbstract: This paper reviews methods."},
                    {"type": "subtitle", "text": "1. Introduction"},
                    {"type": "text", "text": "Distributed resources are growing."}
                ]
            }
        )

    def test_parse_structured_ocr_content_ignores_plain_markdown(self):
        raw = "# Markdown Title\n\nThis is plain markdown."
        structured = parse_structured_ocr_content(raw)
        self.assertEqual(structured, {"version": 1, "blocks": []})

    def test_parse_structured_ocr_content_handles_inline_tokens_and_heading_prefix(self):
        raw = "\n".join([
            "title",
            "# Smooth Q-Learning  text",
            "Author A · Author B  sub_title",
            "## Abstract  text",
            "Paragraph line."
        ])
        structured = parse_structured_ocr_content(raw)
        self.assertEqual(
            structured,
            {
                "version": 1,
                "blocks": [
                    {"type": "title", "text": "Smooth Q-Learning"},
                    {"type": "text", "text": "Author A · Author B"},
                    {"type": "subtitle", "text": "Abstract"},
                    {"type": "text", "text": "Paragraph line."}
                ]
            }
        )

if __name__ == "__main__":
    unittest.main()
