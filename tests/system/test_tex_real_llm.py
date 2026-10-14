"""Phase 0 真实 LLM E2E：.tex/.zip 上传 → tex workflow → 真实 LLM Basic Insight。

默认跳过；设置 AC_E2E_LLM=1 且存在 test/key.json（用户本机 LLM 代理配置）时运行。
启动真实 server 子进程（非 TestClient），走完整 HTTP 链路。
"""
import os
import sys
import io
import json
import time
import uuid
import socket
import shutil
import zipfile
import unittest
import urllib.request
import urllib.error
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
current = BASE_DIR
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
ROOT_DIR = current
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


def _load_key():
    if not os.path.exists(KEY_FILE):
        return None
    with open(KEY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@unittest.skipUnless(os.environ.get("AC_E2E_LLM") == "1", "set AC_E2E_LLM=1 to run real LLM e2e")
class TestTexRealLlmE2E(unittest.TestCase):
    def setUp(self):
        self.key = _load_key()
        if not self.key:
            self.skipTest("test/key.json not found")
        self.ws = os.path.join(BASE_DIR, f"test_ws_tex_e2e_{uuid.uuid4().hex}")
        os.makedirs(self.ws)
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc = subprocess.Popen(
            [os.path.join(ROOT_DIR, "python_embed", "python.exe"),
             os.path.join("backend", "server.py"), str(self.port), self.ws],
            cwd=ROOT_DIR,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self._wait_health()
        self._post_json("/configs", None, params=[
            ("key", "EXTRACT_API_KEY"), ("value", self.key["key"]),
        ])
        self._post_json("/configs", None, params=[
            ("key", "EXTRACT_API_BASE"), ("value", self.key["url"] + "/v1"),
        ])
        self._post_json("/configs", None, params=[
            ("key", "EXTRACT_MODEL_NAME"), ("value", "openai/" + self.key["model-llm"]),
        ])

    def tearDown(self):
        if getattr(self, "proc", None):
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "ws", None) and os.path.exists(self.ws):
            shutil.rmtree(self.ws, ignore_errors=True)

    # ── helpers ──────────────────────────────────────────────

    def _opener(self):
        # 绕过沙箱/系统 HTTP 代理，直连 127.0.0.1
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _req(self, method, path, data=None, params=None, timeout=60):
        url = self.base + path
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)
        req = urllib.request.Request(url, data=data, method=method)
        with self._opener().open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _get_docs_safe(self):
        """轮询用：容忍偶发超时/连接抖动，返回 None 表示本次失败。"""
        try:
            _, docs = self._req("GET", "/documents")
            return docs
        except Exception:
            return None

    def _post_json(self, path, body, params=None):
        data = json.dumps(body).encode() if body is not None else b"{}"
        return self._req("POST", path, data=data, params=params)

    def _wait_health(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                status, _ = self._req("GET", "/health", timeout=5)
                if status == 200:
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("server did not become healthy")

    def _upload(self, filename, content):
        boundary = "----ace2e" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            self.base + "/documents/add", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with self._opener().open(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _wait_doc(self, doc_id, status="completed", timeout=180, with_basic_insight=False):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            docs = self._get_docs_safe()
            if docs is not None:
                doc = next((d for d in docs if d["id"] == doc_id), None)
                if doc:
                    last = doc
                    if doc.get("ocr_status") == status:
                        if not with_basic_insight:
                            return doc
                        try:
                            _, metas = self._req("GET", f"/documents/{doc_id}/metadata")
                            if any(m["label"] == "Basic Insight" for m in metas):
                                return doc
                        except Exception:
                            pass
            time.sleep(1.0)
        raise AssertionError(f"doc {doc_id} never reached {status}: last={last}")

    def _assert_real_insight(self, metas):
        """断言 Basic Insight 是真实 LLM 产物（而非 error JSON 落库）。"""
        basic = [m for m in metas if m["label"] == "Basic Insight"]
        self.assertEqual(len(basic), 1, f"no Basic Insight: {metas}")
        insight = json.loads(basic[0]["content_json"])
        self.assertNotIn("error", insight, f"LLM call failed: {insight}")
        return insight

    # ── tests ────────────────────────────────────────────────

    def test_single_tex_full_flow_with_real_llm(self):
        doc_id = self._upload("e2e_paper.tex", REAL_TEX.encode("utf-8"))["doc_id"]
        doc = self._wait_doc(doc_id, with_basic_insight=True)
        self.assertEqual(doc["ocr_status"], "completed")
        self.assertIn("# Introduction", doc["ocr_markdown"])
        self.assertEqual(doc["title"], "Anchor Stability in OCR-Anchored Knowledge Bases")
        _, metas = self._req("GET", f"/documents/{doc_id}/metadata")
        insight = self._assert_real_insight(metas)
        self.assertTrue(insight.get("title"), "real LLM returned empty title")

    def test_arxiv_style_zip_full_flow_with_real_llm(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("arxiv-src/main.tex", REAL_TEX_WITH_INPUT)
            zf.writestr("arxiv-src/related.tex", RELATED_TEX)
        doc_id = self._upload("e2e_src.zip", buf.getvalue())["doc_id"]
        doc = self._wait_doc(doc_id, with_basic_insight=True)
        self.assertEqual(doc["ocr_status"], "completed")
        self.assertIn("# Introduction", doc["ocr_markdown"])
        self.assertIn("# Related Work", doc["ocr_markdown"])   # \input 已展开
        _, metas = self._req("GET", f"/documents/{doc_id}/metadata")
        self._assert_real_insight(metas)

    def test_non_utf8_tex_fails_with_readable_error(self):
        # 真正的 latin-1 字节（0xE9）：严格 UTF-8 读取必失败
        content = (
            "\\begin{document}\n\\section{Caf\xe9 Latin}\nText.\n\\end{document}\n"
        ).encode("latin-1")
        doc_id = self._upload("e2e_latin.tex", content)["doc_id"]
        doc = self._wait_doc(doc_id, status="failed", timeout=120)
        self.assertEqual(doc["ocr_status"], "failed")

    def test_unsupported_ext_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._upload("e2e_evil.exe", b"MZ")
        self.assertEqual(ctx.exception.code, 400)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
