import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # =========================
    # 路径配置
    # =========================
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    IMAGE_DIR: Path = DATA_DIR / "images"
    LOG_DIR: Path = BASE_DIR / "logs"
    TEMP_DIR: Path = BASE_DIR / "temp"

    # =========================
    # 应用基础配置
    # =========================
    APP_TITLE: str = os.getenv("APP_TITLE", "我的专属 Agent")
    PAGE_ICON: str = os.getenv("PAGE_ICON", "🤖")
    PAGE_LAYOUT: str = os.getenv("PAGE_LAYOUT", "wide")
    DEBUG: bool = _to_bool(os.getenv("DEBUG"), False)

    # =========================
    # 大模型配置
    # =========================
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "").strip()
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro").strip()
    DEEPSEEK_THINKING_MODE: str = os.getenv("DEEPSEEK_THINKING_MODE", "disabled").strip().lower()
    DEEPSEEK_REASONING_EFFORT: str = os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip().lower()
    LLM_TIMEOUT_SECONDS: int = _to_int(os.getenv("LLM_TIMEOUT_SECONDS"), 180)
    ZHIPUAI_BASE_URL: str = os.getenv("ZHIPUAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions").strip()
    ZHIPUAI_API_KEY: str = os.getenv("ZHIPUAI_API_KEY", "").strip()
    ZHIPUAI_VISION_MODEL: str = os.getenv("ZHIPUAI_VISION_MODEL", "glm-4.6v-flash").strip()
    ZHIPUAI_THINKING_MODE: str = os.getenv("ZHIPUAI_THINKING_MODE", "disabled").strip().lower()
    ZHIPUAI_TIMEOUT_SECONDS: int = _to_int(os.getenv("ZHIPUAI_TIMEOUT_SECONDS"), 60)

    LLM_TEMPERATURE: float = _to_float(os.getenv("LLM_TEMPERATURE"), 0.3)
    LLM_MAX_TOKENS: int = _to_int(os.getenv("LLM_MAX_TOKENS"), 2048)
    ENABLE_STREAMING: bool = _to_bool(os.getenv("ENABLE_STREAMING"), False)

    # =========================
    # Embedding 配置
    # =========================
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME",
        "BAAI/bge-small-zh-v1.5"
    ).strip()
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu").strip().lower()
    EMBEDDING_NORMALIZE: bool = _to_bool(os.getenv("EMBEDDING_NORMALIZE"), True)
    VECTOR_SIZE: int = _to_int(os.getenv("VECTOR_SIZE"), 512)
    ENABLE_EMBEDDING_CACHE: bool = _to_bool(os.getenv("ENABLE_EMBEDDING_CACHE"), True)

    # =========================
    # Reranker 配置
    # =========================
    ENABLE_RERANKER: bool = _to_bool(os.getenv("ENABLE_RERANKER"), False)
    RERANKER_MODEL_NAME: str = os.getenv(
        "RERANKER_MODEL_NAME",
        "BAAI/bge-reranker-base"
    ).strip()
    RERANK_TOP_N: int = _to_int(os.getenv("RERANK_TOP_N"), 5)

    # =========================
    # Qdrant / 向量库配置
    # =========================
    QDRANT_PATH: str = os.getenv("QDRANT_PATH", str(DATA_DIR / "local_qdrant"))
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "my_agent_db")
    MEMORY_COLLECTION_NAME: str = os.getenv("MEMORY_COLLECTION_NAME", "my_memory_db")
    ENABLE_MULTI_COLLECTION: bool = _to_bool(os.getenv("ENABLE_MULTI_COLLECTION"), True)

    # =========================
    # 文档切块配置
    # =========================
    CHUNK_SIZE: int = _to_int(os.getenv("CHUNK_SIZE"), 500)
    CHUNK_OVERLAP: int = _to_int(os.getenv("CHUNK_OVERLAP"), 50)

    # =========================
    # 检索配置
    # =========================
    RETRIEVER_TOP_K: int = _to_int(os.getenv("RETRIEVER_TOP_K"), 4)
    ENABLE_MMR: bool = _to_bool(os.getenv("ENABLE_MMR"), True)
    MMR_FETCH_K: int = _to_int(os.getenv("MMR_FETCH_K"), 12)
    MMR_LAMBDA_MULT: float = _to_float(os.getenv("MMR_LAMBDA_MULT"), 0.5)
    ENABLE_HYBRID_SEARCH: bool = _to_bool(os.getenv("ENABLE_HYBRID_SEARCH"), False)
    ENABLE_QUERY_REWRITE: bool = _to_bool(os.getenv("ENABLE_QUERY_REWRITE"), False)

    # =========================
    # 文档管理配置
    # =========================
    ALLOWED_FILE_TYPES: tuple = ("pdf", "txt", "md", "docx")
    MAX_FILE_SIZE_MB: int = _to_int(os.getenv("MAX_FILE_SIZE_MB"), 200)
    ENABLE_DOC_DEDUP: bool = _to_bool(os.getenv("ENABLE_DOC_DEDUP"), True)
    ENABLE_DOC_UPDATE: bool = _to_bool(os.getenv("ENABLE_DOC_UPDATE"), True)
    ENABLE_DOC_DELETE: bool = _to_bool(os.getenv("ENABLE_DOC_DELETE"), True)
    ENABLE_DOC_LIST: bool = _to_bool(os.getenv("ENABLE_DOC_LIST"), True)

    # =========================
    # OCR / 图文配置
    # =========================
    ENABLE_OCR: bool = _to_bool(os.getenv("ENABLE_OCR"), True)
    OCR_ENGINE: str = os.getenv("OCR_ENGINE", "rapidocr").strip().lower()
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "ch")
    ENABLE_IMAGE_EXTRACTION: bool = _to_bool(os.getenv("ENABLE_IMAGE_EXTRACTION"), True)
    ENABLE_IMAGE_QA_HINT: bool = _to_bool(os.getenv("ENABLE_IMAGE_QA_HINT"), True)

    # =========================
    # 工具配置
    # =========================
    ENABLE_WEB_SEARCH: bool = _to_bool(os.getenv("ENABLE_WEB_SEARCH"), True)
    ENABLE_WEATHER_TOOL: bool = _to_bool(os.getenv("ENABLE_WEATHER_TOOL"), False)
    ENABLE_CALCULATOR_TOOL: bool = _to_bool(os.getenv("ENABLE_CALCULATOR_TOOL"), False)
    ENABLE_FILE_TOOL: bool = _to_bool(os.getenv("ENABLE_FILE_TOOL"), True)
    ENABLE_SUMMARY_TOOL: bool = _to_bool(os.getenv("ENABLE_SUMMARY_TOOL"), True)

    # =========================
    # Agent 配置
    # =========================
    ENABLE_ROUTER: bool = _to_bool(os.getenv("ENABLE_ROUTER"), True)
    ENABLE_FALLBACK_ANSWER: bool = _to_bool(os.getenv("ENABLE_FALLBACK_ANSWER"), True)
    ENABLE_TOOL_TRACE: bool = _to_bool(os.getenv("ENABLE_TOOL_TRACE"), True)
    AGENT_VERBOSE: bool = _to_bool(os.getenv("AGENT_VERBOSE"), True)

    # =========================
    # Memory 配置
    # =========================
    ENABLE_LONG_TERM_MEMORY: bool = _to_bool(os.getenv("ENABLE_LONG_TERM_MEMORY"), False)
    ENABLE_SUMMARY_MEMORY: bool = _to_bool(os.getenv("ENABLE_SUMMARY_MEMORY"), False)
    MEMORY_TOP_K: int = _to_int(os.getenv("MEMORY_TOP_K"), 3)
    MAX_CHAT_TURNS: int = _to_int(os.getenv("MAX_CHAT_TURNS"), 20)

    # =========================
    # UI 配置
    # =========================
    ENABLE_SOURCE_CITATION: bool = _to_bool(os.getenv("ENABLE_SOURCE_CITATION"), True)
    ENABLE_DOC_PANEL: bool = _to_bool(os.getenv("ENABLE_DOC_PANEL"), True)
    ENABLE_SETTINGS_PANEL: bool = _to_bool(os.getenv("ENABLE_SETTINGS_PANEL"), True)
    ENABLE_HISTORY_PANEL: bool = _to_bool(os.getenv("ENABLE_HISTORY_PANEL"), True)

    # =========================
    # 日志配置
    # =========================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    LOG_TO_FILE: bool = _to_bool(os.getenv("LOG_TO_FILE"), True)

    # =========================
    # 工具方法
    # =========================
    def ensure_dirs(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        self.ensure_dirs()

        provider = self.LLM_PROVIDER.lower()
        if provider == "deepseek":
            if not self.DEEPSEEK_BASE_URL:
                raise ValueError("缺少 DEEPSEEK_BASE_URL，请检查 .env。")
            if not self.DEEPSEEK_API_KEY:
                raise ValueError("缺少 DEEPSEEK_API_KEY，请检查 .env。")
            if self.DEEPSEEK_THINKING_MODE not in {"enabled", "disabled"}:
                raise ValueError("DEEPSEEK_THINKING_MODE 只能是 enabled 或 disabled。")
            if self.DEEPSEEK_REASONING_EFFORT not in {"high", "max"}:
                raise ValueError("DEEPSEEK_REASONING_EFFORT 只能是 high 或 max。")
            if self.ZHIPUAI_THINKING_MODE not in {"enabled", "disabled"}:
                raise ValueError("ZHIPUAI_THINKING_MODE 只能是 enabled 或 disabled。")
        else:
            raise ValueError(f"暂不支持的模型提供商: {provider}。目前仅支持 deepseek。")

        if self.EMBEDDING_DEVICE not in {"cpu", "cuda"}:
            raise ValueError("EMBEDDING_DEVICE 只能是 cpu 或 cuda。")

        if self.CHUNK_SIZE <= 0:
            raise ValueError("CHUNK_SIZE 必须大于 0。")

        if self.CHUNK_OVERLAP < 0:
            raise ValueError("CHUNK_OVERLAP 不能小于 0。")

        if self.RETRIEVER_TOP_K <= 0:
            raise ValueError("RETRIEVER_TOP_K 必须大于 0。")

        if self.VECTOR_SIZE <= 0:
            raise ValueError("VECTOR_SIZE 必须大于 0。")

        if self.MAX_FILE_SIZE_MB <= 0:
            raise ValueError("MAX_FILE_SIZE_MB 必须大于 0。")

        if self.RERANK_TOP_N <= 0:
            raise ValueError("RERANK_TOP_N 必须大于 0。")

        if self.MEMORY_TOP_K <= 0:
            raise ValueError("MEMORY_TOP_K 必须大于 0。")

        if self.MAX_CHAT_TURNS <= 0:
            raise ValueError("MAX_CHAT_TURNS 必须大于 0。")


settings = Settings()
