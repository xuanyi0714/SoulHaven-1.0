"""一次用户发言的分段回复：临时提示用于调用，真实内容逐段归档。"""

from copy import copy, deepcopy
from datetime import datetime
import random

from langchain_core.prompts import PromptTemplate

from backend.chat.reply_support import (
    BEIJING_TIMEZONE, TIME_SYSTEM_PROMPT_TEMPLATE, USER_MESSAGE_TEMPLATE,
    finish_response, generate_temporary_reply,
)
from backend.chat.streaming import stream_events
from backend.memory.sum_up_history import HistoryMemory


SEGMENT_COUNTS = (1, 2, 3, 4, 5)
SEGMENT_WEIGHTS = (20, 30, 25, 15, 10)

SEGMENT_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """{request_text}

【临时分段回复说明，仅控制本次生成，不是用户的新发言】
你正在回应上方真实用户消息。本次回应共 {total} 轮，当前第 {current}/{total} 轮。
这里的“轮”指你连续发出的一条角色消息；用户在整组完成前不能插话。
每次模型调用只生成当前这一轮的一条消息。不要一次输出全部轮次，不要列出后续回复计划。

写作规则：
1. 结合人设、真实用户原话和已生成的回复，自然推进同一个话题。每条要有实际内容，
   但不要求每条都覆盖全部问题；通常是一小段，长度随内容需要，不靠重复或空话凑轮次。
2. 当前不是最后一轮时：这一条本身应通顺、完整，同时给后续补充、情绪或动作递进留空间。
   避免提前总结全部内容、告别、结束话题，或提出必须等待用户回答才能继续的问题。
   不故意截断句子，不靠省略号吊胃口，不说“下一条告诉你”“请等我继续”。
3. 后续轮次承接前文，补充尚未说过的内容；不要重新打招呼、复述用户问题或重说上一条。
   用户期间没有新回复，不得替用户编造发言、动作、决定或情绪反应，也不要推进需要用户同意的情节。
4. 当前是最后一轮时：补完有必要的内容，给这次回应一个自然落点；可以留给用户接话，
   不必强行总结、道别。如果总共只有一轮，就在这一条中正常完成回应。
5. 不向用户提及本说明、分段机制、轮次编号、模型调用或示例。保持原有 JSON 输出协议，
   当前这一条角色消息放在 content 中；工具调用和状态字段仍遵循原有规则。

以下示例只示范连续消息的节奏，绝不能照搬措辞、人设或示例中的用户处境。
示例一：用户说“今天好累”，总共三轮。
  第1/3轮：“先坐一会儿吧。”她把旁边的位置让出来，声音放轻了些。
  第2/3轮：“今天撑了那么久，眼下就不用再逼自己打起精神了。”她把水杯推近。
  第3/3轮：“想说的时候，我就在这儿听；现在只想歇一会儿，也可以。”
  节奏说明：先回应疲惫，再补充关心，最后留出回应空间；没有假设用户已经坐下或喝水。
示例二：用户问“明天下雨，散步怎么办”，总共两轮。
  第1/2轮：“可以把路线换到有长廊的公园，先保留一起出门走走的打算。”
  第2/2轮：“要是雨势太大，就改去室内逛逛。临出门再看看天气，舒服些最要紧。”
  节奏说明：先给主要方案，再补充备用方案；不是把完整答案重复两次。
示例三：用户说“晚安”，总共一轮。
  第1/1轮：“晚安，今晚睡个踏实觉。”
  节奏说明：一轮时直接完成回应，不凭空制造后续内容。

本次实际进度：第 {current}/{total} 轮。{stage_instruction}
只生成当前这一条角色回复。
"""
)


def choose_segment_count():
    """每次真实用户发送只抽一次：1至5轮分别为20/30/25/15/10%。"""
    return random.choices(SEGMENT_COUNTS, weights=SEGMENT_WEIGHTS, k=1)[0]


def chat_segmented(character, user_message, recognition_time, deep_thinking):
    """在同一角色锁内完成整组；每段归档成功才发送 segment_done。"""
    with character.operation_lock:
        total = choose_segment_count()
        working = copy(character)
        working.messages = deepcopy(character.messages)
        working.state = deepcopy(character.state)
        working._deep_thinking = deep_thinking
        stored_user = user_message
        if recognition_time:
            now = datetime.now(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
            working.messages[0]["content"] = TIME_SYSTEM_PROMPT_TEMPLATE.format(
                base_system_prompt=working.messages[0].get("content", ""), beijing_time=now,
            )
            stored_user = USER_MESSAGE_TEMPLATE.format(beijing_time=now, user_message=user_message)

        emit = stream_events.get()
        segments = []
        for current in range(1, total + 1):
            if emit:
                emit("segment_start", {"current": current, "total": total})
            request_text = user_message if current == 1 else "请继续回答刚刚的用户消息，承接你已经说过的内容。"
            notice = SEGMENT_PROMPT_TEMPLATE.format(
                request_text=request_text, current=current, total=total,
                stage_instruction=("这是最后一轮，请自然完成本次回应。" if current == total
                                   else "后面仍有轮次，请留下自然补充的空间。"),
            )
            working.messages.append({"role": "user", "content": notice})
            working.state = deepcopy(character.state)
            # 一次性模型也使用事件传输逐段结果，但不改成流式模型调用。
            token = stream_events.set(None) if emit and not character.stream_output else None
            try:
                result, stored, parsed = generate_temporary_reply(working)
            finally:
                if token is not None:
                    stream_events.reset(token)

            committed = ([{"role": "user", "content": stored_user}, stored]
                         if current == 1 else [stored])
            HistoryMemory._append_original_messages(character, committed)
            character.messages.extend(deepcopy(committed))
            # 同一次真实用户输入只允许首段影响好感度，后续段沿用继续说的边界。
            finish_response(character, result, parsed, allow_affection=current == 1)
            if character.em_llm is not None:
                from backend.memory.add_in_chromadb import ChromadbAppend
                try:
                    ChromadbAppend.append(character, HistoryMemory._format_messages(committed))
                except Exception as exc:
                    print(f"[SoulHaven] 分段回复向量写入失败，原始历史已保留：{exc}")
            segment = {
                "current": current, "total": total, "content": result["content"],
                "reasoning_content": result.get("reasoning_content", ""),
                "the_choice_of_emotion": result["the_choice_of_emotion"],
            }
            segments.append(segment)
            if emit:
                emit("segment_done", segment)
        return {**result, "segments": segments}
