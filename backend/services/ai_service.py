import base64
import io
import asyncio
import json
from PIL import Image
from litellm import completion

async def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

async def call_ocr_api(image, api_config):
    """
    Calls SiliconFlow DeepSeek-OCR API with 4000 token limit to avoid 8192 context wall.
    """
    base64_image = await pil_to_base64(image)
    prompt = "<image>\n<|grounding|>Convert this document page into high-fidelity markdown. CRITICAL: Include all metadata, DOI strings, and footer text. Do NOT skip any word from the bottom of the page."
    
    try:
        response = await asyncio.to_thread(
            completion,
            model=api_config['model_name'],
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                {"type": "text", "text": prompt}
            ]}],
            api_key=api_config['api_key'],
            api_base=api_config['api_base'],
            temperature=0,
            max_tokens=4000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[API] OCR Error: {e}")
        return f"OCR Failed: {str(e)}"

async def call_chat_api(query, context, api_config):
    """
    World-class academic researcher chat.
    """
    try:
        response = await asyncio.to_thread(
            completion,
            model=api_config['model_name'],
            messages=[
                {"role": "system", "content": "You are a specialized academic assistant. Answer based ONLY on the provided context."},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUERY:\n{query}"}
            ],
            api_key=api_config['api_key'],
            api_base=api_config['api_base'],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Chat Error: {str(e)}"

async def call_json_extraction_api(md_content, api_config, prompt_instructions):
    """
    Converts Markdown to structured JSON.
    """
    try:
        sys_prompt = "You are an academic JSON extractor. Return ONLY raw JSON."
        if "DOI" in prompt_instructions:
            prompt_instructions += "\nCRITICAL: If a DOI URL exists, extract the '10.xxx' part."

        response = await asyncio.to_thread(
            completion,
            model=api_config['model_name'],
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"{prompt_instructions}\n\nCONTENT:\n{md_content}"}
            ],
            api_key=api_config['api_key'],
            api_base=api_config['api_base'],
            temperature=0.1
        )
        raw_content = response.choices[0].message.content
        if "```json" in raw_content:
            raw_content = raw_content.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_content:
            raw_content = raw_content.split("```")[1].strip()
        
        json.loads(raw_content) 
        return raw_content
            
    except Exception as e:
        # 特殊处理：测试脚本期望特定的错误字符串格式
        return json.dumps({"error": "Model returned invalid JSON", "detail": str(e)})
