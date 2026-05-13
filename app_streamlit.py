import os
import tempfile
from pathlib import Path

import streamlit as st
from langchain_core.prompts import ChatPromptTemplate

from config import settings
from core import (
    get_logger,
    get_vectorstore,
    run_health_check,
)
from knowledge import (
    ingest_file_to_vectorstore,
    list_documents,
    delete_document_from_vectorstore,
    build_document_fingerprint,
    load_registry,
)
from agent import build_agent_executor, run_agent
from memory import (
    init_chat_session,
    get_session_messages,
    get_session_summary,
    set_session_summary,
    append_user_message,
    append_assistant_message,
    clear_chat_session,
    get_chat_history_for_agent,
    summarize_messages_if_needed,
    remember_text,
    load_user_profile,
)

logger = get_logger(__name__)


# =========================
# 后端初始化
# =========================
@st.cache_resource
def init_vectorstore():
    return get_vectorstore()


def init_agent_executor():
    from knowledge import get_retriever
    vectorstore = init_vectorstore()
    retriever = get_retriever(vectorstore)
    return build_agent_executor(retriever)


# =========================
# 工具函数
# =========================
def save_uploaded_file_to_temp(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[-1] or ".tmp"

    settings.ensure_dirs()
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
        dir=settings.TEMP_DIR,
    ) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        return tmp_file.name


def safe_delete_temp_file(temp_path: str) -> None:
    try:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    except Exception:
        logger.exception("删除临时文件失败 | path=%s", temp_path)


def get_registry_records():
    try:
        return list_documents()
    except Exception:
        logger.exception("读取文档列表失败")
        return []


def render_health_status():
    st.subheader("⚙️ 系统状态")

    try:
        health = run_health_check()
    except Exception as e:
        st.error(f"健康检查失败：{e}")
        return

    for name, item in health.items():
        ok = item.get("ok", False)
        detail = item.get("detail", "")
        emoji = "✅" if ok else "❌"
        st.markdown(f"**{emoji} {name}**")
        if detail:
            st.caption(detail)


def render_user_profile_panel():
    st.subheader("👤 我的画像")

    profile = load_user_profile()
    name = profile.get("name", "") or "未设置"
    style = profile.get("preferred_style", "") or "未设置"
    interests = profile.get("interests", []) or []
    projects = profile.get("current_projects", []) or []
    goals = profile.get("current_goals", []) or []
    workflow = profile.get("workflow_preferences", []) or []
    persona = profile.get("persona_notes", "") or "未设置"

    st.markdown(f"**姓名/称呼**：{name}")
    st.markdown(f"**偏好风格**：{style}")
    st.markdown(f"**身份背景**：{persona}")
    st.markdown(f"**当前目标**：{', '.join(goals) if goals else '未设置'}")
    st.markdown(f"**核心项目**：{', '.join(projects) if projects else '未设置'}")
    st.markdown(f"**工作流偏好**：{', '.join(workflow) if workflow else '未设置'}")
    st.markdown(f"**兴趣方向**：{', '.join(interests) if interests else '未设置'}")


