import re

def clean_ocr_markdown(md_text):
    """
    整合自官方 DeepSeek-OCR 的高保真后处理逻辑。
    1. 移除布局标签 (ref/det)。
    2. 转换学术 LaTeX 符号。
    3. 规范化空行。
    """
    if not md_text:
        return ""

    # 1. 移除标准的 ref/det 标签对
    # 官方正则模式: (<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>)
    pattern = r'<\|?ref\|>.*?<\|/ref\|><\|?det\|>.*?<\|/det\|>'
    cleaned = re.sub(pattern, '', md_text, flags=re.DOTALL)
    
    # 2. 移除可能残留的单边标签
    cleaned = re.sub(r'<\|?/?ref\|>', '', cleaned)
    cleaned = re.sub(r'<\|?/?det\|>', '', cleaned)
    
    # 3. 转换 LaTeX 学术符号为易读符号
    cleaned = cleaned.replace(r'\coloneqq', ':=').replace(r'\eqqcolon', '=:').replace(r'\approx', '≈')
    
    # 4. 规范化标题
    cleaned = re.sub(r'\n\s*#', '\n#', cleaned)
    
    # 5. 压缩过度空行：将 3 个及以上的换行符统一压缩为 2 个
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    
    return cleaned

def extract_title_from_markdown(md_text):
    """
    从 Markdown 中提取最可能的标题。
    """
    # 优先找 H1 或 H2
    title_match = re.search(r'^(?:#|##) (.*)', md_text, re.MULTILINE)
    if title_match:
        # 清洗掉可能带入的标签
        raw_title = title_match.group(1).strip()
        return clean_ocr_markdown(raw_title)
    
    lines = [l.strip() for l in md_text.split('\n') if l.strip()]
    return lines[0] if lines else "Untitled Document"
