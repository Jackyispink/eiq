from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}")
QID_PATTERN = re.compile(r"\bQ\d+[A-Za-z0-9_-]*\b", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"[\n。！？!?；;]+")
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])(-?\d+(?:\.\d+)?)\s*(%)?")

STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "about",
    "your",
    "their",
    "there",
    "and",
    "the",
    "are",
    "was",
    "were",
    "总体",
    "分析",
    "调查",
    "问卷",
    "结果",
    "数据",
    "显示",
    "说明",
    "建议",
    "可以",
    "进行",
    "方面",
    "问题",
    "情况",
    "学生",
    "用户",
}

ABSOLUTE_TERMS = {
    "全部",
    "所有",
    "完全",
    "一定",
    "必然",
    "绝对",
    "均",
    "没有任何",
    "从不",
    "始终",
    "all",
    "always",
    "never",
    "must",
}

CLAIM_VERBS = {
    "认为",
    "反映",
    "说明",
    "表明",
    "集中",
    "偏高",
    "偏低",
    "满意",
    "不满意",
    "增加",
    "减少",
    "存在",
    "改善",
    "提升",
    "下降",
    "上升",
    "关注",
    "建议",
    "需要",
}


def _clip(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(float(value), max_value))


def _tokenize(text: str) -> list[str]:
    raw_text = str(text or "")
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(raw_text)]
    tokens.extend(qid.lower() for qid in QID_PATTERN.findall(raw_text))
    return [token for token in tokens if token not in STOPWORDS and len(token.strip()) >= 2]


def _token_set(text: str) -> set[str]:
    return set(_tokenize(text))


