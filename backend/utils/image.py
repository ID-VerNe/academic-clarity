"""图像编码工具（B-DRY-14）：PIL Image → DataURI 单一实现。

ocr_service（图像块嵌入 markdown）与 ai_service（OCR 请求体）共用；
data:<mime>;base64, 前缀拼接集中在此，调用方不再手工编码。
"""
import base64
from io import BytesIO

_MIME_BY_FORMAT = {"JPEG": "image/jpeg", "JPG": "image/jpeg", "PNG": "image/png",
                   "WEBP": "image/webp", "GIF": "image/gif"}


def image_to_data_uri(image, format="PNG", quality=None) -> str:
    """PIL Image → data:<mime>;base64,<payload>。

    quality 仅对 JPEG 等有损格式生效（调用方仅在需要时传入）。
    """
    buffer = BytesIO()
    save_kwargs = {"format": format}
    if quality is not None:
        save_kwargs["quality"] = quality
    image.save(buffer, **save_kwargs)
    payload = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime = _MIME_BY_FORMAT.get(format.upper(), f"image/{format.lower()}")
    return f"data:{mime};base64,{payload}"
