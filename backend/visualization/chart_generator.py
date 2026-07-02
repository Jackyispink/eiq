from typing import Any

from backend.visualization.chart_selector import normalize_chart_override, select_chart_type


# 生成图表，服务于图表展示流程。
def _resolve_chart_for_objective(
    question_type: str,
    features: dict[str, Any],
    override: str | None,
) -> dict[str, Any]:
    normalized_override = normalize_chart_override(question_type, override)
    if not normalized_override:
        return select_chart_type(question_type, features)

    if question_type in {"single_choice", "multiple_choice", "likert"}:
        if normalized_override == "pie":
            return {"chart_type": "pie"}
        if question_type == "multiple_choice":
            return {"chart_type": "bar", "orientation": "horizontal", "sort": "desc"}
        return {"chart_type": "bar", "orientation": "vertical"}

    if question_type == "numeric":
        if normalized_override == "boxplot":
            return {"chart_type": "boxplot", "orientation": "vertical"}
        if normalized_override == "bar":
            return {"chart_type": "bar", "orientation": "vertical"}
        return {"chart_type": "histogram", "orientation": "vertical"}

    return select_chart_type(question_type, features)


# 生成，服务于图表展示流程。
def _generate_choice_chart(
    question_id: str,
    question_text: str,
    question_type: str,
    features: dict[str, Any],
    chart_override: str | None = None,
) -> dict[str, Any]:
    distribution = features.get("distribution", {})
    pairs = sorted(distribution.items(), key=lambda item: item[1], reverse=True)

    return {
        "question_id": question_id,
        "question_text": question_text,
        "question_type": question_type,
        "chart": _resolve_chart_for_objective(question_type, features, chart_override),
        "series": [{"name": "count", "data": [value for _, value in pairs]}],
        "labels": [label for label, _ in pairs],
    }


# 生成，服务于图表展示流程。
def _generate_numeric_chart(
    question_id: str,
    question_text: str,
    features: dict[str, Any],
    raw_values: list[float] | None = None,
    chart_override: str | None = None,
) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "question_text": question_text,
        "question_type": "numeric",
        "chart": _resolve_chart_for_objective("numeric", features, chart_override),
        "stats": {
            "mean": features.get("mean", 0.0),
            "std": features.get("std", 0.0),
            "min": features.get("min", 0.0),
            "max": features.get("max", 0.0),
            "outlier": features.get("outlier", 0.0),
        },
        "values": raw_values or [],
    }


# 生成，服务于图表展示流程。
def _generate_sentiment_chart(sentiment: dict[str, float]) -> dict[str, Any]:
    values = [
        sentiment.get("positive", 0.0),
        sentiment.get("neutral", 0.0),
        sentiment.get("negative", 0.0),
    ]
    return {
        "question_id": "__sentiment__",
        "question_text": "情绪分布",
        "question_type": "text",
        "chart": {"chart_type": "pie"},
        "labels": ["positive", "neutral", "negative"],
        "has_data": any(value > 0 for value in values),
        "empty_message": "当前没有情绪分析结果，请启用文本NLP后重新生成分析。",
        "series": [{"name": "sentiment", "data": values}],
    }


# 生成，服务于图表展示流程。
def _generate_topic_charts(
    topic_summary: list[dict[str, Any]],
    keyword_summary: list[dict[str, Any]],
    chart_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    chart_overrides = chart_overrides or {}
    charts: list[dict[str, Any]] = []

    topic_override = normalize_chart_override("text", chart_overrides.get("__topics__"))
    if topic_summary and topic_override != "wordcloud":
        charts.append(
            {
                "question_id": "__topics__",
                "question_text": "文本主题分布",
                "question_type": "text",
                "chart": {"chart_type": "pie"},
                "labels": [topic["topic"] for topic in topic_summary],
                "series": [{"name": "topics", "data": [topic["count"] for topic in topic_summary]}],
            }
        )

    keyword_override = normalize_chart_override("text", chart_overrides.get("__keywords__"))
    if keyword_summary and keyword_override != "pie":
        charts.append(
            {
                "question_id": "__keywords__",
                "question_text": "关键词云",
                "question_type": "text",
                "chart": {"chart_type": "wordcloud"},
                "words": keyword_summary,
            }
        )

    return charts


# 生成，服务于图表展示流程。
def generate_chart_payload(
    top_insights: list[dict[str, Any]],
    analyzer_results: dict[str, list[dict[str, Any]]],
    sentiment: dict[str, float],
    topic_summary: list[dict[str, Any]],
    keyword_summary: list[dict[str, Any]],
    chart_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    objective_lookup = {item["question_id"]: item for item in analyzer_results.get("objective", [])}
    chart_overrides = chart_overrides or {}
    charts: list[dict[str, Any]] = []

    for insight in top_insights:
        question_id = insight["question_id"]
        question_type = insight["question_type"]
        features = insight["features"]
        source = objective_lookup.get(question_id, {})
        question_text = insight.get("question_text", "") or source.get("question_text", "")
        override = chart_overrides.get(question_id)

        if question_type in {"single_choice", "multiple_choice", "likert"}:
            charts.append(
                _generate_choice_chart(
                    question_id,
                    question_text,
                    question_type,
                    features,
                    chart_override=override,
                )
            )
        elif question_type == "numeric":
            charts.append(
                _generate_numeric_chart(
                    question_id,
                    question_text,
                    features,
                    raw_values=source.get("raw_values", []),
                    chart_override=override,
                )
            )

    charts.extend(_generate_topic_charts(topic_summary, keyword_summary, chart_overrides))
    charts.append(_generate_sentiment_chart(sentiment))
    return charts
