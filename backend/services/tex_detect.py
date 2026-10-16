"""tex_detect — arXiv 源码包主 .tex 探测与 \\title 提取（B-SRP-12 拆分）。"""
import os
import re

from services.tex_security import TexConfig, TexConversionError


def _find_main_tex(dest_dir: str) -> str:
    """arXiv 源码包主 .tex 探测：\\documentclass(+100) > 被 \\input 次数×10 >
    \\begin{document}(+5) > 常见文件名(+3) > 路径更浅(-2/层)。"""
    tex_files = []
    for root, dirs, files in os.walk(dest_dir):
        dirs[:] = [d for d in dirs if d != "__MACOSX"]
        tex_files += [os.path.join(root, f) for f in files if f.lower().endswith(".tex")]
    if not tex_files:
        raise TexConversionError("zip 中未找到 .tex 文件")
    texts = {}
    for p in tex_files:
        try:
            texts[p] = open(p, encoding='utf-8', errors='ignore').read()
        except OSError:
            texts[p] = ""
    stems = {p: os.path.splitext(os.path.basename(p))[0] for p in tex_files}
    refs = {p: sum(1 for q, qt in texts.items() if q != p
                   and re.search(r'\\(?:input|include)\{' + re.escape(stems[p]) + r'\}', qt))
            for p in tex_files}
    best, best_score = None, -1
    for p in tex_files:
        t = texts[p]
        score = (100 if r"\documentclass" in t else 0) + (5 if r"\begin{document}" in t else 0)
        score += 10 * refs[p] - 2 * os.path.relpath(p, dest_dir).count(os.sep)
        if stems[p].lower() in TexConfig.MAIN_TEX_NAME_HINTS:
            score += 3
        if score > best_score:
            best, best_score = p, score
    if best is None or best_score < 100:
        raise TexConversionError("未探测到含 \\documentclass 的主 .tex")
    return best


def _extract_latex_title(main_tex_path: str) -> str | None:
    """花括号计数提取 \\title{…}，规避怪癖 Q2（首个 H1 是 Abstract）。"""
    try:
        text = open(main_tex_path, 'r', encoding='utf-8', errors='ignore').read()
    except OSError:
        return None
    m = re.search(r'\\title\{', text)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(text) and depth:
        depth += 1 if text[i] == '{' else (-1 if text[i] == '}' else 0)
        i += 1
    return text[m.end():i - 1].strip() or None
