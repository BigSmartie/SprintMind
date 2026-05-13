import json
import os
import re
import tempfile
from typing import List

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import run_project_team, run_project_team_stream
from api_models import (
    ChatRequest,
    ChatResponse,
    ClearRequest,
    DocumentItem,
    DocumentUploadResponse,
    HealthResponse,
    ProfileResponse,
    TaskItem,
    TaskUpdateRequest,
)
from config import settings
from core import get_logger, get_vectorstore, run_health_check
from knowledge import (
    delete_document_from_vectorstore,
    get_retriever,
    ingest_file_to_vectorstore,
    list_documents,
)
from memory import (
    append_assistant_message,
    append_user_message,
    clear_chat_session,
    get_chat_history_for_agent,
    get_session_messages,
    get_session_summary,
    load_user_profile,
    reflect_on_interaction,
    set_session_summary,
    summarize_messages_if_needed,
)
from memory.tasks import delete_task, load_tasks, update_task

logger = get_logger(__name__)

_app_state = {}

app = FastAPI(
    title=settings.APP_TITLE,
    description="Backend API for SprintMind",
)


@app.on_event("startup")
async def startup_event():
    try:
        logger.info("初始化后端组件中...")
        vectorstore = get_vectorstore()
        retriever = get_retriever(vectorstore)
        _app_state["vectorstore"] = vectorstore
        _app_state["project_retriever"] = retriever
        logger.info("后端组件初始化成功")
    except Exception as exc:
        logger.exception("后端初始化失败")
        raise exc


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        health = run_health_check()
        return HealthResponse(status="ok", details=health)
    except Exception as exc:
        return HealthResponse(status="error", details={"error": str(exc)})


@app.get("/api/profile", response_model=ProfileResponse)
async def get_profile():
    profile = load_user_profile()
    return ProfileResponse(
        name=profile.get("name", ""),
        preferred_style=profile.get("preferred_style", ""),
        interests=profile.get("interests", []),
        current_projects=profile.get("current_projects", []),
        current_goals=profile.get("current_goals", []),
        workflow_preferences=profile.get("workflow_preferences", []),
        persona_notes=profile.get("persona_notes", ""),
    )


@app.get("/api/tasks", response_model=List[TaskItem])
async def get_tasks():
    tasks = load_tasks()
    return [
        TaskItem(
            id=task["id"],
            content=task["content"],
            status=task["status"],
            priority=task.get("priority", "medium"),
            linked_goal=task.get("linked_goal"),
            owner=task.get("owner"),
        )
        for task in tasks
    ]


@app.post("/api/tasks/{task_id}/status")
async def modify_task_status(task_id: int, request: TaskUpdateRequest):
    update_task(task_id, {"status": request.status})
    return {"message": "Task updated"}


@app.delete("/api/tasks/{task_id}")
async def remove_task(task_id: int):
    delete_task(task_id)
    return {"message": "Task deleted"}


@app.get("/api/chat/history")
async def chat_history(session_id: str = "default"):
    messages = get_session_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@app.post("/api/chat/clear")
async def clear_chat(request: ClearRequest):
    clear_chat_session(request.session_id)
    return {"message": "Chat session cleared", "session_id": request.session_id}


def _update_memory_after_chat(session_id: str, user_input: str, output: str):
    messages = get_session_messages(session_id)
    current_summary = get_session_summary(session_id)
    try:
        new_summary = summarize_messages_if_needed(messages, current_summary)
        if new_summary != current_summary:
            set_session_summary(new_summary, session_id)
    except Exception:
        logger.exception("更新会话摘要失败")

    reflect_on_interaction(user_input, output)


