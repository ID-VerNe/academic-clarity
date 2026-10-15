"""extraction_service 单测（Phase 3 方案 §6）。

覆盖：validate_dimension 校验矩阵、save_dimension upsert 与 label 冲突、
select_batch_candidates 枚举语义（无 markdown 排除 / 已完成跳过 / force /
doc_ids 过滤）、run_dimension_extraction 三条路径（成功落库 /
error-JSON 转异常 R6 / 池耗尽异常传播供队列重试）。
"""
import os
import sys
import json
import asyncio
import unittest
import uuid
from unittest.mock import patch, AsyncMock

# 动态路径发现定位 backend/
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
BACKEND_PATH = os.path.join(current, "backend")
if os.path.exists(BACKEND_PATH) and BACKEND_PATH not in sys.path:
    sys.path.insert(0, BACKEND_PATH)

from database import Database                       # noqa: E402
from services import extraction_service as es       # noqa: E402
from services.ai_service import APIKeyPoolExhaustedError  # noqa: E402


class ExtractionServiceTestBase(unittest.TestCase):
    def setUp(self):
        self.db_path = f"test_db_extsvc_{uuid.uuid4().hex}.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        for suffix in ["", "-wal", "-shm"]:
            p = self.db_path + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def _add_doc(self, status="completed", md="Some OCR markdown text."):
        doc_id = self.db.add_document("p.pdf", "/raw/p.pdf", f"/stored/{uuid.uuid4().hex}.pdf")
        self.db.update_document_ocr(doc_id, status, markdown=md)
        return doc_id

    def _save_dim(self, label="Methodology", prompt="Extract the method."):
        return es.save_dimension(self.db, {"label": label, "prompt": prompt})


class TestValidateDimension(unittest.TestCase):
    def test_valid_normalized(self):
        v = es.validate_dimension({"label": "  Method  ", "prompt": "  Extract.  ",
                                   "system_prompt": " be terse ", "enabled": True})
        self.assertEqual(v["label"], "Method")
        self.assertEqual(v["prompt"], "Extract.")
        self.assertEqual(v["system_prompt"], "be terse")
        self.assertEqual(v["enabled"], 1)

    def test_enabled_false_maps_to_0(self):
        v = es.validate_dimension({"label": "L", "prompt": "P", "enabled": False})
        self.assertEqual(v["enabled"], 0)

    def test_empty_label_rejected(self):
        with self.assertRaises(es.DimensionError):
            es.validate_dimension({"label": "  ", "prompt": "P"})

    def test_label_too_long_rejected(self):
        with self.assertRaises(es.DimensionError):
            es.validate_dimension({"label": "x" * 51, "prompt": "P"})

    def test_empty_prompt_rejected(self):
        with self.assertRaises(es.DimensionError):
            es.validate_dimension({"label": "L", "prompt": "  "})

    def test_prompt_too_long_rejected(self):
        with self.assertRaises(es.DimensionError):
            es.validate_dimension({"label": "L", "prompt": "x" * 8001})

    def test_content_placeholder_rejected(self):
        with self.assertRaises(es.DimensionError):
            es.validate_dimension({"label": "L", "prompt": "Extract from {content}."})


class TestDimensionCrud(ExtractionServiceTestBase):
    def test_save_generates_id_and_roundtrips(self):
        saved = self._save_dim()
        self.assertEqual(len(saved["id"]), 12)
        row = es.get_dimension(self.db, saved["id"])
        self.assertEqual(row["label"], "Methodology")
        self.assertEqual(row["enabled"], 1)

    def test_upsert_same_id_updates(self):
        saved = self._save_dim()
        es.save_dimension(self.db, {"id": saved["id"], "label": "Method v2",
                                    "prompt": "New prompt."})
        row = es.get_dimension(self.db, saved["id"])
        self.assertEqual(row["label"], "Method v2")
        self.assertEqual(row["prompt"], "New prompt.")
        self.assertEqual(len(es.list_dimensions(self.db)), 1)

    def test_duplicate_label_different_id_raises(self):
        self._save_dim(label="Method")
        with self.assertRaises(es.DimensionError):
            es.save_dimension(self.db, {"id": "other", "label": "Method", "prompt": "P"})

    def test_list_and_delete(self):
        a = self._save_dim(label="A")
        b = self._save_dim(label="B")
        self.assertEqual({d["id"] for d in es.list_dimensions(self.db)}, {a["id"], b["id"]})
        self.assertTrue(es.delete_dimension(self.db, a["id"]))
        self.assertFalse(es.delete_dimension(self.db, "missing"))
        self.assertEqual({d["id"] for d in es.list_dimensions(self.db)}, {b["id"]})

    def test_get_missing_returns_none(self):
        self.assertIsNone(es.get_dimension(self.db, "nope"))


