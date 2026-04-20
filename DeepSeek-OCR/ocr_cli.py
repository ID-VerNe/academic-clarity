import os
import base64
import io
import re
import fitz
import json
import argparse
import time
from tqdm import tqdm
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import litellm
from litellm import completion

# --- 默认配置 ---
DEFAULT_API_KEYS = [
    "sk-amxyrkodwpvxguiumotfrgjirqstfqmghmiytbdvhriejtve"
]
MODEL_NAME = "openai/deepseek-ai/DeepSeek-OCR"
API_BASE = "https://api.siliconflow.cn/v1"
PROMPT = "<image>
<|grounding|>Convert the document to markdown."
DPI = 144

class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    RESET = '\033[0m'

def pdf_to_images(pdf_path, dpi=144):
    images = []
    try:
        pdf_document = fitz.open(pdf_path)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            images.append(Image.open(io.BytesIO(pixmap.tobytes("png"))))
        pdf_document.close()
    except Exception as e:
        print(f"{Colors.RED}Error rendering PDF {pdf_path}: {e}{Colors.RESET}")
    return images

def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def re_match(text):
    pattern = r'(<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>)'
    matches = re.findall(pattern, text, re.DOTALL)
    mathes_image = [m[0] for m in matches if '<|ref|>image<|/ref|>' in m[0]]
    mathes_other = [m[0] for m in matches if '<|ref|>image<|/ref|>' not in m[0]]
    return matches, mathes_image, mathes_other

def process_page_with_retry(image, page_idx, api_key, retries=3):
    base64_image = pil_to_base64(image)
    for attempt in range(retries):
        try:
            response = completion(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                    {"type": "text", "text": PROMPT}
                ]}],
                api_key=api_key,
                api_base=API_BASE,
                temperature=0,
                max_tokens=4096,
                timeout=60
            )
            return {"page_idx": page_idx, "content": response.choices[0].message.content, "success": True}
        except Exception as e:
            if "max_tokens" in str(e): # 尝试缩小 max_tokens 再次请求
                try:
                    response = completion(
                        model=MODEL_NAME,
                        messages=[{"role": "user", "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                            {"type": "text", "text": PROMPT}
                        ]}],
                        api_key=api_key,
                        api_base=API_BASE,
                        temperature=0,
                        max_tokens=2048
                    )
                    return {"page_idx": page_idx, "content": response.choices[0].message.content, "success": True}
                except: pass
            
            print(f"Page {page_idx} attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt) # 指数退避
    return {"page_idx": page_idx, "content": f"Failed after {retries} retries", "success": False}

def clean_markdown(content, page_idx, images_dir, image_pil, matches_ref):
    # 提取子图
    image_width, image_height = image_pil.size
    img_idx = 0
    for ref in matches_ref:
        if '<|ref|>image<|/ref|>' in ref[0]:
            try:
                coords = eval(ref[2])
                for points in coords:
                    x1, y1, x2, y2 = [int(p / 999 * (image_width if i%2==0 else image_height)) for i, p in enumerate(points)]
                    image_pil.crop((x1, y1, x2, y2)).save(os.path.join(images_dir, f"p{page_idx}_{img_idx}.jpg"))
                    content = content.replace(ref[0], f'![](images/p{page_idx}_{img_idx}.jpg)
')
                    img_idx += 1
            except: pass

    # 清洗标签
    content = re.sub(r'\|?ref\|>.*?\|/ref\|>', '', content)
    content = re.sub(r'\|?det\|>.*?\|/det\|>', '', content)
    content = content.replace(r'\coloneqq', ':=').replace(r'\eqqcolon', '=:').replace(r'\approx', '≈')
    content = re.sub(r'
{3,}', '

', content).strip()
    return content

def process_single_pdf(pdf_path, output_base, api_keys):
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    pdf_out_dir = os.path.join(output_base, pdf_name)
    images_dir = os.path.join(pdf_out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    print(f"{Colors.BLUE}Processing: {pdf_name}{Colors.RESET}")
    images = pdf_to_images(pdf_path, DPI)
    if not images: return
    
    max_workers = min(len(api_keys) * 10, 64)
    tasks = [(images[i], i, api_keys[i % len(api_keys)]) for i in range(len(images))]
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(executor.map(lambda x: process_page_with_retry(*x), tasks), total=len(images), desc=f"OCR {pdf_name}"))
    
    results.sort(key=lambda x: x['page_idx'])
    
    final_md = ""
    for res in results:
        if not res['success']:
            final_md += f"

> [Error on Page {res['page_idx']}: {res['content']}]

"
            continue
        
        matches_all, _, _ = re_match(res['content'])
        cleaned = clean_markdown(res['content'], res['page_idx'], images_dir, images[res['page_idx']], matches_all)
        final_md += cleaned + "

"
    
    with open(os.path.join(pdf_out_dir, f"{pdf_name}.md"), "w", encoding="utf-8") as f:
        f.write(final_md)
    print(f"{Colors.GREEN}Saved to {pdf_out_dir}{Colors.RESET}")

def main():
    parser = argparse.ArgumentParser(description="DeepSeek-OCR PDF to Markdown CLI")
    parser.add_argument("input", help="Path to PDF file or directory")
    parser.add_argument("--output", default="output_results", help="Base output directory")
    parser.add_argument("--keys", nargs="+", help="Optional: List of API keys")
    args = parser.parse_args()
    
    api_keys = args.keys if args.keys else DEFAULT_API_KEYS
    if not api_keys:
        print(f"{Colors.RED}No API keys provided!{Colors.RESET}")
        return

    input_path = os.path.abspath(args.input)
    if os.path.isfile(input_path):
        process_single_pdf(input_path, args.output, api_keys)
    elif os.path.isdir(input_path):
        pdf_files = [os.path.join(input_path, f) for f in os.listdir(input_path) if f.lower().endswith('.pdf')]
        for pdf in pdf_files:
            process_single_pdf(pdf, args.output, api_keys)
    else:
        print(f"{Colors.RED}Invalid input path: {input_path}{Colors.RESET}")

if __name__ == "__main__":
    main()
