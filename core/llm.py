from functools import lru_cache

from langchain_openai import ChatOpenAI

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def _build_extra_body() -> dict:
    extra_body = {}
    if settings.DEEPSEEK_THINKING_MODE:
        extra_body["thinking"] = {"type": settings.DEEPSEEK_THINKING_MODE}
    return extra_body


@lru_cache(maxsize=4)
def get_llm(model_name: str = None):
    """
    初始化并返回 DeepSeek Chat 模型实例。
    """
    provider = settings.LLM_PROVIDER.lower()
    if provider != "deepseek":
        raise ValueError(f"Unsupported provider: {provider}")

    target_model = model_name or settings.DEEPSEEK_MODEL
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("缺少 DEEPSEEK_API_KEY，请先在 .env 中填写后再启动服务。")

    logger.info(
        "正在初始化 DeepSeek LLM | model=%s | base_url=%s | thinking=%s",
        target_model,
        settings.DEEPSEEK_BASE_URL,
        settings.DEEPSEEK_THINKING_MODE,
    )

    return ChatOpenAI(
        model=target_model,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        streaming=settings.ENABLE_STREAMING,
        extra_body=_build_extra_body(),
    )
