from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Callable

from backend.config import PERFORMANCE_MODE
from backend.analysis.feature_extractor import extract_features
from backend.analysis.insight_selector import select_top_insights
from backend.analysis.objective_processor import process_all_questions
from backend.analysis.report_quality import evaluate_report_quality_variants
from backend.analysis.scoring_engine import compute_scores
from backend.data.database import (
    get_nlp_summary_cache,
    load_data_by_batches,
    save_nlp_artifacts,
    set_nlp_summary_cache,
)
from backend.llm.llm_analyzer import analyze_with_llm
from backend.nlp.sentiment import analyze_sentiment_by_respondent, analyze_sentiment_texts
from backend.nlp.model_manager import NLPModelManager
from backend.pipeline.agent_orchestrator import AgentContext, build_agent_plan, describe_agent_design, serialize_task_trace
from backend.pipeline.langchain_agent import summarize_langchain_agent
from backend.visualization.chart_generator import generate_chart_payload
from backend.visualization.chart_selector import get_chart_options, normalize_chart_override, select_chart_type


TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}")
STOPWORDS = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "about",
    "you",
    "and",
    "the",
}
PERFORMANCE_PROFILES = {
    "fast": {
        "text_batch_size": 240,
        "max_subjective_texts": 500,
        "max_respondent_texts": 1200,
        "max_question_respondent_rows": 120,
        "enable_topic_model": False,
        "enable_llm": False,
    },
    "balanced": {
        "text_batch_size": 140,
        "max_subjective_texts": 1200,
        "max_respondent_texts": 3000,
        "max_question_respondent_rows": 320,
        "enable_topic_model": False,
        "enable_llm": True,
    },
    "accurate": {
        "text_batch_size": 100,
        "max_subjective_texts": 3000,
        "max_respondent_texts": 6000,
        "max_question_respondent_rows": 1200,
        "enable_topic_model": True,
        "enable_llm": True,
    },
}
TEXT_BATCH_SIZE = 140
LARGE_SCALE_ROW_THRESHOLD = 25000
LARGE_SCALE_TEXT_THRESHOLD = 2500
SENTIMENT_ALGO_VERSION = "v2_hybrid_adaptive"
TEXT_ANALYTICS_VERSION = "v1_interpretable_panels"


# 处理，服务于增量分析流水线流程。
def _iter_batches(items: list[Any], size: int = TEXT_BATCH_SIZE):
    for i in range(0, len(items), size):
        yield items[i : i + size]


# 处理，服务于增量分析流水线流程。
def _collect_subjective_payload(
    subjective_items: list[dict[str, Any]],
) -> tuple[list[str], dict[str, list[str]], list[dict[str, Any]]]:
    question_texts: dict[str, list[str]] = {}
    all_texts: list[str] = []
    respondent_texts: list[dict[str, Any]] = []

    for item in subjective_items:
        texts = [text.strip() for text in item.get("raw_texts", []) if str(text).strip()]
        if not texts:
            continue
        question_texts[item["question_id"]] = texts
        all_texts.extend(texts)
        respondent_texts.extend(item.get("respondent_texts", []))

    return all_texts, question_texts, respondent_texts


# 处理，服务于增量分析流水线流程。
def _tokenize(text: str) -> list[str]:
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(str(text))]
    return [token for token in tokens if token not in STOPWORDS and len(token.strip()) >= 2]


# 构建，服务于增量分析流水线流程。
def _build_keyword_summary(question_texts: dict[str, list[str]], text_batch_size: int) -> list[dict[str, Any]]:
    if not question_texts:
        return []

    keyword_counter: Counter[str] = Counter()
    for texts in question_texts.values():
        for chunk in _iter_batches(texts[:600], size=text_batch_size):
            for text in chunk:
                keyword_counter.update(_tokenize(text))

    return [{"name": keyword, "value": count} for keyword, count in keyword_counter.most_common(40)]


