"""knowledge_service 适配层测试（Phase 2，方案 §5.2 八项）。

覆盖：全链路/锚可解析不变量、T1 段落级、T2 章节级（含无 abstract
标题退化）、幂等、5% 漂移重绑、空 OCR skip、search 回填、4 线程并发
写无 database is locked。
"""
import os
import sys
import json
import unittest
import uuid
import threading
import tempfile

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

from database import Database                     # noqa: E402
from services import knowledge_service as ks      # noqa: E402
from services.knowledge_service import _conn      # noqa: E402
import anchors                                    # noqa: E402

OCR_MD = """# A Survey Paper

## Abstract
This survey of false data injection attacks targets the state estimator.
The state estimator is the core of the energy management system.
Attackers inject false data to mislead the operator.
We survey detection methods comprehensively.

## III. METHOD
We model the attacker as a rational agent.
The defender deploys a robust state estimator.
Our benchmark covers fifty attack scenarios.

## IV. CONCLUSION
Detection latency drops below one second in simulation.
"""

# title 是 Abstract 首段的逐字子串 → T1；abstract 是 LLM 转述 → T2
INSIGHT = {
    "title": "survey of false data injection",
    "authors": "John Doe, Jane Smith",
    "journal_or_conference": "IEEE Transactions on Smart Grid",
    "date": "2024",
    "abstract": "This paper surveys how attackers mislead operators via bad data.",
    "keywords": ["state estimator", "false data injection"],
    "summary": ["Novelty: unified taxonomy", "Method: robust estimation"],
    "doi": "10.1109/TSG.2024.1234567",
}


class KnowledgeServiceTestBase(unittest.TestCase):
    def setUp(self):
        self.ws = os.path.join(tempfile.gettempdir(),
                               f"know_svc_{uuid.uuid4().hex}")
        os.makedirs(self.ws, exist_ok=True)
        self.db = Database(os.path.join(self.ws, "library.db"))
        ks.init_store(self.ws)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.ws, ignore_errors=True)

    def _add_doc(self, ocr_md=OCR_MD, insight=INSIGHT):
        doc_id = self.db.add_document("paper.pdf", "/raw/paper.pdf",
                                      os.path.join(self.ws, "paper.pdf"))
        self.db.update_document_ocr(doc_id, "completed", markdown=ocr_md,
                                    title="Survey of False Data Injection")
        if insight is not None:
            self.db.add_document_metadata(doc_id, "Basic Insight",
                                          json.dumps(insight))
        return doc_id

    def _claims(self, paper_id):
        conn = _conn()
        try:
            return conn.execute(
                "SELECT concept, quote, anchor, heading_path, prompt_id "
                "FROM claims WHERE paper_id=? ORDER BY claim_id",
                (paper_id,)).fetchall()
        finally:
            conn.close()


