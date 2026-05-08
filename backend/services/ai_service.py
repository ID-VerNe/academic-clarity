import base64
import io
import asyncio
import json
from typing import Optional
from PIL import Image
from litellm import completion
from core.api_key_manager import key_manager, KeyState, ServiceKeyPool

async def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def _extract_tokens_from_response(response) -> int:
    try:
        usage = getattr(response, 'usage', None)
        if usage:
            return getattr(usage, 'total_tokens', 0)
    except:
        pass
    return 0

async def _call_with_key_pool(
    pool: Optional[ServiceKeyPool],
    fallback_config: dict,
    api_call_func
):
    if pool:
        max_retries = 10
        for _ in range(max_retries):
            key_state = await pool.acquire_key()
            if key_state:
                try:
                    return await api_call_func(key_state)
                finally:
                    await pool.release_key(key_state)
        return None
    
    return await api_call_func(None)

async def call_ocr_api(image, api_config):
    prompt = "<image>\n<|grounding|>Convert the document to markdown."
    base64_image = await pil_to_base64(image)
    
    ocr_pool = key_manager.get_pool("ocr")
    
    if api_config.get('_use_multi_key', False) and ocr_pool:
        async def do_call(key_state: Optional[KeyState]):
            if not key_state:
                return "OCR Failed: No available OCR API keys"
            if not key_state.model_name:
                return "OCR Failed: OCR_MODEL not configured in multi-key settings"
            try:
                response = await asyncio.to_thread(
                    completion,
                    model=key_state.model_name,
                    messages=[{"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                        {"type": "text", "text": prompt}
                    ]}],
                    api_key=key_state.key,
                    api_base=key_state.api_base,
                    temperature=0,
                    max_tokens=4000
                )
                tokens_used = _extract_tokens_from_response(response)
                await ocr_pool.report_success(key_state, tokens_used)
                return response.choices[0].message.content
            except Exception as e:
                await ocr_pool.report_error(key_state, str(e))
                return f"OCR Failed: {str(e)}"
        
        result = await _call_with_key_pool(ocr_pool, api_config, do_call)
        return result if result else "OCR Failed: No available OCR API keys"
    else:
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
                max_tokens=4000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[API] OCR Error: {e}")
            return f"OCR Failed: {str(e)}"

async def call_chat_api(query, context, api_config):
    llm_pool = key_manager.get_pool("llm")
    
    if api_config.get('_use_multi_key', False) and llm_pool:
        async def do_call(key_state: Optional[KeyState]):
            if not key_state:
                return "Chat Error: No available LLM API keys"
            if not key_state.model_name:
                return "Chat Error: LLM_MODEL not configured in multi-key settings"
            try:
                response = await asyncio.to_thread(
                    completion,
                    model=key_state.model_name,
                    messages=[
                        {"role": "system", "content": "You are a specialized academic assistant. Answer based ONLY on the provided context."},
                        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUERY:\n{query}"}
                    ],
                    api_key=key_state.key,
                    api_base=key_state.api_base,
                    temperature=0.1
                )
                await llm_pool.report_success(key_state)
                return response.choices[0].message.content
            except Exception as e:
                await llm_pool.report_error(key_state, str(e))
                return f"Chat Error: {str(e)}"
        
        result = await _call_with_key_pool(llm_pool, api_config, do_call)
        return result if result else "Chat Error: No available LLM API keys"
    else:
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
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Chat Error: {str(e)}"

async def call_json_extraction_api(md_content, api_config, prompt_instructions):
    sys_prompt = "You are an academic JSON extractor. Return ONLY raw JSON."
    if "DOI" in prompt_instructions:
        prompt_instructions += "\nCRITICAL: If a DOI URL exists, extract the '10.xxx' part."
    
    llm_pool = key_manager.get_pool("llm")
    
    if api_config.get('_use_multi_key', False) and llm_pool:
        async def do_call(key_state: Optional[KeyState]):
            if not key_state:
                return json.dumps({"error": "Extraction failed: No available LLM API keys"})
            if not key_state.model_name:
                return json.dumps({"error": "Extraction failed: LLM_MODEL not configured in multi-key settings"})
            try:
                response = await asyncio.to_thread(
                    completion,
                    model=key_state.model_name,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": f"{prompt_instructions}\n\nCONTENT:\n{md_content}"}
                    ],
                    api_key=key_state.key,
                    api_base=key_state.api_base,
                    temperature=0.1
                )
                raw_content = response.choices[0].message.content
                await llm_pool.report_success(key_state)
                
                if "```json" in raw_content:
                    raw_content = raw_content.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_content:
                    raw_content = raw_content.split("```")[1].strip()
                
                json.loads(raw_content)
                return raw_content
                
            except Exception as e:
                await llm_pool.report_error(key_state, str(e))
                return json.dumps({"error": "Model returned invalid JSON", "detail": str(e)})
        
        result = await _call_with_key_pool(llm_pool, api_config, do_call)
        return result if result else json.dumps({"error": "Extraction failed: No available LLM API keys"})
    else:
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
            return json.dumps({"error": "Model returned invalid JSON", "detail": str(e)})
