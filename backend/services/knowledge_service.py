"""knowledge_service — know 知识层适配层（Phase 2）：vendor
（backend/vendor/know/）逐字禁改；Basic Insight → claims（evidence_quotes
逐字引文优先）；两级锚定（T1 逐字 / T2 转述降级，锚永可解析）；幂等+
重绑（补 know.ingest 不重绑缺口 R1）；busy_timeout + 单写锁。paper_id
固定 'doc:{id}'（re-ingest 稳定；DOI 走 resolve_doi → unresolved_meta）。
归档层在 knowledge_archive。

实现拆分至：knowledge_store（基础设施/连接）、knowledge_queries（检索）；
本模块保留 ingest_document + 字段映射并 re-export 既有符号
（init_store/_conn/_kb_path 等保持可导入）。
"""
import json
import re

from services.knowledge_archive import write_paper_page
from services.knowledge_store import (KNOW_DB_NAME, _conn, _kb_path,  # noqa: F401
                                      _read_conn, _write_conn, init_store)
from services.knowledge_queries import (forget_paper, get_paper_claims,  # noqa: F401
                                        list_papers, search)

import anchors  # noqa: E402  vendor（sys.path 由 knowledge_store 注入）
import config as know_config  # noqa: E402
import identity as know_identity  # noqa: E402
from derive import (_paragraphs_with_path, _resolve_anchor,  # noqa: E402
                    _resolve_heading_path)

try:
    from backend.constants import MetadataConfig
except ImportError:
    from constants import MetadataConfig

PROMPT_ID_PARA = "basic-insight-v1"          # T1 段落级（逐字）
PROMPT_ID_SECT = "basic-insight-v1~section"  # T2 章节级（转述降级）
OCR_VERSION, _MODEL = "deepseek-ocr-v1", "academic-clarity"

# Basic Insight 字段 → claims.concept（BASIC_INSIGHT_PROMPT 产物）
_FIELD_MAP = [("title", "basic_insight.title"), ("authors", "basic_insight.authors"),
              ("journal_or_conference", "basic_insight.venue"), ("date", "basic_insight.date"),
              ("abstract", "basic_insight.abstract"), ("keywords", "basic_insight.keywords"),
              ("summary", "basic_insight.summary")]


def _paper_meta(doc: dict, insight: dict, doi: str, status: str) -> dict:
    """papers 行（键与 insert_paper 参数同构；title: documents→insight→filename）。"""
    m = re.search(r"\b(\d{4})\b", str(insight.get("date") or ""))
    authors = insight.get("authors") or ""
    authors_json = (json.dumps(authors, ensure_ascii=False) if isinstance(authors, list)
                    else json.dumps([a for a in str(authors).split(",") if a.strip()],
                                    ensure_ascii=False))
    return {"paper_id": f"doc:{doc['id']}",
            "title": doc.get("title") or insight.get("title") or doc.get("filename"),
            "authors": authors_json or "[]", "year": int(m.group(1)) if m else None,
            "project": "academic-clarity", "source_rel": doc.get("filename") or "",
            "ocr_version": OCR_VERSION, "doi": doi, "identity_status": status}


def _t2_anchor(paras_with_path):
    """T2 兜底：heading_path 含 abstract/摘要 的首段，否则文档首段。"""
    for para, path in paras_with_path:
        if "abstract" in (path or "").lower() or "摘要" in (path or ""):
            return para, path or ""
    return paras_with_path[0] if paras_with_path else ("", "")


def _skip(paper_id: str, reason: str) -> dict:
    return dict(paper_id=paper_id, claims=0, rebound=0, section_level=0, skipped_reason=reason)


def ingest_document(doc_id: int, db) -> dict:
    """Basic Insight + ocr_markdown → claims（T1/T2）→ 知识库；锚永可解析（T2 兜底）。"""
    doc = db.get_document(doc_id)
    if not doc:
        return _skip(f"doc:{doc_id}", "no_document")
    paras = anchors.paragraphize(doc.get("ocr_markdown") or "")
    if not paras:
        return _skip(f"doc:{doc_id}", "no_paragraphs")
    insight = db.get_basic_insight(doc_id)          # B-DRY-12/13：label + JSON 容错
    if insight is None:
        # 保留 skip reason 区分：有行但 JSON 损坏 → bad_insight_json；无行 → no_basic_insight
        has_row = any(m.get("label") == MetadataConfig.DEFAULT_LABEL
                      for m in db.get_document_metadata(doc_id))
        return _skip(f"doc:{doc_id}", "bad_insight_json" if has_row else "no_basic_insight")
    paras_with_path = _paragraphs_with_path(doc["ocr_markdown"])
    path_by_para = {p: path for p, path in paras_with_path}
    meta = _paper_meta(doc, insight, *know_identity.resolve_doi({}, insight.get("doi") or ""))
    paper_id = meta["paper_id"]
    eq = insight.get("evidence_quotes") if isinstance(insight.get("evidence_quotes"), dict) else {}
    for f, _c in _FIELD_MAP:                        # v2 逐字引文：命中即替换字段文本
        ev = anchors.coerce_quote(eq.get(f))        # 须在 meta 之后：防污染 papers 行
        if ev and anchors.classify_fragmented(ev, paras)[0] == anchors.MATCHED: insight[f] = ev
    claims, section_level = [], 0
    for field, concept in _FIELD_MAP:               # T1 逐字段 → T2 降级
        quote = anchors.coerce_quote(insight.get(field))
        if not quote:
            continue
        status, _ratio = anchors.classify_fragmented(quote, paras)
        if status == anchors.MATCHED:               # T1 段落级（逐字）
            anchor = _resolve_anchor(quote, paras, path_by_para)
            heading = _resolve_heading_path(quote, paras_with_path)
            prompt_id = PROMPT_ID_PARA
        else:                                       # T2 章节级（转述）
            para, heading = _t2_anchor(paras_with_path)
            anchor, prompt_id = anchors.anchor_id(para), PROMPT_ID_SECT
            section_level += 1
        claims.append({"concept": concept, "quote": quote, "anchor": anchor,
                       "heading_path": heading or "", "prompt_id": prompt_id})
    with _write_conn() as conn:                     # 单写锁（_write_conn 内含）
        know_config.insert_paper(conn, **meta)
        existing = {(r[0], r[1]): (r[2], r[3]) for r in conn.execute(
            "SELECT concept, quote, anchor, claim_id FROM claims "
            "WHERE paper_id=?", (paper_id,)).fetchall()}
        rebound = 0
        for c in claims:                            # 幂等 insert + 锚漂移重绑
            key = (c["concept"], c["quote"])
            if key not in existing:
                know_config.insert_claim(
                    conn, paper_id, c["concept"], c["quote"], c["anchor"],
                    c["heading_path"], _MODEL, c["prompt_id"])
            elif existing[key][0] != c["anchor"]:
                conn.execute("UPDATE claims SET anchor=?, heading_path=? "
                             "WHERE claim_id=?",
                             (c["anchor"], c["heading_path"], existing[key][1]))
                rebound += 1
        conn.commit()
    write_paper_page(paper_id, meta, claims, rebound)
    return {"paper_id": paper_id, "claims": len(claims), "rebound": rebound,
            "section_level": section_level}
