import re

def clean_ocr_markdown(md_text):
    """
    Cleans OCR-generated markdown by removing model-specific tags and normalizing LaTeX.
    """
    cleaned = re.sub(r'<\|?ref\|>.*?<\|/ref\|>', '', md_text, flags=re.DOTALL)
    cleaned = re.sub(r'<\|?det\|>.*?<\|/det\|>', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.replace(r'\coloneqq', ':=').replace(r'\eqqcolon', '=:').replace(r'\approx', '≈')
    cleaned = re.sub(r'\n\s*#', '\n#', cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned

def extract_title_from_markdown(md_text):
    """
    Extracts the document title from the first H1 header or falls back to the first non-empty line.
    """
    text = clean_ocr_markdown(md_text)
    title_match = re.search(r'^# (.*)', text, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    return lines[0] if lines else "Untitled Document"
