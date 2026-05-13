import base64

import requests

from config import settings
from core import get_logger

logger = get_logger(__name__)


def describe_image_for_chat(image_bytes: bytes) -> str:
    """
    使用智谱视觉模型对图片做补充理解。
    若未配置 ZHIPUAI_API_KEY，则降级为纯文本提示。
    """
    if not image_bytes:
        return ""

    if not settings.ENABLE_IMAGE_QA_HINT:
        return ""

    if not settings.ZHIPUAI_API_KEY:
        logger.info("未配置 ZHIPUAI_API_KEY，跳过图片视觉理解。")
        return "当前后端未配置智谱视觉 API，图片将不会做视觉理解。若需分析图片，请补充文字描述或先做 OCR。"

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": settings.ZHIPUAI_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请用中文概括这张图片的关键信息。"
                            "如果是界面截图，请说明页面结构、按钮、输入区和关键文案。"
                            "如果是文档/图片含文字，请提炼主题与重点，不要输出冗长废话。"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            }
        ],
        "thinking": {"type": settings.ZHIPUAI_THINKING_MODE},
    }

    try:
        response = requests.post(
            settings.ZHIPUAI_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.ZHIPUAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.ZHIPUAI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        if content:
            logger.info("智谱视觉分析完成 | model=%s", settings.ZHIPUAI_VISION_MODEL)
            return content

        logger.warning("智谱视觉接口返回为空内容 | response=%s", data)
        return "图片视觉理解结果为空，请补充文字说明。"
    except Exception as exc:
        logger.exception("智谱视觉分析失败")
        return f"图片视觉理解失败：{exc}"


def describe_image_with_ollama(image_bytes: bytes) -> str:
    """
    兼容旧调用名。
    """
    return describe_image_for_chat(image_bytes)
