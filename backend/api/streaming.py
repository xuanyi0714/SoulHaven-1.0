"""普通聊天、继续说与分段回复的逐行 JSON HTTP 接口。"""

import json
from queue import Empty, Full, Queue
from threading import Event, Thread

from flask import Response, request

from backend.chat.outputs import normalize_emotion
from backend.chat.run import chat_stream


def stream_response(character, message, recognition, thinking, segmented_reply=None):
    """工作线程持有角色锁，响应线程持续发送逐行 JSON。"""
    events = Queue(maxsize=128)
    disconnected = Event()

    def enqueue(event):
        while not disconnected.is_set():
            try:
                events.put(event, timeout=0.2)
                return
            except Full:
                continue
        raise ConnectionAbortedError("流式连接已关闭")

    def emit(kind, text):
        if disconnected.is_set():
            raise ConnectionAbortedError("流式连接已关闭")
        if kind in ("segment_start", "segment_done"):
            enqueue({"type": kind, **text})
        elif text or kind == "start":
            enqueue({"type": kind, "text": text})

    def run():
        try:
            result = chat_stream(character, message, recognition, thinking, emit, segmented_reply)
            event = {
                "type": "done",
                "content": result.get("content", ""),
                "reasoning_content": result.get("reasoning_content", ""),
                "the_choice_of_emotion": normalize_emotion(result.get("the_choice_of_emotion")),
            }
        except ConnectionAbortedError:
            if disconnected.is_set():
                return
            event = {"type": "error", "error": "模型连接中断，请重试"}
        except OSError:
            event = {"type": "error", "error": "流式请求或历史归档失败，请重试"}
        except Exception:
            event = {"type": "error", "error": "角色回复失败，请检查模型配置或稍后重试"}
        try:
            enqueue(event)
        except ConnectionAbortedError:
            return

    def generate():
        Thread(target=run, daemon=True).start()
        try:
            while True:
                try:
                    event = events.get(timeout=10)
                except Empty:
                    yield "\n"
                    continue
                yield json.dumps(event) + "\n"
                if event["type"] in ("done", "error"):
                    return
        finally:
            disconnected.set()

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def register_streaming_routes(api, characters, json_error):
    def handle(english_name, data, message):
        recognition = data.get("recognition_time", True)
        thinking = data.get("deep_thinking", True)
        segmented = data.get("segmented_reply")
        if "segmented_reply" in data and not isinstance(segmented, bool):
            return json_error("segmented_reply 必须是布尔值", 400)
        if not isinstance(recognition, bool) or not isinstance(thinking, bool):
            return json_error("对话开关必须是布尔值", 400)
        character = characters.get(english_name)
        if character is None:
            return json_error("角色不存在", 404)
        if character.llm is None:
            return json_error("该角色尚未配置模型", 400)
        effective_segmented = character.segmented_reply if segmented is None else segmented
        if not character.stream_output and not (message is not None and effective_segmented):
            return json_error("该角色未开启流式输出", 400)
        return stream_response(character, message, recognition, thinking, effective_segmented)

    @api.post("/chat/stream")
    def stream_chat():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("请求体必须是 JSON 对象", 400)
        english_name = str(data.get("english_name") or "").strip()
        message = data.get("message")
        if not english_name:
            return json_error("角色英文名不能为空", 400)
        if not isinstance(message, str) or not message.strip():
            return json_error("message 不能为空", 400)
        return handle(english_name, data, message)

    @api.post("/characters/<english_name>/continue/stream")
    def stream_continue(english_name):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return json_error("请求体必须是 JSON 对象", 400)
        return handle(english_name, data, None)
