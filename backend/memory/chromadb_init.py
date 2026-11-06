"""角色 ChromaDB 记忆库初始化。

作用：
1. 在统一数据库根目录 lingqi_database 下创建角色专属客户端目录；
2. 使用 chromadb 原生 PersistentClient 建立连接；
3. 创建 digest 和 original 两个记忆集合，并用 metadata 标明用途；
4. 为后续把摘要和原始对话写入向量数据库、实现 RAG 记忆检索做准备。

当前模块只负责初始化数据库和集合，不写入记忆，也不执行向量检索。
"""

from pathlib import Path
from typing import Any

from backend.memory.make_database import DATABASE_DIR, init_memory_database

CLIENT_DIR_SUFFIX = "_chromadb_client"  # 每个角色客户端目录的后缀
DIGEST_COLLECTION_NAME = "digest"  # 摘要记忆集合名
WORLD_COLLECTION_NAME = "world"
ORIGINAL_COLLECTION_NAME = "original"  # 原始记忆集合名

DIGEST_COLLECTION_METADATA = {  # 摘要集合元数据
    "memory_type": "digest",
    "description": "角色历史总结后的摘要记忆，供 RAG 记忆检索使用。",
    "source": "history/digest/digest.md",
}

ORIGINAL_COLLECTION_METADATA = {  # 原始集合元数据
    "memory_type": "original",
    "description": "角色原始对话归档记忆，供 RAG 记忆检索使用。",
    "source": "history/original/original.json",
}


def get_chroma_client_dir(
    client_name: str,
    database_dir: str | Path | None = None,
) -> Path:
    """返回某个角色的 Chroma 客户端目录，不创建目录。

    Args:
        client_name: 角色英文名，例如 ShenZhiyao。
        database_dir: 可选的数据库根目录。

    Returns:
        `lingqi_database/<client_name>_chromadb_client/` 的 Path。

    Raises:
        ValueError: client_name 为空或包含路径分隔符。
    """
    name = str(client_name).strip()
    if not name or name in {".", ".."}:
        raise ValueError("Chroma 客户端名称不能为空")
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Chroma 客户端名称不能包含路径分隔符")

    root = Path(database_dir) if database_dir is not None else DATABASE_DIR
    return root / f"{name}{CLIENT_DIR_SUFFIX}"


def create_chroma_client(
    client_name: str,
    database_dir: str | Path | None = None,
) -> Any:
    """在记忆库根目录下创建或打开一个角色的 Chroma 客户端。

    该函数会创建客户端目录；只应在角色创建阶段调用。后续追加记忆应使用
    “只打开、不创建”的逻辑，避免给未启用记忆库的角色偷偷建库。

    Args:
        client_name: 角色英文名，例如 ShenZhiyao。
        database_dir: 可选的数据库根目录。

    Returns:
        chromadb.PersistentClient 实例。

    Raises:
        RuntimeError: 当前 Python 环境没有安装 chromadb。
        OSError: 客户端目录创建失败。
    """
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError(
            "缺少 chromadb，请先在项目虚拟环境安装 backend/requirements.txt"
        ) from exc

    init_memory_database(database_dir)
    client_dir = get_chroma_client_dir(client_name, database_dir)
    client_dir.mkdir(parents=True, exist_ok=True)

    return chromadb.PersistentClient(path=str(client_dir))


def init_chromadb(character_dir: str | Path) -> dict[str, Any]:
    """初始化一个角色的 ChromaDB 记忆库。

    Args:
        character_dir: 角色文件夹路径，例如 characters/ShenZhiyao。Chroma
            客户端会建立在项目根目录的 `lingqi_database/<英文名>_chromadb_client/`
            下。

    Returns:
        包含 client、digest 集合和 original 集合的字典，方便后续写入和
        检索时复用同一组对象。

    Raises:
        FileNotFoundError: 角色文件夹不存在，或路径不是文件夹。
        RuntimeError: 当前 Python 环境没有安装 chromadb。
        Exception: ChromaDB 创建持久化客户端或集合失败时，原样抛出底层异常。

    Side Effects:
        - 创建 `lingqi_database/<英文名>_chromadb_client/` 目录；
        - 在 ChromaDB 中创建或打开 digest、original 两个集合。
    """
    role_dir = Path(character_dir)
    if not role_dir.is_dir():
        raise FileNotFoundError(f"角色文件夹不存在：{role_dir}")

    client = create_chroma_client(role_dir.name)

    world_collection = client.get_or_create_collection(name=WORLD_COLLECTION_NAME, embedding_function=None)
    digest_collection = client.get_or_create_collection(
        name=DIGEST_COLLECTION_NAME,
        metadata=DIGEST_COLLECTION_METADATA,
    )
    original_collection = client.get_or_create_collection(
        name=ORIGINAL_COLLECTION_NAME,
        metadata=ORIGINAL_COLLECTION_METADATA,
    )

    return {
        "client": client,
        "world": world_collection,
        "digest": digest_collection,
        "original": original_collection,
    }

def init_world_collection(character_dir: str | Path) -> Any:
    """创建角色的 world 集合；用于创建角色或明确执行旧角色兼容迁移。"""
    role_dir = Path(character_dir)
    if not role_dir.is_dir():
        raise FileNotFoundError("角色目录不存在")
    client = create_chroma_client(role_dir.name)
    return client.get_or_create_collection(name=WORLD_COLLECTION_NAME, embedding_function=None)