def _weighted_keyword_items(items: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in items[:limit] if limit else items:
        name = str(item.get("name") or item.get("keyword") or item.get("topic") or "").strip()
        if not name:
            continue
        weight = float(item.get("value") or item.get("count") or item.get("weight") or 1.0)
        output.append({"name": name, "weight": max(weight, 1.0), "tokens": _token_set(name)})
    return output


def _extract_evidence_terms(
    analyzer_results: dict[str, list[dict[str, Any]]],
    topics: list[dict[str, Any]],
    keywords: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    evidence.extend(_weighted_keyword_items(keywords, limit=top_n))

    for topic in topics[:top_n]:
        topic_name = str(topic.get("topic", "")).strip()
        count = float(topic.get("count") or 1.0)
        if topic_name:
            evidence.append({"name": topic_name, "weight": count, "tokens": _token_set(topic_name)})
        for keyword in topic.get("keywords", [])[:6]:
            keyword_text = str(keyword).strip()
            if keyword_text:
                evidence.append({"name": keyword_text, "weight": count, "tokens": _token_set(keyword_text)})

    for group_name in ("objective", "subjective"):
        for item in analyzer_results.get(group_name, []):
            qid = str(item.get("question_id", "")).strip()
            if qid:
                evidence.append({"name": qid, "weight": 1.0, "tokens": {qid.lower()}})
            qtext = str(item.get("question_text", "")).strip()
            if qtext:
                evidence.append({"name": qtext, "weight": 1.0, "tokens": _token_set(qtext)})
            for option in item.get("category_counts", {}).keys():
                option_text = str(option).strip()
                if option_text:
                    evidence.append({"name": option_text, "weight": 1.0, "tokens": _token_set(option_text)})

    merged: dict[str, dict[str, Any]] = {}
    for item in evidence:
        name = item["name"]
        tokens = item["tokens"]
        if not tokens:
            continue
        if name not in merged:
            merged[name] = item
        else:
            merged[name]["weight"] += item["weight"]
    return list(merged.values())


def _semantic_overlap(a_tokens: set[str], b_tokens: set[str], a_text: str, b_text: str) -> float:
    if not a_tokens or not b_tokens:
        return 0.0
    if a_text and b_text and (a_text in b_text or b_text in a_text):
        return 1.0
    intersection = len(a_tokens & b_tokens)
    if intersection == 0:
        return 0.0
    precision = intersection / len(a_tokens)
    recall = intersection / len(b_tokens)
    return (2 * precision * recall) / (precision + recall) if precision + recall else 0.0


def _extract_report_keywords(report: str, top_k: int = 40) -> list[dict[str, Any]]:
    counter = Counter(_tokenize(report))
    return [{"name": token, "weight": count, "tokens": {token}} for token, count in counter.most_common(top_k)]


def _split_atomic_claims(report: str) -> list[str]:
    claims: list[str] = []
    for raw in SENTENCE_SPLIT_PATTERN.split(str(report or "")):
        text = re.sub(r"^[#*\-\d\.\s、]+", "", raw).strip()
        if len(text) < 6:
            continue
        tokens = _tokenize(text)
        if len(tokens) < 2:
            continue
        if any(verb in text for verb in CLAIM_VERBS) or NUMBER_PATTERN.search(text) or "证据" in text or QID_PATTERN.search(text):
            claims.append(text)
    return claims


def _support_claims(
    claims: list[str],
    evidence_terms: list[dict[str, Any]],
    similarity_threshold: float,
) -> tuple[int, list[dict[str, Any]]]:
    supported = 0
    details: list[dict[str, Any]] = []
    for claim in claims:
        claim_tokens = _token_set(claim)
        best_score = 0.0
        best_term = ""
        for evidence in evidence_terms:
            score = _semantic_overlap(claim_tokens, evidence["tokens"], claim, evidence["name"])
            if score > best_score:
                best_score = score
                best_term = evidence["name"]
        is_supported = best_score >= similarity_threshold
        if is_supported:
            supported += 1
        details.append(
            {
                "claim": claim,
                "supported": is_supported,
                "best_evidence": best_term,
                "support_score": round(best_score, 4),
            }
        )
    return supported, details


def _keyword_consistency(
    report: str,
    evidence_terms: list[dict[str, Any]],
    similarity_threshold: float,
) -> dict[str, Any]:
    report_keywords = _extract_report_keywords(report)
    if not report_keywords or not evidence_terms:
        return {"precision": 0.0, "recall": 0.0, "f05": 0.0, "matched_report_keywords": 0, "covered_evidence": 0}

    matched_report_weight = 0.0
    report_weight = sum(item["weight"] for item in report_keywords)
    for keyword in report_keywords:
        best_score = max(
            (
                _semantic_overlap(keyword["tokens"], evidence["tokens"], keyword["name"], evidence["name"])
                for evidence in evidence_terms
            ),
            default=0.0,
        )
        if best_score >= similarity_threshold:
            matched_report_weight += keyword["weight"]

    covered_evidence_weight = 0.0
    evidence_weight = sum(item["weight"] for item in evidence_terms)
    covered_count = 0
    for evidence in evidence_terms:
        best_score = max(
            (
                _semantic_overlap(keyword["tokens"], evidence["tokens"], keyword["name"], evidence["name"])
                for keyword in report_keywords
            ),
            default=0.0,
        )
        if best_score >= similarity_threshold:
            covered_evidence_weight += evidence["weight"]
            covered_count += 1

    precision = matched_report_weight / report_weight if report_weight else 0.0
    recall = covered_evidence_weight / evidence_weight if evidence_weight else 0.0
    beta2 = 0.5**2
    f05 = ((1 + beta2) * precision * recall / (beta2 * precision + recall)) if precision + recall else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f05": round(f05, 4),
        "matched_report_keywords": int(matched_report_weight),
        "covered_evidence": covered_count,
    }


def _topn_hit_rate(report: str, keywords: list[dict[str, Any]], top_n: int, similarity_threshold: float) -> dict[str, Any]:
    standard = _weighted_keyword_items(keywords, limit=top_n)
    report_keywords = _extract_report_keywords(report, top_k=max(40, top_n * 4))
    if not standard:
        return {"hit_rate": 0.0, "omission_rate": 0.0, "redundancy_rate": 0.0, "hit_count": 0, "top_n": top_n}

    hit_count = 0
    dcg = 0.0
    for idx, item in enumerate(standard, start=1):
        best_score = max(
            (
                _semantic_overlap(item["tokens"], keyword["tokens"], item["name"], keyword["name"])
                for keyword in report_keywords
            ),
            default=0.0,
        )
        if best_score >= similarity_threshold:
            hit_count += 1
            dcg += 1.0 / math.log2(idx + 1)

    ideal_dcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, len(standard) + 1))
    matched_report = 0
    for keyword in report_keywords[:top_n]:
        best_score = max(
            (
                _semantic_overlap(keyword["tokens"], item["tokens"], keyword["name"], item["name"])
                for item in standard
            ),
            default=0.0,
        )
        if best_score >= similarity_threshold:
            matched_report += 1
    redundancy = 1.0 - (matched_report / min(len(report_keywords), top_n)) if report_keywords else 1.0

    return {
        "hit_rate": round(hit_count / len(standard), 4),
        "omission_rate": round(1.0 - hit_count / len(standard), 4),
        "redundancy_rate": round(_clip(redundancy), 4),
        "ndcg": round(dcg / ideal_dcg, 4) if ideal_dcg else 0.0,
        "hit_count": hit_count,
        "top_n": top_n,
    }


