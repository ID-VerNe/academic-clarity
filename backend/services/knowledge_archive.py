"""knowledge_archive — know 知识层 markdown 归档（Phase 2）。

与 vendor 同构分层：config.py = 查询 substrate（SQLite/FTS），
know.py 的 _write_paper_page/_append_log = 归档层（markdown）。
本模块只管文件归档，零 DB/锚定逻辑；knowledge_service  ingest 后调用。
"""
import os


def _kb_path() -> str:
    from services.knowledge_service import _kb_path
    return _kb_path()


def write_paper_page(paper_id: str, meta: dict, claims: list,
                     rebound: int) -> None:
    """papers/{paper_id}.md（frontmatter + claims + cite:// 锚表）
    + log.md 追加（ingest/rebind 条目，复刻 know.py 模板）。"""
    kb = _kb_path()
    os.makedirs(os.path.join(kb, "papers"), exist_ok=True)
    lines = [f"- **{c['concept']}**: {c['quote']}  "
             f"cite://{paper_id}/{c['anchor']}  `{c['prompt_id']}`" for c in claims]
    anchors_ = [f"- `cite://{paper_id}/{c['anchor']}` {c['heading_path']}" for c in claims]
    page = (f"---\ntype: paper\ndoi: {meta['doi']}\ntitle: {meta['title']}\n"
            f"authors: {meta['authors']}\nyear: {meta['year'] or ''}\n"
            f"project: {meta['project']}\nsource_rel: {meta['source_rel']}\n"
            f"ocr_version: {meta['ocr_version']}\n"
            f"identity_status: {meta['identity_status']}\ncreated: code\n---\n\n"
            f"# {meta['title']}\n\n" + ("\n".join(lines) or "_(no anchored claims)_")
            + "\n\n## cite:// anchors\n\n" + ("\n".join(anchors_) or "_(none)_") + "\n")
    with open(os.path.join(kb, "papers", f"{paper_id}.md"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(kb, "log.md"), "a", encoding="utf-8") as f:
        f.write(f"- ingest | paper={paper_id} | claims={len(claims)}"
                + (f" | rebind={rebound}" if rebound else "") + "\n")


def remove_paper_page(paper_id: str) -> None:
    """forget_paper 联动：删归档页（log.md 留痕不删）。"""
    page = os.path.join(_kb_path(), "papers", f"{paper_id}.md")
    if os.path.exists(page):
        os.remove(page)
