"""knowledge_service — know 知识层适配层（Phase 2，≤200 行）。

vendor（backend/vendor/know/）逐字拷贝不修改；本层负责：目录约定适配
（Basic Insight → claims，不依赖 paper-tools 的 _v2_ json/md 目录约定）；
两级锚定（T1 段落级逐字 / T2 章节级转述降级，锚永可解析）；幂等+重绑
（补 know.ingest 不重绑缺口 R1）；busy_timeout + 单写锁。paper_id 固定
'doc:{id}'（DOI 未验证会变，主键须对 re-ingest 稳定；身份走
resolve_doi({}, ...) → unresolved_meta）。归档层在 knowledge_archive。
"""
import json, os, re, sys, threading

# vendor/know 入 sys.path（平铺 import：import anchors，禁改 vendor）
_VENDOR_KNOW = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor", "know")
if os.path.exists(_VENDOR_KNOW) and _VENDOR_KNOW not in sys.path:
    sys.path.insert(0, _VENDOR_KNOW)
import anchors, config as know_config, identity as know_identity  # noqa: E402
from derive import (_paragraphs_with_path, _resolve_anchor,  # noqa: E402
                    _resolve_heading_path)
from services.knowledge_archive import write_paper_page, remove_paper_page  # noqa: E402

KNOW_DB_NAME = "index.sqlite"     # {workspace}/knowledge/index.sqlite
PROMPT_ID_PARA = "basic-insight-v1"          # T1 段落级（逐字）
PROMPT_ID_SECT = "basic-insight-v1~section"  # T2 章节级（转述降级）
OCR_VERSION, _MODEL = "deepseek-ocr-v1", "academic-clarity"

# Basic Insight 字段 → claims.concept（BASIC_INSIGHT_PROMPT 产物）
_FIELD_MAP = [("title", "basic_insight.title"), ("authors", "basic_insight.authors"),
              ("journal_or_conference", "basic_insight.venue"), ("date", "basic_insight.date"),
              ("abstract", "basic_insight.abstract"), ("keywords", "basic_insight.keywords"),
              ("summary", "basic_insight.summary")]

_write_lock = threading.Lock()    # knowledge DB 单写者
_PAPER_ID_RE = re.compile(r"^doc:(\d+)$")
_WORKSPACE = None                 # init_store 记录；_kb_path 据此定位

def init_store(workspace_path: str) -> None:
    """lifespan/workspace 切换时调用：建 {workspace}/knowledge/ + init_db。"""
    global _WORKSPACE
    _WORKSPACE = workspace_path
    os.makedirs(_kb_path(), exist_ok=True)
    _conn().close()

def _kb_path() -> str:
    if not _WORKSPACE:
        raise RuntimeError("knowledge_store not initialized (call init_store)")
    return os.path.join(_WORKSPACE, "knowledge")

def _conn():
    """vendor init_db（幂等建表）+ busy_timeout（vendor 未设，防锁）。"""
    conn = know_config.init_db(os.path.join(_kb_path(), KNOW_DB_NAME))
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def _paper_meta(doc: dict, insight: dict, doi: str, status: str) -> dict:
    """papers 行（键与 config.insert_paper 参数同构）；title 取
    documents.title → insight.title → filename。"""
    m = re.search(r"\b(\d{4})\b", str(insight.get("date") or ""))
    authors = insight.get("authors") or ""
    authors_json = (json.dumps(authors, ensure_ascii=False) if isinstance(authors, list)
                    else json.dumps([a.strip() for a in str(authors).split(",")
                                     if a.strip()], ensure_ascii=False))
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
    return {"paper_id": paper_id, "claims": 0, "rebound": 0, "section_level": 0,
            "skipped_reason": reason}

