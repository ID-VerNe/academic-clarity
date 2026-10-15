"""提取结果导出（Phase 3，litrev postproc 的最小有用子集）。

- flatten_record：顶层键打平为列（借鉴 export_csv 列并集思路）
- sanitize_csv_cell：CSV 公式注入防护（= + - @ \\t \\r 前缀加 ' 中和）
- build_csv：UTF-8 BOM + \\r\\n（Windows Excel 中文兼容）
- build_markdown：分文档节报告（不用宽表格，长文本不破坏结构）
- safe_filename：Content-Disposition 文件名消毒（路径穿越/头注入）
"""
import csv
import io
import json
import re
from datetime import datetime


def flatten_record(obj: dict) -> dict:
    """顶层键打平为列：标量转 str；dict/list → 紧凑 JSON；None → ''。"""
    out = {}
    for k, v in (obj or {}).items():
        if isinstance(v, (dict, list)):
            out[str(k)] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        else:
            out[str(k)] = "" if v is None else str(v)
    return out


def sanitize_csv_cell(v) -> str:
    """CSV 公式注入防护：以 = + - @ \\t \\r 开头的字符串加 ' 前缀。

    Excel/Sheets 会执行以这些字符开头的单元格（如 =cmd|'/C calc'!A0），
    加 ' 前缀强制按文本处理（OWASP CSV Injection 缓解措施）。"""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def build_csv(dimension: dict, rows: list) -> str:
    """表头 = 固定列 + 打平列并集（排序）；单元格全部过注入防护。"""
    flat_rows = [flatten_record(r.get("data")) for r in rows]
    extra_cols = sorted({k for fr in flat_rows for k in fr})
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["doc_id", "filename", "title", "created_at"] + extra_cols)
    for r, fr in zip(rows, flat_rows):
        writer.writerow(
            [sanitize_csv_cell(r.get("doc_id")), sanitize_csv_cell(r.get("filename")),
             sanitize_csv_cell(r.get("title")), sanitize_csv_cell(r.get("created_at"))]
            + [sanitize_csv_cell(fr.get(c, "")) for c in extra_cols])
    return "\ufeff" + buf.getvalue()


def md_escape(v) -> str:
    """Markdown 值净化：换行 → <br>，竖线转义，去首尾空白。"""
    s = "" if v is None else str(v)
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return s.replace("|", "\\|").strip()


def build_markdown(dimension: dict, rows: list) -> str:
    """分文档节报告：元信息行（R4 可追溯）+ 每文档 '- **key**: value'。"""
    lines = [f"# 导出报告：{md_escape(dimension.get('label'))}", "",
             f"- dimension_id: `{dimension.get('id')}`",
             f"- 文档数: {len(rows)}",
             f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
             f"- prompt 长度: {len(dimension.get('prompt') or '')} 字符", ""]
    for r in rows:
        lines.append(f"## {md_escape(r.get('filename') or r.get('doc_id'))}")
        lines.append("")
        if r.get("title"):
            lines.append(f"- **title**: {md_escape(r.get('title'))}")
        data = r.get("data") or {}
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
            lines.append(f"- **{md_escape(k)}**: {md_escape(v)}")
        lines.append("")
    if not rows:
        lines.append("_无提取结果_")
    return "\n".join(lines) + "\n"


def safe_filename(label: str, ext: str) -> str:
    """文件名消毒：只留词字符/中文/连字符，其余转 _（防 ../ 与头注入）。"""
    base = re.sub(r"[^\w\u4e00-\u9fff-]", "_", str(label or "export"))[:60] or "export"
    return f"{base}.{ext}"
