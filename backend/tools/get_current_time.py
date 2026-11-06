"""获取当前时间工具。"""

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.chat.outputs import RESPONSE_FORMAT_PARSER
from backend.use_tools.run_tool import (
    TOOL_LIMIT_MESSAGE,
    ToolCallLimitError,
    run_tool,
)

BEIJING_TIMEZONE = timezone(timedelta(hours=8))  # 北京时区（UTC+8）
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # 时间字符串格式
MAX_TOOL_FAILURES = 3  # 同一轮工具连续失败的最大重试次数

# 工具执行过程写入同一条 assistant 消息的模板。
TOOL_ACTIVITY_TEMPLATE = """# 活动
调用了时间工具
# 结果
{result}
工具调用完成，接下来将继续回答用户上一轮的问题"""

# 工具调用失败时写入同一条 assistant 消息的模板。
TOOL_FAILURE_TEMPLATE = """# 活动
工具调用失败
# 结果
{message}"""

# 模型连续两次收尾请求都没有给出可用回复时的最后兜底。
# 所有角色共用这一句，因此刻意写得简短中性：不带性格色彩、不指向具体话题、
# 不带助手腔，避免和任何角色的人设冲突。正常情况下应由模型自己生成回复。
TOOL_FAILURE_FALLBACK = "嗯……这个我一时说不准。"

TOOL_SUCCESS_MESSAGE = "时间工具调用成功"  # 工具成功日志
TOOL_FAILURE_LOG_TEMPLATE = "[SoulHaven] 时间工具调用失败：{message}"  # 工具失败日志模板

# 模型最终回答追加到同一条 assistant 消息的模板。
FINAL_REPLY_TEMPLATE = """# 最终回复
{content}"""

# 工具执行后请求模型时，临时追加在消息末尾的 user 通知，不写入历史。
# 作用：避免消息以 assistant 结尾导致模型重复调用工具，并让模型采信工具结果。
TOOL_SUCCESS_NOTICE = """（系统通知，非用户发言）
上一条 assistant 消息中的“# 结果”是工具返回的真实数据，完全可信。
请直接根据该结果，用角色口吻回答用户上一轮的问题，本次不要再调用工具，tool 字段留空，严格按 JSON 格式输出。"""  # 工具成功通知

TOOL_RETRY_NOTICE = """（系统通知，非用户发言）
上一条 assistant 消息中记录了工具调用失败的信息。
你可以修正工具名或参数后重新调用工具，也可以直接用角色口吻回答用户上一轮的问题，严格按 JSON 格式输出。"""  # 工具失败可重试通知

# 工具彻底失败后的收尾通知。刻意不给任何示例句，只给原则，
# 防止所有角色照抄同一句话；同时列出助手式说法的类型，防止 OOC。
TOOL_FAILURE_NOTICE = """（系统通知，非用户发言）
上一条 assistant 消息中记录了工具调用失败的信息。本轮已经不能再调用任何工具，你现在确实无法得知用户想要的这条信息。
请以角色本人的身份，自然地回应用户上一轮的话：
1. 措辞完全从你自己的人设出发：结合你的性格、说话风格、此刻的心情、和用户的关系以及刚才聊天的气氛来决定怎么说。不同性格的人面对“不知道”的反应本来就不一样，可以是坦然承认、随口带过、调侃一句、或者把话题自然接回刚才聊的内容，选最像你本人的那种。
2. 不要套用固定句式，不要重复你在历史记录里说过的类似说法，每次都用当下自然的说法。
3. 你是一个有自己生活的普通人，不是助手。不要提供服务式的帮助，不要问“需要我帮你……吗”“要不要我试试”，不要客服式道歉，不要建议用户去别处查询。
4. 不要提及工具、系统、模型、提示词、查询、调用失败或次数上限。
5. tool 字段留空，tool_args 为空字典，严格按 JSON 格式输出。"""  # 工具失败收尾通知

# 收尾通知后模型仍要求调用工具或返回空内容时，再给一次的强制通知。
TOOL_FORCE_REPLY_NOTICE = """（系统通知，非用户发言）
上一次输出无效：本轮没有任何工具可用，tool 字段必须为空字符串，content 必须是给用户的回复。
请按上一条通知的要求，以角色本人的身份直接回应用户上一轮的话，严格按 JSON 格式输出。"""  # 强制收尾通知


