import base64
import io
import asyncio
import json
from typing import Optional, Callable, Any
from PIL import Image
from litellm import completion
from core.api_key_manager import key_manager, KeyState, ServiceKeyPool

try:
    from backend.config import APIConfig, OCRConfig
except ImportError:
    from config import APIConfig, OCRConfig

class APIKeyPoolExhaustedError(Exception):
    """所有 API 密钥都不可用"""
    def __init__(self, service: str, last_error: str = None):
        self.service = service
        self.last_error = last_error
        super().__init__(f"{service} API key pool exhausted. Last error: {last_error}")

class APIResponseError(Exception):
    """API 返回了错误响应"""
    def __init__(self, message: str, raw_response: str = None):
        self.raw_response = raw_response
        super().__init__(message)

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
    api_call_func: Callable,
    error_context: str = "API call"
) -> Any:
    """
    使用密钥池调用 API，带完善的错误处理
    """
    if pool and pool.is_enabled():
        last_error = None

        for attempt in range(APIConfig.MAX_RETRIES):
            key_state = await pool.acquire_key()

            if not key_state:
                await asyncio.sleep(APIConfig.RETRY_INTERVAL * (attempt + 1))
                continue

            try:
                result = await api_call_func(key_state)

                if isinstance(result, str) and result.startswith("Failed:"):
                    last_error = result
                    await pool.report_error(key_state, result)
                    continue

                await pool.report_success(key_state)
                return result

            except Exception as e:
                last_error = str(e)
                await pool.report_error(key_state, last_error)

            finally:
                await pool.release_key(key_state)

        raise APIKeyPoolExhaustedError(error_context, last_error)

    return await api_call_func(None)

async def call_ocr_api(image, api_config):
    prompt = "<image>\n<|grounding|>Convert the document to markdown."
    base64_image = await pil_to_base64(image)

    ocr_pool = key_manager.get_pool("ocr")

    if api_config.get('_use_multi_key', False) and ocr_pool:
        async def do_call(key_state: Optional[KeyState]):
            if not key_state:
                raise APIKeyPoolExhaustedError("OCR", "No available OCR API keys")

            if not key_state.model_name:
                raise APIResponseError("OCR Failed: OCR_MODEL not configured in multi-key settings")

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
                    max_tokens=4000,
                    timeout=APIConfig.REQUEST_TIMEOUT
                )
                tokens_used = _extract_tokens_from_response(response)
                await ocr_pool.report_success(key_state, tokens_used)
                return response.choices[0].message.content
            except asyncio.TimeoutError:
                await ocr_pool.report_error(key_state, "OCR timeout")
                raise APIResponseError(f"OCR timeout after {APIConfig.REQUEST_TIMEOUT}s")
            except Exception as e:
                await ocr_pool.report_error(key_state, str(e))
                raise APIResponseError(f"OCR Failed: {str(e)}")

        result = await _call_with_key_pool(ocr_pool, api_config, do_call, "OCR")
        return result
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
    llm_pool = key_manager.get_pool("llm")

    if api_config.get('_use_multi_key', False) and llm_pool:
        async def do_call(key_state: Optional[KeyState]):
            if not key_state:
                raise APIKeyPoolExhaustedError("LLM", "No available LLM API keys")

            if not key_state.model_name:
                raise APIResponseError("Chat Error: LLM_MODEL not configured in multi-key settings")

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
                    temperature=APIConfig.DEFAULT_TEMPERATURE,
                    timeout=APIConfig.REQUEST_TIMEOUT
                )
                await llm_pool.report_success(key_state)
                return response.choices[0].message.content
            except asyncio.TimeoutError:
                await llm_pool.report_error(key_state, "Chat timeout")
                raise APIResponseError(f"Chat timeout after {APIConfig.REQUEST_TIMEOUT}s")
            except Exception as e:
                await llm_pool.report_error(key_state, str(e))
                raise APIResponseError(f"Chat Error: {str(e)}")

        result = await _call_with_key_pool(llm_pool, api_config, do_call, "Chat")
        return result
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

    llm_pool = key_manager.get_pool("llm")

    if api_config.get('_use_multi_key', False) and llm_pool:
        async def do_call(key_state: Optional[KeyState]):
            if not key_state:
                raise APIKeyPoolExhaustedError("LLM", "No available LLM API keys")

            if not key_state.model_name:
                raise APIResponseError("Extraction failed: LLM_MODEL not configured in multi-key settings")

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
                    temperature=APIConfig.DEFAULT_TEMPERATURE,
                    timeout=APIConfig.REQUEST_TIMEOUT
                )
                raw_content = response.choices[0].message.content
                await llm_pool.report_success(key_state)

                raw_content = _extract_json_from_response(raw_content)
                json.loads(raw_content)
                return raw_content

            except asyncio.TimeoutError:
                await llm_pool.report_error(key_state, "Extraction timeout")
                raise APIResponseError(f"Extraction timeout after {APIConfig.REQUEST_TIMEOUT}s")
            except json.JSONDecodeError as e:
                await llm_pool.report_error(key_state, "Invalid JSON")
                raise APIResponseError(f"Model returned invalid JSON: {str(e)}", raw_content)
            except Exception as e:
                await llm_pool.report_error(key_state, str(e))
                raise APIResponseError(f"Extraction failed: {str(e)}")

        result = await _call_with_key_pool(llm_pool, api_config, do_call, "Extraction")
        return result
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
                temperature=APIConfig.DEFAULT_TEMPERATURE,
                timeout=APIConfig.REQUEST_TIMEOUT
            )
            raw_content = response.choices[0].message.content

            raw_content = _extract_json_from_response(raw_content)
            json.loads(raw_content)
            return raw_content

        except asyncio.TimeoutError:
            raise APIResponseError(f"Extraction timeout after {APIConfig.REQUEST_TIMEOUT}s")
        except json.JSONDecodeError as e:
            raise APIResponseError(f"Model returned invalid JSON: {str(e)}", raw_content)
        except Exception as e:
            raise APIResponseError(f"Extraction failed: {str(e)}")

def _extract_json_from_response(content: str) -> str:
    """从响应中提取 JSON 内容"""
    if "```json" in content:
        return content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        return content.split("```")[1].strip()
    return content.strip()
