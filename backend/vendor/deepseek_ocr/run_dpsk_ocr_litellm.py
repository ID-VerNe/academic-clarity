import os
import base64
import io
import re
import fitz
import json
from tqdm import tqdm
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import litellm
from litellm import completion

# --- 配置区 ---
# --- 配置区 ---
# 硅基流动 API Key 列表，用于多 Key 并发
SILICON_API_KEYS = [
    "sk-amxyrkodwpvxguiumotfrgjirqstfqmghmiytbdvhriejtve"
]

# 动态计算并发数：每个 Key 分配 10 个 worker，总数不超过 64
MAX_WORKERS = min(len(SILICON_API_KEYS) * 10, 64) 

# 注意：硅基流动的 DeepSeek-OCR 模型路径通常如下

class Colors:
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    RESET = '\033[0m'

def pdf_to_images_high_quality(pdf_path, dpi=144):
    images = []
    pdf_document = fitz.open(pdf_path)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        img_data = pixmap.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        images.append(img)
    
    pdf_document.close()
    return images

def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def re_match(text):
    pattern = r'(<\|ref\|>(.*?)<\|/ref\|><\|det\|>(.*?)<\|/det\|>)'
    matches = re.findall(pattern, text, re.DOTALL)
    mathes_image = []
    mathes_other = []
    for a_match in matches:
        if '<|ref|>image<|/ref|>' in a_match[0]:
            mathes_image.append(a_match[0])
        else:
            mathes_other.append(a_match[0])
    return matches, mathes_image, mathes_other

def extract_coordinates(ref_text_match):
    try:
        # ref_text_match 是 re_match 返回的一个 tuple: (full_match, label, coords_str)
        cor_list = eval(ref_text_match[2])
        return cor_list
    except:
        return None

def process_page_with_api(args):
    image, page_idx, api_key = args
    base64_image = pil_to_base64(image)
    
    try:
        response = completion(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                        {"type": "text", "text": PROMPT}
                    ]
                }
            ],
            api_key=api_key,
            api_base=API_BASE,
            temperature=0,
            max_tokens=4096
        )
        content = response.choices[0].message.content
        return {"page_idx": page_idx, "content": content, "success": True}
    except Exception as e:
        print(f"Error processing page {page_idx}: {str(e)}")
        return {"page_idx": page_idx, "content": str(e), "success": False}

def save_layout_images(image, matches_ref, page_idx, output_dir):
    image_width, image_height = image.size
    img_idx = 0
    img_save_dir = os.path.join(output_dir, "images")
    os.makedirs(img_save_dir, exist_ok=True)
    
    for ref in matches_ref:
        if '<|ref|>image<|/ref|>' in ref[0]:
            points_list = extract_coordinates(ref)
            if points_list:
                for points in points_list:
                    x1, y1, x2, y2 = points
                    x1, y1 = int(x1 / 999 * image_width), int(y1 / 999 * image_height)
                    x2, y2 = int(x2 / 999 * image_width), int(y2 / 999 * image_height)
                    try:
                        cropped = image.crop((x1, y1, x2, y2))
                        cropped.save(os.path.join(img_save_dir, f"{page_idx}_{img_idx}.jpg"))
                    except:
                        pass
                    img_idx += 1

def main():
    if not SILICON_API_KEYS:
        print("Please provide at least one SiliconFlow API Key.")
        return

    if not os.path.exists(INPUT_PATH):
        print(f"File not found: {INPUT_PATH}")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print(f"{Colors.BLUE}Step 1: Rendering PDF to high-quality images...{Colors.RESET}")
    images = pdf_to_images_high_quality(INPUT_PATH, DPI)
    num_pages = len(images)
    print(f"Total pages: {num_pages}")

    print(f"{Colors.BLUE}Step 2: Processing pages with LiteLLM (Multi-key Concurrency)...{Colors.RESET}")
    
    tasks = []
    for i in range(num_pages):
        api_key = SILICON_API_KEYS[i % len(SILICON_API_KEYS)]
        tasks.append((images[i], i, api_key))

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(tqdm(executor.map(process_page_with_api, tasks), total=num_pages))

    results.sort(key=lambda x: x['page_idx'])

    print(f"{Colors.BLUE}Step 3: Post-processing and generating Markdown...{Colors.RESET}")
    
    final_md_content = ""
    page_split_tag = "\n\n"

    for res in results:
        if not res['success']:
            final_md_content += f"\n[Error on Page {res['page_idx']}: {res['content']}]\n{page_split_tag}"
            continue
        
        content = res['content']
        page_idx = res['page_idx']
        
        # 提取并保存子图
        matches_ref, matches_images, mathes_other = re_match(content)
        save_layout_images(images[page_idx], matches_ref, page_idx, OUTPUT_DIR)

        # 替换 Markdown 中的图片占位符
        for idx, a_match_image in enumerate(matches_images):
            content = content.replace(a_match_image, f'![](images/{page_idx}_{idx}.jpg)\n')

        # 清洗不需要的布局标签 (修复索引错误)
        for a_match_other in mathes_other:
            content = content.replace(a_match_other, '') 
            
        # 兜底清理：如果还有漏掉的标签
        content = re.sub(r'<\|ref\|>.*?<\|/ref\|>', '', content)
        content = re.sub(r'<\|det\|>.*?<\|/det\|>', '', content)
        content = re.sub(r'\|ref\|>.*?\|/ref\|>', '', content)
        content = re.sub(r'\|det\|>.*?\|/det\|>', '', content)

        # 友好转换 LaTeX 符号
        content = content.replace(r'\coloneqq', ':=').replace(r'\eqqcolon', '=:').replace(r'\approx', '≈')
        
        # 压缩冗余空行：将 3 个及以上的换行符统一压缩为 2 个
        content = re.sub(r'\n{3,}', '\n\n', content).strip()

        final_md_content += content + page_split_tag

    pdf_filename = os.path.basename(INPUT_PATH)
    md_filename = os.path.splitext(pdf_filename)[0] + ".md"
    md_file_path = os.path.join(OUTPUT_DIR, md_filename)
    
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(final_md_content)

    print(f"{Colors.GREEN}Done! Markdown saved to: {md_file_path}{Colors.RESET}")

if __name__ == "__main__":
    main()
