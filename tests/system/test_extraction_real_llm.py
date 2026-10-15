"""Phase 3 真实 LLM E2E：.tex 摄入 → 建维度 → 批量提取 → 导出 CSV/MD。

默认跳过；设置 AC_E2E_LLM=1 且存在 test/key.json（用户本机 LLM 代理配置）时运行。
启动真实 server 子进程（非 TestClient），走完整 HTTP 链路。
复用 tex 摄入路径（免 OCR 模型依赖）；提取 LLM 走 EXTRACT_API_* 配置（调用层剥离
存量 'openai/' 前缀后打到代理）。
"""
import os
import sys
import json
import time
import uuid
import socket
import shutil
import unittest
import subprocess
import urllib.request
import urllib.error
from urllib.parse import urlencode, urlsplit

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


def _proxy_reachable(url):
    """TCP 探测 LLM 代理端口；url 解析失败或连不上返回 False。"""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        # url 形如 http://localhost:37210（不含 /v1），port 可能缺省
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return False
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


@unittest.skipUnless(os.environ.get("AC_E2E_LLM") == "1", "set AC_E2E_LLM=1 to run real LLM e2e")
class TestExtractionRealLlmE2E(unittest.TestCase):
    def setUp(self):
        self.key = _load_key()
        if not self.key:
            self.skipTest("test/key.json not found")
        # 断网/代理未启动时降级 SKIP 而非 FAIL：先探测 TCP 可达，再起 server
        if not _proxy_reachable(self.key["url"]):
            self.skipTest(f"LLM proxy unreachable: {self.key['url']}")
        self.ws = os.path.join(BASE_DIR, f"test_ws_ext_e2e_{uuid.uuid4().hex}")
        os.makedirs(self.ws)
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        # server 输出落盘而非 PIPE：未读 PIPE 写满后子进程阻塞在日志写入上；
        # 且失败时日志可用于诊断。
        self.log_path = os.path.join(self.ws, "server.log")
        self.log_f = open(self.log_path, "w", encoding="utf-8", errors="replace")
        self.proc = subprocess.Popen(
            [os.path.join(ROOT_DIR, "python_embed", "python.exe"),
             os.path.join("backend", "server.py"), str(self.port), self.ws],
            cwd=ROOT_DIR,
            stdout=self.log_f, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONUNBUFFERED="1"),
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
        if getattr(self, "log_f", None):
            self.log_f.close()
        if getattr(self, "ws", None) and os.path.exists(self.ws):
            shutil.rmtree(self.ws, ignore_errors=True)

    # ── helpers ──────────────────────────────────────────────

    def _server_log_tail(self, n=4000):
        """失败诊断：server 日志尾部。"""
        try:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                return f.read()[-n:]
        except OSError as e:
            return f"<server log unavailable: {e}>"

    def _opener(self):
        # 绕过沙箱/系统 HTTP 代理，直连 127.0.0.1
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _req(self, method, path, data=None, params=None, timeout=60):
        url = self.base + path
        if params:
            url += "?" + urlencode(params)
        # 有 body 时必须声明 JSON——否则 FastAPI 拒绝解析（422）
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with self._opener().open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def _req_text(self, path, params=None, timeout=60):
        """导出端点返回文本（非 JSON），单独走原始读取。"""
        url = self.base + path
        if params:
            url += "?" + urlencode(params)
        req = urllib.request.Request(url, method="GET")
        with self._opener().open(req, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8")

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

    def _wait_doc(self, doc_id, status="completed", timeout=180):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                _, docs = self._req("GET", "/documents")
            except Exception:
                time.sleep(1.0)
                continue
            doc = next((d for d in docs if d["id"] == doc_id), None)
            if doc:
                last = doc
                if doc.get("ocr_status") == status:
                    return doc
            time.sleep(1.0)
        raise AssertionError(
            f"doc {doc_id} never reached {status}: last={last}\n"
            f"--- server log tail ---\n{self._server_log_tail()}")

    def _wait_extraction(self, doc_id, label, timeout=300):
        """轮询 metadata 直到维度结果落库，返回解析后的 JSON。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                _, metas = self._req("GET", f"/documents/{doc_id}/metadata")
                for m in metas:
                    if m.get("label") == label:
                        return json.loads(m["content_json"])
            except Exception:
                pass
            time.sleep(2.0)
        raise AssertionError(
            f"extraction '{label}' never appeared for doc {doc_id}\n"
            f"--- server log tail ---\n{self._server_log_tail()}")

    # ── tests ────────────────────────────────────────────────

    def test_extraction_batch_export_full_flow_with_real_llm(self):
        # 1. .tex 摄入（tex 路径免 OCR 模型依赖）
        doc_id = self._upload("e2e_extract.tex", REAL_TEX.encode("utf-8"))["doc_id"]
        doc = self._wait_doc(doc_id, status="completed", timeout=180)
        self.assertIn("# Method", doc["ocr_markdown"])

        # 2. 建维度
        _, resp = self._post_json("/extraction/dimensions", {
            "label": DIM_LABEL, "prompt": DIM_PROMPT, "enabled": True,
        })
        self.assertTrue(resp["success"])
        dim_id = resp["dimension"]["id"]
        self.assertTrue(dim_id, "dimension id should be generated")

        # 3. 批量入队（fresh workspace：1 篇候选，0 跳过）
        _, batch = self._post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": False,
        })
        self.assertEqual(batch["queued"], 1, f"batch={batch}")
        self.assertEqual(batch["skipped"], 0, f"batch={batch}")

        # 4. 等真实 LLM 提取落库（error-JSON 会转异常重试，不应落库）
        data = self._wait_extraction(doc_id, DIM_LABEL)
        self.assertNotIn("error", data, f"LLM call failed: {data}")
        self.assertIsInstance(data, dict)
        self.assertTrue(data, "empty extraction result")

        # 5. 导出 CSV：BOM + CRLF + 文件名列
        status, headers, csv_text = self._req_text("/documents/export", params=[
            ("dimension_id", dim_id), ("format", "csv")])
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers.get("Content-Type", ""))
        self.assertTrue(csv_text.startswith("\ufeff"), "CSV must start with UTF-8 BOM")
        self.assertIn("e2e_extract.tex", csv_text)
        self.assertGreaterEqual(csv_text.count("\r\n"), 2, "header + 1 data row expected")

        # 6. 导出 MD：标题 + 文档节
        status, headers, md = self._req_text("/documents/export", params=[
            ("dimension_id", dim_id), ("format", "md")])
        self.assertEqual(status, 200)
        self.assertIn("text/markdown", headers.get("Content-Type", ""))
        self.assertTrue(md.startswith(f"# 导出报告：{DIM_LABEL}"), f"md head: {md[:80]}")
        self.assertIn("## e2e_extract.tex", md)
        self.assertIn("- **", md, "extracted fields should render as bullets")

        # 7. 断点续跑：无 force 重跑 → 全部跳过（不重复调 LLM）
        _, batch2 = self._post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": False,
        })
        self.assertEqual(batch2["queued"], 0, f"batch2={batch2}")
        self.assertEqual(batch2["skipped"], 1, f"batch2={batch2}")

    def test_force_rerun_replaces_result_with_real_llm(self):
        """force=True：先清旧行再重跑，结果仍为真实 LLM 产物。"""
        doc_id = self._upload("e2e_force.tex", REAL_TEX.encode("utf-8"))["doc_id"]
        self._wait_doc(doc_id, status="completed", timeout=180)

        _, resp = self._post_json("/extraction/dimensions", {
            "label": DIM_LABEL, "prompt": DIM_PROMPT, "enabled": True,
        })
        dim_id = resp["dimension"]["id"]

        _, b1 = self._post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": False})
        self.assertEqual(b1["queued"], 1, f"b1={b1}")
        self._wait_extraction(doc_id, DIM_LABEL)

        _, b2 = self._post_json("/extraction/batch", {
            "dimension_id": dim_id, "doc_ids": [], "force": True})
        self.assertEqual(b2["queued"], 1, f"force rerun should re-queue: {b2}")
        data = self._wait_extraction(doc_id, DIM_LABEL)
        self.assertNotIn("error", data, f"force rerun LLM failed: {data}")


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