def render_upload_panel(vectorstore):
    st.subheader("📥 上传文档")

    uploaded_file = st.file_uploader(
        "上传文件到知识库",
        type=list(settings.ALLOWED_FILE_TYPES),
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        return

    st.caption(f"文件名：{uploaded_file.name}")
    st.caption(f"大小：{round(len(uploaded_file.getvalue()) / 1024 / 1024, 2)} MB")

    if st.button("注入知识库", type="primary", use_container_width=True):
        temp_path = None
        try:
            with st.spinner("正在解析、切块并写入知识库..."):
                temp_path = save_uploaded_file_to_temp(uploaded_file)
                result = ingest_file_to_vectorstore(temp_path, vectorstore)

            status = result.get("status")
            if status == "success":
                st.success(
                    f"✅ 入库成功\n\n"
                    f"- 文件：{uploaded_file.name}\n"
                    f"- doc_id：{result.get('doc_id')}\n"
                    f"- 文档数：{result.get('document_count')}\n"
                    f"- 文本块数：{result.get('chunk_count')}"
                )
            elif status == "skipped_duplicate":
                st.info(
                    f"⚠️ 检测到重复文档，已跳过\n\n"
                    f"- 文件：{uploaded_file.name}\n"
                    f"- doc_id：{result.get('doc_id')}"
                )
            elif status == "empty":
                st.warning(
                    f"⚠️ 文档没有可入库的有效内容\n\n"
                    f"- 文件：{uploaded_file.name}"
                )
            else:
                st.warning(f"未知入库状态：{result}")

            logger.info("文档入库完成 | result=%s", result)

        except Exception as e:
            logger.exception("文档入库失败")
            st.error(f"文档入库失败：{e}")

        finally:
            safe_delete_temp_file(temp_path)


def render_document_panel(vectorstore):
    st.subheader("📚 已入库文档")

    records = get_registry_records()
    if not records:
        st.info("当前知识库中还没有文档。")
        return

    for item in records:
        doc_id = item.get("doc_id", "")
        source_file = item.get("source_file", "未知文件")
        doc_type = item.get("doc_type", "未知")
        document_count = item.get("document_count", "未知")
        chunk_count = item.get("chunk_count", "未知")
        ingest_time = item.get("ingest_time", "未知")

        with st.expander(f"{source_file}"):
            st.markdown(f"**doc_id**：`{doc_id}`")
            st.markdown(f"**类型**：{doc_type}")
            st.markdown(f"**页数/文档数**：{document_count}")
            st.markdown(f"**文本块数**：{chunk_count}")
            st.markdown(f"**入库时间**：{ingest_time}")

            if settings.ENABLE_DOC_DELETE:
                if st.button(f"删除文档：{source_file}", key=f"delete_{doc_id}"):
                    try:
                        result = delete_document_from_vectorstore(vectorstore, doc_id)
                        status = result.get("status")

                        if status == "deleted":
                            st.success(f"已删除文档：{source_file}")
                            st.rerun()
                        elif status == "not_found":
                            st.warning("未找到该文档。")
                        else:
                            st.warning(f"删除结果：{result}")

                    except Exception as e:
                        logger.exception("删除文档失败")
                        st.error(f"删除文档失败：{e}")


def render_memory_dashboard():
    st.sidebar.markdown("---")
    st.sidebar.subheader("📓 思考笔记本 (Thinking Notebook)")
    
    try:
        from core import get_memory_vectorstore
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        vectorstore = get_memory_vectorstore()
        # 检索最近的“深度见解”或“研究报告”
        results = vectorstore.client.scroll(
            collection_name=vectorstore.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="metadata.memory_type", match=MatchValue(value="internal_thought"))
                ]
            ),
            limit=20, # 获取最近的 20 条
        )
        
        points, _ = results
        if not points:
            st.sidebar.info("尚无深度见解记录。")
            return

        for p in points:
            payload = p.payload
            full_content = payload.get("page_content", "")
            # 提取标题
            title = full_content.split("\n")[0].replace("#", "").strip()
            if not title:
                title = "未分类见解"
            
            if st.sidebar.button(f"📖 {title[:20]}...", key=f"note_{p.id}"):
                st.session_state["selected_note"] = full_content
                
    except Exception:
        st.sidebar.error("无法加载思考笔记本。")

def render_wisdom_action():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 智慧大脑 (Wisdom Core)")
    if st.sidebar.button("⚙️ 开始全量记忆提炼"):
        from memory.wisdom import consolidate_wisdom
        with st.spinner("正在全局分析所有对话事实与见解..."):
            result = consolidate_wisdom()
            st.sidebar.success(result)

def render_proactive_radar():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛸 主动建议 (Radar)")
    
    # 仅在非空闲时进行简单扫描
    if "radar_suggestion" not in st.session_state:
        try:
            from core import get_llm
            from memory import load_user_profile, load_tasks
            
            profile = load_user_profile()
            tasks = [t for t in load_tasks() if t["status"] != "completed"]
            
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个主动性极强的私人助理。请根据用户的【画像现状】和【未完成任务列表】，给出一个非常简短（1句）且具有前瞻性的行动建议。直接给出文字。"),
                ("human", "画像：{profile}\n任务：{tasks}")
            ])
            
            chain = prompt | llm
            suggestion_response = chain.invoke({
                "profile": str(profile),
                "tasks": str(tasks)[:1000]
            })
            st.session_state["radar_suggestion"] = getattr(suggestion_response, "content", "继续推进当前目标！")
        except Exception:
            st.session_state["radar_suggestion"] = "随时待命，准备为您服务。"

    st.sidebar.info(f"💡 {st.session_state['radar_suggestion']}")
    if st.sidebar.button("刷新雷达"):
        del st.session_state["radar_suggestion"]
        st.rerun()

def render_selected_note():
    if "selected_note" in st.session_state and st.session_state["selected_note"]:
        with st.expander("📌 查看深度见解详情", expanded=True):
            st.markdown(st.session_state["selected_note"])
            if st.button("关闭阅览"):
                st.session_state["selected_note"] = None
                st.rerun()


def render_task_panel():
    st.subheader("✅ 任务清单")
    from memory.tasks import load_tasks, update_task, delete_task
    tasks = load_tasks()
    if not tasks:
        st.info("目前没有任务。让 Agent 帮你创建一个吧！")
        return

    # 只显示未完成的任务在顶部，或者全部折叠显示
    active_tasks = [t for t in tasks if t["status"] != "done"]
    done_tasks = [t for t in tasks if t["status"] == "done"]

    for t in active_tasks:
        task_id = t["id"]
        content = t["content"]
        status = t["status"]
        
        col1, col2 = st.columns([0.7, 0.3])
        status_emoji = "⏳" if status == "in_progress" else "⭕"
        
        with col1:
            st.markdown(f"**{status_emoji} {content}**")
        with col2:
            if st.button("完成", key=f"done_{task_id}"):
                update_task(task_id, {"status": "done"})
                st.rerun()

    if done_tasks:
        with st.expander(f"已完成清单 ({len(done_tasks)})"):
            for t in done_tasks:
                task_id = t["id"]
                content = t["content"]
                col1, col2 = st.columns([0.7, 0.3])
                with col1:
                    st.markdown(f"~~✅ {content}~~")
                with col2:
                    if st.button("撤回", key=f"todo_{task_id}"):
                        update_task(task_id, {"status": "todo"})
                        st.rerun()