# 构建，服务于增量分析流水线流程。
def _build_topic_summary_fallback(subjective_texts: list[str], text_batch_size: int) -> list[dict[str, Any]]:
    if len(subjective_texts) < 2:
        return []

    topic_counter: Counter[str] = Counter()
    topic_keywords: dict[str, Counter[str]] = {}

    for chunk in _iter_batches(subjective_texts[:1000], size=text_batch_size):
        for text in chunk:
            tokens = _tokenize(text)
            if not tokens:
                continue
            topic_name = " / ".join(tokens[:2]) if len(tokens) >= 2 else tokens[0]
            topic_counter[topic_name] += 1
            topic_keywords.setdefault(topic_name, Counter()).update(tokens[:8])

    topics = []
    for topic_name, count in topic_counter.most_common(10):
        keywords = [word for word, _ in topic_keywords.get(topic_name, Counter()).most_common(6)]
        topics.append({"topic": topic_name, "count": count, "keywords": keywords})
    return topics


# 构建，服务于增量分析流水线流程。
def _build_topic_summary_simple(texts: list[str], top_k: int = 8) -> list[dict[str, Any]]:
    if len(texts) < 2:
        return []
    topic_counter: Counter[str] = Counter()
    keyword_map: dict[str, Counter[str]] = {}
    for text in texts:
        tokens = _tokenize(text)
        if not tokens:
            continue
        topic_name = " / ".join(tokens[:2]) if len(tokens) >= 2 else tokens[0]
        topic_counter[topic_name] += 1
        keyword_map.setdefault(topic_name, Counter()).update(tokens[:8])
    results = []
    for topic_name, count in topic_counter.most_common(top_k):
        keywords = [k for k, _ in keyword_map.get(topic_name, Counter()).most_common(6)]
        results.append({"topic": topic_name, "count": count, "keywords": keywords})
    return results


# 构建，服务于增量分析流水线流程。
def _build_keywords_simple(texts: list[str], top_k: int = 30) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(_tokenize(text))
    return [{"name": name, "value": value} for name, value in counter.most_common(top_k)]