def _extract_structured_numbers(
    analyzer_results: dict[str, list[dict[str, Any]]],
    scores: dict[str, dict[str, Any]] | None,
    sentiment: dict[str, Any] | None,
) -> list[float]:
    values: list[float] = []
    for item in analyzer_results.get("objective", []):
        counts = item.get("category_counts", {})
        total = sum(int(v) for v in counts.values()) if isinstance(counts, dict) else 0
        if total:
            values.extend([count / total * 100 for count in counts.values()])
        for raw in item.get("raw_values", [])[:2000]:
            try:
                values.append(float(raw))
            except Exception:
                continue
    for info in (scores or {}).values():
        features = info.get("features", {})
        for key in ("mean", "std", "top2box", "outlier", "max_ratio", "normalized_entropy"):
            if key in features:
                value = float(features[key])
                values.append(value * 100 if 0 <= value <= 1 and key in {"top2box", "outlier", "max_ratio"} else value)
    for value in (sentiment or {}).values():
        try:
            values.append(float(value) * 100)
        except Exception:
            continue
    return values


def _numeric_accuracy(
    report: str,
    analyzer_results: dict[str, list[dict[str, Any]]],
    scores: dict[str, dict[str, Any]] | None,
    sentiment: dict[str, Any] | None,
) -> dict[str, Any]:
    reference_numbers = _extract_structured_numbers(analyzer_results, scores, sentiment)
    report_numbers: list[float] = []
    for raw_value, percent_mark in NUMBER_PATTERN.findall(str(report or "")):
        try:
            value = float(raw_value)
        except Exception:
            continue
        report_numbers.append(value)

    if not report_numbers:
        return {"accuracy": 1.0, "error": 0.0, "reported_number_count": 0, "matched_number_count": 0}
    if not reference_numbers:
        return {"accuracy": 0.0, "error": 1.0, "reported_number_count": len(report_numbers), "matched_number_count": 0}

    errors: list[float] = []
    matched = 0
    for generated in report_numbers:
        best = min(reference_numbers, key=lambda ref: abs(generated - ref))
        denom = max(abs(best), 1.0)
        relative_error = abs(generated - best) / denom
        errors.append(min(relative_error, 1.0))
        if relative_error <= 0.05 or abs(generated - best) <= 0.05:
            matched += 1
    avg_error = sum(errors) / len(errors) if errors else 0.0
    return {
        "accuracy": round(_clip(1.0 - avg_error), 4),
        "error": round(avg_error, 4),
        "reported_number_count": len(report_numbers),
        "matched_number_count": matched,
    }


def _absolute_expression_rate(claims: list[str], claim_details: list[dict[str, Any]]) -> dict[str, Any]:
    if not claims:
        return {"rate": 0.0, "count": 0}
    unsupported_claims = {item["claim"] for item in claim_details if not item.get("supported")}
    count = 0
    for claim in claims:
        if claim not in unsupported_claims:
            continue
        if any(term in claim for term in ABSOLUTE_TERMS):
            count += 1
    return {"rate": round(count / len(claims), 4), "count": count}


