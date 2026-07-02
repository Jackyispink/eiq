from typing import Any


QUESTION_TYPE_LABELS = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "likert": "量表题",
    "numeric": "数值题",
    "text": "主观题",
}


# 处理，服务于问卷结构化分析流程。
def _is_valid_candidate(info: dict[str, Any], min_score_threshold: float, min_sample_size: int) -> bool:
    if info.get("final_score", 0.0) < min_score_threshold:
        return False
    if info.get("features", {}).get("sample_size", 0) < min_sample_size:
        return False
    return True


# 构建，服务于问卷结构化分析流程。
def _build_summary_hint(info: dict[str, Any]) -> str:
    question_type = info.get("question_type")
    features = info.get("features", {})
    details = info.get("details", {})

    if question_type in {"single_choice", "multiple_choice"}:
        return (
            f"最高选项占比 {details.get('dominance', 0):.2f}，"
            f"信息量 {details.get('info_score', 0):.2f}，"
            f"分散度 {details.get('dispersion_score', 0):.2f}"
        )

    if question_type == "likert":
        return (
            f"均值 {features.get('mean', 0):.2f}，"
            f"Top2Box {features.get('top2box', 0):.2%}，"
            f"标准差 {features.get('std', 0):.2f}"
        )

    if question_type == "numeric":
        return (
            f"均值 {features.get('mean', 0):.2f}，"
            f"标准差 {features.get('std', 0):.2f}，"
            f"离群值比例 {features.get('outlier', 0):.2%}"
        )

    return (
        f"样本量 {features.get('sample_size', 0)}，"
        f"平均文本长度 {features.get('avg_length', 0):.1f}"
    )


# 筛选，服务于问卷结构化分析流程。
def _select_items(
    candidates: list[dict[str, Any]],
    top_n: int,
    per_type_limit: dict[str, int] | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    selected_items: list[dict[str, Any]] = []
    type_counter: dict[str, int] = {}

    for info in candidates:
        question_type = info.get("question_type", "unknown")
        if per_type_limit and type_counter.get(question_type, 0) >= per_type_limit.get(question_type, top_n):
            continue

        selected_items.append(
            {
                "question_id": info["question_id"],
                "question_text": info.get("question_text", ""),
                "question_type": question_type,
                "question_type_label": QUESTION_TYPE_LABELS.get(question_type, question_type),
                "score": info["final_score"],
                "base_score": info["base_score"],
                "features": info["features"],
                "details": info["details"],
                "summary_hint": _build_summary_hint(info),
            }
        )
        type_counter[question_type] = type_counter.get(question_type, 0) + 1

        if len(selected_items) >= top_n:
            break

    return selected_items, type_counter


# 筛选，服务于问卷结构化分析流程。
def select_top_insights(
    scores: dict[str, dict[str, Any]],
    top_n: int = 8,
    min_score_threshold: float = 0.25,
    per_type_limit: dict[str, int] | None = None,
    min_sample_size: int = 5,
) -> dict[str, Any]:
    if not scores:
        return {
            "selected": [],
            "meta": {
                "total_candidates": 0,
                "filtered_count": 0,
                "selected_count": 0,
                "type_distribution": {},
                "min_sample_size_used": min_sample_size,
            },
        }

    max_sample_size = max(
        (info.get("features", {}).get("sample_size", 0) for info in scores.values()),
        default=0,
    )
    adaptive_min_sample_size = min(min_sample_size, max_sample_size) if max_sample_size > 0 else 0

    candidates = [
        info
        for info in scores.values()
        if _is_valid_candidate(info, min_score_threshold, adaptive_min_sample_size)
    ]

    if not candidates:
        relaxed_threshold = min_score_threshold * 0.5
        relaxed_min_sample_size = 1 if max_sample_size > 0 else 0
        candidates = [
            info
            for info in scores.values()
            if _is_valid_candidate(info, relaxed_threshold, relaxed_min_sample_size)
        ]
        adaptive_min_sample_size = relaxed_min_sample_size

    candidates.sort(key=lambda item: item["final_score"], reverse=True)
    selected_items, type_counter = _select_items(candidates, top_n, per_type_limit)

    if not selected_items and scores:
        fallback_candidates = sorted(
            scores.values(),
            key=lambda item: item.get("final_score", 0.0),
            reverse=True,
        )
        selected_items, type_counter = _select_items(fallback_candidates, top_n, per_type_limit)

    return {
        "selected": selected_items,
        "meta": {
            "total_candidates": len(scores),
            "filtered_count": len(candidates),
            "selected_count": len(selected_items),
            "type_distribution": type_counter,
            "min_sample_size_used": adaptive_min_sample_size,
        },
    }
