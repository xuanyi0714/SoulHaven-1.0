"""普通聊天、继续说与分段回复共用的提示、临时调用和状态提交。"""

from copy import deepcopy
from datetime import timedelta, timezone

from langchain_core.prompts import PromptTemplate

from backend.chat.outputs import RESPONSE_FORMAT_PARSER, normalize_emotion
from backend.chat.streaming import invoke_reply
from backend.character.state import update_state, save_state
from backend.llms.llms_main import CHARACTERS_DIR
from backend.use_tools.run_tool import run_tool


# 北京时间时区，用于给每轮请求提供真实当前时间。
BEIJING_TIMEZONE = timezone(timedelta(hours=8))  # 北京时区

# 临时系统提示词模板：在原始系统提示词后追加当前真实北京时间。
# 参数：base_system_prompt（原始系统提示词）、beijing_time（当前北京时间）。
TIME_SYSTEM_PROMPT_TEMPLATE = PromptTemplate.from_template(  # 带时间的系统提示词模板
    """{base_system_prompt}

当前真实北京时间：{beijing_time}
本次请求以该时间作为唯一真实时间，不要被历史记录或用户消息中的时间误导。"""
)

# 永久 user 消息模板：在用户原话前写入发送时间。
# 参数：beijing_time（发送时间）、user_message（用户原话）。
USER_MESSAGE_TEMPLATE = PromptTemplate.from_template(  # 用户消息模板
    """***该信息发送时间：{beijing_time}***
{user_message}"""
)


def _commit_state(character, parsed, allow_affection=True):
    if not isinstance(parsed, dict) or not isinstance(getattr(character, "state", None), dict):
        return
    old = character.state["affection_level"]
    next_state = deepcopy(character.state)
    update_state(next_state, parsed, allow_affection=allow_affection)
    try:
        save_state(CHARACTERS_DIR, character.english_name, next_state)
        character.state.clear()
        character.state.update(next_state)
        from backend.character.records import record_affection
        if (CHARACTERS_DIR / character.english_name).is_dir():
            record_affection(CHARACTERS_DIR, character, old, parsed.get("affection_event_reason"))
    except OSError as exc:
        print(f"[SoulHaven] 角色状态保存失败：{exc}")


def finish_response(character, result, parsed, allow_affection=True):
    """成功归档后提交最终情绪；缺失或无效时回退 calm。"""
    response = dict(parsed) if isinstance(parsed, dict) else {}
    emotion = normalize_emotion(response.get("the_choice_of_emotion"))
    response["the_choice_of_emotion"] = emotion
    result["the_choice_of_emotion"] = emotion
    _commit_state(character, response, allow_affection=allow_affection)


def generate_temporary_reply(working):
    """在角色副本中调用模型和工具，返回待归档的回复，不保存临时 user。"""
    result = invoke_reply(working, working.messages)
    raw = str(result.get("content") or "")
    try:
        parsed = RESPONSE_FORMAT_PARSER.parse(raw)
    except Exception:
        parsed = None
    if isinstance(parsed, dict) and str(parsed.get("tool") or "").strip():
        tool_name = str(parsed["tool"]).strip()
        tool_info = working.tools.get(tool_name)
        if not isinstance(tool_info, dict) or tool_info.get("tool") is None:
            raise ValueError("模型选择了不存在的工具")
        args = parsed.get("tool_args", {})
        if args is None:
            args = {}
        parameters = tool_info.get("parameters", [])
        if not isinstance(args, dict) or not isinstance(parameters, list) or set(args) - set(parameters):
            raise ValueError("模型返回的工具参数无效")
        working.messages.append({"role": "assistant", "content": "本轮需要调用工具"})
        result = run_tool(tool_info["tool"], working, **args)
        parsed = result.pop("_character_response", None)
        stored = deepcopy(working.messages[-1])
        working.messages[-1] = stored
    else:
        result["content"] = str(parsed.get("content") or "") if isinstance(parsed, dict) else raw
        stored = {"role": "assistant", "content": result["content"], "reasoning_content": result.get("reasoning_content", "")}
    if not str(result.get("content") or "").strip() or stored.get("role") != "assistant":
        raise ValueError("模型没有返回内容")
    if working.messages[-1] is not stored:
        working.messages.append(stored)
    return result, stored, parsed