def ingest_document(doc_id: int, db) -> dict:
    """Basic Insight + ocr_markdown → claims（T1/T2 锚定）→ 知识库；
    任何 quote 都有可解析锚（T2 兜底）→ 结构上不产生死 claim。"""
    doc = db.get_document(doc_id)
    if not doc:
        return _skip(f"doc:{doc_id}", "no_document")
    paras = anchors.paragraphize(doc.get("ocr_markdown") or "")
    if not paras:
        return _skip(f"doc:{doc_id}", "no_paragraphs")
    row = next((m for m in db.get_document_metadata(doc_id)
                if m["label"] == "Basic Insight"), None)
    if not row:
        return _skip(f"doc:{doc_id}", "no_basic_insight")
    try:
        insight = json.loads(row["content_json"])
    except (json.JSONDecodeError, TypeError):
        return _skip(f"doc:{doc_id}", "bad_insight_json")
    paras_with_path = _paragraphs_with_path(doc["ocr_markdown"])
    path_by_para = {p: path for p, path in paras_with_path}
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
    meta = _paper_meta(doc, insight,
                       *know_identity.resolve_doi({}, insight.get("doi") or ""))
    paper_id = meta["paper_id"]
    with _write_lock:                               # 单写锁
        conn = _conn()
        try:
            know_config.insert_paper(conn, **meta)
            existing = {(r[0], r[1]): (r[2], r[3]) for r in conn.execute(
                "SELECT concept, quote, anchor, claim_id FROM claims "
                "WHERE paper_id=?", (paper_id,)).fetchall()}
            rebound = 0
            for c in claims:                        # 幂等 insert + 锚漂移重绑
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
        finally:
            conn.close()
    write_paper_page(paper_id, meta, claims, rebound)
    return {"paper_id": paper_id, "claims": len(claims), "rebound": rebound,
            "section_level": section_level}

def search(query: str, limit: int = 10) -> list:
    """config.search_claims（FTS 双表 + LIKE 兜底）+ papers 回填。"""
    if not query or not query.strip():
        return []
    conn = _conn()
    rows, papers = [], {}
    try:
        rows = know_config.search_claims(conn, query.strip(), limit=limit)
        if rows:
            pids = sorted({r["paper_id"] for r in rows})
            papers = {r[0]: (r[1], r[2]) for r in conn.execute(
                f"SELECT paper_id, title, doi FROM papers WHERE paper_id IN "
                f"({','.join('?' * len(pids))})", pids).fetchall()}
    finally:
        conn.close()
    return [{**r, "doc_id": int(m.group(1)) if (m := _PAPER_ID_RE.match(r["paper_id"] or "")) else None,
             "title": papers.get(r["paper_id"], (None, None))[0],
             "doi": papers.get(r["paper_id"], (None, None))[1]} for r in rows]

def get_paper_claims(paper_id: str) -> list:
    """单篇 claims（按 claim_id 升序）。"""
    conn = _conn()
    try:
        rows = conn.execute("SELECT claim_id, concept, quote, anchor, heading_path, "
                            "conflicting, prompt_id FROM claims WHERE paper_id=? ORDER BY claim_id",
                            (paper_id,)).fetchall()
    finally:
        conn.close()
    return [{"claim_id": r[0], "concept": r[1], "quote": r[2], "anchor": r[3],
             "heading_path": r[4], "conflicting": r[5], "prompt_id": r[6]} for r in rows]

def forget_paper(doc_id: int) -> bool:
    """文档删除联动：删知识行（含 FTS）+ 归档页；知识库可重建。"""
    paper_id = f"doc:{doc_id}"
    with _write_lock:
        conn = _conn()
        try:
            rids = [r[0] for r in conn.execute(
                "SELECT claim_id FROM claims WHERE paper_id=?", (paper_id,))]
            for tbl in ("claims_fts", "claims_fts_cjk"):
                conn.executemany(f"DELETE FROM {tbl} WHERE rowid=?", [(r,) for r in rids])
            conn.execute("DELETE FROM claims WHERE paper_id=?", (paper_id,))
            conn.execute("DELETE FROM papers WHERE paper_id=?", (paper_id,))
            conn.commit()
        finally:
            conn.close()
    remove_paper_page(paper_id)
    return True
