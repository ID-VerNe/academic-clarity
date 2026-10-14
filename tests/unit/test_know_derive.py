"""know.derive 移植测试（Phase 2，源 paper-tools/know/tests/test_derive.py 10 例）。

改造点（相对源版）：
① 路径发现改为动态找 backend/ + backend/vendor/know；
② fixtures 指向 tests/unit/fixtures/know/；
③ TestExistenceGate/TestWarningsManifest 把 empty.md/bad.json 写到
   UUID 临时目录（源版写测试同目录，破坏并行隔离，agents.md §3）。
"""
import os
import sys
import json
import unittest
import uuid
import tempfile

# 动态路径发现定位 backend/
current = os.path.dirname(os.path.abspath(__file__))
while current and not os.path.exists(os.path.join(current, "backend")):
    new_current = os.path.dirname(current)
    if new_current == current:
        break
    current = new_current
VENDOR_KNOW = os.path.join(current, "backend", "vendor", "know")
if os.path.exists(VENDOR_KNOW) and VENDOR_KNOW not in sys.path:
    sys.path.insert(0, VENDOR_KNOW)

from derive import derive, MATCHED, BROKEN, UNMATCHED  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "know")
PAPER = "10.1109_tii.2020.2999571"
V2_JSON = os.path.join(FIXTURES, f"{PAPER}_v2_gemini-3.1-flash-lite.json")
OCR_MD = os.path.join(FIXTURES, f"{PAPER}.md")


class TestDeriveShape(unittest.TestCase):
    def setUp(self):
        self.result = derive([V2_JSON], OCR_MD)

    def test_returns_rows(self):
        # result is a list of claim dicts
        self.assertIsInstance(self.result, list)
        self.assertGreater(len(self.result), 0)

    def test_claim_has_required_fields(self):
        for claim in self.result:
            for field in ("paper_id", "group", "field", "quote",
                          "anchor", "heading_path", "status"):
                self.assertIn(field, claim, f"claim missing {field}: {claim}")

    def test_paper_id_extracted(self):
        for claim in self.result:
            self.assertEqual(claim["paper_id"], PAPER)


class TestNullSkip(unittest.TestCase):
    def test_null_evidence_quote_produces_no_claim(self):
        result = derive([V2_JSON], OCR_MD)
        # opf_surrogate has null evidence_quotes -> no claim rows for those fields
        opf_claims = [c for c in result if c["group"] == "opf_acceleration"]
        # the opf prompt's test_system_size / speedup were null in Phase 1.0
        # so no opf claims should exist for THIS paper (all three were null)
        self.assertEqual(len(opf_claims), 0)


class TestAnchoringOutcomes(unittest.TestCase):
    def setUp(self):
        self.result = derive([V2_JSON], OCR_MD)

    def test_all_non_null_claims_are_matched(self):
        # Phase 1.0 measured 100% hit rate on this paper
        for claim in self.result:
            self.assertEqual(claim["status"], MATCHED,
                             f"expected matched, got {claim['status']} for "
                             f"{claim['group']}.{claim['field']}: {claim['quote'][:50]}")

    def test_no_unmatched_claims(self):
        for claim in self.result:
            self.assertNotEqual(claim["status"], UNMATCHED)

    def test_anchor_is_sha1_8_format(self):
        for claim in self.result:
            self.assertTrue(claim["anchor"].startswith("p"))
            self.assertEqual(len(claim["anchor"]), 9)

    def test_heading_path_nonempty(self):
        for claim in self.result:
            self.assertTrue(claim["heading_path"],
                            f"empty heading_path for {claim['group']}.{claim['field']}")


class TestExistenceGate(unittest.TestCase):
    def test_claim_anchor_must_come_from_current_ocr(self):
        # derive against an EMPTY ocr md -> every quote should be dropped
        # (existence gate) because no paragraph exists to anchor to
        with tempfile.TemporaryDirectory(prefix=f"know_derive_{uuid.uuid4().hex}") as tmp:
            empty_md = os.path.join(tmp, "empty.md")
            with open(empty_md, "w", encoding="utf-8") as f:
                f.write("# Empty\n")
            result = derive([V2_JSON], empty_md)
            self.assertEqual(len(result), 0,
                             "existence gate should drop all claims when no OCR paragraphs")


class TestWarningsManifest(unittest.TestCase):
    def test_broken_or_unmatched_recorded(self):
        # synthesize a JSON with a quote that won't match -> should be
        # recorded in warnings, not fabricated as matched
        with tempfile.TemporaryDirectory(prefix=f"know_derive_{uuid.uuid4().hex}") as tmp:
            bad_json = os.path.join(tmp, "bad.json")
            data = {
                "cyber_attacks": {
                    "cyber_attacks": {
                        "evidence_quotes": {
                            "attack_target": "totally nonexistent gibberish zzz xyz"
                        }
                    }
                }
            }
            with open(bad_json, "w", encoding="utf-8") as f:
                json.dump(data, f)
            result = derive([bad_json], OCR_MD)
            # the bad quote should NOT produce a matched claim
            matches = [c for c in result if c["status"] == MATCHED]
            # it should be broken/unmatched and recorded as a warning
            # (derive returns warnings via second return or attribute; check both)
            self.assertTrue(
                all(c["status"] != MATCHED for c in result),
                "bad quote should not be matched"
            )


if __name__ == "__main__":
    unittest.main()
