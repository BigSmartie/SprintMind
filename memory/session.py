from core import get_logger

logger = get_logger(__name__)

_sessions = {}


def get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        init_chat_session(session_id)
    return _sessions[session_id]


def init_chat_session(session_id: str = "default") -> None:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "你好，我是 SprintMind，一套面向软件项目管理课程的三智能体协作系统。\n\n"
                        "我会同时调度：\n"
                        "- 需求分析 Agent：澄清目标、范围和交付物\n"
                        "- 迭代规划 Agent：拆解 Sprint 任务并安排三人分工\n"
                        "- 风险质控 Agent：补齐风险、验收和答辩准备\n\n"
                        "你可以直接告诉我项目主题、课程要求，或上传资料让我开始规划。"
                    ),
                }
            ],
            "summary": "",
        }
        logger.info("聊天会话已初始化: %s", session_id)


def get_session_messages(session_id: str = "default") -> list:
    return get_session(session_id)["messages"]


def get_session_summary(session_id: str = "default") -> str:
    return get_session(session_id)["summary"]


def set_session_summary(summary: str, session_id: str = "default") -> None:
    get_session(session_id)["summary"] = (summary or "").strip()
    logger.info("已更新会话摘要: %s", session_id)


def append_user_message(content: str, session_id: str = "default") -> None:
    if not content or not content.strip():
        logger.warning("append_user_message 收到空内容，已忽略")
        return

    session = get_session(session_id)
    session["messages"].append(
        {
            "role": "user",
            "content": content.strip(),
        }
    )
    logger.info("已追加用户消息: %s", session_id)


def append_assistant_message(content: str, session_id: str = "default", extra: dict = None) -> None:
    if not content or not content.strip():
        logger.warning("append_assistant_message 收到空内容，已忽略")
        return

    session = get_session(session_id)
    message = {
        "role": "assistant",
        "content": content.strip(),
    }
    if extra:
        message.update(extra)
    session["messages"].append(message)
    logger.info("已追加助手消息: %s", session_id)


def clear_chat_session(session_id: str = "default") -> None:
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info("已清空聊天会话: %s", session_id)
    init_chat_session(session_id)
