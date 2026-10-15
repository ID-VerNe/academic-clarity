"""Phase 3 批量提取端到端集成测试（方案 §6）。

TestClient + lifespan 启 worker；mock services.extraction_service
.call_json_extraction_api（无网络）。覆盖：批量成功落库/二次 skip/
force 替换、失败进死信且不拖累其他文档、导出 CSV/MD 与 404/400、
维度 CRUD 端点。
"""
import os
import sys
import json
import time
import uuid
import shutil
import unittest
from unittest.mock import patch, AsyncMock

# 强力隔离环境：在导入 server 之前先伪造 argv
unique_id = uuid.uuid4().hex
module_ws = os.path.abspath(
    os.path.join(os.path.dirname(__file__), f"test_ws_ext_{unique_id}"))
if not os.path.exists(module_ws):
    os.makedirs(module_ws)

sys.argv = [sys.argv[0], "38396", module_ws]

current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from fastapi.testclient import TestClient  # noqa: E402
import server  # noqa: E402
from server import app, state  # noqa: E402
from services import extraction_service as es  # noqa: E402
from core.priority_queue import QueuedTask  # noqa: E402


class TestExtractionBatchFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)
        shutil.rmtree(module_ws, ignore_errors=True)

    def setUp(self):
        self.test_ws = os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         f"test_ws_ext_case_{uuid.uuid4().hex}"))
        os.makedirs(self.test_ws, exist_ok=True)
        state.initialize(self.test_ws)
        self.d1 = self._add_doc("a.pdf", "# A\n\ncontent A")
        self.d2 = self._add_doc("b.pdf", "# B\n\ncontent B")
        resp = self.client.post("/extraction/dimensions",
                                json={"label": "Method", "prompt": "Extract method."})
        self.assertEqual(resp.status_code, 200)
        self.dim_id = resp.json()["dimension"]["id"]

    def tearDown(self):
        shutil.rmtree(self.test_ws, ignore_errors=True)

    def _add_doc(self, name, md):
        doc_id = state.db.add_document(name, f"/raw/{name}",
                                       os.path.join(self.test_ws, name))
        state.db.update_document_ocr(doc_id, "completed", markdown=md, title=name)
        return doc_id

    def _wait(self, cond, timeout=30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cond():
                return True
            time.sleep(0.15)
        return False

    def _dim_rows(self, doc_id):
        return [r for r in state.db.get_document_metadata(doc_id)
                if r["dimension_id"] == self.dim_id]

    # ── 批量成功 / 幂等 skip / force ────────────────────────

    def test_batch_success_then_idempotent_skip(self):
        with patch.object(es, "call_json_extraction_api",
                          new=AsyncMock(return_value='{"method": "X"}')):
            resp = self.client.post("/extraction/batch",
                                    json={"dimension_id": self.dim_id})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["queued"], 2)
            self.assertTrue(self._wait(
                lambda: len(self._dim_rows(self.d1)) == 1
                and len(self._dim_rows(self.d2)) == 1))
            # 结果行 label/dimension_id 正确
            row = self._dim_rows(self.d1)[0]
            self.assertEqual(row["label"], "Method")
            self.assertEqual(json.loads(row["content_json"]), {"method": "X"})
            # 二次批量：全部 skipped（断点续跑等价物）
            resp2 = self.client.post("/extraction/batch",
                                     json={"dimension_id": self.dim_id})
            self.assertEqual(resp2.json()["queued"], 0)
            self.assertEqual(resp2.json()["skipped"], 2)

    def test_force_rerun_replaces_rows(self):
        with patch.object(es, "call_json_extraction_api",
                          new=AsyncMock(return_value='{"method": "v1"}')):
            self.client.post("/extraction/batch",
                             json={"dimension_id": self.dim_id,
                                   "doc_ids": [self.d1]})
            self.assertTrue(self._wait(lambda: len(self._dim_rows(self.d1)) == 1))
        with patch.object(es, "call_json_extraction_api",
                          new=AsyncMock(return_value='{"method": "v2"}')):
            resp = self.client.post("/extraction/batch",
                                    json={"dimension_id": self.dim_id,
                                          "doc_ids": [self.d1], "force": True})
            self.assertEqual(resp.json()["queued"], 1)
            self.assertTrue(self._wait(
                lambda: self._dim_rows(self.d1)
                and json.loads(self._dim_rows(self.d1)[0]["content_json"])["method"] == "v2"))
            self.assertEqual(len(self._dim_rows(self.d1)), 1)   # 旧行被替换

    # ── 失败：死信 + 不拖累其他文档 ─────────────────────────

    def test_failure_dead_letter_others_unaffected(self):
        def flaky(md, cfg, prompt):
            if "content A" in md:
                raise RuntimeError("boom")
            return '{"method": "ok"}'

        # patch QueuedTask.get_retry_delay 而非 TaskConfig.RETRY_BACKOFF：
        # 队列持 backend.constants 的类对象，patch 独立 constants 模块不生效
        with patch.object(QueuedTask, "get_retry_delay", return_value=0):
            with patch.object(es, "call_json_extraction_api",
                              new=AsyncMock(side_effect=flaky)):
                resp = self.client.post("/extraction/batch",
                                        json={"dimension_id": self.dim_id})
                self.assertEqual(resp.json()["queued"], 2)
                # 好文档成功
                self.assertTrue(self._wait(lambda: len(self._dim_rows(self.d2)) == 1))
                # 坏文档重试耗尽进死信
                def in_dead_letters():
                    entries = self.client.get("/tasks/dead-letters").json()
                    return any(e["doc_id"] == self.d1 for e in entries.values())
                self.assertTrue(self._wait(in_dead_letters))
                # 失败文档无结果行（错误没被当结果落库——R6）
                self.assertEqual(self._dim_rows(self.d1), [])

    # ── 导出 ───────────────────────────────────────────────

    def test_export_csv_and_md(self):
        with patch.object(es, "call_json_extraction_api",
                          new=AsyncMock(return_value='{"method": "X", "score": 1}')):
            self.client.post("/extraction/batch", json={"dimension_id": self.dim_id})
            self.assertTrue(self._wait(
                lambda: len(self._dim_rows(self.d1)) == 1
                and len(self._dim_rows(self.d2)) == 1))
        resp = self.client.get("/documents/export",
                               params={"dimension_id": self.dim_id, "format": "csv"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers["content-disposition"])
        self.assertTrue(resp.text.startswith("\ufeff"))
        self.assertIn("method", resp.text)
        md = self.client.get("/documents/export",
                             params={"dimension_id": self.dim_id, "format": "md"})
        self.assertEqual(md.status_code, 200)
        self.assertIn("# 导出报告：Method", md.text)
        self.assertIn("## a.pdf", md.text)
        self.assertIn("## b.pdf", md.text)

    def test_export_404_and_bad_format(self):
        self.assertEqual(self.client.get(
            "/documents/export", params={"dimension_id": "nope"}).status_code, 404)
        self.assertEqual(self.client.get(
            "/documents/export",
            params={"dimension_id": self.dim_id, "format": "xml"}).status_code, 400)

    # ── 维度 CRUD 端点 ─────────────────────────────────────

    def test_dimension_crud_endpoints(self):
        resp = self.client.get("/extraction/dimensions")
        self.assertEqual(len(resp.json()["dimensions"]), 1)
        # 更新（同 id upsert）
        resp = self.client.post("/extraction/dimensions",
                                json={"id": self.dim_id, "label": "Method v2",
                                      "prompt": "P2"})
        self.assertTrue(resp.json()["success"])
        self.assertEqual(resp.json()["dimension"]["label"], "Method v2")
        # 校验失败 400
        self.assertEqual(self.client.post(
            "/extraction/dimensions",
            json={"label": "", "prompt": "P"}).status_code, 400)
        self.assertEqual(self.client.post(
            "/extraction/dimensions",
            json={"label": "X", "prompt": "uses {content}"}).status_code, 400)
        # 删除
        self.assertEqual(self.client.delete(
            "/extraction/dimensions/missing").status_code, 404)
        self.assertEqual(self.client.delete(
            f"/extraction/dimensions/{self.dim_id}").status_code, 200)

    def test_batch_unknown_dimension_404(self):
        resp = self.client.post("/extraction/batch",
                                json={"dimension_id": "missing"})
        self.assertEqual(resp.status_code, 404)

    def test_batch_disabled_dimension_400_fail_fast(self):
        # 停用维度：端点直接 400，不产生注定失败的队列任务
        resp = self.client.post("/extraction/dimensions",
                                json={"id": self.dim_id, "label": "Method",
                                      "prompt": "Extract method.",
                                      "enabled": False})
        self.assertTrue(resp.json()["success"])
        resp = self.client.post("/extraction/batch",
                                json={"dimension_id": self.dim_id})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "dimension disabled")
        # 无结果行产生
        self.assertEqual(self._dim_rows(self.d1), [])


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
