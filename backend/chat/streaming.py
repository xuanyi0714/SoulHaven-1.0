"""在当前聊天轮次中转发思考和可展示的正文。"""

import json
import re
from collections.abc import Callable
from contextvars import ContextVar


stream_events: ContextVar[Callable[[str, str | dict[str, object]], None] | None] = ContextVar(
    "stream_events", default=None
)

# 先确认模型决定直接回复，再读取顶层 content。其他 JSON 字段始终留在后端。
_REPLY_START = re.compile(r'\s*(?:\x60{3}(?:json)?\s*)?\{\s*"tool"\s*:\s*""\s*,\s*"content"\s*:\s*"')
_STRING_PART = re.compile(
    r'(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]'
    r'|u(?![dD][89a-fA-F])[0-9a-fA-F]{4}'
    r'|u[dD][89aAbB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}))+'
)


class ReplyFragments:
    """只发送已接收完整的字符，支持跨分片的引号和 Unicode 转义。"""

    def __init__(self):
        self.buffer = ""
        self.reading = False
        self.finished = False

    def feed(self, text: str) -> str:
        if self.finished:
            return ""
        self.buffer += text
        if not self.reading:
            start = _REPLY_START.match(self.buffer)
            if start is None:
                return ""
            self.buffer = self.buffer[start.end():]
            self.reading = True

        match = _STRING_PART.match(self.buffer)
        decoded = ""
        if match:
            decoded = json.loads('"' + match[0] + '"')
            self.buffer = self.buffer[match.end():]
        if self.buffer.startswith('"'):
            self.finished = True
            self.buffer = ""
        return decoded


def invoke_reply(character, messages):
    """让普通聊天和工具后的回复复用各自原有的完整结果处理。"""
    emit = stream_events.get()
    if emit is None:
        return character.invoke(messages)

    fragments = ReplyFragments()
    emit("start", "")

    def publish(kind: str, text: str) -> None:
        if kind == "content":
            text = fragments.feed(text)
        # 即使没有可见正文，也给传输层机会检查连接是否已经关闭。
        emit(kind, text)

    result = character.invoke_stream(messages, publish)
    emit("check", "")
    return result
