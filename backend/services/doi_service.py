"""CrossRef DOI 权威校验适配器（Phase 1）。

vendor（backend/vendor/pdf_doi_toolkit/）逐字拷贝不修改；本层负责：
SSRF 域名白名单、timeout/重试压缩、标题覆盖硬门槛（补 vendor
_pick_best 初始分 -1 的缺口）、BibTeX content negotiation、离线降级
（失败不抛断流水线，标记 unverified）。
"""
import json
import re
import urllib.request
import urllib.error
import urllib.parse

from services.config_service import ConfigService

CROSSREF_HOST = "api.crossref.org"
CROSSREF_WORKS = "https://api.crossref.org/works"
DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s?#]+$")     # 防 URL 注入（R1）
TITLE_OVERLAP_MIN = 0.6                             # 自建标题门槛（R10）


class DoiServiceError(Exception):
    """DOI 服务错误（BibTeX 拉取失败等，端点层转 502）。"""


def _client(db):
    """CrossRefClient：UA 注入 mailto（R4）、压底重试参数（R2）。"""
    cfg = ConfigService(db).get_crossref_config()
    ua = f"AcademicClarity/1.0 (mailto:{cfg['mailto']})" if cfg["mailto"] else "AcademicClarity/1.0"
    from vendor.pdf_doi_toolkit import CrossRefClient
    return CrossRefClient(user_agent=ua, max_retries=cfg["max_retries"],
                          timeout=cfg["timeout"], request_delay=0.35)


def _assert_safe_url(url: str):
    """SSRF 防线：仅允许 https + api.crossref.org 字面量主机名；
    拒绝 userinfo（合法 CrossRef URL 永不含凭据，纵深防御）。"""
    p = urllib.parse.urlparse(url)
    if p.scheme != "https" or (p.hostname or "").lower() != CROSSREF_HOST:
        raise DoiServiceError(f"blocked non-crossref url: {url}")
    if "@" in (p.netloc or ""):
        raise DoiServiceError(f"blocked url with userinfo: {url}")


def normalize_doi(raw: str):
    """去 https://doi.org/ 前缀、剥 .sNNN；不匹配 DOI_RE 返回 None。"""
    if not raw:
        return None
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", raw.strip(), flags=re.I)
    from vendor.pdf_doi_toolkit.utils import strip_supplement
    d = strip_supplement(d).strip()
    return d if DOI_RE.match(d) else None


def _title_overlap(query: str, cr_title: str) -> float:
    """查询标题词在 CrossRef 标题中的覆盖率（补 vendor 缺口 R10）。"""
    q = {w for w in re.split(r"\W+", (query or "").lower()) if len(w) > 2}
    if not q:
        return 0.0
    t = {w for w in re.split(r"\W+", (cr_title or "").lower()) if len(w) > 2}
    return len(q & t) / len(q)


def verify_doi(title: str, authors: str, llm_doi: str, db=None) -> dict:
    """→ {"status": verified|corrected|mismatch|unverified, "doi": str|None,
         "score": int, "source": crossref|llm|unverified,
         "cr_author"/"cr_title": str|None, "note": str}"""
    llm_norm = normalize_doi(llm_doi or "")
    src_llm = {"status": "unverified", "doi": llm_norm, "score": 0,
               "source": "llm" if llm_norm else "unverified"}
    if not title:
        return {**src_llm, "note": "no_title"}
    try:
        res = _client(db).search_by_title(title, authors or None)   # 可能 raise（R5）
    except Exception as e:                       # 网络失败 / 非 429 HTTPError
        return {**src_llm, "note": f"crossref_error: {str(e)[:60]}"}
    cr_doi = normalize_doi(res.get("doi") or "")
    overlap = _title_overlap(title, res.get("title") or "")
    if not cr_doi:
        return {**src_llm, "note": res.get("note") or "no_good_match"}
    if overlap < TITLE_OVERLAP_MIN:              # 标题覆盖不足 → 不采信 CrossRef
        return {**src_llm, "note": "low_title_overlap"}
    from vendor.pdf_doi_toolkit.utils import authors_match
    author_ok = bool(authors) and authors_match(authors, res.get("author") or "")
    score = int(50 * overlap) + (50 if author_ok else 0)
    if authors and not author_ok:                # 作者不符 → 绝不改写 DOI
        return {"status": "mismatch", "doi": llm_norm or cr_doi, "score": score,
                "source": "llm", "cr_author": res.get("author"),
                "cr_title": res.get("title"), "note": "author_mismatch"}
    status = "verified" if (not llm_norm or llm_norm.lower() == cr_doi.lower()) else "corrected"
    return {"status": status, "doi": cr_doi, "score": score, "source": "crossref",
            "cr_author": res.get("author"), "cr_title": res.get("title"),
            "note": "no_author_to_verify" if not authors else "ok"}


def fetch_bibtex(doi: str, db=None) -> str:
    """content negotiation：Accept: application/x-bibtex（vendor 无此能力）。"""
    d = normalize_doi(doi or "")
    if not d:
        raise DoiServiceError("invalid doi")
    url = f"{CROSSREF_WORKS}/{urllib.parse.quote(d, safe='')}"   # safe='' 防 ../
    _assert_safe_url(url)
    cfg = ConfigService(db).get_crossref_config()
    req = urllib.request.Request(url, headers={
        "Accept": "application/x-bibtex",
        "User-Agent": f"AcademicClarity/1.0 (mailto:{cfg['mailto']})"})
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            return resp.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as e:
        raise DoiServiceError(f"crossref bibtex HTTP {e.code}")
    except Exception as e:
        raise DoiServiceError(f"crossref bibtex error: {str(e)[:60]}")


def verify_document(db, doc_id: int) -> dict:
    """task 链入口：读 Basic Insight → verify_doi → 落库。"""
    metas = db.get_document_metadata(doc_id)
    insight = next((m for m in metas if m["label"] == "Basic Insight"), None)
    if not insight:
        return {"status": "unverified", "note": "no_basic_insight"}
    data = json.loads(insight["content_json"])
    result = verify_doi(data.get("title") or "", data.get("authors") or "",
                        data.get("doi") or "", db)
    db.update_document_doi(doc_id, doi=result["doi"], doi_source=result["source"])
    return result
