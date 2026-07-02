from __future__ import annotations

import os
import re

import pandas as pd


TEXT_HINT_KEYWORDS = [
    "主观",
    "开放",
    "描述",
    "建议",
    "comment",
    "feedback",
    "reason",
    "suggest",
    "text",
]

QUESTIONNAIRE_HEADERS = ["题号", "题型", "题目", "选项/说明", "受访者答案"]
QUESTIONNAIRE_REQUIRED = set(QUESTIONNAIRE_HEADERS)


# 安全计算，服务于问卷数据管理流程。
def _safe_id_fragment(text: str) -> str:
    value = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", str(text or "").strip())
    value = value.strip("_")
    return value or "unknown"


# 处理，服务于问卷数据管理流程。
def is_identifier_column(series: pd.Series) -> bool:
    if len(series) == 0:
        return False

    unique_ratio = series.nunique() / len(series)
    if unique_ratio > 0.98:
        return True

    name = str(series.name or "")
    return any(keyword in name for keyword in ["编号", "ID", "学号", "工号"])


# 识别，服务于问卷数据管理流程。
def detect_column_type(series: pd.Series) -> str:
    series = series.dropna()
    if series.empty:
        return "categorical"

    if is_identifier_column(series):
        return "metadata"

    column_name = str(series.name or "").strip().lower()
    if any(keyword in column_name for keyword in TEXT_HINT_KEYWORDS):
        return "text"

    text_series = series.astype(str).str.strip()
    text_series = text_series[text_series != ""]
    if text_series.empty:
        return "categorical"

    avg_length = text_series.str.len().mean()
    unique_ratio = text_series.nunique() / max(len(text_series), 1)
    long_text_ratio = (text_series.str.len() >= 8).mean()

    if pd.to_numeric(series, errors="coerce").notna().sum() > len(series) * 0.7:
        return "numeric"
    if avg_length >= 12 or (avg_length >= 8 and long_text_ratio >= 0.5) or (avg_length >= 6 and unique_ratio >= 0.7):
        return "text"
    if text_series.nunique() <= 12:
        return "categorical"
    if unique_ratio >= 0.6:
        return "text"
    return "categorical"


# 处理，服务于问卷数据管理流程。
def _find_questionnaire_header_row(df: pd.DataFrame) -> int | None:
    sample = df.head(20).fillna("").astype(str)
    for index, row in sample.iterrows():
        values = {value.strip() for value in row.tolist() if value and value.strip()}
        if QUESTIONNAIRE_REQUIRED.issubset(values):
            return int(index)
    return None


# 提取，服务于问卷数据管理流程。
def _extract_metadata(df: pd.DataFrame, header_row: int) -> dict[str, str]:
    metadata: dict[str, str] = {}
    pre_header = df.iloc[:header_row].fillna("")
    for _, row in pre_header.iterrows():
        values = [str(value).strip() for value in row.tolist() if str(value).strip()]
        if len(values) >= 2:
            metadata[values[0]] = values[1]
    return metadata


# 映射，服务于问卷数据管理流程。
def _map_question_type(question_type: str, answer: str, description: str) -> str:
    normalized = str(question_type or "").strip().lower()
    answer_text = str(answer or "").strip()
    description_text = str(description or "").strip().lower()

    if any(k in normalized for k in ["主观", "开放", "文本", "简答", "text", "comment", "feedback"]):
        return "text"
    if any(k in normalized for k in ["多选", "multiple"]):
        return "categorical"
    if any(k in normalized for k in ["单选", "single"]):
        return "categorical"
    if any(k in normalized for k in ["量表", "likert", "scale", "rating", "评分", "打分"]):
        return "likert"
    if any(k in normalized for k in ["填空", "数值", "数字", "numeric"]):
        if pd.to_numeric(pd.Series([answer_text]), errors="coerce").notna().iloc[0]:
            return "numeric"
        if any(k in description_text for k in ["文本", "说明", "简答", "text", "comment"]):
            return "text"
        return "text"

    if pd.to_numeric(pd.Series([answer_text]), errors="coerce").notna().iloc[0]:
        return "numeric"
    return "text"


