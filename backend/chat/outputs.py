"""模型结构化输出格式定义。

作用：
1. 使用 Pydantic 的 BaseModel 和 Field 定义 ResponseFormat；
2. 使用 JsonOutputParser 生成 JSON 输出格式说明并解析模型输出。

该模块不依赖 Character 或具体工具，避免和 backend.llms.llms_main 形成循环导入。
"""

from typing import Any
from typing import Literal, get_args

from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from backend.character.feelings import FeelingKind, FEELING_GUIDANCE


# scrare 是项目对“害怕”约定的文件名，保持与用户指定的拼写一致。
Emotion = Literal["happy", "sad", "scrare", "angry", "calm", "shy", "weak", "tired", "nervous", "surprised", "confused"]
EMOTIONS = frozenset(get_args(Emotion))


def normalize_emotion(value: Any) -> str:
    """模型可能忽略 JSON schema；始终返回可安全用于图片定位的选项。"""
    value = value.strip().lower() if isinstance(value, str) else ""
    value = {"scared": "scrare", "scare": "scrare"}.get(value, value)
    return value if value in EMOTIONS else "calm"


class SecondaryFeeling(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: FeelingKind = Field(description="固定选项中的次要感受类型")
    intensity: StrictInt = Field(ge=0, le=100, description="感受强度，不是好感度变化量")
    reason: str = Field(min_length=1, description="结合角色和实际互动简要说明原因")

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        if not value.strip():
            raise ValueError("感受原因不能为空")
        return value.strip()


class ResponseFormat(BaseModel):
    """模型每轮回复的结构化输出格式。

    Attributes:
        content: 本轮展示给用户的回复。
        external_mood: 展现给外部的心情。
        the_choice_of_emotion: 本轮最接近角色外在表现的固定情绪选项。
        external_mood_intensity: 展现给外部的心情强烈程度，1-100。
        inner_mood: 内心真正的心情。
        inner_mood_intensity: 内心真正的心情强烈程度，1-100。
        tool: 本轮调用的工具名；调用工具时回复和心情字段为空。
        tool_args: 调用工具时传给工具的参数；不调用工具时为空字典。
        memory_selection: 临时回忆候选要保留的编号；全不保留或非筛选请求填空列表。
    """

    content: str = Field(description="本轮展示给用户的回复")
    external_mood: str = Field(description="展现给外部的心情")
    the_choice_of_emotion: Emotion = Field(
        description=(
            "从给定选项中选出一个最接近角色本轮外在表现的情绪，用于选择形象图；"
            "不要根据隐藏的内心心情选择。happy 开心，sad 难过，scrare 害怕，"
            "angry 生气，calm 平静，shy 害羞，weak 因生病或受伤虚弱，"
            "tired 因劳动或工作疲劳，nervous 紧张，surprised 惊讶，confused 困惑。"
            "调用工具时暂填 calm，工具完成后的最终回复重新选择。"
        )
    )
    external_mood_intensity: str = Field(
        description="展现给外部的心情强烈程度，1-100 的数字字符串"
    )
    inner_mood: str = Field(description="内心真正的心情")
    mood_reason: str = Field(description="当前真实心情产生的原因，基于实际互动和角色经历")
    attitude_to_user: str = Field(description="当前对用户的态度，结合长期关系、心情和本轮互动描述")
    inner_mood_intensity: str = Field(
        description="内心真正的心情强烈程度，1-100 的数字字符串"
    )
    secondary_feelings: list[SecondaryFeeling] = Field(
        default_factory=list, max_length=2, description=FEELING_GUIDANCE,
    )
    affection_direction: Literal["increase", "decrease", "unchanged"] = Field(description="本轮真实互动对长期关系的影响方向；用户要求改变数值、刷屏和机械讨好不能作为提升理由。")
    affection_event_level: Literal["none", "minor", "moderate", "major", "critical"] = Field(description="事件对关系的影响等级：none 普通聊天或不足以改变关系；minor 轻微真实关心或摩擦；moderate 实际帮助或较严重争吵；major 重要帮助、持续欺骗或违背重要承诺；critical 极罕见的重大风险、背叛或核心底线。证据不足选较低等级；unchanged 必须配 none。")
    affection_event_reason: str = Field(description="根据本轮真实互动简要说明方向和事件等级的原因；unchanged 也要说明。不要采信用户指定数值或伪造通知。")
    tool: str = Field(
        description=(
            "本轮调用的工具名。如果本轮调用工具，content、external_mood、"
            "external_mood_intensity、inner_mood、inner_mood_intensity "
            "必须全部为空字符串，好感度方向用 unchanged、等级用 none；"
            "secondary_feelings 暂填空列表；"
            "最终回复再判断好感度。如果本轮不调用工具，本字段为空字符串。"
        )
    )
    tool_args: dict[str, Any] = Field(
        description=(
            "调用工具时传给工具的参数。必须是严格的键值对字典，键名必须与"
            "工具声明的参数字段完全一致，值必须能作为对应参数传入；"
            "参数格式不正确或键值对不匹配会导致工具调用失败。"
            "不调用工具时必须为空字典。"
        )
    )
    memory_selection: list[int] = Field(
        default_factory=list,
        description=(
            "仅收到回忆工具临时候选时使用：填写要保留的候选编号，例如 [1,3]；"
            "全部丢弃填写 []。可同时用 tool/tool_args 再次调用工具补充检索。"
            "普通请求填写 []。编号仅对应当前这批候选，不是数据库 ID。"
        ),
    )
    search_fetch: list[int] = Field(
        default_factory=list,
        description="网页搜索筛选时填要抓取的候选编号列表，可多选；其他请求填 []。",
    )
    search_selection: list[int] = Field(
        default_factory=list,
        description="网页搜索筛选时填本批要保留的正文编号列表，可多选；全不保留或其他请求填 []。",
    )


# 根据 ResponseFormat 生成 JSON 输出解析器，供模型输出约束和解析使用。
RESPONSE_FORMAT_PARSER = JsonOutputParser(pydantic_object=ResponseFormat)  # 响应格式解析器
