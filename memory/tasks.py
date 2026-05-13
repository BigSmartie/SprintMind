import json
from datetime import datetime
from typing import Dict, List, Optional

from config import settings
from core import get_logger

logger = get_logger(__name__)

TASKS_FILE = settings.DATA_DIR / "tasks.json"


def load_tasks() -> List[Dict]:
    if not TASKS_FILE.exists():
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        logger.exception("加载任务列表失败")
        return []


def save_tasks(tasks: List[Dict]) -> None:
    settings.ensure_dirs()
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as handle:
            json.dump(tasks, handle, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("保存任务列表失败")


def add_task(
    content: str,
    priority: str = "medium",
    linked_goal: Optional[str] = None,
    owner: Optional[str] = None,
) -> Dict:
    tasks = load_tasks()
    new_id = (max([t.get("id", 0) for t in tasks]) + 1) if tasks else 1
    new_task = {
        "id": new_id,
        "content": content,
        "priority": priority,
        "status": "todo",
        "linked_goal": linked_goal,
        "owner": owner,
        "created_at": datetime.now().isoformat(),
    }
    tasks.append(new_task)
    save_tasks(tasks)
    logger.info("任务已添加 | id=%s | content=%s", new_id, content)
    return new_task


def update_task(task_id: int, updates: Dict) -> Optional[Dict]:
    tasks = load_tasks()
    for task in tasks:
        if task.get("id") == task_id:
            updates.pop("id", None)
            task.update(updates)
            save_tasks(tasks)
            logger.info("任务已更新 | id=%s | updates=%s", task_id, updates)
            return task
    return None


def delete_task(task_id: int) -> bool:
    tasks = load_tasks()
    original_len = len(tasks)
    tasks = [task for task in tasks if task.get("id") != task_id]
    if len(tasks) < original_len:
        save_tasks(tasks)
        logger.info("任务已删除 | id=%s", task_id)
        return True
    return False


def format_tasks_for_prompt(tasks: List[Dict], only_active: bool = False) -> str:
    if not tasks:
        return "当前任务清单为空。"

    display_tasks = tasks
    if only_active:
        display_tasks = [task for task in tasks if task.get("status") != "done"]

    if not display_tasks:
        return "目前没有进行中的任务。"

    lines = ["### 我的任务清单"]
    status_map = {
        "todo": "待办",
        "in_progress": "进行中",
        "done": "已完成",
    }

    for task in display_tasks:
        status_str = status_map.get(task.get("status"), task.get("status"))
        goal_hint = f" (关联目标: {task['linked_goal']})" if task.get("linked_goal") else ""
        owner_hint = f" | 负责人: {task['owner']}" if task.get("owner") else ""
        priority_hint = f" | 优先级: {task.get('priority', 'medium')}" if task.get("priority") else ""
        lines.append(
            f"{task['id']}. [{status_str}] {task['content']}{goal_hint}{owner_hint}{priority_hint}"
        )

    return "\n".join(lines)