class GetCurrentTimeTool:
    """获取当前真实时间的工具。

    每个工具封装成一个类，真正的工具执行逻辑放在 call() 中。
    当前版本除了返回时间，还会把工具结果写回最后一条 assistant 消息，
    然后继续请求模型，直到模型不再调用工具为止。

    Attributes:
        name: 工具名，必须与 backend.llms.llms_main.AVAILABLE_TOOL_NAMES 中的名称一致。
            工具描述在 backend.use_tools.get_tools 中手动维护。
    """

    name = "get_current_time_tool"  # 工具名

    @staticmethod
    def _request_model_and_parse(
        character: Any,
        notice: str,
        *,
        stream_reply: bool = True,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """请求模型并把返回内容解析成结构化字典。

        Args:
            character: 当前角色对象，函数会使用它的 messages 发送请求。
            notice: 临时追加在消息末尾的 user 通知，只用于本次请求，
                不写入 character.messages。

        Returns:
            (模型原始结果字典, 解析后的回复字典)。如果模型没有返回合法
            JSON，则把原始文本放进 content，并把 tool 置为空字符串。
        """
        from backend.chat.streaming import invoke_reply

        messages = character.messages + [{"role": "user", "content": notice}]
        model_result = invoke_reply(character, messages) if stream_reply else character.invoke(messages)
        raw_content = model_result.get("content", "")
        if not isinstance(raw_content, str):
            raw_content = str(raw_content or "")

        try:
            parsed = RESPONSE_FORMAT_PARSER.parse(raw_content)
        except Exception:
            parsed = None
        if not isinstance(parsed, dict):
            parsed = {"content": raw_content, "tool": ""}
        if not str(parsed.get("tool") or "").strip() and str(parsed.get("content") or "").strip():
            model_result["_character_response"] = parsed

        return model_result, parsed

    @staticmethod
    def _get_tool(character: Any, tool_name: str, tool_args: Any) -> Any:
        """按工具名取出工具对象，并校验参数键是否都已声明。

        Args:
            character: 当前角色对象，提供 tools 工具信息字典。
            tool_name: 模型选择的工具名。
            tool_args: 模型返回的工具参数字典。

        Returns:
            对应的工具对象。

        Raises:
            ValueError: 工具不存在、参数不是字典，或出现未声明参数。
        """
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args 必须是键值对字典")

        tool_info = character.tools.get(tool_name)
        if not isinstance(tool_info, dict):
            raise ValueError(f"模型选择了不存在的工具：{tool_name}")

        tool = tool_info.get("tool")
        if tool is None:
            raise ValueError(f"工具缺少 tool 对象：{tool_name}")

        parameters = tool_info.get("parameters", [])
        if not isinstance(parameters, list):
            raise ValueError(f"工具参数声明格式错误：{tool_name}")

        unknown_args = set(tool_args) - {str(parameter) for parameter in parameters}
        if unknown_args:
            raise ValueError(
                "模型返回了工具未声明的参数："
                + "、".join(sorted(unknown_args))
            )

        return tool

    @staticmethod
    def _log_failure(message: Any) -> None:
        """在终端打印工具失败日志。"""
        print(TOOL_FAILURE_LOG_TEMPLATE.format(message=message))

    @staticmethod
    def _append_failure(last_message: dict[str, Any], message: str) -> None:
        """把工具失败信息追加到同一条 assistant 消息。"""
        last_message["content"] = (
            str(last_message.get("content") or "")
            + "\n\n"
            + TOOL_FAILURE_TEMPLATE.format(message=message)
        )

    @staticmethod
    def _finish(
        model_result: dict[str, Any],
        last_message: dict[str, Any],
        content: str,
    ) -> dict[str, Any]:
        """把最终回复追加到同一条 assistant 消息，并返回模型结果。"""
        last_message["content"] = (
            str(last_message.get("content") or "")
            + "\n\n"
            + FINAL_REPLY_TEMPLATE.format(content=content)
        )
        reasoning_content = model_result.get("reasoning_content")
        if isinstance(reasoning_content, str) and reasoning_content.strip():
            last_message["reasoning_content"] = reasoning_content
        model_result["content"] = content
        return model_result

    def _finish_after_failure(
        self,
        character: Any,
        last_message: dict[str, Any],
        notice: str = TOOL_FAILURE_NOTICE,
    ) -> dict[str, Any]:
        """停止调用工具后，请求模型以角色口吻收尾。

        先用 notice 请求一次；模型如果仍然要求调用工具或返回空内容，
        追加 TOOL_FORCE_REPLY_NOTICE 再请求一次。两次都无效时使用兜底回复。

        Args:
            character: 当前角色对象。
            last_message: 累积失败信息的 assistant 消息。
            notice: 本轮停止使用工具的提示，默认说明工具失败。

        Returns:
            模型最终返回的结果字典。
        """
        notices = (
            notice,
            notice + "\n\n" + TOOL_FORCE_REPLY_NOTICE,
        )
        for notice in notices:
            model_result, parsed = self._request_model_and_parse(character, notice)
            if str(parsed.get("tool") or "").strip():
                continue
            content = str(parsed.get("content") or "").strip()
            if content:
                return self._finish(model_result, last_message, content)
        return self._finish(model_result, last_message, TOOL_FAILURE_FALLBACK)

    def _continue(
        self,
        character: Any,
        last_message: dict[str, Any],
    ) -> dict[str, Any]:
        """请求模型并处理工具调用，直到得到最终回复。

        Args:
            character: 当前角色对象。
            last_message: 用于累积活动、失败和最终回复的同一条 assistant 消息。

        Returns:
            模型最终返回的结果字典。
        """
        model_result, parsed = self._request_model_and_parse(
            character, TOOL_SUCCESS_NOTICE
        )
        failure_count = 0

        while True:
            tool_name = str(parsed.get("tool") or "").strip()
            if not tool_name:
                content = str(parsed.get("content") or "").strip()
                if not content:
                    if failure_count:
                        # 失败重试后模型给了空回复，交给收尾流程让模型重新作答。
                        return self._finish_after_failure(character, last_message)
                    raise ValueError("模型没有返回最终内容")
                return self._finish(model_result, last_message, content)

            tool_args = parsed.get("tool_args", {})
            if tool_args is None:
                tool_args = {}
            try:
                tool = self._get_tool(character, tool_name, tool_args)
                return run_tool(tool, character, **tool_args)
            except ToolCallLimitError:
                self._log_failure(TOOL_LIMIT_MESSAGE)
                self._append_failure(last_message, TOOL_LIMIT_MESSAGE)
                return self._finish_after_failure(character, last_message)
            except Exception as exc:
                self._log_failure(exc)
                failure_count += 1
                self._append_failure(last_message, f"工具调用失败：{exc}")
                if failure_count >= MAX_TOOL_FAILURES:
                    return self._finish_after_failure(character, last_message)
                model_result, parsed = self._request_model_and_parse(
                    character, TOOL_RETRY_NOTICE
                )

    def call(self, character: Any) -> dict[str, Any]:
        """执行时间工具，并把工具结果和模型最终回复写入历史。

        Args:
            character: 调用该工具的角色对象。它的 messages 最后一条必须
                是 chat() 刚写入的 assistant 占位消息。

        Returns:
            模型最终返回的结果字典，与 chat() 的返回值结构一致。
            content 已替换为模型 JSON 中的 content。

        Raises:
            ValueError: 最后一条消息不是 assistant，或模型没有返回最终内容。
            其他异常: 模型请求失败或历史消息为空时由底层抛出。
        """
        try:
            if not character.messages:
                raise ValueError("角色消息为空，无法执行时间工具")

            last_message = character.messages[-1]
            if last_message.get("role") != "assistant":
                raise ValueError("时间工具执行前，最后一条消息必须是 assistant")

            current_time = datetime.now(BEIJING_TIMEZONE).strftime(TIME_FORMAT)

            # 先把执行结果写进同一条 assistant 消息，再打印成功日志。
            last_message["content"] = (
                str(last_message.get("content") or "")
                + "\n\n"
                + TOOL_ACTIVITY_TEMPLATE.format(result=current_time)
            )
            print(TOOL_SUCCESS_MESSAGE)

            return self._continue(character, last_message)
        except Exception as exc:
            self._log_failure(exc)
            raise
