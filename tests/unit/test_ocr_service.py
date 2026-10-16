import sys
import os
import unittest
from PIL import Image

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path  # noqa: E402
add_backend_to_sys_path()

from services.ocr_service import replace_image_tags_with_markdown


class TestOcrService(unittest.TestCase):
    def test_replace_image_tags_with_markdown_embeds_data_uri(self):
        image = Image.new("RGB", (100, 100), "white")
        raw = "<|ref|>image<|/ref|><|det|>[[0,0,999,999]]<|/det|>"
        converted = replace_image_tags_with_markdown(raw, image)
        self.assertIn("![](data:image/jpeg;base64,", converted)
        self.assertNotIn("<|ref|>", converted)
        self.assertNotIn("<|det|>", converted)

    def test_replace_image_tags_with_markdown_keeps_textual_ref(self):
        image = Image.new("RGB", (100, 100), "white")
        raw = "<|ref|>Figure 1 caption<|/ref|><|det|>[[0,0,999,999]]<|/det|>"
        converted = replace_image_tags_with_markdown(raw, image)
        self.assertEqual(converted, "Figure 1 caption")


if __name__ == "__main__":
    unittest.main()