# 标准化，服务于问卷数据管理流程。
def _standardize_questionnaire_rows(
    df: pd.DataFrame,
    batch_id: str | None = None,
    source_name: str | None = None,
) -> pd.DataFrame:
    header_row = _find_questionnaire_header_row(df)
    if header_row is None:
        return pd.DataFrame()

    metadata = _extract_metadata(df, header_row)
    source_hint = _safe_id_fragment(os.path.splitext(str(source_name or ""))[0])
    respondent_id = (
        metadata.get("受访者编号")
        or metadata.get("编号")
        or metadata.get("respondent_id")
        or source_hint
        or "unknown"
    )
    respondent_id = _safe_id_fragment(respondent_id)
    if batch_id:
        respondent_id = f"{batch_id}_{respondent_id}"

    body = df.iloc[header_row:].reset_index(drop=True).copy()
    body.columns = [str(value).strip() for value in body.iloc[0].tolist()]
    body = body.iloc[1:].reset_index(drop=True)
    body = body.dropna(axis=0, how="all").dropna(axis=1, how="all")

    if not QUESTIONNAIRE_REQUIRED.issubset(set(body.columns)):
        return pd.DataFrame()

    rows: list[dict[str, str]] = []
    for _, row in body.iterrows():
        question_id = str(row.get("题号", "")).strip()
        answer = str(row.get("受访者答案", "")).strip()
        if not question_id or not answer or answer.lower() in {"nan", "none", "null"}:
            continue

        question_type = _map_question_type(
            row.get("题型", ""),
            answer,
            row.get("选项/说明", ""),
        )

        if question_type == "categorical" and ("," in answer or ";" in answer or "，" in answer or "；" in answer):
            parts = re.split(r"[;,，；]", answer)
            for part in parts:
                option = part.strip()
                if not option:
                    continue
                rows.append(
                    {
                        "respondent_id": respondent_id,
                        "question_id": question_id,
                        "question_text": str(row.get("题目", "")).strip(),
                        "question_type": question_type,
                        "answer": option,
                    }
                )
            continue

        rows.append(
            {
                "respondent_id": respondent_id,
                "question_id": question_id,
                "question_text": str(row.get("题目", "")).strip(),
                "question_type": question_type,
                "answer": answer,
            }
        )

    return pd.DataFrame(rows)


# 标准化，服务于问卷数据管理流程。
def standardize_to_long(
    df: pd.DataFrame,
    batch_id: str | None = None,
    source_name: str | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)
    df.columns = df.columns.astype(str).str.strip()
    respondent_col = df.columns[0]

    source_hint = _safe_id_fragment(os.path.splitext(str(source_name or ""))[0])
    for col in df.columns[1:]:
        qtype = detect_column_type(df[col])
        for idx, val in enumerate(df[col]):
            if pd.isna(val):
                continue

            respondent_id = str(df.loc[idx, respondent_col]).strip()
            if not respondent_id or respondent_id.lower() in {"nan", "none", "null", "unknown"}:
                respondent_id = f"{source_hint}_{idx+1}"
            respondent_id = _safe_id_fragment(respondent_id)
            if batch_id:
                respondent_id = f"{batch_id}_{respondent_id}"

            if qtype == "categorical" and isinstance(val, str) and ("," in val or ";" in val or "，" in val or "；" in val):
                parts = re.split(r"[;,，；]", val)
                for part in parts:
                    option = str(part).strip()
                    if not option:
                        continue
                    rows.append(
                        {
                            "respondent_id": respondent_id,
                            "question_id": col,
                            "question_text": col,
                            "question_type": qtype,
                            "answer": option,
                        }
                    )
            else:
                rows.append(
                    {
                        "respondent_id": respondent_id,
                        "question_id": col,
                        "question_text": col,
                        "question_type": qtype,
                        "answer": str(val),
                    }
                )

    return pd.DataFrame(rows)


# 智能标准化，服务于问卷数据管理流程。
def smart_standardize(
    df: pd.DataFrame,
    batch_id: str | None = None,
    source_name: str | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    try:
        questionnaire_df = _standardize_questionnaire_rows(df, batch_id=batch_id, source_name=source_name)
        if not questionnaire_df.empty:
            return questionnaire_df
        return standardize_to_long(df, batch_id=batch_id, source_name=source_name)
    except Exception as exc:
        print("standardize failed:", exc)
        return pd.DataFrame()


# 格式化，服务于问卷数据管理流程。
def to_wide_format(df_long: pd.DataFrame) -> pd.DataFrame:
    if df_long.empty:
        return df_long

    try:
        return (
            df_long.pivot_table(
                index="respondent_id",
                columns="question_id",
                values="answer",
                aggfunc="first",
            )
            .reset_index()
        )
    except Exception as exc:
        print("pivot failed:", exc)
        return pd.DataFrame()