class TestSelectBatchCandidates(ExtractionServiceTestBase):
    def setUp(self):
        super().setUp()
        self.dim = self._save_dim()
        self.c1 = self._add_doc()                                # 候选
        self.p = self._add_doc(status="processing")              # 非 completed
        self.e = self._add_doc(md="   ")                         # 无 markdown
        self.c2 = self._add_doc()                                # 已完成提取
        self.db.add_document_metadata(self.c2, self.dim["label"], "{}",
                                      dimension_id=self.dim["id"])

    def test_enumeration_skips_not_ready_and_done(self):
        to_run, skipped = es.select_batch_candidates(self.db, self.dim["id"])
        self.assertEqual(to_run, [self.c1])
        self.assertEqual(set(skipped), {self.p, self.e, self.c2})

    def test_force_includes_done(self):
        to_run, _ = es.select_batch_candidates(self.db, self.dim["id"], force=True)
        self.assertEqual(set(to_run), {self.c1, self.c2})

    def test_doc_ids_filter(self):
        to_run, skipped = es.select_batch_candidates(
            self.db, self.dim["id"], doc_ids=[self.c1, self.p])
        self.assertEqual(to_run, [self.c1])
        self.assertEqual(skipped, [self.p])

    def test_dimension_id_scoping(self):
        # 其他维度的结果不影响本维度候选
        other = self._save_dim(label="Other")
        self.db.add_document_metadata(self.c1, "Other", "{}", dimension_id=other["id"])
        to_run, _ = es.select_batch_candidates(self.db, self.dim["id"])
        self.assertIn(self.c1, to_run)


class TestRunDimensionExtraction(ExtractionServiceTestBase):
    def setUp(self):
        super().setUp()
        self.dim = self._save_dim()
        self.doc = self._add_doc()

    def _run(self, mock_return=None, mock_side_effect=None):
        m = AsyncMock(return_value=mock_return, side_effect=mock_side_effect)
        with patch.object(es, "call_json_extraction_api", new=m):
            return asyncio.run(es.run_dimension_extraction(
                self.doc, self.dim["id"], self.db))

    def _metadata_rows(self):
        return [r for r in self.db.get_document_metadata(self.doc)
                if r["dimension_id"] == self.dim["id"]]

    def test_success_stores_row_with_dimension_id(self):
        result = self._run(mock_return='{"method": "X", "score": 1}')
        self.assertEqual(result, {"doc_id": self.doc, "dimension_id": self.dim["id"]})
        rows = self._metadata_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], self.dim["label"])
        self.assertEqual(json.loads(rows[0]["content_json"]), {"method": "X", "score": 1})

    def test_error_json_raises_not_stored(self):
        # R6：ai_service 单 key 失败路径返回 {"error":...}，必须转异常
        with self.assertRaises(es.DimensionError):
            self._run(mock_return='{"error": "Extraction timeout"}')
        self.assertEqual(self._metadata_rows(), [])

    def test_pool_exhausted_propagates_for_retry(self):
        with self.assertRaises(APIKeyPoolExhaustedError):
            self._run(mock_side_effect=APIKeyPoolExhaustedError("all keys down"))
        self.assertEqual(self._metadata_rows(), [])

    def test_invalid_json_propagates(self):
        with self.assertRaises(json.JSONDecodeError):
            self._run(mock_return='not json at all')
        self.assertEqual(self._metadata_rows(), [])

    def test_disabled_dimension_raises(self):
        es.save_dimension(self.db, {"id": self.dim["id"], "label": self.dim["label"],
                                    "prompt": "P", "enabled": False})
        with self.assertRaises(es.DimensionError):
            self._run(mock_return='{}')

    def test_doc_without_markdown_raises(self):
        empty = self._add_doc(md="")
        with self.assertRaises(es.DimensionError):
            asyncio.run(es.run_dimension_extraction(empty, self.dim["id"], self.db))


if __name__ == "__main__":
    unittest.main()
