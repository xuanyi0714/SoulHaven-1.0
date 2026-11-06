"""角色对话的记忆、时间与深度思考处理。

作用：
1. 接收 Character 对象和用户消息；
2. 复制历史消息，仅在本轮请求中把当前北京时间合并进系统提示词；
3. 达到阈值时先调用 HistoryMemory.sum_up_history() 压缩旧历史；
4. 把本轮深度思考开关写入角色，调用 Character.invoke() 发送请求；
5. 请求成功后，把带发送时间的用户消息和 assistant 回复写入角色历史；
6. 本轮成功后立即把最后两条 user + assistant 追加到 original 归档。
7. continue_say 使用临时用户提示继续接话，成功后只归档 assistant。
8. 开启分段回复时分发到 segmented_reply.py，整组只保存一次真实用户输入。

临时系统时间不会写入 character.messages，角色历史中的下标 0 始终是原始系统提示词。
"""

from datetime import datetime
from typing import Any

from backend.chat.outputs import RESPONSE_FORMAT_PARSER
from backend.chat.streaming import invoke_reply, stream_events
from backend.chat.reply_support import (
    BEIJING_TIMEZONE, TIME_SYSTEM_PROMPT_TEMPLATE, USER_MESSAGE_TEMPLATE,
    finish_response, generate_temporary_reply,
)
from backend.llms.llms_main import Character
from backend.memory.sum_up_history import HistoryMemory
from backend.use_tools.run_tool import run_tool

# 自动压缩阈值：约 200 轮对话后再总结（每轮 user + assistant 两条），
# 减少频繁压缩导致的缓存失效和 token 消耗。
AUTO_SUMMARY_THRESHOLD = 400  # 自动总结消息数阈值（200 轮 × 2 条）


