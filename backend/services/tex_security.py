"""tex_security — tex 输入安全预检（B-SRP-12 拆分）。

zip-slip / 符号链接 / zip 炸弹防护、\\input 图绝对路径与越界拒绝、
文件大小上限。TexConversionError 定义于此（面向用户的统一异常）；
TexConfig 亦以此模块为单一导入点——tex_detect/tex_service 从此导入，
保证全子系统引用同一类对象（测试经 tex_service.TexConfig 改限值生效）。
"""
import os
import re
import zipfile

try:
    from backend.constants import TexConfig
except ImportError:
    from constants import TexConfig


class TexConversionError(Exception):
    """LaTeX 转换失败（编码/空输出/zip 非法/探测失败等），消息面向用户。"""


def _check_main_tex_size(main_tex_path: str) -> None:
    """主 .tex 大小上限（转换入口第一步）。"""
    if os.path.getsize(main_tex_path) > TexConfig.MAX_MAIN_TEX_BYTES:
        raise TexConversionError("主 .tex 文件超过大小上限")


def _check_zip_size(zip_path: str) -> None:
    """zip 本身上限（解压前检查）。"""
    if os.path.getsize(zip_path) > TexConfig.MAX_ZIP_BYTES:
        raise TexConversionError("zip 文件超过大小上限")


def _safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    """zip-slip 防护：逐条校验全部条目后才 extractall。"""
    dest_real = os.path.realpath(dest_dir)
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if os.path.isabs(name) or name.startswith(("/", "\\")) or os.path.splitdrive(name)[0]:
                raise TexConversionError(f"zip 含绝对路径条目: {name}")
            target = os.path.realpath(os.path.join(dest_real, name))
            if os.path.commonpath([dest_real, target]) != dest_real:
                raise TexConversionError(f"zip-slip 条目被拒绝: {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise TexConversionError(f"zip 含符号链接条目: {name}")
            total += info.file_size
            if total > TexConfig.MAX_ZIP_TOTAL_BYTES:
                raise TexConversionError("zip 解压总量超限")
        zf.extractall(dest_real)   # 全部条目已通过校验


def _validate_input_refs(main_tex_path: str) -> None:
    """镜像 resolver 的解析语义遍历 \\input 图，拒绝绝对路径与越出 root_dir 的
    ref（对应 resolver.py:23-24 任意本地文件读，风险 R6）。"""
    root_dir = os.path.dirname(os.path.abspath(main_tex_path))
    seen, stack, depth = set(), [os.path.abspath(main_tex_path)], 0
    while stack:
        cur = stack.pop()
        if cur in seen or depth > TexConfig.MAX_INPUT_DEPTH:
            continue
        seen.add(cur)
        depth += 1
        try:
            text = open(cur, 'r', encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue  # 读取问题交由 resolve_inputs/convert_tex 报错
        for m in re.finditer(r'\\(?:input|include)\{(.+?)\}', text):
            ref = m.group(1).strip()
            if os.path.isabs(ref) or os.path.splitdrive(ref)[0]:
                raise TexConversionError(f"拒绝绝对路径 \\input 引用: {m.group(1)}")
            if not ref.endswith('.tex'):
                ref += '.tex'
            child = os.path.normpath(os.path.join(os.path.dirname(cur), ref))
            if not os.path.isfile(child):
                child = os.path.normpath(os.path.join(root_dir, ref))
            if os.path.commonpath([root_dir, child]) != root_dir:
                raise TexConversionError(f"拒绝越界 \\input 引用: {m.group(1)}")
            stack.append(child)
