from __future__ import annotations

import re
from typing import Any

import numpy as np
from snownlp import SnowNLP


POSITIVE_WORDS = {
    "满意",
    "开心",
    "高兴",
    "喜欢",
    "不错",
    "很好",
    "优秀",
    "支持",
    "认可",
    "轻松",
    "有帮助",
    "舒服",
    "积极",
    "改善",
    "提升",
}

NEGATIVE_WORDS = {
    "不满意",
    "糟糕",
    "很差",
    "不好",
    "焦虑",
    "压力",
    "痛苦",
    "失望",
    "崩溃",
    "烦",
    "累",
    "无语",
    "困难",
    "拖延",
    "失眠",
    "抑郁",
    "担心",
    "害怕",
}

NEUTRAL_WORDS = {
    "一般",
    "还行",
    "普通",
    "中等",
    "一般般",
    "尚可",
    "中立",
}

NEGATION_WORDS = {"不", "没", "无", "未", "别", "非"}
OPTION_PREFIX_RE = re.compile(r"^[A-Za-zＡ-Ｚａ-ｚ]\s*[\.．、:：]\s*")


# 归一化，服务于主观题语义分析流程。
def _normalize_text(text: str) -> str:
    value = str(text or "").strip()
    value = OPTION_PREFIX_RE.sub("", value)
    return value


# 计算评分，服务于主观题语义分析流程。
def _score_text(text: str) -> float:
    try:
        return float(SnowNLP(text).sentiments)
    except Exception:
        return 0.5


# 处理，服务于主观题语义分析流程。
def _lexicon_adjustment(text: str) -> float:
    content = _normalize_text(text)
    if not content:
        return 0.0

    pos_hits = sum(1 for w in POSITIVE_WORDS if w in content)
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in content)
    neu_hits = sum(1 for w in NEUTRAL_WORDS if w in content)
    negation_hits = sum(content.count(w) for w in NEGATION_WORDS)

    delta = 0.0
    delta += 0.08 * pos_hits
    delta -= 0.11 * neg_hits
    delta -= 0.03 * negation_hits

    if neu_hits > 0:
        delta *= 0.5

    return float(delta)


# 计算评分，服务于主观题语义分析流程。
def _final_score(text: str) -> float:
    base = _score_text(text)
    tuned = base + _lexicon_adjustment(text)
    return float(max(0.0, min(1.0, tuned)))


# 处理，服务于主观题语义分析流程。
def _compute_thresholds(scores: list[float]) -> tuple[float, float]:
    if not scores:
        return 0.42, 0.58

    if len(scores) < 8:
        return 0.42, 0.58

    arr = np.asarray(scores, dtype=float)
    q35 = float(np.quantile(arr, 0.35))
    q65 = float(np.quantile(arr, 0.65))

    low = max(0.30, min(0.48, q35))
    high = min(0.70, max(0.52, q65))
    if low >= high:
        low, high = 0.42, 0.58
    return low, high


# 计算评分，服务于主观题语义分析流程。
def _label_from_score(score: float, low: float, high: float) -> str:
    if score > high:
        return "positive"
    if score < low:
        return "negative"
    return "neutral"


# 执行分析，服务于主观题语义分析流程。
def analyze_sentiment_texts(texts: list[str]) -> dict[str, float]:
    cleaned_texts = [_normalize_text(text) for text in texts if _normalize_text(text)][:2000]

    if not cleaned_texts:
        return {"positive": 0.0, "neutral": 0.0, "negative": 0.0}

    scores = [_final_score(text) for text in cleaned_texts]
    low, high = _compute_thresholds(scores)
    labels = [_label_from_score(score, low, high) for score in scores]

    total = len(labels)
    positive = sum(1 for item in labels if item == "positive")
    neutral = sum(1 for item in labels if item == "neutral")
    negative = sum(1 for item in labels if item == "negative")

    return {
        "positive": positive / total,
        "neutral": neutral / total,
        "negative": negative / total,
    }


# 提取，服务于主观题语义分析流程。
def extract_subjective_texts(df) -> list[str]:
    if df is None or getattr(df, "empty", True):
        return []
    if "question_type" in df.columns and "answer" in df.columns:
        subjective_df = df[df["question_type"] == "text"]
        return subjective_df["answer"].dropna().astype(str).tolist()
    return []


# 执行分析，服务于主观题语义分析流程。
def analyze_sentiment(df) -> dict[str, float]:
    return analyze_sentiment_texts(extract_subjective_texts(df))


# 执行分析，服务于主观题语义分析流程。
def analyze_sentiment_by_respondent(respondent_texts: list[dict[str, Any]]) -> dict[str, Any]:
    grouped_texts: dict[str, list[str]] = {}
    for item in respondent_texts:
        respondent_id = str(item.get("respondent_id", "")).strip()
        text = _normalize_text(item.get("text", ""))
        if not respondent_id or not text:
            continue
        grouped_texts.setdefault(respondent_id, []).append(text)

    if not grouped_texts:
        return {
            "positive": 0.0,
            "neutral": 0.0,
            "negative": 0.0,
            "respondent_count": 0,
            "respondents": [],
        }

    respondent_results: list[dict[str, Any]] = []
    respondent_scores: list[float] = []

    for respondent_id, texts in list(grouped_texts.items())[:10000]:
        scores = [_final_score(text) for text in texts[:200]]
        if not scores:
            continue
        average_score = float(sum(scores) / len(scores))
        respondent_scores.append(average_score)
        respondent_results.append(
            {
                "respondent_id": respondent_id,
                "score": round(average_score, 4),
                "label": "neutral",
                "text_count": len(texts),
            }
        )

    if not respondent_results:
        return {
            "positive": 0.0,
            "neutral": 0.0,
            "negative": 0.0,
            "respondent_count": 0,
            "respondents": [],
        }

    low, high = _compute_thresholds(respondent_scores)
    for item in respondent_results:
        item["label"] = _label_from_score(float(item["score"]), low, high)

    total = len(respondent_results)
    positive = sum(1 for item in respondent_results if item["label"] == "positive")
    neutral = sum(1 for item in respondent_results if item["label"] == "neutral")
    negative = sum(1 for item in respondent_results if item["label"] == "negative")

    return {
        "positive": positive / total,
        "neutral": neutral / total,
        "negative": negative / total,
        "respondent_count": total,
        "respondents": respondent_results,
    }
