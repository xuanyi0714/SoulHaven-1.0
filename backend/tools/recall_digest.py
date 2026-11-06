"""摘要回忆工具，后续模型筛选由 run_memory_tool 统一处理。"""

from typing import Any

from backend.memory.recall import query_memory


class RecallDigestTool:
    name = "recall_digest"

    def call(self, character: Any, question: str) -> dict[str, Any]:
        return query_memory(character, question, "digest")