def render_sidebar(vectorstore):
    with st.sidebar:
        st.header("🧠 我的 Agent")

        if settings.ENABLE_DOC_PANEL:
            render_upload_panel(vectorstore)
            st.divider()
            render_document_panel(vectorstore)
            st.divider()

        if settings.ENABLE_SETTINGS_PANEL:
            render_health_status()
            st.divider()
            render_user_profile_panel()
            st.divider()
            render_task_panel()
            render_memory_dashboard()
            render_proactive_radar()
            render_wisdom_action()
            st.divider()

        st.subheader("💬 会话管理")
        if st.button("清空当前对话", use_container_width=True):
            clear_chat_session()
            st.success("会话已清空。")
            st.rerun()

        st.divider()

        st.subheader("🔧 当前配置")
        st.markdown(f"**LLM**：`{settings.DEEPSEEK_MODEL}`")
        st.markdown(f"**Embedding**：`{settings.EMBEDDING_MODEL_NAME}`")
        st.markdown(f"**Device**：`{settings.EMBEDDING_DEVICE}`")
        st.markdown(f"**Top K**：`{settings.RETRIEVER_TOP_K}`")
        st.markdown(f"**Chunk Size**：`{settings.CHUNK_SIZE}`")
        st.markdown(f"**Chunk Overlap**：`{settings.CHUNK_OVERLAP}`")
        st.markdown(f"**Weather Tool**：`{settings.ENABLE_WEATHER_TOOL}`")
        st.markdown(f"**Long Memory**：`{settings.ENABLE_LONG_TERM_MEMORY}`")
        st.markdown(f"**Summary Memory**：`{settings.ENABLE_SUMMARY_MEMORY}`")


def render_chat_header():
    st.title(settings.APP_TITLE)
    st.caption("私人知识库 + 工具调用 + 长期记忆")


def render_chat_messages():
    messages = get_session_messages()

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    summary = get_session_summary()
    if summary and settings.ENABLE_SUMMARY_MEMORY:
        with st.expander("📝 当前对话摘要"):
            st.write(summary)


def maybe_update_summary():
    messages = get_session_messages()
    current_summary = get_session_summary()

    try:
        new_summary = summarize_messages_if_needed(messages, current_summary)
        if new_summary != current_summary:
            set_session_summary(new_summary)
    except Exception:
        logger.exception("更新会话摘要失败")


def reflect_on_chat(user_input: str, output: str):
    """
    对话结束后，异步或同步触发反思抽提事实。
    """
    from memory import reflect_on_interaction
    reflect_on_interaction(user_input, output)


def handle_user_input(agent_executor):
    user_input = st.chat_input("请输入你的问题，或让我帮你处理文档、查天气、做总结...")

    if not user_input:
        return

    append_user_message(user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    messages = get_session_messages()
    summary = get_session_summary()
    history = get_chat_history_for_agent(
        messages=messages,
        summary=summary,
        exclude_last_user=True,
    )

    with st.chat_message("assistant"):
        with st.spinner("Agent 正在思考并调用工具..."):
            result = run_agent(
                agent_executor=agent_executor,
                user_input=user_input,
                chat_history=history,
            )
            output = result["output"]
            image_paths = result.get("image_paths", [])
            
            import re
            # 解析思维计划
            plan_match = re.search(r"<thought_plan>(.*?)</thought_plan>", output, re.DOTALL)
            if plan_match:
                plan_content = plan_match.group(1).strip()
                final_output = output.replace(plan_match.group(0), "").strip()
                with st.status("📋 任务拆解与执行计划", expanded=False):
                    st.markdown(plan_content)
                st.markdown(final_output)
            else:
                st.markdown(output)
            
            # 如果有相关图片，展示出来
            if image_paths:
                for img_path in image_paths:
                    st.image(img_path, caption="关联参考图", use_column_width=True)

    append_assistant_message(output)

    # 对话后更新摘要
    maybe_update_summary()

    # 对话后触发反思逻辑
    reflect_on_chat(user_input, output)


def main():
    st.set_page_config(
        page_title=settings.APP_TITLE,
        page_icon=settings.PAGE_ICON,
        layout=settings.PAGE_LAYOUT,
    )

    init_chat_session()
    render_chat_header()

    try:
        vectorstore = init_vectorstore()
        agent_executor = init_agent_executor()
    except Exception as e:
        logger.exception("后端初始化失败")
        st.error(f"系统初始化失败：{e}")
        st.stop()
        return

    render_sidebar(vectorstore)
    render_chat_messages()
    handle_user_input(agent_executor)


if __name__ == "__main__":
    main()