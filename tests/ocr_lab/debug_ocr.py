import os
import sys
import asyncio
import json
import fitz
from PIL import Image
from io import BytesIO
import base64
from litellm import completion

# 导入我们的核心服务进行测试
current = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(os.path.dirname(current))
sys.path.append(os.path.join(root, "backend"))

# 实验目标
TARGET_PDF = r"C:\Users\VerNe\Downloads\Documents\academic-clarity\workspace\10_1007-978-3-031-35233-1_6_1.pdf"
LAB_DIR = os.path.join(current, "output")

async def ocr_lab_phase_3():
    os.makedirs(LAB_DIR, exist_ok=True)
    import config as main_config
    ocr_config = {
        "api_key": main_config.DEEPSEEK_API_KEY,
        "api_base": main_config.API_BASE,
        "model_name": main_config.OCR_MODEL
    }

    doc = fitz.open(TARGET_PDF)
    pix = doc[0].get_pixmap(dpi=144)
    img = Image.open(BytesIO(pix.tobytes("png")))
    doc.close()
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # 实验：对比 Grounding vs Pure OCR 空间占用
    p = "<image>\nConvert this image to markdown flawlessly. High priority: transcribe the DOI and URLs in the footer."
    
    print(f"[Lab-P3] Starting Pure OCR (No Grounding)...")
    resp = await asyncio.to_thread(
        completion,
        model=ocr_config['model_name'],
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
            {"type": "text", "text": p}
        ]}],
        api_key=ocr_config['api_key'],
        api_base=ocr_config['api_base'],
        temperature=0,
        max_tokens=2048 # 故意调低，看是否有能力达到页脚
    )
    content = resp.choices[0].message.content
    with open(os.path.join(LAB_DIR, "p3_pure_ocr.md"), "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[Lab-P3] Saved.")

if __name__ == "__main__":
    asyncio.run(ocr_lab_phase_3())
