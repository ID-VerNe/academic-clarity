"""Phase 0 真实 LLM E2E：.tex/.zip 上传 → tex workflow → 真实 LLM Basic Insight。

默认跳过；设置 AC_E2E_LLM=1 且存在 test/key.json（用户本机 LLM 代理配置）时运行。
启动真实 server 子进程（非 TestClient），走完整 HTTP 链路。
"""
import os
import sys
import io
import json
import uuid
import zipfile
import unittest
import urllib.error

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path  # noqa: E402
ROOT_DIR = os.path.dirname(add_backend_to_sys_path())
from e2e_llm_harness import LlmE2eHarness, load_key, proxy_reachable  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(ROOT_DIR, "test", "key.json")

REAL_TEX = (
    "\\documentclass{article}\n"
    "\\title{Anchor Stability in OCR-Anchored Knowledge Bases}\n"
    "\\author{Alice Zhang and Bob Li}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{abstract}\n"
    "We study how paragraph-level content hashes behave under repeated OCR passes.\n"
    "Our experiments show that fewer than five percent of paragraphs drift between passes.\n"
    "\\end{abstract}\n"
    "\\section{Introduction}\n"
    "Knowledge anchoring requires stable paragraph identities across re-OCR runs.\n"
    "Prior work relies on fuzzy matching, which degrades on short paragraphs.\n"
    "\\section{Method}\n"
    "We compute a sha1-8 digest over the NFKC-normalized paragraph text.\n"
    "Anchors resolve exactly when the digest matches, and approximately otherwise.\n"
    "\\end{document}\n"
)
REAL_TEX_WITH_INPUT = REAL_TEX.replace(
    "\\end{document}", "\\input{related}\n\\end{document}"
)
RELATED_TEX = "\\section{Related Work}\nClaim anchoring was introduced by the know package.\n"


@unittest.skipUnless(os.environ.get("AC_E2E_LLM") == "1", "set AC_E2E_LLM=1 to run real LLM e2e")
class TestTexRealLlmE2E(unittest.TestCase):
    def setUp(self):
        self.key = load_key(KEY_FILE)
        if not self.key:
            self.skipTest("test/key.json not found")
        # 断网/代理未启动时降级 SKIP 而非 FAIL：先探测 TCP 可达，再起 server
        if not proxy_reachable(self.key["url"]):
            self.skipTest(f"LLM proxy unreachable: {self.key['url']}")
        self.ws = os.path.join(BASE_DIR, f"test_ws_tex_e2e_{uuid.uuid4().hex}")
        os.makedirs(self.ws)
        self.h = LlmE2eHarness(ROOT_DIR, self.ws, self.key)
        self.h.start()

    def tearDown(self):
        self.h.stop()

    # ── helpers ──────────────────────────────────────────────

    def _assert_real_insight(self, metas):
        """断言 Basic Insight 是真实 LLM 产物（而非 error JSON 落库）。"""
        basic = [m for m in metas if m["label"] == "Basic Insight"]
        self.assertEqual(len(basic), 1, f"no Basic Insight: {metas}")
        insight = json.loads(basic[0]["content_json"])
        self.assertNotIn("error", insight, f"LLM call failed: {insight}")
        return insight

    # ── tests ────────────────────────────────────────────────

    def test_single_tex_full_flow_with_real_llm(self):
        doc_id = self.h.upload("e2e_paper.tex", REAL_TEX.encode("utf-8"))["doc_id"]
        doc = self.h.wait_doc(doc_id, with_basic_insight=True)
        self.assertEqual(doc["ocr_status"], "completed")
        self.assertIn("# Introduction", doc["ocr_markdown"])
        self.assertEqual(doc["title"], "Anchor Stability in OCR-Anchored Knowledge Bases")
        _, metas = self.h.req("GET", f"/documents/{doc_id}/metadata")
        insight = self._assert_real_insight(metas)
        self.assertTrue(insight.get("title"), "real LLM returned empty title")

    def test_arxiv_style_zip_full_flow_with_real_llm(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("arxiv-src/main.tex", REAL_TEX_WITH_INPUT)
            zf.writestr("arxiv-src/related.tex", RELATED_TEX)
        doc_id = self.h.upload("e2e_src.zip", buf.getvalue())["doc_id"]
        doc = self.h.wait_doc(doc_id, with_basic_insight=True)
        self.assertEqual(doc["ocr_status"], "completed")
        self.assertIn("# Introduction", doc["ocr_markdown"])
        self.assertIn("# Related Work", doc["ocr_markdown"])   # \input 已展开
        _, metas = self.h.req("GET", f"/documents/{doc_id}/metadata")
        self._assert_real_insight(metas)

    def test_non_utf8_tex_fails_with_readable_error(self):
        # 真正的 latin-1 字节（0xE9）：严格 UTF-8 读取必失败
        content = (
            "\\begin{document}\n\\section{Caf\xe9 Latin}\nText.\n\\end{document}\n"
        ).encode("latin-1")
        doc_id = self.h.upload("e2e_latin.tex", content)["doc_id"]
        doc = self.h.wait_doc(doc_id, status="failed", timeout=120)
        self.assertEqual(doc["ocr_status"], "failed")

    def test_unsupported_ext_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.h.upload("e2e_evil.exe", b"MZ")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
