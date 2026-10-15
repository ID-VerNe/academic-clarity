import base64
import io
import asyncio
import json
from typing import Optional, Callable, Any
from PIL import Image
from litellm import completion

try:
    from backend.constants import APIConfig
except ImportError:
    from constants import APIConfig

class APIResponseError(Exception):
    """API 返回了错误响应"""
    def __init__(self, message: str, raw_response: str = None):
        self.raw_response = raw_response
        super().__init__(message)

async def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

async def call_ocr_api(image, api_config):
    prompt = "<image>\n<|grounding|>Convert the document to markdown."
    base64_image = await pil_to_base64(image)

    model_name = api_config.get('model_name', '')
    if not model_name:
        print("[API] OCR Error: OCR_MODEL not configured")
        return "OCR Failed: OCR_MODEL not configured in settings"

    try:
        response = await asyncio.to_thread(
            completion,
            model=model_name,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                {"type": "text", "text": prompt}
            ]}],
            api_key=api_config['api_key'],
            api_base=api_config['api_base'],
            temperature=0,
            max_tokens=4000,
            timeout=APIConfig.REQUEST_TIMEOUT
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        raise APIResponseError(f"OCR timeout after {APIConfig.REQUEST_TIMEOUT}s")
    except Exception as e:
        print(f"[API] OCR Error: {e}")
        return f"OCR Failed: {str(e)}"

async def call_chat_api(query, context, api_config):
    model_name = api_config.get('model_name', '')
    if not model_name:
        return "Chat Error: LLM_MODEL not configured in settings"

    try:
        response = await asyncio.to_thread(
            completion,
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a specialized academic assistant. Answer based ONLY on the provided context."},
                {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUERY:\n{query}"}
            ],
            api_key=api_config['api_key'],
            api_base=api_config['api_base'],
            temperature=APIConfig.DEFAULT_TEMPERATURE,
            timeout=APIConfig.REQUEST_TIMEOUT
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        raise APIResponseError(f"Chat timeout after {APIConfig.REQUEST_TIMEOUT}s")
    except Exception as e:
        raise APIResponseError(f"Chat Error: {str(e)}")

async def call_json_extraction_api(md_content, api_config, prompt_instructions):
    sys_prompt = "You are an academic JSON extractor. Return ONLY raw JSON."
    if "DOI" in prompt_instructions:
        prompt_instructions += "\nCRITICAL: If a DOI URL exists, extract the '10.xxx' part."

    model_name = api_config.get('model_name', '')
    if not model_name:
        return json.dumps({"error": "Extraction failed: LLM_MODEL not configured in settings"})

    try:
        response = await asyncio.to_thread(
            completion,
            model=model_name,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"{prompt_instructions}\n\nCONTENT:\n{md_content}"}
            ],
            api_key=api_config['api_key'],
            api_base=api_config['api_base'],
            temperature=APIConfig.DEFAULT_TEMPERATURE,
            timeout=APIConfig.REQUEST_TIMEOUT
        )
        raw_content = response.choices[0].message.content

        raw_content = _extract_json_from_response(raw_content)
        json.loads(raw_content)
        return raw_content

    except asyncio.TimeoutError:
        return json.dumps({"error": "Extraction timeout"})
    except json.JSONDecodeError as e:
        return json.dumps({"error": "Model returned invalid JSON", "detail": str(e)})
    except Exception as e:
        return json.dumps({"error": "Extraction failed", "detail": str(e)})

def _extract_json_from_response(content: str) -> str:
    """从响应中提取 JSON 内容"""
    if "```json" in content:
        return content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        return content.split("```")[1].strip()
    return content.strip()
