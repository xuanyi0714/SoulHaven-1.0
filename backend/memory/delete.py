"""Explicit, confirmed deletion of one character's conversation memories."""
from contextlib import ExitStack
from backend.llms import llms_main
from backend.memory import chromadb_init
from backend.memory.sum_up_history import HistoryMemory

CONFIRMATION_TEXT = "我确认要清空聊天记录"


def delete_memory(character, confirmation: str) -> None:
    """Empty memories and restore the opening line to archives and runtime history.

    This function is destructive and validates the exact confirmation itself.
    It never deletes role definitions, images, settings, or other characters.
    """
    if confirmation != CONFIRMATION_TEXT:
        raise ValueError("请输入完整确认文字：" + CONFIRMATION_TEXT)
    name = character.english_name
    if not llms_main.ENGLISH_NAME_PATTERN.fullmatch(name) or name.upper() in llms_main.WINDOWS_RESERVED_NAMES:
        raise ValueError("角色英文名无效")
    root = llms_main.CHARACTERS_DIR.resolve()
    directory = (root / name).resolve()
    if directory.parent != root or not directory.is_dir():
        raise ValueError("角色目录不存在或无效")
    paths = HistoryMemory._get_paths(name)
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise ValueError("历史文件路径无效")
    client_path = chromadb_init.get_chroma_client_dir(name)
    if client_path.resolve().parent != chromadb_init.DATABASE_DIR.resolve():
        raise ValueError("记忆库路径无效")
    with character.operation_lock:
        if not character.messages or character.messages[0].get("role") != "system":
            raise ValueError("角色缺少系统设定，无法清空")
        system = dict(character.messages[0])
        collections = []
        if client_path.exists():
            if not client_path.is_dir() or not (client_path / "chroma.sqlite3").is_file():
                raise RuntimeError("记忆库目录异常，清空未执行")
            import chromadb
            client = chromadb.PersistentClient(path=str(client_path))
            for entry in client.list_collections():
                collection_name = entry.name if hasattr(entry, "name") else str(entry)
                # 清空聊天只处理对话记忆，不能清除角色绑定的世界观。
                if collection_name in {chromadb_init.DIGEST_COLLECTION_NAME, chromadb_init.ORIGINAL_COLLECTION_NAME}:
                    collections.append(client.get_collection(collection_name))
        # Verify every file is writable before deleting any database records.
        with ExitStack() as stack:
            files = []
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                files.append(stack.enter_context(path.open("a+b")))
            for collection in collections:
                while True:
                    ids = collection.get(limit=1000, include=[])["ids"]
                    if not ids:
                        break
                    collection.delete(ids=ids)
                if collection.count():
                    raise RuntimeError("记忆库未完全清空，请重试")
            for stream in files:
                stream.seek(0)
                stream.truncate(0)
                stream.flush()
        HistoryMemory.initialize_character_history(character)
        character.messages[:] = [system, {"role": "assistant", "content": character.opening_line}]
