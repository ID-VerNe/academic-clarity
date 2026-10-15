"""knowledge_queries — claims/papers 检索与删除（B-SRP-13 拆分）。

search/get_paper_claims/list_papers/forget_paper；连接经 knowledge_store
的 _read_conn/_write_conn（B-DRY-16），busy_timeout 走 DBConfig（B-DRY-20）。
"""
import re

from services.knowledge_archive import remove_paper_page
from services.knowledge_store import _read_conn, _write_conn  # 注入 vendor sys.path
import config as know_config  # noqa: E402  vendor（路径由 knowledge_store 注入）

_PAPER_ID_RE = re.compile(r"^doc:(\d+)$")


def search(query: str, limit: int = 10) -> list:
    """config.search_claims（FTS 双表 + LIKE 兜底）+ papers 回填。"""
    if not (query or "").strip():
        return []
    with _read_conn() as conn:
        rows = know_config.search_claims(conn, query.strip(), limit=limit)
        if rows:
            pids = sorted({r["paper_id"] for r in rows})
            papers = {r[0]: (r[1], r[2]) for r in conn.execute(
                f"SELECT paper_id, title, doi FROM papers WHERE paper_id IN "
                f"({','.join('?' * len(pids))})", pids).fetchall()}
    return [{**r, "doc_id": int(m.group(1)) if (m := _PAPER_ID_RE.match(r["paper_id"] or "")) else None,
             "title": papers.get(r["paper_id"], (None, None))[0],
             "doi": papers.get(r["paper_id"], (None, None))[1]} for r in rows]


def get_paper_claims(paper_id: str) -> list:
    """单篇 claims（按 claim_id 升序）。"""
    with _read_conn() as conn:
        rows = conn.execute("SELECT claim_id, concept, quote, anchor, heading_path, "
                            "conflicting, prompt_id FROM claims WHERE paper_id=? ORDER BY claim_id",
                            (paper_id,)).fetchall()
    return [{"claim_id": r[0], "concept": r[1], "quote": r[2], "anchor": r[3],
             "heading_path": r[4], "conflicting": r[5], "prompt_id": r[6]} for r in rows]


def list_papers() -> list:
    """papers + claim 计数（Dashboard 检索来源）。"""
    with _read_conn() as conn:
        rows = conn.execute("SELECT p.paper_id, p.title, p.doi, p.identity_status, "
                            "COUNT(c.claim_id) FROM papers p LEFT JOIN claims c "
                            "ON c.paper_id = p.paper_id GROUP BY p.paper_id "
                            "ORDER BY p.paper_id").fetchall()
    return [{"paper_id": r[0], "title": r[1], "doi": r[2],
             "identity_status": r[3], "claim_count": r[4]} for r in rows]


def forget_paper(doc_id: int) -> bool:
    """文档删除联动：删知识行（含 FTS）+ 归档页；知识库可重建。"""
    paper_id = f"doc:{doc_id}"
    with _write_conn() as conn:                     # 单写锁（_write_conn 内含）
        rids = [r[0] for r in conn.execute(
            "SELECT claim_id FROM claims WHERE paper_id=?", (paper_id,))]
        for tbl in ("claims_fts", "claims_fts_cjk"):
            conn.executemany(f"DELETE FROM {tbl} WHERE rowid=?", [(r,) for r in rids])
        conn.execute("DELETE FROM claims WHERE paper_id=?", (paper_id,))
        conn.execute("DELETE FROM papers WHERE paper_id=?", (paper_id,))
        conn.commit()
    remove_paper_page(paper_id)
    return True
