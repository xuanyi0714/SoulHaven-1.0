"""旧版灵栖的好感度事件等级、关系惯性与变化上限。"""

BASE = {"none": 0.0, "minor": 0.5, "moderate": 1.5, "major": 3.0, "critical": 6.0}
FLOOR = {"none": 0.0, "minor": 0.2, "moderate": 0.5, "major": 1.0, "critical": 2.0}
NEGATIVE = {"none": 0.0, "minor": 0.0, "moderate": 0.45, "major": 0.60, "critical": 0.7}


def calculate_affection(old, direction, event):
    """返回新的好感度；最高 100，保留两位小数，不设最低值。"""
    change = 0.0
    if event != "none" and direction == "increase":
        cap = next((cap for threshold, cap in ((90, .2), (85, .5), (80, .8), (75, 1), (70, 1.2), (65, 1.5), (60, 2)) if old >= threshold), 5)
        change = min(BASE[event], max(cap, FLOOR[event]))
    elif event != "none" and direction == "decrease":
        factor = next((factor for threshold, factor in ((90, .25), (80, .45), (70, .65), (60, .8)) if old >= threshold), 1)
        change = -BASE[event] * max(factor, NEGATIVE[event])
    return round(min(100.0, old + change), 2)
