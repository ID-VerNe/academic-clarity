"""真实 LLM E2E 共享 harness（T-03）。

两个套件共用：test_tex_real_llm / test_extraction_real_llm。

- server 子进程生命周期：输出落盘（subprocess.PIPE 不读取会阻塞子进程写日志）
- HTTP：JSON / 文本 / multipart 上传（绕过系统代理直连 127.0.0.1）
- 轮询：health / doc 状态 / 提取结果落库（失败断言携带 server 日志尾部）
- 代理可达性探测：不可达 → 调用方 skipTest（断网时 SKIP 而非 FAIL）

用法：
    from helpers import add_backend_to_sys_path
    ROOT_DIR = os.path.dirname(add_backend_to_sys_path())
    key = load_key(os.path.join(ROOT_DIR, "test", "key.json"))

    def setUp(self):
        ...
        self.h = LlmE2eHarness(ROOT_DIR, self.ws, self.key)
        self.h.start()

    def tearDown(self):
        self.h.stop()
"""
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
import uuid
from urllib.parse import urlencode, urlsplit

from helpers import free_port


def load_key(key_file):
    """读 test/key.json（本机 LLM 代理配置）；不存在返回 None。"""
    if not os.path.exists(key_file):
        return None
    with open(key_file, encoding="utf-8") as f:
        return json.load(f)


def proxy_reachable(url):
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


class LlmE2eHarness:
    """server 子进程 + HTTP 客户端 + 轮询工具。"""

    def __init__(self, root_dir, ws, key, port=None):
        self.root_dir = root_dir
        self.ws = ws
        self.key = key
        self.port = port or free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log_path = os.path.join(ws, "server.log")
        self._log_f = None
        self._proc = None

    # ---------------------------------------------------------- 生命周期

    def start(self, health_timeout=60):
        """起 server 子进程 → 等健康 → 注入 EXTRACT_* 配置（打到本机代理）。"""
        self._log_f = open(self.log_path, "w", encoding="utf-8", errors="replace")
        self._proc = subprocess.Popen(
            [os.path.join(self.root_dir, "python_embed", "python.exe"),
             os.path.join("backend", "server.py"), str(self.port), self.ws],
            cwd=self.root_dir,
            stdout=self._log_f, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONUNBUFFERED="1"),
        )
        self.wait_health(timeout=health_timeout)
        self._inject_extract_config()

    def stop(self):
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._log_f:
            self._log_f.close()
        if self.ws and os.path.exists(self.ws):
            shutil.rmtree(self.ws, ignore_errors=True)

    def _inject_extract_config(self):
        # "openai/" 前缀由调用层（services/ai_service）在 HTTP 前剥离
        self.post_json("/configs", None, params=[
            ("key", "EXTRACT_API_KEY"), ("value", self.key["key"])])
        self.post_json("/configs", None, params=[
            ("key", "EXTRACT_API_BASE"), ("value", self.key["url"] + "/v1")])
        self.post_json("/configs", None, params=[
            ("key", "EXTRACT_MODEL_NAME"),
            ("value", "openai/" + self.key["model-llm"])])

    # ---------------------------------------------------------- 诊断

    def server_log_tail(self, n=4000):
        """失败诊断：server 日志尾部。"""
        try:
            with open(self.log_path, encoding="utf-8", errors="replace") as f:
                return f.read()[-n:]
        except OSError as e:
            return f"<server log unavailable: {e}>"

    # ---------------------------------------------------------- HTTP

    @staticmethod
    def _opener():
        # 绕过沙箱/系统 HTTP 代理，直连 127.0.0.1
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def req(self, method, path, data=None, params=None, timeout=60):
        url = self.base + path
        if params:
            url += "?" + urlencode(params)
        # 有 body 时必须声明 JSON——否则 FastAPI 拒绝解析（422）
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with self._opener().open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def req_text(self, path, params=None, timeout=60):
        """导出端点返回文本（非 JSON），单独走原始读取。"""
        url = self.base + path
        if params:
            url += "?" + urlencode(params)
        req = urllib.request.Request(url, method="GET")
        with self._opener().open(req, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8")

    def post_json(self, path, body, params=None):
        data = json.dumps(body).encode() if body is not None else b"{}"
        return self.req("POST", path, data=data, params=params)

    def upload(self, filename, content):
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

    # ---------------------------------------------------------- 轮询

    def wait_health(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                status, _ = self.req("GET", "/health", timeout=5)
                if status == 200:
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("server did not become healthy")

    def wait_doc(self, doc_id, status="completed", timeout=180,
                 with_basic_insight=False):
        """轮询 /documents 直到目标状态；with_basic_insight 时还要求 Basic Insight 落库。"""
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                _, docs = self.req("GET", "/documents")
            except Exception:
                time.sleep(1.0)
                continue
            doc = next((d for d in docs if d["id"] == doc_id), None)
            if doc:
                last = doc
                if doc.get("ocr_status") == status:
                    if not with_basic_insight:
                        return doc
                    try:
                        _, metas = self.req("GET", f"/documents/{doc_id}/metadata")
                        if any(m["label"] == "Basic Insight" for m in metas):
                            return doc
                    except Exception:
                        pass
            time.sleep(1.0)
        raise AssertionError(
            f"doc {doc_id} never reached {status} (with_basic_insight={with_basic_insight}): "
            f"last={last}\n--- server log tail ---\n{self.server_log_tail()}")

    def wait_extraction(self, doc_id, label, timeout=300):
        """轮询 metadata 直到维度结果落库，返回解析后的 JSON。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                _, metas = self.req("GET", f"/documents/{doc_id}/metadata")
                for m in metas:
                    if m.get("label") == label:
                        return json.loads(m["content_json"])
            except Exception:
                pass
            time.sleep(2.0)
        raise AssertionError(
            f"extraction '{label}' never appeared for doc {doc_id}\n"
            f"--- server log tail ---\n{self.server_log_tail()}")
