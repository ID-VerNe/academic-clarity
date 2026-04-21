import os
import sys
import asyncio
import json
import fitz
from PIL import Image
from io import BytesIO

# 导入我们的核心服务进行测试
current = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(os.path.dirname(current))
sys.path.append(os.path.join(root, "backend"))

from services.ai_service import call_ocr_api
from services.config_service import ConfigService
from database import Database

# 实验目标
TARGET_PDF = r"C:\Users\VerNe\Downloads\Documents\academic-clarity\workspace\10_1007-978-3-031-35233-1_6_1.pdf"
LAB_DIR = os.path.join(current, "output")

async def ocr_lab_experiment():
    os.makedirs(LAB_DIR, exist_ok=True)
    
    # 1. 准备配置 (Mock 一个临时库用于拿 Key)
    db = Database(":memory:")
    # 从主 config.py 读取 Key
    import config as main_config
    ocr_config = {
        "api_key": main_config.DEEPSEEK_API_KEY,
        "api_base": main_config.API_BASE,
        "model_name": main_config.OCR_MODEL
    }
    
    print(f"[Lab] Target PDF: {TARGET_PDF}")
    print(f"[Lab] Model: {ocr_config['model_name']}")

    # 2. 仅处理第一页 (DOI 通常在这里)
    doc = fitz.open(TARGET_PDF)
    page = doc[0]
    pix = page.get_pixmap(dpi=144)
    img = Image.open(BytesIO(pix.tobytes("png")))
    doc.close()

    # 3. 实验不同 Prompt
    prompts = {
        "Standard": "<image>\n<|grounding|>Convert the document to markdown.",
        "Deep_Metadata": "<image>\n<|grounding|>Convert this document page into high-fidelity markdown. CRITICAL: Do NOT skip footnotes, page headers, or DOIs. Include all formulas and table data accurately."
    }

    results = {}
    for name, p in prompts.items():
        print(f"[Lab] Running Experiment: {name}...")
        # 临时覆盖全局 prompt (由于 ai_service 里的 prompt 是硬编码的，我们直接调 completion 模拟)
        from litellm import completion
        import base64
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        try:
            resp = await asyncio.to_thread(
                completion,
                model=ocr_config['model_name'],
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": p}
                ]}],
                api_key=ocr_config['api_key'],
                api_base=ocr_config['api_base'],
                temperature=0
            )
            results[name] = resp.choices[0].message.content
        except Exception as e:
            results[name] = f"Error: {e}"

    # 4. 保存结果进行对比
    for name, content in results.items():
        save_path = os.path.join(LAB_DIR, f"ocr_{name.lower()}.md")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[Lab] Result for {name} saved to {save_path}")

if __name__ == "__main__":
    asyncio.run(ocr_lab_experiment())
