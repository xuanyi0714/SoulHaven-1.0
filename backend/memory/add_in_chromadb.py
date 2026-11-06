"""把原始对话或摘要追加到角色已有的 ChromaDB 集合。

该模块不创建数据库，也不创建集合。角色创建阶段已经通过
`chromadb_init.init_chromadb()` 建好客户端和集合；这里只负责打开已有的
客户端，并把文本写入已存在的 `original` 或 `digest` 集合。

写入失败只记录日志，不向调用方抛异常，也不影响 original.json / original.md。
"""

from typing import Any

from backend.memory.chromadb_init import (
    DIGEST_COLLECTION_NAME,
    ORIGINAL_COLLECTION_NAME,
    get_chroma_client_dir,
)


class ChromadbAppend:
    """向已有 ChromaDB original 集合追加原始文本。"""

    @classmethod
    def append(
        cls,
        character: Any,
        texts: str | list[str],
        collection_name: str = ORIGINAL_COLLECTION_NAME,
    ) -> bool:
        """把一条或多条文本写入角色的 original 集合。

        Args:
            character: 角色对象，需要 english_name、name 和 em_llm 属性。
            texts: 单个字符串或字符串列表。
            collection_name: original（默认）或 digest，摘要和原始对话共用追加入口。

        Returns:
            写入成功返回 True；未启用记忆库、集合不存在、向量化失败或
            写入失败时返回 False。所有失败只打印日志，不抛异常。
        """
        try:
            if collection_name not in (ORIGINAL_COLLECTION_NAME, DIGEST_COLLECTION_NAME):
                raise ValueError("仅支持 original 和 digest 集合")
            if getattr(character, "em_llm", None) is None:
                print("[SoulHaven] Chroma 写入跳过：角色未绑定 EmLLM")
                return False

            normalized = cls._normalize_texts(texts)
            if not normalized:
                return False

            with character.operation_lock:
                client_dir = get_chroma_client_dir(character.english_name)
                if not client_dir.is_dir() or not (client_dir / "chroma.sqlite3").is_file():
                    print(
                        "[SoulHaven] Chroma 写入跳过："
                        f"{character.english_name} 没有记忆库目录 {client_dir}"
                    )
                    return False

                import chromadb

                client = chromadb.PersistentClient(path=str(client_dir))
                collection = client.get_collection(collection_name)
                before_count = collection.count()

                # 字符串是完整的一段文档，只生成一个向量；列表则批量处理。
                embedded = character.em_llm.invoke(texts if isinstance(texts, str) else normalized)
                vectors = [embedded] if isinstance(texts, str) else embedded
                if len(vectors) != len(normalized):
                    raise ValueError(
                        "向量数量与文本数量不一致："
                        f"{len(vectors)} != {len(normalized)}"
                    )

                ids = [
                    f"{'d' if collection_name == DIGEST_COLLECTION_NAME else 'o'}{before_count + index}"
                    for index in range(1, len(normalized) + 1)
                ]
                collection.upsert(
                    ids=ids,
                    embeddings=vectors,
                    documents=normalized,
                )

                after_count = collection.count()
                print(
                    f"{character.name}chromadb_client "
                    f"原有{before_count}条数据，"
                    f"现有{after_count}条数据，"
                    f"本次成功插入{len(normalized)}条数据"
                )
                return True
        except Exception as exc:
            print(
                "[SoulHaven] Chroma 写入失败："
                f"{getattr(character, 'english_name', '未知角色')}：{exc}"
            )
            return False

    @staticmethod
    def _normalize_texts(texts: str | list[str]) -> list[str]:
        """把字符串或字符串列表规范化为非空文本列表。"""
        if isinstance(texts, str):
            return [texts] if texts.strip() else []

        if isinstance(texts, list):
            result = []
            for item in texts:
                if not isinstance(item, str):
                    raise TypeError("texts 列表中的每一项都必须是字符串")
                if not item.strip():
                    continue
                result.append(item)
            return result

        raise TypeError("texts 必须是字符串或字符串列表")
