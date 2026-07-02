import re
from typing import Any

import pandas as pd


TEXT_TYPES = {"text", "subjective", "open_text"}
CHOICE_SPLIT_PATTERN = re.compile(r"[;,/|]")
LIKERT_HINT_PATTERN = re.compile(
    r"(likert|scale|rating|程度|满意|同意|评价|频率|质量|压力)",
    re.IGNORECASE,
)


# 处理，服务于问卷结构化分析流程。
def _clean_answers(series: pd.Series) -> pd.Series:
    cleaned = series.dropna().astype(str).str.strip()
    cleaned = cleaned[cleaned != ""]
    cleaned = cleaned[~cleaned.str.lower().isin({"nan", "none", "null"})]
    return cleaned


# 计算数值题，服务于问卷结构化分析流程。
def _numeric_values(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").dropna()


# 处理，服务于问卷结构化分析流程。
def _is_likert(values: list[float]) -> bool:
    if len(values) < 2:
        return False
    integer_values = [int(v) for v in values if float(v).is_integer()]
    if len(integer_values) / max(len(values), 1) < 0.9:
        return False
    min_value = min(integer_values)
    max_value = max(integer_values)
    if min_value < 1 or max_value > 7:
        return False
    unique_count = len(set(integer_values))
    return 2 <= unique_count <= 7


# 处理，服务于问卷结构化分析流程。
def _looks_like_likert_question(question_df: pd.DataFrame) -> bool:
    declared_type = str(question_df["question_type"].iloc[0]).strip().lower()
    if declared_type in {"likert", "scale", "rating", "scale_5", "scale_7"}:
        return True

    if any(keyword in declared_type for keyword in ["量表", "评分", "打分"]):
        return True

    question_text = str(question_df.get("question_text", pd.Series([""])).iloc[0]).strip()
    return bool(LIKERT_HINT_PATTERN.search(question_text))


# 识别，服务于问卷结构化分析流程。
def _detect_question_type(question_df: pd.DataFrame, answers: pd.Series) -> str:
    declared_type = str(question_df["question_type"].iloc[0]).lower()
    if declared_type in TEXT_TYPES:
        return "text"
    if declared_type in {"likert", "scale", "rating"}:
        return "likert"
    if any(keyword in declared_type for keyword in ["量表", "评分", "打分"]):
        return "likert"

    answer_lengths = answers.astype(str).str.len()
    avg_length = float(answer_lengths.mean()) if not answer_lengths.empty else 0.0
    unique_ratio = answers.nunique() / max(len(answers), 1)

    numeric_values = _numeric_values(answers)
    numeric_ratio = len(numeric_values) / max(len(answers), 1)
    respondent_answer_counts = question_df.groupby("respondent_id")["answer"].nunique().fillna(0)
    is_multi = respondent_answer_counts.max() > 1

    if avg_length >= 12 or (avg_length >= 8 and unique_ratio >= 0.7):
        return "text"

    if numeric_ratio >= 0.9:
        numeric_list = numeric_values.tolist()
        if _is_likert(numeric_list) and _looks_like_likert_question(question_df):
            return "likert"
        return "numeric"

    if is_multi:
        return "multiple_choice"

    if answers.nunique() <= 12:
        return "single_choice"

    return "text"


# 构建，服务于问卷结构化分析流程。
def _build_choice_distribution(question_df: pd.DataFrame) -> dict[str, Any]:
    counts = (
        question_df["answer"]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .to_dict()
    )
    total = sum(counts.values())
    return {
        "category_counts": counts,
        "sample_size": int(question_df["respondent_id"].nunique()),
        "response_count": int(total),
    }


# 构建，服务于问卷结构化分析流程。
def _build_numeric_payload(question_df: pd.DataFrame, answers: pd.Series) -> dict[str, Any] | None:
    numeric_values = _numeric_values(answers)
    if numeric_values.empty:
        return None

    return {
        "raw_values": numeric_values.astype(float).tolist(),
        "sample_size": int(question_df["respondent_id"].nunique()),
    }


# 构建，服务于问卷结构化分析流程。
def _build_text_payload(question_df: pd.DataFrame, answers: pd.Series) -> dict[str, Any] | None:
    texts = answers.astype(str).tolist()
    if not texts:
        return None

    respondent_texts = [
        {
            "respondent_id": str(row["respondent_id"]),
            "text": str(row["answer"]).strip(),
        }
        for _, row in question_df.iterrows()
        if str(row["answer"]).strip()
    ]

    return {
        "raw_texts": texts,
        "respondent_texts": respondent_texts,
        "sample_size": int(question_df["respondent_id"].nunique()),
    }


# 处理，服务于问卷结构化分析流程。
def process_all_questions(df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if df is None or df.empty:
        return {"objective": [], "subjective": []}

    results = {"objective": [], "subjective": []}

    for question_id, question_df in df.groupby("question_id", sort=False):
        working_df = question_df.copy()
        working_df["answer"] = _clean_answers(working_df["answer"])
        working_df = working_df.dropna(subset=["answer"])

        if working_df.empty:
            continue

        detected_type = _detect_question_type(working_df, working_df["answer"])
        payload: dict[str, Any] | None

        if detected_type in {"numeric", "likert"}:
            payload = _build_numeric_payload(working_df, working_df["answer"])
        elif detected_type in {"single_choice", "multiple_choice"}:
            payload = _build_choice_distribution(working_df)
        else:
            payload = _build_text_payload(working_df, working_df["answer"])

        if not payload:
            continue

        item = {
            "question_id": str(question_id),
            "question_text": str(question_df.get("question_text", pd.Series([""])).iloc[0]).strip(),
            "question_type": detected_type,
            "original_type": str(question_df["question_type"].iloc[0]),
            **payload,
        }

        if detected_type == "text":
            results["subjective"].append(item)
        else:
            results["objective"].append(item)

    return results
