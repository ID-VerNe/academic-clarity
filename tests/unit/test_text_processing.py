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
from utils.text_processor import clean_ocr_markdown, extract_title_from_markdown

class TestTextProcessing(unittest.TestCase):
    def test_clean_ocr_markdown_removes_tags(self):
        raw = "<|ref|>image<|/ref|><|det|>1,2,3,4<|/det|> # Header"
        cleaned = clean_ocr_markdown(raw)
        self.assertEqual(cleaned, "# Header")

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

if __name__ == "__main__":
    unittest.main()
