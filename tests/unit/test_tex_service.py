"""tex_service 单元测试（Phase 0）。

临时目录落系统 temp（ac_test_ 前缀）；路径引导经 tests/helpers 统一；
适配层自行把 backend/vendor 入 sys.path。固化 vendor 已知怪癖（Q1/Q2/Q3/Q7）。
"""
import os
import sys
import unittest
import shutil
import zipfile

# 路径引导：注入 tests/（helpers）与 backend/（被测模块）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import add_backend_to_sys_path, make_temp_ws  # noqa: E402
add_backend_to_sys_path()

from services.tex_service import (  # noqa: E402
    TexConversionError,
    convert_tex,
    convert_tex_zip,
    _find_main_tex,
    _extract_latex_title,
)


class TestTexService(unittest.TestCase):
    def setUp(self):
        # 临时目录落系统 temp（ac_test_ 前缀，调度器可清理）
        self.tmp = make_temp_ws("ac_test_tex_unit")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    # ── 基础转换 ──────────────────────────────────────────────

    def test_convert_basic_sections_and_formatting(self):
        p = self._write("basic.tex", (
            "\\documentclass{article}\n\\begin{document}\n"
            "\\section{Intro}\nHello \\textbf{bold} and \\textit{it}.\n"
            "\\end{document}\n"
        ))
        md = convert_tex(p)
        self.assertIn("# Intro", md)
        self.assertIn("**bold**", md)
        self.assertIn("*it*", md)
        self.assertNotIn("\\documentclass", md)

    def test_body_extraction_drops_preamble(self):
        # 无导言区时正确截断（body_start=0，body_end 索引有效）
        p = self._write("preamble.tex", (
            "\\begin{document}\nBody only.\n\\end{document}\n"
            "\\section{After} never reached\n"
        ))
        md = convert_tex(p)
        self.assertIn("Body only.", md)
        self.assertNotIn("never reached", md)

    def test_body_extraction_quirk_preamble_leaks_after_end_document(self):
        # 固化 vendor 怪癖（processor.py:31-43）：有导言区时 body_end 按
        # 原文索引切片，\\end{document} 之后的内容会残留。
        p = self._write("preamble2.tex", (
            "\\documentclass{article}\n\\usepackage{amsmath}\n"
            "\\begin{document}\nBody only.\n\\end{document}\n"
            "\\section{After} leaked\n"
        ))
        md = convert_tex(p)
        self.assertIn("Body only.", md)
        self.assertNotIn("amsmath", md)   # 导言区仍被丢弃
        self.assertIn("leaked", md)       # 但 end{document} 后内容残留（已知怪癖）

    def test_no_document_environment_keeps_all(self):
        # Q1 固化：无 \begin{document} 时全文处理，\documentclass 残入输出
        p = self._write("nodoc.tex", "\\documentclass{article}\n\\section{Frag}\nText.\n")
        md = convert_tex(p)
        self.assertIn("# Frag", md)
        self.assertIn("Text.", md)

    def test_abstract_becomes_first_h1(self):
        # Q2 固化：步 3 先于步 5，首个 H1 恒为 # Abstract
        p = self._write("abs.tex", (
            "\\begin{document}\n\\begin{abstract}\nWe show X.\n\\end{abstract}\n"
            "\\section{Intro}\nHi.\n\\end{document}\n"
        ))
        md = convert_tex(p)
        self.assertTrue(md.startswith("# Abstract"))
        self.assertIn("We show X.", md)

    # ── \input 展开 ───────────────────────────────────────────

    def test_input_expansion_sibling_and_subdir(self):
        self._write("sub/child.tex", "\\section{Child}\nFrom child.\n")
        p = self._write("main.tex", (
            "\\begin{document}\n\\input{sub/child}\n\\input{sib}\n\\end{document}\n"
        ))
        self._write("sib.tex", "Sibling content.\n")
        md = convert_tex(p)
        self.assertIn("# Child", md)
        self.assertIn("From child.", md)
        self.assertIn("Sibling content.", md)

    def test_root_dir_fallback(self):
        # resolver.py:72-75：相对当前文件找不到时回退 root_dir
        self._write("shared.tex", "\\section{Shared}\nRoot fallback.\n")
        self._write("sub/inner.tex", "\\input{shared}\n")
        p = self._write("main.tex", "\\begin{document}\n\\input{sub/inner}\n\\end{document}\n")
        md = convert_tex(p)
        self.assertIn("Root fallback.", md)

    def test_cyclic_input_terminates(self):
        self._write("a.tex", "\\input{b}\nA content.\n")
        self._write("b.tex", "\\input{a}\nB content.\n")
        p = self._write("main.tex", "\\begin{document}\n\\input{a}\n\\end{document}\n")
        md = convert_tex(p)  # 不死循环即通过
        self.assertIn("A content.", md)

    def test_diamond_input_second_expansion_empty(self):
        # Q3 固化：seen 跨递归共享，菱形引用第二次展开为 ''
        self._write("d.tex", "Shared leaf.\n")
        self._write("b.tex", "\\input{d}\nB path.\n")
        self._write("c.tex", "\\input{d}\nC path.\n")
        p = self._write("main.tex", "\\begin{document}\n\\input{b}\n\\input{c}\n\\end{document}\n")
        md = convert_tex(p)
        self.assertEqual(md.count("Shared leaf."), 1)  # 只出现一次

    def test_missing_input_warns_and_continues(self):
        p = self._write("main.tex", (
            "\\begin{document}\n\\input{nonexistent}\nAfter missing.\n\\end{document}\n"
        ))
        md = convert_tex(p)  # stderr 警告后返回 ''，不抛异常
        self.assertIn("After missing.", md)

    # ── 失败路径 ──────────────────────────────────────────────

    def test_non_utf8_raises_tex_conversion_error(self):
        p = os.path.join(self.tmp, "latin.tex")
        with open(p, "wb") as f:
            f.write(b"\\begin{document}\n\\section{Caf\xe9}\n\\end{document}\n")
        with self.assertRaises(TexConversionError) as ctx:
            convert_tex(p)
        self.assertIn("UTF-8", str(ctx.exception))

    def test_empty_output_raises(self):
        # 纯注释文件 → remove_comments 后为空 → 抛错（不写空 markdown）
        p = self._write("empty.tex", "% only a comment\n")
        with self.assertRaises(TexConversionError):
            convert_tex(p)

    def test_absolute_input_ref_rejected(self):
        # R6 回归：绝对路径 \input 是任意本地文件读向量
        secret = self._write("secret.tex", "TOPSECRET-CONTENT\n")
        p = self._write("evil.tex", (
            "\\begin{document}\n"
            f"\\input{{{secret.replace(os.sep, '/')}}}\n"
            "\\end{document}\n"
        ))
        with self.assertRaises(TexConversionError) as ctx:
            convert_tex(p)
        self.assertIn("绝对路径", str(ctx.exception))

    def test_oversized_main_tex_rejected(self):
        p = self._write("big.tex", "\\begin{document}\nx\n\\end{document}\n")
        from services.tex_service import TexConfig
        old = TexConfig.MAX_MAIN_TEX_BYTES
        TexConfig.MAX_MAIN_TEX_BYTES = 10
        try:
            with self.assertRaises(TexConversionError):
                convert_tex(p)
        finally:
            TexConfig.MAX_MAIN_TEX_BYTES = old

    # ── 环境保护 / 引用 / 脚注 ────────────────────────────────

    def test_protected_environment_restored_verbatim(self):
        p = self._write("eq.tex", (
            "\\begin{document}\n"
            "\\begin{equation}\nE = mc^2\n\\end{equation}\n"
            "\\end{document}\n"
        ))
        md = convert_tex(p)
        self.assertIn("\\begin{equation}", md)  # 原样保留
        self.assertIn("E = mc^2", md)

    def test_citations_and_footnotes_placeholders(self):
        p = self._write("cite.tex", (
            "\\begin{document}\nSee \\cite{foo} and \\ref{bar}.\n"
            "Text\\footnote{a note}.\n\\end{document}\n"
        ))
        md = convert_tex(p)
        self.assertIn("[citation]", md)
        self.assertIn("[ref]", md)
        self.assertIn("(a note)", md)

    # ── 标题提取（Q2 规避）────────────────────────────────────

    def test_extract_latex_title_brace_counting(self):
        p = self._write("title.tex", (
            "\\title{A Study of \\textbf{Bold} Things}\n\\begin{document}\n\\end{document}\n"
        ))
        self.assertEqual(_extract_latex_title(p), "A Study of \\textbf{Bold} Things")

    def test_extract_latex_title_missing(self):
        p = self._write("notitle.tex", "\\begin{document}\n\\end{document}\n")
        self.assertIsNone(_extract_latex_title(p))

    # ── 主 tex 探测 ───────────────────────────────────────────

    def test_find_main_tex_heuristics(self):
        self._write("preamble.tex", "\\usepackage{x}\n")           # 无 documentclass
        self._write("appendix.tex", "\\section{A}\n")              # 被 main 引用
        self._write("main.tex", "\\documentclass{article}\n\\begin{document}\n\\input{appendix}\n\\end{document}\n")
        best = _find_main_tex(self.tmp)
        self.assertEqual(os.path.basename(best), "main.tex")

    def test_find_main_tex_none_with_documentclass_raises(self):
        self._write("frag.tex", "\\section{No class}\n")
        with self.assertRaises(TexConversionError):
            _find_main_tex(self.tmp)

    # ── zip 快乐路径 ──────────────────────────────────────────

    def test_convert_tex_zip_happy_path(self):
        zip_path = os.path.join(self.tmp, "src.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("arxiv/main.tex", (
                "\\documentclass{article}\n\\title{Zip Paper}\n"
                "\\begin{document}\n\\section{One}\nAlpha.\n"
                "\\input{sections/two}\n\\end{document}\n"
            ))
            zf.writestr("arxiv/sections/two.tex", "\\section{Two}\nBeta.\n")
        dest = os.path.join(self.tmp, "src_out")
        md = convert_tex_zip(zip_path, dest)
        self.assertIn("# One", md)
        self.assertIn("Alpha.", md)
        self.assertIn("# Two", md)
        self.assertIn("Beta.", md)
        self.assertEqual(_extract_latex_title(_find_main_tex(dest)), "Zip Paper")


if __name__ == "__main__":
    unittest.main()
