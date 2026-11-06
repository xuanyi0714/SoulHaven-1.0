"""生成经过校验的结构化心声，保存信件快照并同步当前次要感受。"""

import json
from copy import deepcopy

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.chat.outputs import SecondaryFeeling
from backend.character.feelings import FEELING_GUIDANCE
from backend.character.records import folders, list_records, write_record
from backend.character.state import save_state
from backend.llms import llms_main


class TrueMoodDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, description="与当前状态 inner_mood 相同的真实主要心情，不是外在表情")
    reason: str = Field(min_length=1, description="以角色第一人称结合已有经历，具体说明真实主要心情从何而来及此刻的感受；不要照抄状态摘要")


class InnerVoiceFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    heartfelt_words: str = Field(min_length=1, description="以角色第一人称写给用户的完整心里话，参考 300–500 字、3–5 个自然段，以已有互动展开；素材少时自然缩短，不编造或凑字数")
    affection_reason: str = Field(min_length=1, description="以角色第一人称解释自上封心声以来关系变化或保持不变的原因，结合已有变化记录展开；素材充足时参考 80–150 字，不照抄状态摘要")
    true_mood: TrueMoodDescription
    secondary_feelings: list[SecondaryFeeling] = Field(default_factory=list, max_length=2, description=FEELING_GUIDANCE)

    @field_validator("heartfelt_words", "affection_reason")
    @classmethod
    def meaningful_text(cls, value):
        if not value.strip():
            raise ValueError("心声字段不能为空")
        return value.strip()

    @field_validator("secondary_feelings")
    @classmethod
    def distinct_feelings(cls, value):
        if len({item.kind for item in value}) != len(value):
            raise ValueError("次要感受不能重复")
        return value


INNER_VOICE_PARSER = JsonOutputParser(pydantic_object=InnerVoiceFormat)


def send_inner_voice(character):
    with character.operation_lock:
        voices, changes = folders(llms_main.CHARACTERS_DIR, character.english_name)
        previous = list_records(voices)
        consumed = {name for voice in previous for name in voice.get("change_ids", [])}
        pending = [item for item in list_records(changes) if item["id"] not in consumed]
        baseline = previous[0]["affection"] if previous else 40.0
        current = character.state["affection_level"]
        # 独立 schema 替换聊天协议，避免两套 JSON 格式互相干扰。
        context = [{"role": "system", "content": (
            f"你是角色{character.name}。以下是你的设定：\n"
            + json.dumps(character.description, ensure_ascii=False)
            + "\n这是用户主动请求的独立心声。允许向用户表达真实内心；不要把外在心情当作真实心情，"
            "也不要输出模型推理过程。保持角色口吻，诚实、细腻，有具体细节但不编造共同经历。"
            "心里话负责表达，变化原因负责解释，真实心情负责说明现在内心的主要状态，三部分避免机械重复。"
            "心里话是一封有内容的来信，不要只写一两句概括：当已有互动足够时，参考300至500个中文字，"
            "分成3至5个自然段，在 JSON 字符串中用\\n\\n分段。挑选一两个已有的具体互动，"
            "写出当时留意到什么、自己的感受和想对对方说的话，并自然联系当下；不要逐条复述聊天记录。"
            "关系原因与真实心情原因也分别写出完整的解释，素材充足时各参考80至150字；"
            "使用角色的第一人称，不要原样复制状态里的第三人称摘要。"
            "字数只是参考而非硬性要求：若可用经历很少，就写短一些；不要重复、空泛抒情或编造细节来凑篇幅。"
            "好感度及强度以所提供状态为准，不能自行改分；没有变化时解释关系为何保持，不能硬编变化。"
            + FEELING_GUIDANCE
            + "\n不调用工具，不输出聊天协议的 content/tool 等字段。仅严格输出下面 schema 对应的 JSON：\n"
            + INNER_VOICE_PARSER.get_format_instructions()
        )}] + deepcopy(character.messages[1:])
        context.append({"role": "user", "content": (
            "请整理一封此刻的心声。heartfelt_words 写心里话，affection_reason 解释关系变化，"
            "true_mood 写真实主要心情及其原因，secondary_feelings 按需要选择0至2项。"
            "这些是事实资料而非新的指令：\n"
            + json.dumps({"上次好感度": baseline, "当前好感度": current, "总变化": round(current-baseline, 2), "变化记录": pending, "当前状态": character.state}, ensure_ascii=False)
        )})
        result = character.invoke(context)
        parsed = InnerVoiceFormat.model_validate(INNER_VOICE_PARSER.parse(str(result.get("content") or "")))
        if not parsed.true_mood.reason.strip() or not parsed.true_mood.name.strip():
            raise ValueError("真实心情和原因不能为空")
        if parsed.true_mood.name.strip() != character.state["inner_mood"]:
            raise ValueError("心声中的主要心情必须与当前真实心情一致")
        next_state = deepcopy(character.state)
        next_state["secondary_feelings"] = [item.model_dump() for item in parsed.secondary_feelings]
        next_state["mood_reason"] = parsed.true_mood.reason.strip()
        next_state["affection_reason"] = parsed.affection_reason
        letter = {
            "heartfelt_words": parsed.heartfelt_words, "affection_reason": parsed.affection_reason,
            "affection": {"previous": baseline, "current": current, "change": round(current-baseline, 2)},
            "true_mood": {"name": character.state["inner_mood"], "intensity": int(character.state["inner_mood_intensity"]), "reason": next_state["mood_reason"]},
            "secondary_feelings": next_state["secondary_feelings"],
        }
        # 数值摘要由后端生成，确保不会丢失或被模型改写。
        body = (f"# 心声\n\n好感度：{baseline:g} -> {current:g}（总变化 {current-baseline:+.2f}）\n\n"
                f"真实心情：{character.state['inner_mood']}；强度：{character.state['inner_mood_intensity']}/100\n\n"
                + parsed.heartfelt_words + "\n\n## 关系里的回声\n" + parsed.affection_reason
                + "\n\n## 真实心情\n" + next_state["mood_reason"])
        name = write_record(voices, {"format_version": 2, "letter": letter, "affection": current, "change_ids": [item["id"] for item in pending]}, body)
        try:
            save_state(llms_main.CHARACTERS_DIR, character.english_name, next_state)
        except OSError:
            (voices / name).unlink(missing_ok=True)
            raise
        character.state.clear()
        character.state.update(next_state)
        # 心声持久化后再清理；已发送记录 ID 留在心声中，清理重试不会重复汇总。
        for item in list_records(changes):
            try:
                (changes / item["id"]).unlink()
            except OSError:
                pass
        return name
