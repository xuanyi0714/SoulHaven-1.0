"""记忆库根目录初始化。

目录结构：

    SoulHaven/
    └─ lingqi_database/                        统一数据库根目录
       └─ <英文名>_chromadb_client/      每个角色独立的 Chroma 客户端目录

`lingqi_database` 是项目内的数据根目录，不是 Python 包。当前模块只负责创建
这个根目录；客户端目录和集合的创建由 `chromadb_init.py` 负责。
"""

from pathlib import Path

DATABASE_NAME = "lingqi_database"  # 统一数据库根目录名

# backend/memory/make_database.py -> SoulHaven/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_DIR = PROJECT_ROOT / DATABASE_NAME  # 默认数据库根目录


def init_memory_database(database_dir: str | Path | None = None) -> None:
    """确保记忆库根目录存在，不返回路径或数据库对象。

    Args:
        database_dir: 可选的根目录路径。不传时使用项目根目录下的
            `lingqi_database/`；测试时可以传临时目录。

    Returns:
        None。仅确保目录存在。

    Raises:
        OSError: 目录创建失败。
    """
    root = Path(database_dir) if database_dir is not None else DATABASE_DIR
    root.mkdir(parents=True, exist_ok=True)
