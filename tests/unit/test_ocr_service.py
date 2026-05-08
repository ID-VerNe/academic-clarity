import sys
import os
import unittest
from PIL import Image

# Add backend to path for imports
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

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
