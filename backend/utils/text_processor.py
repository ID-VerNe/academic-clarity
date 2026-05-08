import re

def clean_ocr_markdown(md_text):
    """
    整合自官方 DeepSeek-OCR 的高保真后处理逻辑。
    1. 提取 ref 标签内的文字内容，删除 det 坐标标签。
    2. 转换学术 LaTeX 符号。
    3. 规范化空行。
    """
    if not md_text:
        return ""

    # 1. 提取 ref 标签内的文字，删除 det 标签及其坐标
    # DeepSeek-OCR 格式: <|ref|>文字内容<|/ref|><|det|>[[x1,y1,x2,y2]]<|/det|>
    # 保留文字内容，删除整个标签对
    pattern = r'<\|ref\|>(.*?)<\|/ref\|><\|det\|>.*?<\|/det\|>'
    cleaned = re.sub(pattern, r'\1', md_text, flags=re.DOTALL)

    # 2. 清理可能残留的单边标签
    cleaned = re.sub(r'<\|?/?ref\|>', '', cleaned)
    cleaned = re.sub(r'<\|?/?det\|>', '', cleaned)

    # 3. 转换 LaTeX 学术符号为易读符号
    cleaned = cleaned.replace(r'\coloneqq', ':=').replace(r'\eqqcolon', '=:').replace(r'\approx', '≈')

    # 4. 规范化标题
    cleaned = re.sub(r'\n\s*#', '\n#', cleaned)

    # 5. 压缩过度空行：将 3 个及以上的换行符统一压缩为 2 个
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()

    return cleaned

def parse_structured_ocr_content(md_text):
    """
    Parse tagged OCR text into structured JSON blocks.
    Supported tags: title, text, sub_title/subtitle.
    """
    empty_result = {"version": 1, "blocks": []}
    if not md_text:
        return empty_result

    normalized = md_text.replace("\r\n", "\n")
    # DeepSeek sometimes appends tokens in-line with double spaces (e.g. "...  text")
    normalized = re.sub(r'(?i)[ \t]{2,}(sub_title|subtitle|title|text)(?=[ \t\n]|$)', r'\n\1', normalized)
    normalized = re.sub(r'(?i)(sub_title|subtitle|title|text)[ \t]{2,}', r'\1\n', normalized)

    blocks = []
    pending_tag = None
    saw_tag = False

    def normalize_block_type(tag):
        lowered = tag.strip().lower()
        if lowered == "title":
            return "title"
        if lowered in ("sub_title", "subtitle"):
            return "subtitle"
        return "text"

    def append_block(block_type, value):
        text = value.strip()
        if not text:
            return
        normalized_type = normalize_block_type(block_type)
        if normalized_type in ("title", "subtitle"):
            text = re.sub(r'^#{1,6}\s*', '', text).strip()
            if not text:
                return
        if normalized_type == "text" and blocks and blocks[-1]["type"] == "text":
            blocks[-1]["text"] = f"{blocks[-1]['text']}\n{text}"
            return
        blocks.append({"type": normalized_type, "text": text})

    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower()
        if lowered in ("title", "text", "sub_title", "subtitle"):
            saw_tag = True
            pending_tag = lowered
            continue

        inline_match = re.match(
            r'^(title|text|sub_title|subtitle)\s*[:：-]?\s*(.+)$',
            line,
            flags=re.IGNORECASE
        )
        if inline_match:
            saw_tag = True
            append_block(inline_match.group(1), inline_match.group(2))
            pending_tag = None
            continue

        if pending_tag:
            append_block(pending_tag, line)
            pending_tag = None
            continue

        append_block("text", line)

    if not saw_tag:
        return empty_result
    return {"version": 1, "blocks": blocks}

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