def chat(
    character: Character,
    user_message: str,
    recognition_time: bool = True,
    deep_thinking: bool = True,
    segmented_reply: bool | None = None,
) -> dict[str, Any]:
    """发送一条用户消息给角色，并在成功后维护角色历史。

    Args:
        character: 要对话的 Character 对象。它的 messages[0] 必须是
            system 消息；messages[1] 通常是开场白 assistant 消息。
        user_message: 用户本轮输入的原始文本，必须是非空字符串。
        segmented_reply: 是否分段回复；None 时沿用角色 output.segmented 配置。
        recognition_time: 是否在系统提示词中加入当前北京时间，并在
            永久 user 消息前记录发送时间。默认 True。
        deep_thinking: 是否开启深度思考。开启后会临时在系统提示词中
            追加深入的思考要求，并让支持该开关的模型启用思考模式；
            关闭时只发送普通请求。默认 True。

    Returns:
        Character.invoke() 的结果字典，包含 content、reasoning_content
        和 usage。content 已从模型 JSON 中提取。如果本轮调用了工具，
        则直接返回 run_tool() 的结果，由工具负责生成最终 content。
        reasoning_content 会随结果返回，由前端折叠显示。
        分段模式另含 segments 数组，逐段归档；后续失败保留已完成段。

    Raises:
        ValueError: user_message 为空、recognition_time 或 deep_thinking
            不是布尔值、角色的 messages 缺少下标 0 的 system 消息、
            模型返回空内容，或模型选择了 character.tools 中不存在的工具。
        OSError: 自动总结或本轮原始归档写入历史文件失败。

    Side Effects:
        当 character.messages 达到 AUTO_SUMMARY_THRESHOLD 时，会先调用
        HistoryMemory.sum_up_history() 压缩旧历史，再发送本轮消息。发送前
        会临时写入本轮 user；请求失败、未处理的工具异常或模型返回空内容
        时会回滚该 user。模型返回非空 tool 字段时，会先写入一条 assistant
        占位消息，再调用 run_tool() 并直接返回其结果；工具负责把执行过程
        和最终回复继续追加到这条 assistant 消息中。工具次数耗尽时由工具
        把失败信息交给模型，不直接向用户抛出错误。普通回复和工具回复都
        成功后，会把本轮最后两条写入 original.md / original.json；归档失败
        会回滚本轮消息并抛出异常。deep_thinking 会写入
        character._deep_thinking，供本轮工具继续请求模型时沿用。
    """
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("用户消息不能为空")
    if not isinstance(recognition_time, bool):
        raise ValueError("recognition_time 必须是布尔值")
    if not isinstance(deep_thinking, bool):
        raise ValueError("deep_thinking 必须是布尔值")
    if not character.messages or character.messages[0].get("role") != "system":
        raise ValueError("角色 messages 缺少位于下标 0 的系统提示词")

    if segmented_reply is None:
        segmented_reply = getattr(character, "segmented_reply", False)
    if not isinstance(segmented_reply, bool):
        raise ValueError("segmented_reply 必须是布尔值")

    # 记录本轮开关，工具内部继续调用 character.invoke() 时会沿用。
    character._deep_thinking = deep_thinking

    # 达到阈值时先压缩旧历史，再把本轮新消息加入临时请求。
    if len(character.messages) >= AUTO_SUMMARY_THRESHOLD:  # 自动总结消息数阈值
        HistoryMemory.sum_up_history(character.messages, character)

    if segmented_reply:
        from backend.chat.segmented_reply import chat_segmented
        return chat_segmented(character, user_message, recognition_time, deep_thinking)

    # 复制历史，临时系统提示词不会写进原列表；本轮 user 在请求前后单独处理。
    temporary_messages = list(character.messages)

    beijing_time = None
    if recognition_time:
        beijing_time = datetime.now(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")  # 北京时区
        base_system_prompt = character.messages[0].get("content", "")
        temporary_system_prompt = TIME_SYSTEM_PROMPT_TEMPLATE.format(  # 带时间的系统提示词模板
            base_system_prompt=base_system_prompt,
            beijing_time=beijing_time,
        )
        # 只替换复制列表中的系统提示词，原 character.messages[0] 保持不变。
        temporary_messages[0] = {
            "role": "system",
            "content": temporary_system_prompt,
        }

    # 当前用户消息使用原话发送；时间由临时系统提示词提供。
    temporary_messages.append({"role": "user", "content": user_message})

    if beijing_time is not None:
        stored_user_message = USER_MESSAGE_TEMPLATE.format(  # 用户消息模板
            beijing_time=beijing_time,
            user_message=user_message,
        )
    else:
        stored_user_message = user_message

    # 先把本轮 user 写入历史，模型失败时再回滚这一条，避免留下无回复消息。
    character.messages.append({"role": "user", "content": stored_user_message})

    placeholder = None
    try:
        result = invoke_reply(character, temporary_messages)

        raw_content = result.get("content", "")
        if not isinstance(raw_content, str):
            raw_content = str(raw_content or "")

        # 模型按约定返回 JSON；解析失败时退回原始文本，避免旧模型或异常
        # 输出直接导致整轮对话失败。
        try:
            parsed = RESPONSE_FORMAT_PARSER.parse(raw_content)
        except Exception:
            parsed = None

        if isinstance(parsed, dict):
            content = str(parsed.get("content") or "")
            tool_name = str(parsed.get("tool") or "").strip()
            if tool_name:
                tool_info = character.tools.get(tool_name)
                if not isinstance(tool_info, dict):
                    raise ValueError(f"模型选择了不存在的工具：{tool_name}")

                tool = tool_info.get("tool")
                if tool is None:
                    raise ValueError(f"工具缺少 tool 对象：{tool_name}")

                tool_args = parsed.get("tool_args", {})
                if tool_args is None:
                    tool_args = {}
                if not isinstance(tool_args, dict):
                    raise ValueError("模型返回的 tool_args 必须是键值对字典")

                parameters = tool_info.get("parameters", [])
                if not isinstance(parameters, list):
                    raise ValueError(f"工具参数声明格式错误：{tool_name}")

                unknown_args = set(tool_args) - {
                    str(parameter) for parameter in parameters
                }
                if unknown_args:
                    raise ValueError(
                        "模型返回了工具未声明的参数："
                        + "、".join(sorted(unknown_args))
                    )

                # 工具需要在同一条 assistant 消息中记录执行过程，因此先写入
                # 占位消息；工具执行完成后会继续修改这条消息。
                placeholder = {
                    "role": "assistant",
                    "content": "本轮无法直接回答，需要调用工具",
                }
                character.messages.append(placeholder)
                result = run_tool(tool, character, **tool_args)
                # 工具调用成功时也会修改占位 assistant，最后两条仍是一轮
                # 完整的 user + assistant；在这里补一次原始归档。
                HistoryMemory.archive_latest_round(character)
                finish_response(character, result, result.pop("_character_response", None))
                return result

            result["content"] = content
        else:
            content = raw_content
    except Exception:
        if placeholder is not None:
            for index in range(len(character.messages) - 1, -1, -1):
                if character.messages[index] is placeholder:
                    del character.messages[index]
                    break

        if (
            character.messages
            and character.messages[-1].get("role") == "user"
            and character.messages[-1].get("content") == stored_user_message
        ):
            character.messages.pop()
        raise

    if not isinstance(content, str) or not content.strip():
        character.messages.pop()
        raise ValueError("模型没有返回内容")

    character.messages.append(
        {
            "role": "assistant",
            "content": content,
            "reasoning_content": result.get("reasoning_content", ""),
        }
    )

    try:
        # 模型成功回复后才归档本轮，失败时不留下半轮记录。
        HistoryMemory.archive_latest_round(character)
    except Exception:
        character.messages.pop()  # 回滚本轮 assistant
        character.messages.pop()  # 回滚本轮 user
        raise

    finish_response(character, result, parsed)
    return result


def continue_say(
    character: Character,
    recognition_time: bool = True,
    deep_thinking: bool = True,
) -> dict[str, Any]:
    """用临时消息续说，只归档助手回复，不保存临时用户提示。

    已有消息末尾连续超过三条 assistant 时，提醒角色温和询问用户。
    工具执行也使用副本；文件归档成功后才提交真实内存中的回复。
    """
    from copy import copy, deepcopy
    if not isinstance(recognition_time, bool) or not isinstance(deep_thinking, bool):
        raise ValueError("recognition_time 和 deep_thinking 必须是布尔值")
    with character.operation_lock:
        if not character.messages or character.messages[0].get("role") != "system":
            raise ValueError("角色缺少系统提示词")
        consecutive = 0
        for message in reversed(character.messages):
            if message.get("role") != "assistant":
                break
            consecutive += 1
        if len(character.messages) >= AUTO_SUMMARY_THRESHOLD:
            HistoryMemory.sum_up_history(character.messages, character)
        character._deep_thinking = deep_thinking
        working = copy(character)
        working.messages = deepcopy(character.messages)
        working.state = deepcopy(character.state)
        if recognition_time:
            working.messages[0]["content"] = TIME_SYSTEM_PROMPT_TEMPLATE.format(
                base_system_prompt=working.messages[0].get("content", ""),
                beijing_time=datetime.now(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
            )
        notice = (
            "本轮用户没有输入新的消息，只希望你继续接话。请承接刚才的话题，"
            "自然补充一小段，避免重复已经说过的内容；不要替用户编造发言、行动或回应，"
            "也不要提到本提示、按钮或系统操作。保持角色原本的身份和语气。"
        )
        if consecutive > 3:
            notice += (
                f"你已经连续发送了{consecutive}条消息，用户一直没有反应。"
                "请注意给对方留出回应空间，用符合人设的温和方式轻轻点一下对方，"
                "例如确认对方还在不在、是否想换个话题；不要指责、催促或擅自猜测对方的想法。"
            )
        working.messages.append({"role": "user", "content": notice})
        result, stored, parsed = generate_temporary_reply(working)
        # The temporary user and tool context stay on the copied character only.
        HistoryMemory._append_original_messages(character, [stored])
        character.messages.append(stored)
        finish_response(character, result, parsed, allow_affection=False)
        if character.em_llm is not None:
            from backend.memory.add_in_chromadb import ChromadbAppend
            try:
                ChromadbAppend.append(character, HistoryMemory._format_messages([stored]))
            except Exception as exc:
                print(f"[SoulHaven] 续说向量写入失败，原始历史已保留：{exc}")
        return result


def chat_stream(character, message, recognition_time, deep_thinking, emit, segmented_reply=None):
    """绑定聊天事件；普通/继续说传输分片，分段还传输逐段完成事件。"""
    with character.operation_lock:
        emit("check", "")
        token = stream_events.set(emit)
        try:
            if message is None:
                return continue_say(character, recognition_time, deep_thinking)
            return chat(character, message, recognition_time, deep_thinking, segmented_reply)
        finally:
            stream_events.reset(token)
