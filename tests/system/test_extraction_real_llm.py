"""Phase 3 真实 LLM E2E：.tex 摄入 → 建维度 → 批量提取 → 导出 CSV/MD。

默认跳过；设置 AC_E2E_LLM=1 且存在 test/key.json（用户本机 LLM 代理配置）时运行。
启动真实 server 子进程（非 TestClient），走完整 HTTP 链路。
复用 tex 摄入路径（免 OCR 模型依赖）；提取 LLM 走 EXTRACT_API_* 配置（调用层剥离
存量 'openai/' 前缀后打到代理）。
"""
import os
import sys
import uuid
import unittest

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path  # noqa: E402
ROOT_DIR = os.path.dirname(add_backend_to_sys_path())
from e2e_llm_harness import LlmE2eHarness, load_key, proxy_reachable  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(ROOT_DIR, "test", "key.json")

REAL_TEX = (
    "\\documentclass{article}\n"
    "\\title{Batch Extraction over Anchored Papers}\n"
    "\\author{Carol Wu}\n"
    "\\begin{document}\n"
    "\\maketitle\n"
    "\\begin{abstract}\n"
    "We present a batch extraction pipeline for OCR-ingested papers.\n"
    "\\end{abstract}\n"
    "\\section{Method}\n"
    "Our pipeline uses a three-stage design: ingestion, anchoring, and extraction.\n"
    "\\section{Experiments}\n"
    "We evaluate on a corpus of 120 papers against two baseline systems.\n"
    "\\end{document}\n"
)

DIM_LABEL = "E2E Core Method"
DIM_PROMPT = (
    'Extract the paper core method and evaluation corpus size. '
    'Return JSON: {"method": "<one sentence>", "corpus_size": <number>}'
)


@unittest.skipUnless(os.environ.get("AC_E2E_LLM") == "1", "set AC_E2E_LLM=1 to run real LLM e2e")
class TestExtractionRealLlmE2E(unittest.TestCase):
    def setUp(self):
        self.key = load_key(KEY_FILE)
        if not self.key:
            self.skipTest("test/key.json not found")
        # 断网/代理未启动时降级 SKIP 而非 FAIL：先探测 TCP 可达，再起 server
        if not proxy_reachable(self.key["url"]):
            self.skipTest(f"LLM proxy unreachable: {self.key['url']}")
        self.ws = os.path.join(BASE_DIR, f"test_ws_ext_e2e_{uuid.uuid4().hex}")
        os.makedirs(self.ws)
        self.h = LlmE2eHarness(ROOT_DIR, self.ws, self.key)
        self.h.start()

    def tearDown(self):
        self.h.stop()

    # ── tests ────────────────────────────────────────────────

    def test_extraction_batch_export_full_flow_with_real_llm(self):
        # 1. .tex 摄入（tex 路径免 OCR 模型依赖）
        doc_id = self.h.upload("e2e_extract.tex", REAL_TEX.encode("utf-8"))["doc_id"]
        doc = self.h.wait_doc(doc_id, status="completed", timeout=180)
        self.assertIn("# Method", doc["ocr_markdown"])

        # 2. 建维度
        _, resp = self.h.post_json("/extraction/dimensions", {
            "label": DIM_LABEL, "prompt": DIM_PROMPT, "enabled": True,
        })
        self.assertTrue(resp["success"])
        dim_id = resp["dimension"]["id"]
        self.assertTrue(dim_id, "dimension id should be generated")

        # 3. 批量入队（fresh workspace：1 篇候选，0 跳过）
        _, batch = self.h.post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": False,
        })
        self.assertEqual(batch["queued"], 1, f"batch={batch}")
        self.assertEqual(batch["skipped"], 0, f"batch={batch}")

        # 4. 等真实 LLM 提取落库（error-JSON 会转异常重试，不应落库）
        data = self.h.wait_extraction(doc_id, DIM_LABEL)
        self.assertNotIn("error", data, f"LLM call failed: {data}")
        self.assertIsInstance(data, dict)
        self.assertTrue(data, "empty extraction result")

        # 5. 导出 CSV：BOM + CRLF + 文件名列
        status, headers, csv_text = self.h.req_text("/documents/export", params=[
            ("dimension_id", dim_id), ("format", "csv")])
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers.get("Content-Type", ""))
        self.assertTrue(csv_text.startswith("\ufeff"), "CSV must start with UTF-8 BOM")
        self.assertIn("e2e_extract.tex", csv_text)
        self.assertGreaterEqual(csv_text.count("\r\n"), 2, "header + 1 data row expected")

        # 6. 导出 MD：标题 + 文档节
        status, headers, md = self.h.req_text("/documents/export", params=[
            ("dimension_id", dim_id), ("format", "md")])
        self.assertEqual(status, 200)
        self.assertIn("text/markdown", headers.get("Content-Type", ""))
        self.assertTrue(md.startswith(f"# 导出报告：{DIM_LABEL}"), f"md head: {md[:80]}")
        self.assertIn("## e2e_extract.tex", md)
        self.assertIn("- **", md, "extracted fields should render as bullets")

        # 7. 断点续跑：无 force 重跑 → 全部跳过（不重复调 LLM）
        _, batch2 = self.h.post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": False,
        })
        self.assertEqual(batch2["queued"], 0, f"batch2={batch2}")
        self.assertEqual(batch2["skipped"], 1, f"batch2={batch2}")

    def test_force_rerun_replaces_result_with_real_llm(self):
        """force=True：先清旧行再重跑，结果仍为真实 LLM 产物。"""
        doc_id = self.h.upload("e2e_force.tex", REAL_TEX.encode("utf-8"))["doc_id"]
        self.h.wait_doc(doc_id, status="completed", timeout=180)

        _, resp = self.h.post_json("/extraction/dimensions", {
            "label": DIM_LABEL, "prompt": DIM_PROMPT, "enabled": True,
        })
        dim_id = resp["dimension"]["id"]

        _, b1 = self.h.post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": False})
        self.assertEqual(b1["queued"], 1, f"b1={b1}")
        self.h.wait_extraction(doc_id, DIM_LABEL)

        _, b2 = self.h.post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": True})
        self.assertEqual(b2["queued"], 1, f"force rerun should re-queue: {b2}")
        data = self.h.wait_extraction(doc_id, DIM_LABEL)
        self.assertNotIn("error", data, f"force rerun LLM failed: {data}")


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
