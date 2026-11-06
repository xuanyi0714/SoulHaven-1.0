"""次要感受的固定选项，模型可以选零至两项，不允许自行创造类型。"""

from typing import Literal

FeelingKind = Literal[
    "shame", "possession", "fear", "anticipation", "dependence", "trust",
    "loneliness", "insecurity", "gratitude", "jealousy", "curiosity", "relief",
]
FEELING_LABELS = {
    "shame": "羞耻感", "possession": "占有欲", "fear": "恐惧值", "anticipation": "期待感",
    "dependence": "依赖度", "trust": "信任感", "loneliness": "孤独感", "insecurity": "不安感",
    "gratitude": "感激感", "jealousy": "醋意", "curiosity": "好奇心", "relief": "安心感",
}
FEELING_GUIDANCE = (
    "次要感受只可从以下固定类型选择：" + "、".join(f"{key}（{label}）" for key, label in FEELING_LABELS.items())
    + "。它们是主要真实心情之外的补充感受，不是必须凑齐的任务。"
    "按角色人设和真实互动选择零至两项；一种主要心情已足够时填 []，只需一项就选一项。"
    "不要随机选，不要总选相同类型，不要重复同类，不要为制造戏剧性夸大占有欲、依赖或恐惧。"
    "每项提供 kind、0至100的整数 intensity，以及基于真实上下文的简短 reason。"
)


def normalize_secondary_feelings(value):
    """容错读取旧状态和普通模型输出；None 表示无效，[] 表示明确没有补充感受。"""
    if not isinstance(value, list):
        return None
    result, seen = [], set()
    for item in value:
        if not isinstance(item, dict):
            continue
        kind, intensity = item.get("kind"), item.get("intensity")
        reason = item.get("reason")
        if (not isinstance(kind, str) or kind not in FEELING_LABELS or kind in seen
                or type(intensity) is not int or not 0 <= intensity <= 100
                or not isinstance(reason, str) or not reason.strip()):
            continue
        result.append({"kind": kind, "intensity": intensity, "reason": reason.strip()})
        seen.add(kind)
        if len(result) == 2:
            break
    return result if result or not value else None
