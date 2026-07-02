import pandas as pd
import csv


QUESTIONNAIRE_HEADERS = {"题号", "题型", "题目", "受访者答案"}


# 处理，服务于问卷数据管理流程。
def _looks_like_questionnaire_export(df: pd.DataFrame) -> bool:
    if df is None or df.empty:
        return False

    sample = df.head(12).fillna("").astype(str)
    for _, row in sample.iterrows():
        values = {value.strip() for value in row.tolist() if value.strip()}
        if QUESTIONNAIRE_HEADERS.issubset(values):
            return True
    return False


# 读取，服务于问卷数据管理流程。
def _read_file(file_path: str, skiprows: int | None = None) -> pd.DataFrame:
    if file_path.endswith(".csv"):
        with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file)
            rows = list(reader)

        if skiprows:
            rows = rows[skiprows:]

        rows = [row for row in rows if any(str(cell).strip() for cell in row)]
        if not rows:
            return pd.DataFrame()

        max_columns = max(len(row) for row in rows)
        normalized_rows = [row + [""] * (max_columns - len(row)) for row in rows]
        header = normalized_rows[0]
        data_rows = normalized_rows[1:]

        return pd.DataFrame(data_rows, columns=header)

    if file_path.endswith(".xlsx"):
        return pd.read_excel(file_path, skiprows=skiprows)

    raise ValueError(f"unsupported file format: {file_path}")


# 加载，服务于问卷数据管理流程。
def load_file(file_path, skip_meta_rows=4):

    try:
        raw_df = _read_file(file_path, skiprows=None)
        raw_df.columns = raw_df.columns.astype(str).str.strip()

        if _looks_like_questionnaire_export(raw_df):
            return raw_df

        df = _read_file(file_path, skiprows=skip_meta_rows)
        df.columns = df.columns.astype(str).str.strip()
        return df

    except Exception as e:
        print(f"读取失败: {file_path} -> {e}")
        return pd.DataFrame()