def _enrich_user_input_with_image(user_input: str, image_base64: str = None) -> str:
    text = user_input or ""
    if not image_base64:
        return text

    from knowledge.vision import describe_image_for_chat
    import base64

    b64_data = re.sub(r"^data:image/.+;base64,", "", image_base64)
    try:
        image_bytes = base64.b64decode(b64_data)
        description = describe_image_for_chat(image_bytes)
        if description:
            text += (
                "\n\n[用户提供了一张图片，视觉模型分析结果如下：\n"
                f"{description}\n请结合图中内容继续回答用户问题。]"
            )
    except Exception:
        logger.exception("解析图片 Base64 参数失败")

    return text


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id
    user_input = _enrich_user_input_with_image(request.message, request.image_base64)

    if not user_input.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    append_user_message(user_input, session_id)

    messages = get_session_messages(session_id)
    summary = get_session_summary(session_id)
    history = get_chat_history_for_agent(
        messages=messages,
        summary=summary,
        exclude_last_user=True,
    )

    project_retriever = _app_state.get("project_retriever")
    if not project_retriever:
        raise HTTPException(status_code=500, detail="Project retriever not initialized")

    try:
        result = run_project_team(project_retriever, user_input, history)
        raw_output = result["output"]
        image_paths = result.get("image_paths", [])
        agent_reports = result.get("agent_reports", [])
        project_snapshot = result.get("project_snapshot")

        answer_text = re.sub(r"<thought_plan>.*?</thought_plan>", "", raw_output, flags=re.DOTALL).strip()
        if not answer_text:
            answer_text = raw_output.strip()

        append_assistant_message(
            answer_text,
            session_id,
            extra={
                "agent_reports": agent_reports,
                "project_snapshot": project_snapshot,
            },
        )

        background_tasks.add_task(_update_memory_after_chat, session_id, user_input, answer_text)

        return ChatResponse(
            session_id=session_id,
            answer=answer_text,
            thought_plan=None,
            image_paths=image_paths,
            agent_reports=agent_reports,
            project_snapshot=project_snapshot,
        )

    except Exception as exc:
        logger.exception("执行多智能体流程失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id
    user_input = _enrich_user_input_with_image(request.message, request.image_base64)

    if not user_input.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    append_user_message(user_input, session_id)

    messages = get_session_messages(session_id)
    summary = get_session_summary(session_id)
    history = get_chat_history_for_agent(
        messages=messages,
        summary=summary,
        exclude_last_user=True,
    )

    project_retriever = _app_state.get("project_retriever")
    if not project_retriever:
        raise HTTPException(status_code=500, detail="Project retriever not initialized")

    def event_stream():
        try:
            for event in run_project_team_stream(project_retriever, user_input, history):
                event_name = event.get("event", "message")
                payload = event.get("data", {})

                if event_name == "final":
                    raw_output = payload.get("output", "")
                    answer_text = re.sub(r"<thought_plan>.*?</thought_plan>", "", raw_output, flags=re.DOTALL).strip()
                    if not answer_text:
                        answer_text = raw_output.strip()

                    append_assistant_message(
                        answer_text,
                        session_id,
                        extra={
                            "agent_reports": payload.get("agent_reports", []),
                            "project_snapshot": payload.get("project_snapshot"),
                        },
                    )
                    background_tasks.add_task(_update_memory_after_chat, session_id, user_input, answer_text)

                    yield _format_sse(
                        "final",
                        {
                            "session_id": session_id,
                            "answer": answer_text,
                            "thought_plan": None,
                            "image_paths": payload.get("image_paths", []),
                            "agent_reports": payload.get("agent_reports", []),
                            "project_snapshot": payload.get("project_snapshot"),
                        },
                    )
                    continue

                yield _format_sse(event_name, payload)
        except Exception as exc:
            logger.exception("执行流式多智能体流程失败")
            yield _format_sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/knowledge", response_model=List[DocumentItem])
async def get_documents():
    try:
        records = list_documents()
        return [DocumentItem(**item) for item in records]
    except Exception as exc:
        logger.exception("读取文档列表失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/knowledge/{doc_id}")
async def delete_document(doc_id: str):
    vectorstore = _app_state.get("vectorstore")
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vectorstore not initialized")

    try:
        result = delete_document_from_vectorstore(vectorstore, doc_id)
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Document not found")
        return {"message": "Document deleted", "result": result}
    except Exception as exc:
        logger.exception("删除文档失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/knowledge/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    vectorstore = _app_state.get("vectorstore")
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vectorstore not initialized")

    settings.ensure_dirs()
    suffix = os.path.splitext(file.filename)[-1] or ".tmp"
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            dir=settings.TEMP_DIR,
        ) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            temp_path = tmp_file.name

        result = ingest_file_to_vectorstore(temp_path, vectorstore, original_filename=file.filename)
        status = result.get("status", "unknown")

        if status == "success":
            return DocumentUploadResponse(
                status=status,
                doc_id=result.get("doc_id"),
                document_count=result.get("document_count"),
                chunk_count=result.get("chunk_count"),
                message=f"Successfully ingested {file.filename}",
            )
        if status == "skipped_duplicate":
            return DocumentUploadResponse(
                status=status,
                doc_id=result.get("doc_id"),
                message=f"Skipped duplicate document: {file.filename}",
            )
        return DocumentUploadResponse(
            status=status,
            message=f"File processing returned state: {status}",
        )

    except Exception as exc:
        logger.exception("文档上传和处理失败")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


@app.post("/api/wisdom/consolidate")
async def consolidate_wisdom():
    from memory.wisdom import consolidate_wisdom as consolidate_func

    try:
        result = consolidate_func()
        return {"message": "Wisdom consolidation complete", "details": result}
    except Exception as exc:
        logger.exception("提炼智慧失败")
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
