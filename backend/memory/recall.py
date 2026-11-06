"""只读检索当前角色已有的记忆集合，不创建库、集合或默认嵌入模型。"""

import math
import random
from typing import Any

from backend.memory.chromadb_init import get_chroma_client_dir

RECALL_LIMITS = {"digest": 5, "original": 10}
FORGETTING_PROBABILITY = 0.30


def query_memory(character: Any, question: str, collection_name: str) -> dict[str, Any]:
    """用角色的 EmLLM 查询摘要前五条或原文前十条。"""
    if collection_name not in {"digest", "original"}:
        raise ValueError("仅支持 digest 和 original")
    if not isinstance(question, str) or not question.strip():
        return {"status": "invalid_question", "message": "question 必须是非空的问题字符串", "records": []}

    # 延迟导入，避免 Character -> get_tools -> recall -> get_character 循环。
    from backend.chat.get_character import load_settings

    with character.operation_lock:
        try:
            settings = load_settings(character.english_name) or {}
        except Exception as exc:
            print(f"[SoulHaven] 回忆配置读取失败：{type(exc).__name__}")
            return {"status": "settings_error", "message": "角色记忆配置读取失败，不是概率遗忘。", "records": []}
        embedding = settings.get("embedding") or {}
        if not isinstance(embedding, dict) or not embedding.get("enabled", False):
            return {"status": "disabled", "message": "角色未启用 Embedding 记忆库。", "records": []}
        if embedding.get("probabilistic_forgetting") is True and random.random() < FORGETTING_PROBABILITY:
            return {"status": "forgotten", "message": "这段往事暂时想不起来。本轮不要再调用 recall_digest 或 recall_original，也不要换工具绕过遗忘。", "records": []}
        if getattr(character, "em_llm", None) is None:
            return {"status": "unavailable", "message": "角色的 Embedding 模型不可用，不是概率遗忘。", "records": []}

        try:
            client_dir = get_chroma_client_dir(character.english_name)
            if not client_dir.is_dir() or not (client_dir / "chroma.sqlite3").is_file():
                return {"status": "missing_database", "message": "角色没有已有的记忆库，不会自动创建。", "records": []}
            import chromadb

            client = chromadb.PersistentClient(path=str(client_dir))
            collection = client.get_collection(collection_name, embedding_function=None)
            count = collection.count()
            if count == 0:
                return {"status": "empty", "message": f"{collection_name} 集合中尚无记忆。", "records": []}
            vector = character.em_llm.invoke(question.strip())
            result = collection.query(
                query_embeddings=[vector],
                n_results=min(RECALL_LIMITS[collection_name], count),
                include=["documents", "distances"],
            )
            ids = (result.get("ids") or [[]])[0]
            documents = (result.get("documents") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            records = []
            for record_id, document, distance in zip(ids, documents, distances):
                if not isinstance(document, str) or not document.strip():
                    continue
                distance = float(distance)
                if not math.isfinite(distance):
                    continue
                records.append({"id": record_id, "text": document, "distance": distance})
            records.sort(key=lambda item: item["distance"])
            records = records[:RECALL_LIMITS[collection_name]]
            for number, record in enumerate(records, 1):
                record["number"] = number
            return {"status": "ok" if records else "empty", "records": records,
                    "message": "匹配度用原始距离 distance 表示：越小越匹配，不是置信概率；最近邻仍可能与问题无关。"}
        except Exception as exc:
            # 服务商异常可能包含 API Key，不将异常正文放入日志或模型上下文。
            print(f"[SoulHaven] {collection_name} 回忆检索失败：{type(exc).__name__}")
            return {"status": "query_error", "message": "记忆集合缺失或检索服务异常，不是概率遗忘。", "records": []}
