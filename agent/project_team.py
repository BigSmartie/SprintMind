import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from core import get_llm, get_logger
from knowledge import format_retrieved_docs, list_documents, retrieve_documents
from memory import (
    add_task,
    format_tasks_for_prompt,
    load_tasks,
    load_user_profile,
    update_task,
    format_user_profile,
)

logger = get_logger(__name__)

TEAM_ROLES = [
    {
        "agent_id": "analyst",
        "agent_name": "需求分析 Agent",
        "focus": "澄清项目目标、范围边界、用户故事与交付物",
    },
    {
        "agent_id": "planner",
        "agent_name": "迭代规划 Agent",
        "focus": "拆解 Sprint 任务、安排三人分工并同步任务清单",
    },
    {
        "agent_id": "guardian",
        "agent_name": "风险质控 Agent",
        "focus": "识别进度与质量风险，补齐验收与答辩准备",
    },
]

META_QUERY_KEYWORDS = [
    "agent",
    "智能体",
    "作用",
    "分工",
    "角色",
    "平台",
    "系统",
    "能做什么",
    "可以做什么",
    "有什么功能",
    "功能",
    "用途",
]

AGENT_INTRO_KEYWORDS = [
    "三个agent",
    "三个 agent",
    "三位agent",
    "三位 agent",
    "智能体作用",
    "agent 的作用",
    "agent作用",
    "分工",
    "角色",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    normalized = (text or "").lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _is_meta_query(text: str) -> bool:
    return _contains_any(text, META_QUERY_KEYWORDS)


def _is_agent_intro_query(text: str) -> bool:
    normalized = (text or "").lower()
    return (
        _contains_any(text, AGENT_INTRO_KEYWORDS)
        or ("agent" in normalized and _contains_any(text, ["作用", "分工", "角色", "负责什么"]))
        or ("智能体" in text and _contains_any(text, ["作用", "分工", "角色", "负责什么"]))
    )


def _safe_knowledge_count() -> int:
    try:
        return len(list_documents())
    except Exception:
        logger.exception("读取知识库目录失败")
        return 0


def _safe_active_task_count() -> int:
    try:
        return len([task for task in load_tasks() if task.get("status") != "done"])
    except Exception:
        logger.exception("读取任务清单失败")
        return 0


def _serialize_chat_history(chat_history: list, max_items: int = 6) -> str:
    if not chat_history:
        return "暂无近期对话。"

    lines = []
    for message in chat_history[-max_items:]:
        role = getattr(message, "type", "assistant")
        content = getattr(message, "content", "")
        if isinstance(content, list):
            content = " ".join(str(item) for item in content)
        content = str(content).strip()
        if not content:
            continue
        if role == "human":
            label = "用户"
        elif role == "system":
            label = "系统"
        else:
            label = "助手"
        lines.append(f"{label}: {content[:300]}")

    return "\n".join(lines) if lines else "暂无近期对话。"


def _build_knowledge_context(retriever, query: str) -> str:
    if not retriever or not (query or "").strip():
        return "知识库上下文暂不可用。"

    try:
        docs = retrieve_documents(retriever, query)
        return format_retrieved_docs(docs, max_chars_per_doc=600)
    except Exception:
        logger.exception("构建知识库上下文失败")
        return "知识库中暂无与本轮问题直接相关的片段。"


def _build_runtime_context(retriever, query: str, chat_history: list) -> Dict[str, str]:
    tasks = load_tasks()
    return {
        "user_profile": format_user_profile(load_user_profile()),
        "current_tasks": format_tasks_for_prompt(tasks, only_active=False),
        "recent_dialogue": _serialize_chat_history(chat_history),
        "knowledge_context": _build_knowledge_context(retriever, query),
        "knowledge_count": _safe_knowledge_count(),
        "active_task_count": len([task for task in tasks if task.get("status") != "done"]),
    }


def _invoke_role_agent(
    system_prompt: str,
    human_prompt: str,
    values: Dict[str, str],
    llm=None,
) -> str:
    llm = llm or get_llm()
    chain = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", human_prompt),
        ]
    ) | llm
    response = chain.invoke(values)
    content = getattr(response, "content", str(response))
    return str(content).strip()


