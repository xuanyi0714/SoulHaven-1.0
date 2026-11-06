"""角色世界观向量集合：逐条写入、检索和全角色同步。"""
from contextlib import ExitStack
from typing import Any

from backend.chat.create_world import load_world, save_world_file, WORLD_LOCK
from backend.memory.chromadb_init import get_chroma_client_dir, init_world_collection


def _collection(character: Any):
    from backend.llms.llms_main import CHARACTERS_DIR
    return init_world_collection(CHARACTERS_DIR / character.english_name)


def _texts(world: dict) -> list[str]:
    if not world["directory"] or not world["details"]:
        return []
    return [f"{entry['title']}\n{entry['content']}" for entry in world["details"]]


def _prepare(character: Any, world: dict) -> tuple[list[str], list]:
    texts = _texts(world)
    if not texts or character.em_llm is None:
        return [], []
    vectors = []
    for start in range(0, len(texts), 32):
        batch = texts[start:start + 32]
        embedded = character.em_llm.invoke(batch)
        if len(embedded) != len(batch):
            raise ValueError("世界观向量数量与资料条目不一致")
        vectors.extend(embedded)
    return texts, vectors


def _clear(collection):
    while True:
        ids = collection.get(limit=1000, include=[])["ids"]
        if not ids:
            return
        collection.delete(ids=ids)


def _write(collection, texts, vectors):
    for start in range(0, len(texts), 32):
        end = min(start + 32, len(texts))
        collection.add(ids=[f"w{i + 1}" for i in range(start, end)], documents=texts[start:end], embeddings=vectors[start:end])


def _snapshot(collection):
    return collection.get(include=["documents", "embeddings", "metadatas"])


def _restore(collection, snapshot):
    _clear(collection)
    ids = snapshot["ids"]
    for i, item in enumerate(ids):
        fields = {"ids": [item], "embeddings": [[float(x) for x in snapshot["embeddings"][i]]]}
        if snapshot["documents"][i] is not None:
            fields["documents"] = [snapshot["documents"][i]]
        if snapshot["metadatas"][i] is not None:
            fields["metadatas"] = [snapshot["metadatas"][i]]
        collection.add(**fields)


def rebuild_world_for_character(character: Any) -> bool:
    """创建角色时写入所绑定世界的每条资料；没有模型则保留空集合。"""
    world = load_world(character.world_id)
    with character.operation_lock:
        texts, vectors = _prepare(character, world)
        collection = _collection(character)
        _clear(collection)
        _write(collection, texts, vectors)
    return bool(texts)


def rebuild_all_worlds(characters: list[Any], edited_id: str, edited_world: dict) -> list[str]:
    """先嵌入并快照，再重建所有角色；失败时尝试恢复旧向量。"""
    from backend.llms.llms_main import SYSTEM_PROMPT_TEMPLATE, format_description, format_tool_names, RESPONSE_FORMAT_PARSER, format_world_setting
    ordered = sorted(characters, key=lambda c: c.english_name.casefold())
    with WORLD_LOCK, ExitStack() as stack:
        for character in ordered:
            stack.enter_context(character.operation_lock)
        prepared = []
        skipped = []
        for character in ordered:
            world = edited_world if character.world_id == edited_id else load_world(character.world_id)
            if _texts(world) and character.em_llm is None:
                from backend.chat.get_character import load_settings
                settings = load_settings(character.english_name) or {}
                embedding = settings.get("embedding") or {}
                if isinstance(embedding, dict) and embedding.get("enabled"):
                    raise RuntimeError("有角色已配置记忆模型但当前不可用，世界观未保存；请检查模型后重试。")
                skipped.append(character.name)
            texts, vectors = _prepare(character, world)
            collection = _collection(character)
            prepared.append((character, collection, texts, vectors, _snapshot(collection)))
        changed = []
        try:
            for character, collection, texts, vectors, snapshot in prepared:
                changed.append((collection, snapshot))
                _clear(collection)
                _write(collection, texts, vectors)
            save_world_file(edited_id, edited_world)
        except Exception as exc:
            restore_errors = []
            for collection, snapshot in reversed(changed):
                try:
                    _restore(collection, snapshot)
                except Exception as restore_exc:
                    restore_errors.append(type(restore_exc).__name__)
            if restore_errors:
                raise RuntimeError("世界观保存失败，部分角色的世界观向量恢复失败，请检查并重试") from exc
            raise RuntimeError("世界观保存失败，已恢复原有向量") from exc
        for character in ordered:
            if character.world_id == edited_id and character.messages and character.messages[0].get("role") == "system":
                character.messages[0] = {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(
                    name=character.name, description=format_description(character.description),
                    world_setting=format_world_setting(character.world_id),
                    tool_names=format_tool_names(list(character.tools), character.tools),
                    response_format=RESPONSE_FORMAT_PARSER.get_format_instructions())}
        return skipped


def query_world(character: Any, question: str) -> dict:
    """检索当前角色的 world 集合；不使用记忆遗忘概率。"""
    if not isinstance(question, str) or not question.strip():
        return {"status": "invalid_question", "message": "请输入查询问题。", "records": []}
    if character.em_llm is None:
        return {"status": "disabled", "message": "角色没有配置记忆模型，无法查询世界观详细资料。", "records": []}
    try:
        import chromadb
        folder = get_chroma_client_dir(character.english_name)
        if not folder.is_dir() or not (folder / "chroma.sqlite3").is_file():
            return {"status": "missing_database", "message": "世界观数据库不存在。", "records": []}
        collection = chromadb.PersistentClient(path=str(folder)).get_collection("world", embedding_function=None)
        count = collection.count()
        if not count:
            return {"status": "empty", "message": "没有可查询的世界观详细资料。", "records": []}
        vector = character.em_llm.invoke(question.strip())
        result = collection.query(query_embeddings=[vector], n_results=min(5, count), include=["documents", "distances"])
        records = [{"number": i + 1, "id": identifier, "text": document, "distance": float(distance)} for i, (identifier, document, distance) in enumerate(zip(result["ids"][0], result["documents"][0], result["distances"][0])) if isinstance(document, str) and document.strip()]
        return {"status": "ok", "message": "距离越小越匹配，仍需判断相关性。", "records": records}
    except Exception as exc:
        print(f"[SoulHaven] 世界观查询失败：{type(exc).__name__}")
        return {"status": "query_error", "message": "世界观资料查询失败。", "records": []}
