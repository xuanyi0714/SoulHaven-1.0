"""世界观文件的创建、读取和保存；向量同步由调用方协调。"""

import json
import re
import uuid
from pathlib import Path
from threading import RLock
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORLD_ROOT = PROJECT_ROOT / "worlds"
BUILTIN_WORLDS = {
    "reality": PROJECT_ROOT / "web" / "data" / "reality_world.json",
    "jianghu": PROJECT_ROOT / "web" / "data" / "jianghu_world.json",
    "vampire": PROJECT_ROOT / "web" / "data" / "vampire_world.json",
    "space": PROJECT_ROOT / "web" / "data" / "space_world.json",
}
WORLD_ID_PATTERN = re.compile(r"^(?:reality|jianghu|vampire|space|[a-f0-9]{32})$")
WORLD_LOCK = RLock()


def _world_path(world_id: str) -> Path:
    if not isinstance(world_id, str) or not WORLD_ID_PATTERN.fullmatch(world_id):
        raise ValueError("世界观标识无效")
    return WORLD_ROOT / world_id / "world.json"


def normalize_world(data: dict[str, Any]) -> dict[str, Any]:
    """校验世界名称、常驻内容、分条资料和目录，保留文字完整内容。"""
    if not isinstance(data, dict):
        raise ValueError("世界观内容必须是对象")
    name = data.get("name")
    core = data.get("core")
    if isinstance(core, str):
        core = [core] if core.strip() else []
    details = data.get("details", [])
    directory = data.get("directory", [])
    if isinstance(directory, str):
        directory = [directory] if directory.strip() else []
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        raise ValueError("世界名称不能为空，且不能超过 100 字")
    if not isinstance(core, list) or not core or any(not isinstance(x, str) or not x.strip() for x in core):
        raise ValueError("请填写常驻世界设定")
    if not isinstance(details, list) or any(not isinstance(x, dict) or not isinstance(x.get("title"), str) or not x["title"].strip() or not isinstance(x.get("content"), str) or not x["content"].strip() for x in details):
        raise ValueError("每条详细资料都需要标题和正文")
    if not isinstance(directory, list) or any(not (isinstance(x, str) and x.strip()) and not (isinstance(x, dict) and isinstance(x.get("title"), str) and x["title"].strip() and isinstance(x.get("hint"), str) and x["hint"].strip()) for x in directory):
        raise ValueError("资料目录格式无效")
    return {"name": name.strip(), "core": [x.strip() for x in core],
            "details": [{"title": x["title"].strip(), "content": x["content"].strip()} for x in details],
            "directory": [x.strip() if isinstance(x, str) else {"title": x["title"].strip(), "hint": x["hint"].strip()} for x in directory]}


def load_world(world_id: str) -> dict[str, Any]:
    """读取已保存世界观；内置世界首次修改前读取项目自带的源文件。"""
    path = _world_path(world_id)
    if not path.is_file():
        path = BUILTIN_WORLDS.get(world_id, path)
    if not path.is_file():
        raise ValueError("世界观不存在")
    world = normalize_world(json.loads(path.read_text(encoding="utf-8-sig")))
    return {"id": world_id, **world}


def list_worlds() -> list[dict[str, Any]]:
    ids = list(BUILTIN_WORLDS)
    if WORLD_ROOT.is_dir():
        ids.extend(sorted(p.name for p in WORLD_ROOT.iterdir() if p.is_dir() and p.name not in BUILTIN_WORLDS and WORLD_ID_PATTERN.fullmatch(p.name) and (p / "world.json").is_file()))
    return [load_world(world_id) for world_id in ids]


def save_world_file(world_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """原子替换世界文件；不直接操作角色的世界集合。"""
    path = _world_path(world_id)
    world = normalize_world(data)
    with WORLD_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".world-{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(world, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return {"id": world_id, **world}


def create_world(data: dict[str, Any]) -> dict[str, Any]:
    """创建拥有独立标识的世界观，内容保存在项目 worlds 目录。"""
    return save_world_file(uuid.uuid4().hex, data)
