import math
from typing import Any

import numpy as np


# 安全计算，服务于问卷结构化分析流程。
def _safe_entropy(probabilities: list[float]) -> float:
    valid = [p for p in probabilities if p > 0]
    if not valid:
        return 0.0
    return float(-sum(p * math.log(p, 2) for p in valid))


# 归一化，服务于问卷结构化分析流程。
def _normalized_entropy(probabilities: list[float]) -> float:
    if len(probabilities) <= 1:
        return 0.0
    entropy = _safe_entropy(probabilities)
    max_entropy = math.log(len(probabilities), 2)
    if max_entropy == 0:
        return 0.0
    return float(entropy / max_entropy)


# 计算异常值，服务于问卷结构化分析流程。
def _outlier_ratio(values: np.ndarray) -> float:
    if len(values) < 4:
        return 0.0
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    if iqr == 0:
        return 0.0
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = ((values < lower) | (values > upper)).sum()
    return float(outliers / len(values))


# 计算高分占比，服务于问卷结构化分析流程。
def _top2box(values: np.ndarray) -> float:
    if len(values) == 0:
        return 0.0
    max_value = np.max(values)
    threshold = max_value - 1
    return float((values >= threshold).sum() / len(values))


# 计算数值题，服务于问卷结构化分析流程。
def _numeric_metrics(values: list[float], question_type: str, sample_size: int) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    mean = float(np.mean(array))
    std = float(np.std(array))
    min_value = float(np.min(array))
    max_value = float(np.max(array))
    value_range = max(max_value - min_value, 1e-9)
    center = (max_value + min_value) / 2
    extreme_score = min(abs(mean - center) / (value_range / 2), 1.0) if value_range > 0 else 0.0
    entropy_input = [count / len(array) for count in np.unique(array, return_counts=True)[1].tolist()]

    metrics = {
        "mean": mean,
        "std": std,
        "min": min_value,
        "max": max_value,
        "sample_size": sample_size,
        "entropy": _safe_entropy(entropy_input),
        "normalized_entropy": _normalized_entropy(entropy_input),
        "outlier": _outlier_ratio(array),
        "dispersion_raw": std / value_range if value_range > 0 else 0.0,
        "extreme_raw": extreme_score,
    }

    if question_type == "likert":
        unique_values, unique_counts = np.unique(array, return_counts=True)
        metrics["top2box"] = _top2box(array)
        metrics["max_ratio"] = float(np.max(np.unique(array, return_counts=True)[1]) / len(array))
        metrics["distribution"] = {
            str(int(v) if float(v).is_integer() else v): int(c)
            for v, c in zip(unique_values.tolist(), unique_counts.tolist())
        }

    return metrics


# 计算选项题，服务于问卷结构化分析流程。
def _choice_metrics(category_counts: dict[str, int], sample_size: int) -> dict[str, Any]:
    total = sum(category_counts.values())
    probabilities = [count / total for count in category_counts.values()] if total else []
    counts = list(category_counts.values())

    return {
        "sample_size": sample_size,
        "response_count": total,
        "option_count": len(category_counts),
        "max_ratio": max(probabilities) if probabilities else 0.0,
        "top2box": 0.0,
        "entropy": _safe_entropy(probabilities),
        "normalized_entropy": _normalized_entropy(probabilities),
        "dispersion_raw": 1 - (max(probabilities) if probabilities else 0.0),
        "extreme_raw": 0.0,
        "outlier": 0.0,
        "distribution": category_counts,
        "counts_std": float(np.std(counts)) if counts else 0.0,
    }


# 计算文本题，服务于问卷结构化分析流程。
def _text_metrics(texts: list[str], sample_size: int) -> dict[str, Any]:
    lengths = [len(text.strip()) for text in texts if text.strip()]
    return {
        "sample_size": sample_size,
        "text_count": len(texts),
        "avg_length": float(np.mean(lengths)) if lengths else 0.0,
    }


# 提取，服务于问卷结构化分析流程。
def extract_features(analyzer_results: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []

    for item in analyzer_results.get("objective", []):
        question_type = item["question_type"]
        sample_size = int(item.get("sample_size", 0))

        if question_type in {"numeric", "likert"}:
            metrics = _numeric_metrics(item.get("raw_values", []), question_type, sample_size)
        else:
            metrics = _choice_metrics(item.get("category_counts", {}), sample_size)

        features.append(
            {
                "question_id": item["question_id"],
                "question_text": item.get("question_text", ""),
                "question_type": question_type,
                "analysis_features": metrics,
            }
        )

    for item in analyzer_results.get("subjective", []):
        features.append(
            {
                "question_id": item["question_id"],
                "question_text": item.get("question_text", ""),
                "question_type": "text",
                "analysis_features": _text_metrics(
                    item.get("raw_texts", []),
                    int(item.get("sample_size", 0)),
                ),
            }
        )

    return features
