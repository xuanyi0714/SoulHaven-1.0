"""按问题查询角色所绑定的世界观详细资料。"""
from typing import Any
from backend.memory.world import query_world


class RecallWorldTool:
    name = "recall_world"

    def call(self, character: Any, question: str) -> dict:
        return query_world(character, question)
