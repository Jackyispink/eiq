from typing import Any


TYPE_WEIGHT_MAP = {
    "single_choice": 0.95,
    "multiple_choice": 0.9,
    "likert": 1.0,
    "numeric": 0.85,
    "text": 0.7,
}

ALPHA = 0.8


# 处理，服务于问卷结构化分析流程。
def _clip(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(value, max_value))


# 归一化，服务于问卷结构化分析流程。
def _normalize_sample_size(sample_size: int, max_size: int) -> float:
    if max_size <= 0:
        return 0.0
    return _clip(sample_size / max_size)


# 归一化，服务于问卷结构化分析流程。
def _normalize_objective_scores(features: dict[str, Any], question_type: str) -> dict[str, float]:
    dominance = _clip(features.get("max_ratio", 0.0))
    info_score = _clip(features.get("normalized_entropy", 0.0))
    outlier_score = _clip(features.get("outlier", 0.0))

    if question_type == "likert":
        dispersion_score = _clip(features.get("std", 0.0) / 2.0)
        extreme_score = _clip(features.get("extreme_raw", 0.0))
        dominance = _clip(features.get("top2box", 0.0))
    elif question_type == "numeric":
        dispersion_score = _clip(features.get("dispersion_raw", 0.0) * 2.0)
        extreme_score = _clip(features.get("extreme_raw", 0.0))
    else:
        dispersion_score = _clip(features.get("dispersion_raw", 0.0))
        extreme_score = 0.0

    return {
        "dominance": dominance,
        "info_score": info_score,
        "dispersion_score": dispersion_score,
        "extreme_score": extreme_score,
        "outlier_score": outlier_score,
    }


# 计算综合评分，服务于问卷结构化分析流程。
def compute_scores(feature_list: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    max_sample_size = max(
        (item["analysis_features"].get("sample_size", 0) for item in feature_list),
        default=0,
    )
    results: dict[str, dict[str, Any]] = {}

    for item in feature_list:
        question_id = item["question_id"]
        question_type = item["question_type"]
        features = item["analysis_features"]
        sample_size = int(features.get("sample_size", 0))
        sample_factor = _normalize_sample_size(sample_size, max_sample_size)

        if question_type == "text":
            base_score = _clip(
                0.6 * sample_factor + 0.4 * _clip(features.get("avg_length", 0.0) / 50.0)
            )
            details = {
                "sample_factor": sample_factor,
                "avg_length_score": _clip(features.get("avg_length", 0.0) / 50.0),
            }
        else:
            normalized = _normalize_objective_scores(features, question_type)
            if question_type == "single_choice":
                base_score = (
                    0.5 * normalized["dominance"]
                    + 0.3 * normalized["info_score"]
                    + 0.2 * normalized["dispersion_score"]
                )
            elif question_type == "multiple_choice":
                base_score = (
                    0.6 * normalized["dominance"]
                    + 0.3 * normalized["info_score"]
                    + 0.1 * normalized["dispersion_score"]
                )
            elif question_type == "likert":
                base_score = (
                    0.4 * normalized["extreme_score"]
                    + 0.3 * normalized["dispersion_score"]
                    + 0.2 * normalized["dominance"]
                    + 0.1 * normalized["info_score"]
                )
            elif question_type == "numeric":
                base_score = (
                    0.5 * normalized["dispersion_score"]
                    + 0.3 * normalized["extreme_score"]
                    + 0.2 * normalized["outlier_score"]
                )
            else:
                base_score = 0.0

            base_score = _clip(base_score * (0.7 + 0.3 * sample_factor))
            details = {**normalized, "sample_factor": sample_factor}

        type_weight = TYPE_WEIGHT_MAP.get(question_type, 0.8)
        final_score = ALPHA * base_score + (1 - ALPHA) * type_weight

        results[question_id] = {
            "question_id": question_id,
            "question_text": item.get("question_text", ""),
            "question_type": question_type,
            "type": question_type,
            "base_score": round(base_score, 4),
            "final_score": round(final_score, 4),
            "type_weight": type_weight,
            "features": features,
            "details": details,
        }

    return results
