"""原始对话回忆工具，摘要优先约束由 run_memory_tool 统一处理。"""

from typing import Any

from backend.memory.recall import query_memory


class RecallOriginalTool:
    name = "recall_original"

    def call(self, character: Any, question: str) -> dict[str, Any]:
        return query_memory(character, question, "original")