def _first_meaningful_line(text: str) -> str:
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[#>*\-\d.\s]+", "", line).strip()
        if line:
            return line[:120]
    return "暂无摘要。"


def _extract_section_value(text: str, heading: str) -> str:
    pattern = rf"{re.escape(heading)}\s*\n(.+?)(?:\n### |\Z)"
    match = re.search(pattern, text or "", flags=re.S)
    if not match:
        return ""
    section = match.group(1).strip()
    first_line = section.splitlines()[0].strip() if section else ""
    return re.sub(r"^[\-\d.\s]+", "", first_line)


def _extract_json_block(text: str) -> Dict:
    if not text:
        return {}

    fence_match = re.search(r"```json\s*(\{.*?})\s*```", text, flags=re.S)
    candidates = []
    if fence_match:
        candidates.append(fence_match.group(1))

    brace_match = re.search(r"(\{[\s\S]*\"tasks\"[\s\S]*})", text, flags=re.S)
    if brace_match:
        candidates.append(brace_match.group(1))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            continue
    return {}


def _normalize_task_status(value: Optional[str]) -> str:
    status = (value or "todo").strip().lower()
    if status not in {"todo", "in_progress", "done"}:
        return "todo"
    return status


def _normalize_priority(value: Optional[str]) -> str:
    priority = (value or "medium").strip().lower()
    if priority not in {"high", "medium", "low"}:
        return "medium"
    return priority


def _normalize_task_key(content: str) -> str:
    return re.sub(r"\s+", "", (content or "").strip().lower())


def _sync_tasks_from_plan(plan_payload: Dict) -> Dict[str, int]:
    tasks = plan_payload.get("tasks") or []
    if not isinstance(tasks, list):
        return {"added": 0, "updated": 0}

    existing_tasks = load_tasks()
    indexed_tasks = {
        _normalize_task_key(task.get("content", "")): task
        for task in existing_tasks
        if task.get("content")
    }

    added = 0
    updated = 0

    for item in tasks[:8]:
        if not isinstance(item, dict):
            continue

        content = (item.get("content") or "").strip()
        if not content:
            continue

        status = _normalize_task_status(item.get("status"))
        priority = _normalize_priority(item.get("priority"))
        linked_goal = (item.get("linked_goal") or "").strip() or None
        owner = (item.get("owner") or "").strip() or None
        task_key = _normalize_task_key(content)

        if task_key in indexed_tasks:
            task = indexed_tasks[task_key]
            changes = {}
            if task.get("status") != status:
                changes["status"] = status
            if task.get("priority") != priority:
                changes["priority"] = priority
            if task.get("linked_goal") != linked_goal:
                changes["linked_goal"] = linked_goal
            if task.get("owner") != owner:
                changes["owner"] = owner

            if changes:
                update_task(task["id"], changes)
                updated += 1
            continue

        new_task = add_task(
            content=content,
            priority=priority,
            linked_goal=linked_goal,
            owner=owner,
        )
        if status != new_task.get("status"):
            update_task(new_task["id"], {"status": status})
        added += 1

    return {"added":  added, "updated": updated}


def _meta_agent_reports() -> list[Dict[str, str]]:
    return [
        {
            "agent_id": "analyst",
            "agent_name": "需求分析 Agent",
            "focus": "负责把题目、课程要求和项目资料整理成可执行需求。",
            "summary": "把“要做什么”说清楚。",
            "content": "\n".join(
                [
                    "### 主要作用",
                    "- 明确项目目标、范围边界和用户故事",
                    "- 归纳课程要求中的关键交付物",
                    "- 为后续任务拆解提供统一输入",
                    "",
                    "### 典型产出",
                    "- 项目目标",
                    "- 关键需求",
                    "- 用户故事",
                    "- 范围边界",
                ]
            ),
        },
        {
            "agent_id": "planner",
            "agent_name": "迭代规划 Agent",
            "focus": "负责把需求结论拆成可执行 Sprint 任务并安排三人协作。",
            "summary": "把“怎么做、谁来做”拆出来。",
            "content": "\n".join(
                [
                    "### 主要作用",
                    "- 把目标拆成 4 到 6 条可推进任务",
                    "- 生成三人分工与节奏安排",
                    "- 同步任务 JSON，驱动侧边栏任务区更新",
                    "",
                    "### 典型产出",
                    "- Sprint 目标",
                    "- 任务拆解",
                    "- 三人分工",
                    "- 节奏安排",
                ]
            ),
        },
        {
            "agent_id": "guardian",
            "agent_name": "风险质控 Agent",
            "focus": "负责检查进度、质量和答辩准备，避免项目只会做不会讲。",
            "summary": "把“哪里有风险、怎么收口”补齐。",
            "content": "\n".join(
                [
                    "### 主要作用",
                    "- 识别进度风险和实现风险",
                    "- 检查验收口径是否完整",
                    "- 预估课堂展示和答辩时可能被问到的问题",
                    "",
                    "### 典型产出",
                    "- 关键风险",
                    "- 验收检查",
                    "- 答辩问答准备",
                    "- 下一步建议",
                ]
            ),
        },
    ]


def _build_meta_response(text: str) -> Optional[Dict]:
    if not _is_meta_query(text):
        return None

    knowledge_count = _safe_knowledge_count()
    active_task_count = _safe_active_task_count()

    if _is_agent_intro_query(text):
        output = "\n".join(
            [
                "## 三位 Agent 的作用",
                "",
                "SprintMind 不是单个聊天机器人，而是把一个课程项目拆成三类协作角色：",
                "",
                "- 需求分析 Agent：负责把项目题目、课程要求和资料梳理成清晰需求。",
                "- 迭代规划 Agent：负责把需求拆成 Sprint 任务，并安排三人分工。",
                "- 风险质控 Agent：负责检查进度、质量和答辩风险，帮助项目顺利收口。",
                "",
                "三者串起来后，系统就能同时支持“理解项目、规划任务、控制风险、准备汇报”这四件事。",
            ]
        )
        agent_reports = _meta_agent_reports()
        snapshot_objective = "帮助团队理解三位 Agent 的职责分工，并快速进入协作状态。"
    else:
        output = "\n".join(
            [
                "## SprintMind 可以做什么",
                "",
                "这个平台主要服务于软件工程课程项目或小型团队协作场景，能把资料、需求、任务和展示过程串起来。",
                "",
                "- 需求分析：把项目题目和资料整理成项目目标、关键需求与用户故事。",
                "- 任务规划：生成 Sprint 目标、任务拆解和三人分工。",
                "- 知识检索：基于已上传的 PDF / 文档内容回答项目相关问题。",
                "- 风险控制：识别进度、质量与答辩风险，补齐验收和展示准备。",
                "- 项目展示：把多 Agent 结论整理成适合课堂展示的结构化输出。",
            ]
        )
        agent_reports = []
        snapshot_objective = "概览 SprintMind 平台能力，并帮助团队选择下一步协作方式。"

    return {
        "output": output,
        "agent_reports": agent_reports,
        "project_snapshot": {
            "project_name": "SprintMind",
            "objective": snapshot_objective,
            "sprint_goal": "快速理解平台能力，并决定接下来是上传资料、问答还是开始规划。",
            "risk_level": "低",
            "next_step": "如果你已经有课程题目或项目资料，可以直接继续提问或上传 PDF 开始规划。",
            "task_sync_message": f"当前知识库文档 {knowledge_count} 份，未完成任务 {active_task_count} 条。",
            "knowledge_count": knowledge_count,
        },
    }


def _build_prompts():
    analyst_system = (
        "你是软件项目管理课程中的需求分析 Agent。"
        "你的任务是把用户问题与项目资料转成清晰、可执行的需求结论。"
        "输出必须使用中文 Markdown，并严格包含以下标题：\n"
        "### 项目目标\n"
        "### 关键需求\n"
        "### 用户故事\n"
        "### 范围边界\n"
        "### 交付物\n"
        "### 给迭代规划 Agent 的交接\n"
        "要求：聚焦课程项目，不要闲聊，不要输出与项目管理无关的内容。"
    )
    analyst_human = (
        "用户本轮请求：\n{user_input}\n\n"
        "用户画像：\n{user_profile}\n\n"
        "当前任务：\n{current_tasks}\n\n"
        "近期对话：\n{recent_dialogue}\n\n"
        "知识库片段：\n{knowledge_context}"
    )

    planner_system = (
        "你是迭代规划 Agent，负责把需求分析结论转成三人团队可执行的 Sprint 计划。"
        "输出必须使用中文 Markdown，并严格包含以下标题：\n"
        "### Sprint 目标\n"
        "### 任务拆解\n"
        "### 三人分工\n"
        "### 节奏安排\n"
        "### 对老师展示时的亮点\n"
        "### 任务同步 JSON\n"
        "在“### 任务同步 JSON”标题下，必须给出一个 ```json 代码块，格式如下："
        "{{\"sprint_goal\":\"...\",\"tasks\":[{{\"content\":\"...\",\"status\":\"todo\",\"priority\":\"high|medium|low\",\"linked_goal\":\"...\",\"owner\":\"成员1/成员2/成员3\"}}]}}"
        "。任务数控制在 4 到 6 条。"
    )
    planner_human = (
        "用户本轮请求：\n{user_input}\n\n"
        "需求分析结果：\n{analyst_output}\n\n"
        "当前任务：\n{current_tasks}\n\n"
        "知识库片段：\n{knowledge_context}"
    )

    guardian_system = (
        "你是风险质控 Agent，负责发现项目推进中的进度、质量与答辩风险。"
        "输出必须使用中文 Markdown，并严格包含以下标题：\n"
        "### 关键风险\n"
        "### 验收检查\n"
        "### 进度预警\n"
        "### 答辩问答准备\n"
        "### 下一步建议\n"
        "### 总体风险等级\n"
        "在“### 总体风险等级”下只写一行，例如：中。"
    )
    guardian_human = (
        "用户本轮请求：\n{user_input}\n\n"
        "需求分析结果：\n{analyst_output}\n\n"
        "当前任务：\n{current_tasks}\n\n"
        "知识库片段：\n{knowledge_context}"
    )

    return {
        "analyst": (analyst_system, analyst_human),
        "planner": (planner_system, planner_human),
        "guardian": (guardian_system, guardian_human),
    }


def _run_three_role_workflow(text: str, context: Dict, llm=None) -> Dict[str, str]:
    prompts = _build_prompts()
    llm = llm or get_llm()

    analyst_system, analyst_human = prompts["analyst"]
    analyst_output = _invoke_role_agent(
        analyst_system,
        analyst_human,
        {
            "user_input": text,
            "user_profile": context["user_profile"],
            "current_tasks": context["current_tasks"],
            "recent_dialogue": context["recent_dialogue"],
            "knowledge_context": context["knowledge_context"],
        },
        llm=llm,
    )

    planner_system, planner_human = prompts["planner"]
    guardian_system, guardian_human = prompts["guardian"]

    planner_values = {
        "user_input": text,
        "analyst_output": analyst_output,
        "current_tasks": context["current_tasks"],
        "knowledge_context": context["knowledge_context"],
    }
    guardian_values = {
        "user_input": text,
        "analyst_output": analyst_output,
        "current_tasks": context["current_tasks"],
        "knowledge_context": context["knowledge_context"],
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        planner_future = executor.submit(
            _invoke_role_agent,
            planner_system,
            planner_human,
            planner_values,
            llm,
        )
        guardian_future = executor.submit(
            _invoke_role_agent,
            guardian_system,
            guardian_human,
            guardian_values,
            llm,
        )
        planner_output = planner_future.result()
        guardian_output = guardian_future.result()

    return {
        "analyst_output": analyst_output,
        "planner_output": planner_output,
        "guardian_output": guardian_output,
    }


def _build_project_result(text: str, context: Dict, outputs: Dict[str, str], timings: Optional[Dict] = None) -> Dict:
    analyst_output = outputs["analyst_output"]
    planner_output = outputs["planner_output"]
    guardian_output = outputs["guardian_output"]

    plan_payload = _extract_json_block(planner_output)
    sync_result = _sync_tasks_from_plan(plan_payload)

    sprint_goal = (plan_payload.get("sprint_goal") or "").strip()
    if not sprint_goal:
        sprint_goal = _extract_section_value(planner_output, "### Sprint 目标")

    project_goal = _extract_section_value(analyst_output, "### 项目目标")
    next_step = _extract_section_value(guardian_output, "### 下一步建议")
    risk_level = _extract_section_value(guardian_output, "### 总体风险等级") or "中"

    sync_message = f"任务同步：新增 {sync_result['added']} 条，更新 {sync_result['updated']} 条。"

    agent_reports = [
        {
            "agent_id": TEAM_ROLES[0]["agent_id"],
            "agent_name": TEAM_ROLES[0]["agent_name"],
            "focus": TEAM_ROLES[0]["focus"],
            "summary": _first_meaningful_line(analyst_output),
            "content": analyst_output,
        },
        {
            "agent_id": TEAM_ROLES[1]["agent_id"],
            "agent_name": TEAM_ROLES[1]["agent_name"],
            "focus": TEAM_ROLES[1]["focus"],
            "summary": _first_meaningful_line(planner_output),
            "content": planner_output,
        },
        {
            "agent_id": TEAM_ROLES[2]["agent_id"],
            "agent_name": TEAM_ROLES[2]["agent_name"],
            "focus": TEAM_ROLES[2]["focus"],
            "summary": _first_meaningful_line(guardian_output),
            "content": guardian_output,
        },
    ]

    project_snapshot = {
        "project_name": "SprintMind",
        "objective": project_goal or "围绕课程作业形成可演示的软件项目管理多智能体系统。",
        "sprint_goal": sprint_goal or "生成本轮 Sprint 计划并推进三人协作。",
        "risk_level": risk_level,
        "next_step": next_step or "先确认本轮目标，再按任务拆解推进。",
        "task_sync_message": sync_message,
        "knowledge_count": context["knowledge_count"],
    }
    if timings:
        project_snapshot["workflow_timing"] = timings

    final_answer = "\n".join(
        [
            "## SprintMind 协作总览",
            f"- 项目目标：{project_snapshot['objective']}",
            f"- Sprint 目标：{project_snapshot['sprint_goal']}",
            f"- 总体风险：{project_snapshot['risk_level']}",
            f"- {project_snapshot['task_sync_message']}",
            "",
            "三位 Agent 的详细结论已经整理在下方卡片中，可直接用于课堂展示、阶段汇报和任务推进。",
        ]
    )

    return {
        "output": final_answer,
        "agent_reports": agent_reports,
        "project_snapshot": project_snapshot,
    }


def _chunk_text(text: str, chunk_size: int = 56) -> list[str]:
    content = (text or "").strip()
    if not content:
        return []
    return [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]


def run_project_team(retriever, user_input: str, chat_history: list) -> Dict:
    text = (user_input or "").strip()
    if not text:
        return {
            "output": "请输入和项目管理有关的有效问题。",
            "agent_reports": [],
            "project_snapshot": None,
        }

    meta_response = _build_meta_response(text)
    if meta_response:
        logger.info("命中 SprintMind 快速说明路径 | input=%s", text)
        return meta_response

    context = _build_runtime_context(retriever, text, chat_history)
    llm = get_llm()

    stage_started_at = time.perf_counter()
    outputs = _run_three_role_workflow(text, context, llm=llm)
    elapsed = time.perf_counter() - stage_started_at

    result = _build_project_result(
        text,
        context,
        outputs,
        timings={"workflow_seconds": round(elapsed, 2)},
    )
    logger.info("三智能体完整流程完成 | seconds=%.2f | input=%s", elapsed, text)
    return result


def run_project_team_stream(retriever, user_input: str, chat_history: list):
    text = (user_input or "").strip()
    if not text:
        yield {"event": "error", "data": {"detail": "请输入和项目管理有关的有效问题。"}}
        return

    meta_response = _build_meta_response(text)
    if meta_response:
        yield {"event": "status", "data": {"stage": "meta", "label": "正在整理平台说明"}}
        for chunk in _chunk_text(meta_response["output"]):
            yield {"event": "delta", "data": {"text": chunk}}
        yield {"event": "final", "data": meta_response}
        return

    workflow_started_at = time.perf_counter()
    yield {"event": "status", "data": {"stage": "retrieve", "label": "正在检索项目资料与上下文"}}
    context = _build_runtime_context(retriever, text, chat_history)
    llm = get_llm()

    prompts = _build_prompts()

    yield {"event": "status", "data": {"stage": "analyst", "label": "需求分析 Agent 正在梳理目标与范围"}}
    analyst_system, analyst_human = prompts["analyst"]
    analyst_output = _invoke_role_agent(
        analyst_system,
        analyst_human,
        {
            "user_input": text,
            "user_profile": context["user_profile"],
            "current_tasks": context["current_tasks"],
            "recent_dialogue": context["recent_dialogue"],
            "knowledge_context": context["knowledge_context"],
        },
        llm=llm,
    )

    planner_system, planner_human = prompts["planner"]
    guardian_system, guardian_human = prompts["guardian"]
    yield {"event": "status", "data": {"stage": "parallel", "label": "规划与风控 Agent 正在并行处理任务与风险"}}
    planner_values = {
        "user_input": text,
        "analyst_output": analyst_output,
        "current_tasks": context["current_tasks"],
        "knowledge_context": context["knowledge_context"],
    }
    guardian_values = {
        "user_input": text,
        "analyst_output": analyst_output,
        "current_tasks": context["current_tasks"],
        "knowledge_context": context["knowledge_context"],
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        planner_future = executor.submit(
            _invoke_role_agent,
            planner_system,
            planner_human,
            planner_values,
            llm,
        )
        guardian_future = executor.submit(
            _invoke_role_agent,
            guardian_system,
            guardian_human,
            guardian_values,
            llm,
        )
        planner_output = planner_future.result()
        guardian_output = guardian_future.result()

    result = _build_project_result(
        text,
        context,
        {
            "analyst_output": analyst_output,
            "planner_output": planner_output,
            "guardian_output": guardian_output,
        },
        timings={"workflow_seconds": round(time.perf_counter() - workflow_started_at, 2)},
    )

    yield {"event": "status", "data": {"stage": "finalize", "label": "正在整理最终答复与协作卡片"}}
    for chunk in _chunk_text(result["output"]):
        yield {"event": "delta", "data": {"text": chunk}}
    yield {"event": "final", "data": result}
