from typing import Any


# 筛选，服务于图表展示流程。
def select_chart_type(question_type: str, features: dict[str, Any]) -> dict[str, Any]:
    if question_type == "single_choice":
        return {"chart_type": "bar", "orientation": "vertical"}

    if question_type == "multiple_choice":
        return {"chart_type": "bar", "orientation": "horizontal", "sort": "desc"}

    if question_type == "likert":
        return {"chart_type": "bar", "orientation": "vertical"}

    if question_type == "numeric":
        if features.get("outlier", 0) >= 0.08:
            return {"chart_type": "boxplot", "orientation": "vertical", "secondary": "histogram"}
        return {"chart_type": "histogram", "orientation": "vertical"}

    if question_type == "text":
        return {"chart_type": "topic_bundle"}

    return {"chart_type": "table"}


# 获取，服务于图表展示流程。
def get_chart_options(question_type: str) -> list[str]:
    if question_type in {"single_choice", "multiple_choice", "likert"}:
        return ["bar", "pie", "line", "radar", "funnel"]
    if question_type == "numeric":
        return ["histogram", "boxplot", "bar"]
    if question_type == "text":
        return ["pie", "wordcloud"]
    return ["bar"]


# 归一化，服务于图表展示流程。
def normalize_chart_override(question_type: str, override: str | None) -> str | None:
    if not override:
        return None
    normalized = str(override).strip().lower()
    options = get_chart_options(question_type)
    if normalized in options:
        return normalized
    return None
