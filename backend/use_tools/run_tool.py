"""工具执行入口。"""

from dataclasses import dataclass
from typing import Any

from backend.tools.web_search import WebSearchTool
from backend.use_tools.run_memory_tool import MEMORY_TOOL_NAMES, run_memory_tool
from backend.use_tools.run_search_tool import run_search_tool

MAX_TOOL_CALLS = 15
MAX_SEARCH_CALLS = 5
TOOL_LIMIT_MESSAGE = "本轮调用失败，工具使用次数已达上限，本次无法再调用工具"  # 工具上限提示


class ToolCallLimitError(ValueError):
    """本轮工具调用次数达到上限。"""


@dataclass
class ToolCallBudget:
    remaining_calls: int = MAX_TOOL_CALLS
    remaining_searches: int = MAX_SEARCH_CALLS


def run_tool(tool: Any, character: Any, **kwargs: Any) -> Any:
    """执行一个工具对象，并返回工具的最终结果。

    Args:
        tool: 具有 call 方法的工具对象。
        character: 调用工具的角色对象，会作为 call 的第一个参数传入。
        **kwargs: 传给工具 call 方法的关键字参数。没有额外参数时调用
            tool.call(character)；有关键字参数时调用
            tool.call(character, **kwargs)。

    Returns:
        普通工具直接执行，回忆和搜索工具进入各自的筛选流程。

    Raises:
        AttributeError: 传入的对象没有 call 方法。
        ToolCallLimitError: 本轮工具调用达到 MAX_TOOL_CALLS。
    """
    is_first_call = not hasattr(character, "_tool_budget")
    if is_first_call:
        character._tool_budget = ToolCallBudget()
        character._memory_tool_state = {"digest_attempted": False, "blocked": False}
    try:
        budget = character._tool_budget
        if budget.remaining_calls <= 0:
            raise ToolCallLimitError(TOOL_LIMIT_MESSAGE)
        if getattr(tool, "name", "") == WebSearchTool.name:
            return run_search_tool(tool, character, **kwargs)
        budget.remaining_calls -= 1
        if getattr(tool, "name", "") in MEMORY_TOOL_NAMES:
            return run_memory_tool(tool, character, **kwargs)
        if kwargs:
            return tool.call(character, **kwargs)
        return tool.call(character)
    finally:
        if is_first_call:
            del character._tool_budget
            del character._memory_tool_state