# 构建，服务于增量分析流水线流程。
def _build_text_question_analytics(
    subjective_items: list[dict[str, Any]],
    include_nlp: bool,
    max_subjective_texts: int,
    include_response_details: bool = True,
    max_question_respondent_rows: int = 400,
) -> dict[str, dict[str, Any]]:
    # 构建，服务于增量分析流水线流程。
    def _build_keyword_stats(
        response_rows: list[dict[str, Any]],
        keyword_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not response_rows or not keyword_items:
            return []
        respondent_ids = {
            str(item.get("respondent_id", "")).strip()
            for item in response_rows
            if str(item.get("respondent_id", "")).strip()
        }
        respondent_total = max(len(respondent_ids), 1)
        keyword_stats: list[dict[str, Any]] = []

        for kw_item in keyword_items[:20]:
            keyword = str(kw_item.get("name", "")).strip()
            if not keyword:
                continue
            matched = [item for item in response_rows if keyword.lower() in str(item.get("text", "")).lower()]
            if not matched:
                continue
            covered = {
                str(item.get("respondent_id", "")).strip()
                for item in matched
                if str(item.get("respondent_id", "")).strip()
            }
            total = len(matched)
            pos = sum(1 for item in matched if item.get("label") == "positive")
            neu = sum(1 for item in matched if item.get("label") == "neutral")
            neg = sum(1 for item in matched if item.get("label") == "negative")
            keyword_stats.append(
                {
                    "keyword": keyword,
                    "count": int(kw_item.get("value", total)),
                    "coverage": len(covered) / respondent_total,
                    "sentiment": {
                        "positive": pos / total if total else 0.0,
                        "neutral": neu / total if total else 0.0,
                        "negative": neg / total if total else 0.0,
                    },
                }
            )
        return keyword_stats[:15]

    # 构建，服务于增量分析流水线流程。
    def _build_topic_sentiment(
        response_rows: list[dict[str, Any]],
        topics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not response_rows or not topics:
            return []
        topic_rows: list[dict[str, Any]] = []
        for topic in topics[:10]:
            topic_name = str(topic.get("topic", "")).strip()
            topic_keywords = [str(k).strip().lower() for k in topic.get("keywords", []) if str(k).strip()]
            if not topic_keywords:
                topic_keywords = [token.lower() for token in _tokenize(topic_name)]
            if not topic_keywords:
                continue
            matched = [
                item
                for item in response_rows
                if any(keyword in str(item.get("text", "")).lower() for keyword in topic_keywords)
            ]
            if not matched:
                continue
            total = len(matched)
            pos = sum(1 for item in matched if item.get("label") == "positive")
            neu = sum(1 for item in matched if item.get("label") == "neutral")
            neg = sum(1 for item in matched if item.get("label") == "negative")
            topic_rows.append(
                {
                    "topic": topic_name,
                    "count": total,
                    "sentiment": {
                        "positive": pos / total if total else 0.0,
                        "neutral": neu / total if total else 0.0,
                        "negative": neg / total if total else 0.0,
                    },
                }
            )
        return topic_rows

    # 构建，服务于增量分析流水线流程。
    def _build_representative_quotes(
        response_rows: list[dict[str, Any]],
        topics: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not response_rows or not topics:
            return []
        output: list[dict[str, Any]] = []
        for topic in topics[:8]:
            topic_name = str(topic.get("topic", "")).strip()
            topic_keywords = [str(k).strip().lower() for k in topic.get("keywords", []) if str(k).strip()]
            if not topic_keywords:
                topic_keywords = [token.lower() for token in _tokenize(topic_name)]
            if not topic_keywords:
                continue
            matched = [
                item
                for item in response_rows
                if any(keyword in str(item.get("text", "")).lower() for keyword in topic_keywords)
            ]
            if not matched:
                continue
            matched.sort(key=lambda item: len(str(item.get("text", "")).strip()), reverse=True)
            quotes = []
            for item in matched[:3]:
                quotes.append(
                    {
                        "text": str(item.get("text", "")).strip(),
                        "label": str(item.get("label", "neutral")),
                        "respondent_id": str(item.get("respondent_id", "")),
                    }
                )
            output.append({"topic": topic_name, "quotes": quotes})
        return output

    results: dict[str, dict[str, Any]] = {}
    for item in subjective_items:
        question_id = item["question_id"]
        question_text = item.get("question_text", "")
        raw_texts = [str(t).strip() for t in item.get("raw_texts", []) if str(t).strip()]
        respondent_texts = item.get("respondent_texts", [])
        clipped_texts = raw_texts[:max_subjective_texts]
        clipped_respondents = respondent_texts[:max_question_respondent_rows]

        cache_source = "||".join(clipped_texts)
        cache_key = "textq:" + hashlib.sha256(
            f"{TEXT_ANALYTICS_VERSION}|{SENTIMENT_ALGO_VERSION}|{question_id}|{int(include_nlp)}|{cache_source}".encode("utf-8", errors="ignore")
        ).hexdigest()
        cached_payload = get_nlp_summary_cache(cache_key)
        if cached_payload:
            results[question_id] = cached_payload
            continue

        response_sentiments = []
        sentiment_labeled_rows: list[dict[str, Any]] = []
        sentiment_distribution = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
        if include_nlp and clipped_respondents:
            by_respondent = analyze_sentiment_by_respondent(clipped_respondents)
            sentiment_distribution = {
                "positive": by_respondent.get("positive", 0.0),
                "neutral": by_respondent.get("neutral", 0.0),
                "negative": by_respondent.get("negative", 0.0),
            }
            respondent_map = {
                str(row.get("respondent_id", "")).strip(): {
                    "label": str(row.get("label", "neutral")),
                    "score": float(row.get("score", 0.0) or 0.0),
                    "text_count": int(row.get("text_count", 0) or 0),
                }
                for row in by_respondent.get("respondents", [])
            }
            for row in clipped_respondents:
                rid = str(row.get("respondent_id", "")).strip()
                text = str(row.get("text", "")).strip()
                if not rid or not text:
                    continue
                meta = respondent_map.get(rid)
                if not meta:
                    continue
                sentiment_labeled_rows.append(
                    {
                        "respondent_id": rid,
                        "text": text,
                        "label": meta["label"],
                        "score": meta["score"],
                        "text_count": meta["text_count"],
                    }
                )
            if include_response_details:
                response_sentiments = [
                    {
                        "respondent_id": row["respondent_id"],
                        "score": row.get("score", 0.0),
                        "label": row["label"],
                        "text_count": row.get("text_count", 1),
                        "text": row["text"],
                    }
                    for row in sentiment_labeled_rows[:500]
                ]

        topics = _build_topic_summary_simple(clipped_texts) if include_nlp else []
        keywords = _build_keywords_simple(clipped_texts) if include_nlp else []
        keyword_stats = _build_keyword_stats(sentiment_labeled_rows, keywords) if include_nlp else []
        topic_sentiment = _build_topic_sentiment(sentiment_labeled_rows, topics) if include_nlp else []
        representative_quotes = _build_representative_quotes(sentiment_labeled_rows, topics) if include_nlp else []

        payload = {
            "question_id": question_id,
            "question_text": question_text,
            "response_count": len(raw_texts),
            "topics": topics,
            "keywords": keywords,
            "sentiment": sentiment_distribution,
            "responses": response_sentiments,
            "keyword_stats": keyword_stats,
            "topic_sentiment": topic_sentiment,
            "representative_quotes": representative_quotes,
            "raw_texts": clipped_texts,
        }
        results[question_id] = payload
        set_nlp_summary_cache(cache_key, payload)
    return results


# 构建，服务于增量分析流水线流程。
def _build_topic_summary(subjective_texts: list[str], text_batch_size: int, enable_topic_model: bool) -> list[dict[str, Any]]:
    if len(subjective_texts) < 2:
        return []
    if not enable_topic_model:
        return _build_topic_summary_fallback(subjective_texts, text_batch_size)

    try:
        from backend.nlp.topic_model import TopicExtractor

        extractor = TopicExtractor()
        merged: Counter[str] = Counter()
        merged_keywords: dict[str, Counter[str]] = {}
        for chunk in _iter_batches(subjective_texts[:1000], size=text_batch_size):
            topics = extractor.extract_topics(chunk)
            for item in topics:
                topic_name = str(item.get("topic", "")).strip()
                if not topic_name:
                    continue
                merged[topic_name] += int(item.get("count", 0))
                merged_keywords.setdefault(topic_name, Counter()).update(item.get("keywords", []))
        if merged:
            results = []
            for topic_name, count in merged.most_common(10):
                keywords = [k for k, _ in merged_keywords.get(topic_name, Counter()).most_common(6)]
                results.append({"topic": topic_name, "count": count, "keywords": keywords})
            return results
    except Exception:
        pass
    return _build_topic_summary_fallback(subjective_texts, text_batch_size)


# 构建，服务于增量分析流水线流程。
def _build_llm_inputs(
    top_insights: list[dict[str, Any]],
    topic_summary: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objective_insights = [
        {
            "question_id": item["question_id"],
            "question_text": item.get("question_text", ""),
            "metrics": item["features"],
            "score": item["score"],
        }
        for item in top_insights
        if item["question_type"] != "text"
    ]
    return objective_insights, topic_summary


# 构建，服务于增量分析流水线流程。
def _build_debug_payload(analyzer_results: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    objective_items = analyzer_results.get("objective", [])
    subjective_items = analyzer_results.get("subjective", [])

    question_types = [
        {
            "question_id": item["question_id"],
            "question_text": item.get("question_text", ""),
            "question_type": item["question_type"],
            "sample_size": item.get("sample_size", 0),
        }
        for item in objective_items + subjective_items
    ]

    text_questions = [
        {
            "question_id": item["question_id"],
            "question_text": item.get("question_text", ""),
            "response_count": len(item.get("raw_texts", [])),
            "preview": item.get("raw_texts", [])[:2],
        }
        for item in subjective_items
    ]

    return {"question_types": question_types, "text_questions": text_questions}


# 构建，服务于增量分析流水线流程。
def _build_question_results(
    analyzer_results: dict[str, list[dict[str, Any]]],
    scores: dict[str, dict[str, Any]],
    text_question_analytics: dict[str, dict[str, Any]],
    chart_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    chart_overrides = chart_overrides or {}
    objective_lookup = {item["question_id"]: item for item in analyzer_results.get("objective", [])}
    subjective_lookup = {item["question_id"]: item for item in analyzer_results.get("subjective", [])}

    results: list[dict[str, Any]] = []

    for question_id, score_info in scores.items():
        question_type = score_info.get("question_type", "unknown")
        features = score_info.get("features", {})
        selected_override = normalize_chart_override(question_type, chart_overrides.get(question_id))
        recommended = select_chart_type(question_type, features).get("chart_type", "bar")

        source = objective_lookup.get(question_id) or subjective_lookup.get(question_id) or {}
        distribution = features.get("distribution", {}) if isinstance(features, dict) else {}
        results.append(
            {
                "question_id": question_id,
                "question_text": score_info.get("question_text", "") or source.get("question_text", ""),
                "question_type": question_type,
                "sample_size": int(features.get("sample_size", 0)),
                "score": score_info.get("final_score", 0.0),
                "base_score": score_info.get("base_score", 0.0),
                "features": features,
                "score_details": score_info.get("details", {}),
                "chart_options": get_chart_options(question_type),
                "recommended_chart": selected_override or recommended,
                "option_rows": [
                    {"option": str(k), "count": int(v)}
                    for k, v in sorted(distribution.items(), key=lambda x: x[1], reverse=True)
                ],
                "raw_values": source.get("raw_values", []) if question_type in {"numeric", "likert"} else [],
                "text_analysis": text_question_analytics.get(question_id, {}) if question_type == "text" else {},
            }
        )

    results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return results


# 构建，服务于增量分析流水线流程。
def _build_quality_metrics(
    analyzer_results: dict[str, list[dict[str, Any]]],
    topic_summary: list[dict[str, Any]],
    keyword_summary: list[dict[str, Any]],
    llm_report: str | None,
    scores: dict[str, dict[str, Any]] | None = None,
    sentiment_result: dict[str, Any] | None = None,
    previous_report: str | None = None,
) -> dict[str, Any]:
    objective_count = len(analyzer_results.get("objective", []))
    subjective_count = len(analyzer_results.get("subjective", []))
    total = max(objective_count + subjective_count, 1)

    report_words = len(str(llm_report or "").split())
    explainability_score = min(report_words / 240.0, 1.0) if llm_report else 0.0

    metrics = {
        "structured_coverage": round(objective_count / total, 4),
        "semantic_coverage": round(subjective_count / total, 4),
        "cluster_topic_count": len(topic_summary),
        "report_explainability": round(explainability_score, 4),
    }
    metrics["report_quality"] = evaluate_report_quality_variants(
        analyzer_results=analyzer_results,
        topics=topic_summary,
        keywords=keyword_summary,
        llm_report=llm_report,
        scores=scores,
        sentiment=sentiment_result,
        previous_report=previous_report,
    )
    return metrics


# 执行，服务于增量分析流水线流程。
def run_analysis(
    batch_ids: list[str],
    top_n: int = 8,
    per_type_limit: dict[str, int] | None = None,
    include_nlp: bool = False,
    include_llm: bool = True,
    chart_overrides: dict[str, str] | None = None,
    llm_source: str | None = None,
    performance_mode: str | None = None,
    progress_callback: Callable[[float, str], None] | None = None,
) -> dict[str, Any]:
    # 生成报告，服务于增量分析流水线流程。
    def _report(progress: float, stage: str) -> None:
        if progress_callback:
            try:
                progress_callback(progress, stage)
            except Exception:
                pass

    _report(5, "loading_data")
    df_long = load_data_by_batches(batch_ids)
    if df_long.empty:
        return {"error": "No survey data found for selected batch."}
    _report(12, "detecting_question_types")

    profile_name = (performance_mode or PERFORMANCE_MODE or "fast").lower()
    profile = dict(PERFORMANCE_PROFILES.get(profile_name, PERFORMANCE_PROFILES["fast"]))
    effective_include_llm = include_llm and bool(profile["enable_llm"])
    agent_context = AgentContext(
        include_nlp=include_nlp,
        include_llm=effective_include_llm,
        performance_mode=profile_name,
    )
    task_plan = build_agent_plan(agent_context)

    analyzer_results = process_all_questions(df_long)
    _report(26, "extracting_features")
    feature_list = extract_features(analyzer_results)
    _report(34, "scoring_questions")
    scores = compute_scores(feature_list)

    insights = select_top_insights(
        scores,
        top_n=top_n,
        per_type_limit=per_type_limit or {"likert": 3, "single_choice": 3, "multiple_choice": 3, "numeric": 3},
    )
    _report(42, "selecting_top_insights")

    subjective_texts, question_texts, respondent_texts = _collect_subjective_payload(
        analyzer_results.get("subjective", [])
    )
    is_large_scale = (len(df_long) >= LARGE_SCALE_ROW_THRESHOLD) or (
        len(subjective_texts) >= LARGE_SCALE_TEXT_THRESHOLD
    )
    agent_context.has_subjective_text = bool(subjective_texts)
    agent_context.large_scale = is_large_scale
    task_plan = build_agent_plan(agent_context)
    if include_nlp and is_large_scale and profile_name != "accurate":
        profile["text_batch_size"] = max(int(profile["text_batch_size"]), 320)
        profile["max_subjective_texts"] = min(int(profile["max_subjective_texts"]), 800)
        profile["max_respondent_texts"] = min(int(profile["max_respondent_texts"]), 1500)
        profile["max_question_respondent_rows"] = min(int(profile["max_question_respondent_rows"]), 120)
        profile["enable_topic_model"] = False

    sentiment_result = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
    sentiment_detail = {"respondent_count": 0, "respondents": []}
    topic_summary: list[dict[str, Any]] = []
    keyword_summary: list[dict[str, Any]] = []
    max_subjective_texts = int(profile["max_subjective_texts"])

    if include_nlp:
        _report(50, "running_nlp")
        max_respondent_texts = int(profile["max_respondent_texts"])
        text_batch_size = int(profile["text_batch_size"])

        if respondent_texts:
            respondents_all: list[dict[str, Any]] = []
            for chunk in _iter_batches(respondent_texts[:max_respondent_texts], size=text_batch_size):
                chunk_result = analyze_sentiment_by_respondent(chunk)
                respondents_all.extend(chunk_result.get("respondents", []))

            if respondents_all:
                total = len(respondents_all)
                positive = sum(1 for item in respondents_all if item.get("label") == "positive")
                neutral = sum(1 for item in respondents_all if item.get("label") == "neutral")
                negative = sum(1 for item in respondents_all if item.get("label") == "negative")
                sentiment_result = {
                    "positive": positive / total,
                    "neutral": neutral / total,
                    "negative": negative / total,
                }
                sentiment_detail = {
                    "respondent_count": total,
                    "respondents": respondents_all[: (120 if is_large_scale else 500)],
                }
        else:
            scored_texts: list[str] = []
            for chunk in _iter_batches(subjective_texts[:max_subjective_texts], size=text_batch_size):
                scored_texts.extend(chunk)
            sentiment_result = analyze_sentiment_texts(scored_texts)
        topic_summary = _build_topic_summary(
            subjective_texts[:max_subjective_texts],
            text_batch_size=text_batch_size,
            enable_topic_model=bool(profile["enable_topic_model"]),
        )
        keyword_summary = _build_keyword_summary(question_texts, text_batch_size=text_batch_size)
        _report(72, "nlp_completed")
    else:
        _report(60, "skipping_nlp")

    chart_candidates = [
        {
            "question_id": item["question_id"],
            "question_text": item.get("question_text", ""),
            "question_type": item.get("question_type", ""),
            "features": item.get("features", {}),
            "score": item.get("final_score", 0.0),
        }
        for item in scores.values()
        if item.get("question_type") in {"single_choice", "multiple_choice", "likert", "numeric"}
    ]
    chart_candidates.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    charts = generate_chart_payload(
        chart_candidates,
        analyzer_results,
        sentiment_result,
        topic_summary,
        keyword_summary,
        chart_overrides=chart_overrides,
    )
    report_charts = generate_chart_payload(
        insights["selected"],
        analyzer_results,
        sentiment_result,
        topic_summary,
        keyword_summary,
        chart_overrides=chart_overrides,
    )
    _report(82, "building_charts")

    objective_insights, semantic_insights = _build_llm_inputs(insights["selected"], topic_summary)
    llm_report = None
    if effective_include_llm and include_nlp:
        _report(90, "generating_llm_report")
        llm_report = analyze_with_llm(
            objective_insights=objective_insights,
            subjective_insights=semantic_insights,
            sentiment_result=sentiment_result,
            llm_source=llm_source,
        )

    save_nlp_artifacts(
        batch_ids,
        {"topics": topic_summary, "keywords": keyword_summary, "sentiment": sentiment_result},
    )

    text_question_analytics = _build_text_question_analytics(
        analyzer_results.get("subjective", []),
        include_nlp=include_nlp,
        max_subjective_texts=max_subjective_texts,
        include_response_details=not is_large_scale,
        max_question_respondent_rows=int(profile.get("max_question_respondent_rows", 320)),
    )

    question_results = _build_question_results(
        analyzer_results=analyzer_results,
        scores=scores,
        text_question_analytics=text_question_analytics,
        chart_overrides=chart_overrides,
    )
    _report(98, "finalizing_result")

    result = {
        "batch_ids": batch_ids,
        "analysis_mode": "deep" if include_nlp else "fast",
        "performance_mode": profile_name,
        "sample_size": int(df_long["respondent_id"].nunique()),
        "question_count": int(df_long["question_id"].nunique()),
        "question_breakdown": {
            "objective": len(analyzer_results.get("objective", [])),
            "subjective": len(analyzer_results.get("subjective", [])),
        },
        "text_stats": {"question_count": len(question_texts), "response_count": len(subjective_texts)},
        "scores": scores,
        "question_results": question_results,
        "top_insights": insights["selected"],
        "insight_meta": insights["meta"],
        "sentiment": sentiment_result,
        "sentiment_detail": sentiment_detail,
        "topics": topic_summary,
        "keywords": keyword_summary,
        "charts": charts,
        "report_charts": report_charts,
        "llm_analysis": llm_report,
        "llm_source": (llm_source or "api") if llm_report else None,
        "task_trace": serialize_task_trace(task_plan, context=agent_context),
        "agent_design": describe_agent_design(),
        "langchain_agent": summarize_langchain_agent(agent_context),
        "quality_metrics": _build_quality_metrics(
            analyzer_results,
            topic_summary,
            keyword_summary,
            llm_report,
            scores=scores,
            sentiment_result=sentiment_result,
        ),
        "debug": _build_debug_payload(analyzer_results),
        "runtime": NLPModelManager.get_runtime_info() if include_nlp else {"device": "cpu", "gpu_available": False},
        "performance_guard": {
            "is_large_scale": is_large_scale,
            "topic_model_enabled": bool(profile.get("enable_topic_model")),
            "profile_name": profile_name,
        },
        "sentiment_algo_version": SENTIMENT_ALGO_VERSION,
    }
    _report(100, "completed")
    return result
