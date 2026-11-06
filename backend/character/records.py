"""角色心声和好感度变化记录的文件存取。"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.character.state import state_path


def folders(root, name):
    path = state_path(root, name)
    if path is None:
        raise ValueError("角色目录不存在或路径无效")
    result = []
    for folder in ("inner_voice", "favorability_change"):
        directory = path.parent / folder
        if directory.is_symlink():
            raise ValueError("记录目录不能是链接")
        directory.mkdir(exist_ok=True)
        result.append(directory)
    return result


def write_record(directory, metadata, content):
    now = datetime.now(timezone(timedelta(hours=8)))
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    name = now.strftime("%Y%m%d_%H%M%S_%f_") + uuid.uuid4().hex[:12] + ".md"
    metadata = dict(metadata, created_at=stamp)
    # 排除半写文件；只有完整记录才使用 .md 扩展名。
    temp = directory / (name + ".tmp")
    try:
        temp.write_text("<!-- " + json.dumps(metadata, ensure_ascii=False) + " -->\n\n" + content, encoding="utf-8")
        temp.replace(directory / name)
    finally:
        temp.unlink(missing_ok=True)
    return name


def read_record(path):
    if path.is_symlink():
        raise ValueError("记录不能是链接")
    text = path.read_text(encoding="utf-8")
    first, _, content = text.partition("\n\n")
    metadata = json.loads(first.removeprefix("<!-- ").removesuffix(" -->"))
    return dict(metadata, id=path.name, content=content)


def list_records(directory):
    return [read_record(path) for path in sorted(directory.glob("*.md"), reverse=True)]


def record_affection(root, character, old, reason=None):
    new = character.state["affection_level"]
    if old == new:
        return
    _, directory = folders(root, character.english_name)
    reason = reason or character.state.get("affection_reason", "")
    write_record(directory, {"old": old, "new": new}, f"# 好感度变化\n\n{old:g} -> {new:g}\n\n原因：{reason}\n")
