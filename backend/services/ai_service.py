import base64
import io
import asyncio
from PIL import Image
from litellm import completion

async def pil_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

async def call_ocr_api(image_pil, api_config):
    """
    Calls the SiliconFlow OCR API for a single image.
    """
    if image_pil.mode == 'RGBA':
        image_pil = image_pil.convert('RGB')
    base64_image = await pil_to_base64(image_pil)

    response = await asyncio.to_thread(
        completion,
        model=api_config['model_name'],
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            {"type": "text", "text": "<image>\n<|grounding|>Convert this document page into high-fidelity markdown. CRITICAL: Do NOT skip footnotes, page headers, or DOIs. Include all formulas and table data accurately."}
        ]}],
        api_key=api_config['api_key'],
        api_base=api_config['api_base'],
        temperature=0,
        max_tokens=4096
    )
    return response.choices[0].message.content

async def call_chat_api(query, context, api_config):
    """
    Calls the AI Chat API with document context.
    """
    prompt = f"Context from the document:\n\n{context}\n\nUser Question: {query}\n\nPlease answer the user's question based on the provided document context. If the answer is not in the context, please say so."
    
    response = await asyncio.to_thread(
        completion,
        model=api_config['model_name'],
        messages=[
            {"role": "system", "content": "You are a helpful academic research assistant. Use the provided document context to answer questions accurately and professionally."},
            {"role": "user", "content": prompt}
        ],
        api_key=api_config['api_key'],
        api_base=api_config['api_base']
    )
    return response.choices[0].message.content

async def call_json_extraction_api(content, api_config, custom_prompt):
    """
    Extracts structured JSON from markdown content using a custom prompt.
    Includes timeout and basic JSON validation.
    """
    import json
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(
                completion,
                model=api_config['model_name'],
                messages=[
                    {"role": "system", "content": "You are an expert data extractor. Output ONLY valid JSON."},
                    {"role": "user", "content": f"{custom_prompt}\n\nContent:\n{content}"}
                ],
                api_key=api_config['api_key'],
                api_base=api_config['api_base'],
                response_format={"type": "json_object"}
            ),
            timeout=60.0
        )
        raw_content = response.choices[0].message.content
        # Basic validation
        try:
            json.loads(raw_content)
            return raw_content
        except json.JSONDecodeError:
            return json.dumps({"error": "Model returned invalid JSON", "raw": raw_content})
            
    except asyncio.TimeoutError:
        return json.dumps({"error": "AI Extraction timed out after 60s"})
    except Exception as e:
        return json.dumps({"error": f"AI Extraction failed: {str(e)}"})