class TestIngestFullFlow(KnowledgeServiceTestBase):
    def test_ingest_creates_paper_and_claims_with_resolvable_anchors(self):
        doc_id = self._add_doc()
        result = ks.ingest_document(doc_id, self.db)
        self.assertEqual(result["paper_id"], f"doc:{doc_id}")
        self.assertGreaterEqual(result["claims"], 7)

        # papers 行：identity_status=unresolved_meta（LLM DOI 记录不晋升）
        conn = _conn()
        try:
            row = conn.execute("SELECT doi, identity_status, title, year "
                               "FROM papers WHERE paper_id=?",
                               (f"doc:{doc_id}",)).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "10.1109/TSG.2024.1234567")
        self.assertEqual(row[1], "unresolved_meta")
        self.assertEqual(row[2], "Survey of False Data Injection")
        self.assertEqual(row[3], 2024)

        # 锚可解析不变量：每条 anchor 都能在 paragraphize 集合中找到
        para_anchors = {anchors.anchor_id(p)
                        for p in anchors.paragraphize(OCR_MD)}
        claims = self._claims(f"doc:{doc_id}")
        self.assertTrue(claims)
        for concept, quote, anchor, heading, prompt_id in claims:
            self.assertIn(anchor, para_anchors,
                          f"死 claim：{concept} 锚 {anchor} 不可解析")

        # markdown 归档页含 cite://doc:
        page = os.path.join(self.ws, "knowledge", "papers", f"doc:{doc_id}.md")
        self.assertTrue(os.path.exists(page))
        text = open(page, encoding="utf-8").read()
        self.assertIn(f"cite://doc:{doc_id}/", text)
        self.assertIn("identity_status: unresolved_meta", text)
        # log.md 留痕
        log = open(os.path.join(self.ws, "knowledge", "log.md"),
                   encoding="utf-8").read()
        self.assertIn(f"- ingest | paper=doc:{doc_id}", log)

    def test_t1_paragraph_level_when_verbatim(self):
        doc_id = self._add_doc()
        ks.ingest_document(doc_id, self.db)
        claims = {c[0]: c for c in self._claims(f"doc:{doc_id}")}
        title_claim = claims["basic_insight.title"]
        # title 是 OCR 逐字子串 → T1
        self.assertEqual(title_claim[4], ks.PROMPT_ID_PARA)
        target = next(p for p in anchors.paragraphize(OCR_MD)
                      if "survey of false data injection" in p)
        self.assertEqual(title_claim[2], anchors.anchor_id(target))

    def test_t2_section_level_when_paraphrase(self):
        doc_id = self._add_doc()
        result = ks.ingest_document(doc_id, self.db)
        self.assertGreaterEqual(result["section_level"], 1)
        claims = {c[0]: c for c in self._claims(f"doc:{doc_id}")}
        abstract_claim = claims["basic_insight.abstract"]
        self.assertEqual(abstract_claim[4], ks.PROMPT_ID_SECT)
        # 锚 = Abstract 节首段（heading_path 含 Abstract）
        first_abstract_para = "This survey of false data injection attacks targets the state estimator."
        self.assertEqual(abstract_claim[2],
                         anchors.anchor_id(first_abstract_para))
        self.assertIn("Abstract", abstract_claim[3])

    def test_t2_fallback_first_paragraph_without_abstract_heading(self):
        md = "# Paper\n\nFirst paragraph of the body without any abstract heading.\n\n## METHOD\nMethod paragraph here.\n"
        insight = dict(INSIGHT, abstract="Pure paraphrase with no verbatim overlap xyz.")
        doc_id = self._add_doc(ocr_md=md, insight=insight)
        ks.ingest_document(doc_id, self.db)
        claims = {c[0]: c for c in self._claims(f"doc:{doc_id}")}
        self.assertEqual(claims["basic_insight.abstract"][4], ks.PROMPT_ID_SECT)
        self.assertEqual(
            claims["basic_insight.abstract"][2],
            anchors.anchor_id("First paragraph of the body without any abstract heading."))

    def test_idempotent_reingest_no_duplicates(self):
        doc_id = self._add_doc()
        first = ks.ingest_document(doc_id, self.db)
        second = ks.ingest_document(doc_id, self.db)
        self.assertEqual(second["claims"], first["claims"])
        self.assertEqual(second["rebound"], 0)
        self.assertEqual(len(self._claims(f"doc:{doc_id}")), first["claims"])

    def test_rebind_on_anchor_drift(self):
        doc_id = self._add_doc()
        ks.ingest_document(doc_id, self.db)
        before = {c[0]: c[2] for c in self._claims(f"doc:{doc_id}")}
        # 模拟 re-OCR 漂移：Abstract 首段改 ~10% 词（新 anchor；
        # T2 claims 全部锚在该段 → 必发生 rebind）
        drifted = OCR_MD.replace(
            "This survey of false data injection attacks targets the state estimator.",
            "This survey of false data injection threats focus on the state estimator.")
        self.db.update_document_ocr(doc_id, "completed", markdown=drifted,
                                    title="Survey of False Data Injection")
        result = ks.ingest_document(doc_id, self.db)
        self.assertGreaterEqual(result["rebound"], 1)
        after = {c[0]: c[2] for c in self._claims(f"doc:{doc_id}")}
        self.assertEqual(set(after), set(before))          # 行数不增
        # 受影响 claim 锚已变
        self.assertTrue(any(after[k] != before[k] for k in before))
        log = open(os.path.join(self.ws, "knowledge", "log.md"),
                   encoding="utf-8").read()
        self.assertIn("rebind=", log)

    def test_empty_ocr_skips(self):
        doc_id = self._add_doc(ocr_md="# Only Heading\n\n## Another\n")
        result = ks.ingest_document(doc_id, self.db)
        self.assertEqual(result["skipped_reason"], "no_paragraphs")
        self.assertEqual(result["claims"], 0)
        self.assertEqual(self._claims(f"doc:{doc_id}"), [])

    def test_missing_insight_skips(self):
        doc_id = self._add_doc(insight=None)
        result = ks.ingest_document(doc_id, self.db)
        self.assertEqual(result["skipped_reason"], "no_basic_insight")

    def test_search_backfills_doc_id_and_title(self):
        doc_id = self._add_doc()
        ks.ingest_document(doc_id, self.db)
        rows = ks.search("state estimator")
        self.assertTrue(rows)
        row = rows[0]
        self.assertEqual(row["doc_id"], doc_id)
        self.assertEqual(row["title"], "Survey of False Data Injection")
        self.assertTrue(row["anchor"].startswith("p"))

    def test_search_cjk_two_char(self):
        insight = dict(INSIGHT, abstract="P2P 交易瓶颈在于各 agent 需顺序更新。")
        doc_id = self._add_doc(insight=insight)
        ks.ingest_document(doc_id, self.db)
        rows = ks.search("交易")           # Gap 5 门槛：2 字符 CJK
        self.assertGreaterEqual(len(rows), 1)

    def test_search_empty_query(self):
        self.assertEqual(ks.search(""), [])
        self.assertEqual(ks.search("   "), [])

    def test_get_paper_claims(self):
        doc_id = self._add_doc()
        ks.ingest_document(doc_id, self.db)
        claims = ks.get_paper_claims(f"doc:{doc_id}")
        self.assertGreaterEqual(len(claims), 7)
        self.assertEqual([c["claim_id"] for c in claims],
                         sorted(c["claim_id"] for c in claims))

    def test_forget_paper_removes_rows_and_page(self):
        doc_id = self._add_doc()
        ks.ingest_document(doc_id, self.db)
        self.assertTrue(ks.forget_paper(doc_id))
        self.assertEqual(ks.get_paper_claims(f"doc:{doc_id}"), [])
        page = os.path.join(self.ws, "knowledge", "papers", f"doc:{doc_id}.md")
        self.assertFalse(os.path.exists(page))

    def test_concurrent_ingest_no_locked(self):
        docs = [self._add_doc(insight=dict(INSIGHT, title=f"Paper {i}"))
                for i in range(4)]
        errors = []

        def worker(did):
            try:
                ks.ingest_document(did, self.db)
            except Exception as e:                      # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(d,)) for d in docs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"concurrent ingest errors: {errors}")
        for d in docs:
            self.assertGreaterEqual(len(ks.get_paper_claims(f"doc:{d}")), 7)


if __name__ == "__main__":
    unittest.main()
