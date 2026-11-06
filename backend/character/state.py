"""角色当前状态的校验、好感度计算和精简 JSON 持久化。"""

import json
import math
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.character.affection import calculate_affection, BASE
from backend.character.feelings import normalize_secondary_feelings
from backend.chat.outputs import normalize_emotion


def default_state():
    return {
        "affection_level": 40.0, "affection_reason": "故事刚刚开始，还在慢慢了解彼此。",
        "external_mood": "平静", "external_mood_intensity": "50", "the_choice_of_emotion": "calm",
        "inner_mood": "平静", "inner_mood_intensity": "50", "mood_reason": "尚无互动",
        "attitude_to_user": "尚在了解", "secondary_feelings": [], "updated_at": "",
    }


def state_path(root, name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        return None
    directory = Path(root) / name
    if not directory.is_dir() or directory.resolve().parent != Path(root).resolve():
        return None
    return directory / "state.json"


def persistent_state(data):
    """只保留当前状态；单次变化方向、等级和差值由独立变化记录负责。"""
    state = default_state()
    if not isinstance(data, dict):
        return state
    try:
        level = float(data.get("affection_level", 40))
        if isinstance(data.get("affection_level"), bool) or not math.isfinite(level) or level > 100:
            raise ValueError("invalid affection level")
        state["affection_level"] = level
    except (TypeError, ValueError):
        pass
    for key in ("external_mood", "inner_mood", "mood_reason", "attitude_to_user", "affection_reason", "updated_at"):
        if isinstance(data.get(key), str) and data[key].strip():
            state[key] = data[key].strip()
    for key in ("external_mood_intensity", "inner_mood_intensity"):
        value = data.get(key)
        if not isinstance(value, bool) and isinstance(value, (str, int)) and str(value).isdigit() and 1 <= int(value) <= 100:
            state[key] = str(int(value))
    state["the_choice_of_emotion"] = normalize_emotion(data.get("the_choice_of_emotion"))
    feelings = normalize_secondary_feelings(data.get("secondary_feelings", []))
    if feelings is not None:
        state["secondary_feelings"] = feelings
    if "affection_reason" not in data and isinstance(data.get("affection_event_reason"), str):
        state["affection_reason"] = data["affection_event_reason"]
    return state


def load_state(root, name):
    path = state_path(root, name)
    if path and path.is_file():
        try:
            return persistent_state(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            pass
    return default_state()


def save_state(root, name, state):
    path = state_path(root, name)
    if not path:
        return
    saved = persistent_state(state)
    saved["updated_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as f:
            temp = f.name
            json.dump(saved, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp, path)
        state.clear()
        state.update(saved)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def update_state(state, response, allow_affection=True):
    """成功完成一轮后更新；无效字段保留原值，次要感受最多两项。"""
    if "the_choice_of_emotion" in response:
        state["the_choice_of_emotion"] = normalize_emotion(response["the_choice_of_emotion"])
    for key in ("external_mood", "inner_mood", "mood_reason", "attitude_to_user"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            state[key] = value.strip()
    for key in ("external_mood_intensity", "inner_mood_intensity"):
        value = response.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).isdigit() and 1 <= int(value) <= 100:
            state[key] = str(int(value))
    if "secondary_feelings" in response:
        feelings = normalize_secondary_feelings(response["secondary_feelings"])
        if feelings is not None:
            state["secondary_feelings"] = feelings
    direction = response.get("affection_direction") if allow_affection else "unchanged"
    event = response.get("affection_event_level") if allow_affection else "none"
    if not isinstance(direction, str) or not isinstance(event, str) or direction not in ("increase", "decrease", "unchanged") or event not in BASE:
        return
    if direction == "unchanged":
        event = "none"
    state["affection_level"] = calculate_affection(float(state["affection_level"]), direction, event)
    reason = response.get("affection_event_reason")
    if allow_affection and isinstance(reason, str) and reason.strip():
        state["affection_reason"] = reason.strip()
