"""LLM 调用层（OpenAI 兼容端点，B-SRP-21 / B-DRY-04）。

三条调用路径（OCR / Chat / JSON 提取）共用 _make_client 工厂与
_call_llm 请求样板；测试经 patch('services.ai_service._make_client')
一行覆盖全部网络出口（替代旧 LiteLLM 符号 patch）。

模型名兼容：存量配置（config.py.example 与用户 DB）携带旧路由前缀
"openai/<name>"，发往 HTTP 前由 _strip_provider_prefix 统一剥离。
"""
import base64
import io
import asyncio
import json

from openai import APITimeoutError, OpenAI

try:
    from backend.constants import APIConfig, OCRConfig
except ImportError:
    from constants import APIConfig, OCRConfig

_OCR_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."
_CHAT_SYS_PROMPT = (
    "You are a specialized academic assistant. "
    "Answer based ONLY on the provided context."
)
_EXTRACT_SYS_PROMPT = "You are an academic JSON extractor. Return ONLY raw JSON."


class APIResponseError(Exception):
    """API 返回了错误响应"""
    def __init__(self, message: str, raw_response: str = None):
        self.raw_response = raw_response
        super().__init__(message)


def _make_client(api_config):
    """模块级 seam（B-DRY-04）：client 工厂，测试 patch 此函数即可拦截全部网络出口。

    max_retries=0：重试策略由上层（process_page_task / retry.py）统一负责，
    避免 SDK 内建重试与业务重试叠加导致超时放大。
    """
    return OpenAI(
        api_key=api_config["api_key"],
        base_url=api_config["api_base"],
        timeout=APIConfig.REQUEST_TIMEOUT,
        max_retries=0,
    )


def _strip_provider_prefix(model_name: str) -> str:
    """剥离存量 LiteLLM 路由前缀（"openai/<name>" → "<name>"），兼容旧配置与 DB 值。"""
    return model_name.removeprefix("openai/")


async def _call_llm(api_config, model_name, messages, **overrides) -> str:
    """共享请求样板（B-DRY-04）：client 构造 + 同步 SDK 调用转线程 + 取首个 choice 文本。"""
    def _invoke():
        client = _make_client(api_config)
        response = client.chat.completions.create(
            model=_strip_provider_prefix(model_name),
            messages=messages,
            **overrides,
        )
        return response.choices[0].message.content

    return await asyncio.to_thread(_invoke)


async def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


async def call_ocr_api(image, api_config):
    """单页 OCR。失败一律抛 APIResponseError（统一异常协议，B-SRP-21）。"""
    model_name = api_config.get('model_name', '')
    if not model_name:
        print("[API] OCR Error: OCR_MODEL not configured")
        raise APIResponseError("OCR Failed: OCR_MODEL not configured in settings")

    base64_image = await pil_to_base64(image)
    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
        {"type": "text", "text": _OCR_PROMPT}
    ]}]
    try:
        return await _call_llm(
            api_config, model_name, messages,
            temperature=OCRConfig.DEFAULT_TEMPERATURE,
            max_tokens=OCRConfig.DEFAULT_MAX_TOKENS,
        )
    except APITimeoutError:
        raise APIResponseError(f"OCR timeout after {APIConfig.REQUEST_TIMEOUT}s")
    except APIResponseError:
        raise
    except Exception as e:
        print(f"[API] OCR Error: {e}")
        raise APIResponseError(f"OCR Failed: {str(e)}")


async def call_chat_api(query, context, api_config):
    """文档问答。失败一律抛 APIResponseError。"""
    model_name = api_config.get('model_name', '')
    if not model_name:
        raise APIResponseError("Chat Error: LLM_MODEL not configured in settings")

    messages = [
        {"role": "system", "content": _CHAT_SYS_PROMPT},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUERY:\n{query}"}
    ]
    try:
        return await _call_llm(
            api_config, model_name, messages,
            temperature=APIConfig.DEFAULT_TEMPERATURE,
        )
    except APITimeoutError:
        raise APIResponseError(f"Chat timeout after {APIConfig.REQUEST_TIMEOUT}s")
    except APIResponseError:
        raise
    except Exception as e:
        raise APIResponseError(f"Chat Error: {str(e)}")


async def call_json_extraction_api(md_content, api_config, prompt_instructions):
    """JSON 提取。保持 error-JSON 返回协议（调用方 extraction_service 负责转异常）。"""
    sys_prompt = _EXTRACT_SYS_PROMPT
    if "DOI" in prompt_instructions:
        prompt_instructions += "\nCRITICAL: If a DOI URL exists, extract the '10.xxx' part."

    model_name = api_config.get('model_name', '')
    if not model_name:
        return json.dumps({"error": "Extraction failed: LLM_MODEL not configured in settings"})

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"{prompt_instructions}\n\nCONTENT:\n{md_content}"}
    ]
    try:
        raw_content = await _call_llm(
            api_config, model_name, messages,
            temperature=APIConfig.DEFAULT_TEMPERATURE,
        )
        raw_content = _extract_json_from_response(raw_content)
        json.loads(raw_content)
        return raw_content

    except (APITimeoutError, asyncio.TimeoutError):
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