def _incremental_consistency(
    report: str,
    previous_report: str | None,
    similarity_threshold: float,
) -> dict[str, Any]:
    if not previous_report:
        return {"score": 1.0, "enabled": False, "shared_keyword_rate": 1.0}
    current = set(_tokenize(report))
    previous = set(_tokenize(previous_report))
    if not current and not previous:
        return {"score": 1.0, "enabled": True, "shared_keyword_rate": 1.0}
    if not current or not previous:
        return {"score": 0.0, "enabled": True, "shared_keyword_rate": 0.0}
    union = current | previous
    shared = current & previous
    score = len(shared) / len(union) if union else 1.0
    return {
        "score": round(_clip(score / max(similarity_threshold, 0.01)), 4),
        "enabled": True,
        "shared_keyword_rate": round(score, 4),
    }


def evaluate_report_quality(
    analyzer_results: dict[str, list[dict[str, Any]]],
    topics: list[dict[str, Any]] | None,
    keywords: list[dict[str, Any]] | None,
    llm_report: str | None,
    scores: dict[str, dict[str, Any]] | None = None,
    sentiment: dict[str, Any] | None = None,
    previous_report: str | None = None,
    top_n: int = 10,
    similarity_threshold: float = 0.35,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    report = str(llm_report or "").strip()
    topics = topics or []
    keywords = keywords or []
    weights = weights or {"support": 0.4, "topic": 0.3, "numeric": 0.2, "incremental": 0.1}

    evidence_terms = _extract_evidence_terms(analyzer_results, topics, keywords, top_n=top_n)
    claims = _split_atomic_claims(report)
    supported_count, claim_details = _support_claims(claims, evidence_terms, similarity_threshold)
    support_rate = supported_count / len(claims) if claims else 0.0
    hallucination_error_rate = 1.0 - support_rate if claims else 0.0
    topic_score = _keyword_consistency(report, evidence_terms, similarity_threshold)
    topn_score = _topn_hit_rate(report, keywords, top_n, similarity_threshold)
    numeric_score = _numeric_accuracy(report, analyzer_results, scores, sentiment)
    incremental_score = _incremental_consistency(report, previous_report, similarity_threshold)
    absolute_rate = _absolute_expression_rate(claims, claim_details)

    weight_total = sum(weights.values()) or 1.0
    normalized_weights = {key: value / weight_total for key, value in weights.items()}
    dgrcs = (
        normalized_weights.get("support", 0.0) * support_rate
        + normalized_weights.get("topic", 0.0) * topic_score["f05"]
        + normalized_weights.get("numeric", 0.0) * numeric_score["accuracy"]
        + normalized_weights.get("incremental", 0.0) * incremental_score["score"]
    )

    score = round(dgrcs * 100, 2)
    return {
        "metric_name": "EGRE",
        "score": score,
        "egre_score": score,
        "dgrcs_score": score,
        "support_rate": round(support_rate, 4),
        "hallucination_error_rate": round(hallucination_error_rate, 4),
        "topic_consistency": topic_score,
        "topn": topn_score,
        "numeric_accuracy": numeric_score,
        "incremental_consistency": incremental_score,
        "absolute_expression_rate": absolute_rate,
        "atomic_claim_count": len(claims),
        "supported_claim_count": supported_count,
        "evidence_term_count": len(evidence_terms),
        "settings": {
            "top_n": top_n,
            "similarity_threshold": similarity_threshold,
            "weights": normalized_weights,
        },
        "claim_details": claim_details[:30],
    }


def evaluate_report_quality_variants(
    analyzer_results: dict[str, list[dict[str, Any]]],
    topics: list[dict[str, Any]] | None,
    keywords: list[dict[str, Any]] | None,
    llm_report: str | None,
    scores: dict[str, dict[str, Any]] | None = None,
    sentiment: dict[str, Any] | None = None,
    previous_report: str | None = None,
) -> dict[str, Any]:
    configs = {
        "balanced_top10": {"top_n": 10, "similarity_threshold": 0.35},
        "strict_top10": {"top_n": 10, "similarity_threshold": 0.5},
        "lenient_top10": {"top_n": 10, "similarity_threshold": 0.25},
        "balanced_top5": {"top_n": 5, "similarity_threshold": 0.35},
        "balanced_top20": {"top_n": 20, "similarity_threshold": 0.35},
    }
    return {
        name: evaluate_report_quality(
            analyzer_results=analyzer_results,
            topics=topics,
            keywords=keywords,
            llm_report=llm_report,
            scores=scores,
            sentiment=sentiment,
            previous_report=previous_report,
            **config,
        )
        for name, config in configs.items()
    }
