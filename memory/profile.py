import json
from pathlib import Path
from typing import Dict

from config import settings
from core import get_logger

logger = get_logger(__name__)

PROFILE_FILE = settings.DATA_DIR / "user_profile.json"


def load_user_profile() -> Dict:
    if not PROFILE_FILE.exists():
        return {
            "name": "",
            "preferred_style": "简洁",
            "interests": [],
            "current_projects": [],
            "current_goals": [],
            "workflow_preferences": [],
            "persona_notes": "",
            "notes": "",
        }

    try:
        with open(PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 补齐可能缺失的字段
            default = {
                "name": "",
                "preferred_style": "简洁",
                "interests": [],
                "current_projects": [],
                "current_goals": [],
                "workflow_preferences": [],
                "persona_notes": "",
                "notes": "",
            }
            for k, v in default.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception:
        logger.exception("读取用户画像失败，返回默认画像")
        return {
            "name": "",
            "preferred_style": "简洁",
            "interests": [],
            "current_projects": [],
            "current_goals": [],
            "workflow_preferences": [],
            "persona_notes": "",
            "notes": "",
        }


def save_user_profile(profile: Dict) -> None:
    settings.ensure_dirs()
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    logger.info("用户画像已保存")


def update_user_profile(updates: Dict) -> Dict:
    profile = load_user_profile()
    profile.update(updates or {})
    save_user_profile(profile)
    return profile


def format_user_profile(profile: Dict) -> str:
    """
    将用户画像格式化为供 LLM 阅读的 Context。
    """
    if not profile:
        return "用户画像信息不足。"

    lines = []
    if profile.get("name"):
        lines.append(f"- 称呼: {profile['name']}")
    if profile.get("preferred_style"):
        lines.append(f"- 偏好回答风格: {profile['preferred_style']}")
    if profile.get("persona_notes"):
        lines.append(f"- 用户身份/背景: {profile['persona_notes']}")
    
    interests = profile.get("interests", [])
    if interests:
        lines.append(f"- 兴趣领域: {', '.join(interests)}")
        
    projects = profile.get("current_projects", [])
    if projects:
        lines.append(f"- 当前核心项目: {', '.join(projects)}")
        
    goals = profile.get("current_goals", [])
    if goals:
        lines.append(f"- 当前学习/工作目标: {', '.join(goals)}")
        
    prefs = profile.get("workflow_preferences", [])
    if prefs:
        lines.append(f"- 工作流偏好: {', '.join(prefs)}")
        
    if profile.get("notes"):
        lines.append(f"- 其他备注: {profile['notes']}")

    if not lines:
        return "暂无详细用户画像信息。"

    return "\n".join(lines)