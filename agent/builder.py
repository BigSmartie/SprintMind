from langchain_classic.agents import create_react_agent, AgentExecutor

from config import settings
from core import get_llm, get_logger, get_vectorstore
from tools import (
    build_local_search_tool,
    build_web_search_tool,
    build_list_documents_tool,
    build_delete_document_tool,
    build_document_summary_tool,
    build_weather_tool,
    build_profile_tools,
    build_task_tools,
    build_thought_tools,
    build_research_tools,
)
from agent.prompts import get_agent_prompt

logger = get_logger(__name__)


def build_agent_executor(retriever) -> AgentExecutor:
    logger.info("开始构建 AgentExecutor")

    llm = get_llm()
    vectorstore = get_vectorstore()

    tools = [
        build_local_search_tool(retriever),
    ]

    if settings.ENABLE_FILE_TOOL:
        tools.append(build_list_documents_tool())
        tools.append(build_delete_document_tool(vectorstore))

    if settings.ENABLE_SUMMARY_TOOL:
        tools.append(build_document_summary_tool(retriever, llm))

    if settings.ENABLE_WEB_SEARCH:
        tools.append(build_web_search_tool())

    tools.extend(build_profile_tools())
    tools.extend(build_task_tools())
    tools.extend(build_thought_tools())
    tools.extend(build_research_tools())

    if settings.ENABLE_WEATHER_TOOL:
        tools.append(build_weather_tool())

    prompt = get_agent_prompt()

    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt,
    )

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.AGENT_VERBOSE,
        handle_parsing_errors=True,
        return_intermediate_steps=True, # 允许捕获中间步骤中的图片元数据
    )

    logger.info("AgentExecutor 构建完成 | tool_count=%s", len(tools))
    return agent_executor