import json
import os
import sqlite3
import uuid
import hashlib
import secrets
from datetime import datetime
from typing import Any

import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "survey.db")


# 初始化，服务于问卷数据管理流程。
def init_db() -> None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS responses (
            respondent_id TEXT,
            question_id TEXT,
            question_text TEXT,
            question_type TEXT,
            answer TEXT,
            batch_id TEXT,
            owner_user_id INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_ids TEXT,
            created_at TEXT,
            result TEXT,
            user_id INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nlp_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT,
            question_id TEXT,
            artifact_type TEXT,
            payload TEXT,
            created_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_tasks (
            task_id TEXT PRIMARY KEY,
            batch_ids TEXT,
            include_nlp INTEGER,
            include_llm INTEGER,
            performance_mode TEXT,
            chart_overrides TEXT,
            status TEXT,
            analysis_id INTEGER,
            error TEXT,
            created_at TEXT,
            updated_at TEXT,
            user_id INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            created_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            created_at TEXT,
            expires_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS nlp_summary_cache (
            cache_key TEXT PRIMARY KEY,
            payload TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            batch_ids TEXT,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON responses(batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_question_id ON responses(question_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_respondent ON responses(respondent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nlp_batch ON nlp_artifacts(batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)")

    cursor.execute("PRAGMA table_info(responses)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if "question_text" not in existing_columns:
        cursor.execute("ALTER TABLE responses ADD COLUMN question_text TEXT DEFAULT ''")
    if "owner_user_id" not in existing_columns:
        cursor.execute("ALTER TABLE responses ADD COLUMN owner_user_id INTEGER")

    cursor.execute("PRAGMA table_info(analysis_history)")
    history_columns = {row[1] for row in cursor.fetchall()}
    if "user_id" not in history_columns:
        cursor.execute("ALTER TABLE analysis_history ADD COLUMN user_id INTEGER")

    cursor.execute("PRAGMA table_info(analysis_tasks)")
    task_columns = {row[1] for row in cursor.fetchall()}
    if "performance_mode" not in task_columns:
        cursor.execute("ALTER TABLE analysis_tasks ADD COLUMN performance_mode TEXT DEFAULT 'balanced'")
    if "progress" not in task_columns:
        cursor.execute("ALTER TABLE analysis_tasks ADD COLUMN progress REAL DEFAULT 0")
    if "stage" not in task_columns:
        cursor.execute("ALTER TABLE analysis_tasks ADD COLUMN stage TEXT DEFAULT ''")
    if "user_id" not in task_columns:
        cursor.execute("ALTER TABLE analysis_tasks ADD COLUMN user_id INTEGER")

    conn.commit()
    conn.close()


# 处理，服务于问卷数据管理流程。
def _hash_password(password: str) -> str:
    return hashlib.sha256(str(password).encode("utf-8", errors="ignore")).hexdigest()


# 创建，服务于问卷数据管理流程。
def create_user(username: str, password: str) -> tuple[bool, str]:
    username = str(username or "").strip()
    password = str(password or "")
    if not username or not password:
        return False, "username and password are required"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    exists = cursor.fetchone()
    if exists:
        conn.close()
        return False, "username already exists"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, created_at)
        VALUES (?, ?, ?)
        """,
        (username, _hash_password(password), now),
    )
    conn.commit()
    conn.close()
    return True, "ok"


# 校验，服务于问卷数据管理流程。
def verify_user(username: str, password: str) -> dict[str, Any] | None:
    username = str(username or "").strip()
    password_hash = _hash_password(password)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, created_at
        FROM users
        WHERE username = ? AND password_hash = ?
        """,
        (username, password_hash),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": int(row[0]), "username": row[1], "created_at": row[2]}


# 创建，服务于问卷数据管理流程。
def create_auth_token(user_id: int, ttl_hours: int = 24 * 7) -> str:
    token = secrets.token_urlsafe(36)
    now_dt = datetime.now()
    created_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now_dt.timestamp() + ttl_hours * 3600)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO auth_tokens (token, user_id, created_at, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (token, int(user_id), created_at, str(expires_at)),
    )
    conn.commit()
    conn.close()
    return token


# 获取，服务于问卷数据管理流程。
def get_user_by_token(token: str) -> dict[str, Any] | None:
    token = str(token or "").strip()
    if not token:
        return None
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.user_id, t.expires_at, u.username
        FROM auth_tokens t
        LEFT JOIN users u ON u.id = t.user_id
        WHERE t.token = ?
        """,
        (token,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    user_id = int(row[0])
    expires_at = float(row[1] or 0)
    username = row[2] or ""

    if expires_at <= datetime.now().timestamp():
        cursor.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        return None

    conn.close()
    return {"id": user_id, "username": username}


# 生成，服务于问卷数据管理流程。
def generate_batch_id() -> str:
    return f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"


# 保存，服务于问卷数据管理流程。
def save_to_db(df: pd.DataFrame, batch_id: str, owner_user_id: int | None = None) -> None:
    if df is None or df.empty:
        return

    working = df.copy()
    working["batch_id"] = batch_id
    working["owner_user_id"] = int(owner_user_id) if owner_user_id is not None else None
    working["respondent_id"] = working["respondent_id"].astype(str)
    working["question_id"] = working["question_id"].astype(str)
    if "question_text" not in working.columns:
        working["question_text"] = ""
    working["question_text"] = working["question_text"].fillna("").astype(str)
    working["question_type"] = working["question_type"].astype(str)
    working["answer"] = working["answer"].astype(str)
    working = working[working["answer"].str.strip() != ""]
    working = working[working["question_id"].str.strip() != ""]
    working = working.drop_duplicates(subset=["respondent_id", "question_id", "answer"])

    conn = sqlite3.connect(DB_NAME)
    working.to_sql("responses", conn, if_exists="append", index=False)
    conn.close()


# 保存，服务于问卷数据管理流程。
def save_nlp_artifacts(batch_ids: list[str], artifacts: dict[str, Any]) -> None:
    if not batch_ids or not artifacts:
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    batch_key = json.dumps(batch_ids, ensure_ascii=False)

    rows = []
    for artifact_type, payload in artifacts.items():
        if not payload:
            continue
        rows.append(
            (
                batch_key,
                "__global__",
                artifact_type,
                json.dumps(payload, ensure_ascii=False),
                created_at,
            )
        )

    if rows:
        cursor.executemany(
            """
            INSERT INTO nlp_artifacts (batch_id, question_id, artifact_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    conn.close()


# 保存，服务于问卷数据管理流程。
def save_analysis_history(batch_ids: list[str], result: dict[str, Any], user_id: int | None = None) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO analysis_history (batch_ids, created_at, result, user_id)
        VALUES (?, ?, ?, ?)
        """,
        (
            json.dumps(batch_ids, ensure_ascii=False),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(result, ensure_ascii=False),
            int(user_id) if user_id is not None else None,
        ),
    )
    analysis_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return int(analysis_id)


# 加载，服务于问卷数据管理流程。
def load_cached_analysis(batch_ids: list[str], analysis_mode: str = "fast", user_id: int | None = None) -> dict[str, Any] | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute(
            """
            SELECT id, result
            FROM analysis_history
            ORDER BY id DESC
            """
        )
    else:
        cursor.execute(
            """
            SELECT id, result
            FROM analysis_history
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (int(user_id),),
        )
    rows = cursor.fetchall()
    conn.close()

    target_batch_ids = list(batch_ids)

    for analysis_id, raw_result in rows:
        try:
            result = json.loads(raw_result)
        except Exception:
            continue

        if result.get("batch_ids") != target_batch_ids:
            continue
        if result.get("analysis_mode") != analysis_mode:
            continue

        result["analysis_id"] = analysis_id
        return result

    return None


# 获取，服务于问卷数据管理流程。
def get_latest_batch_ids(limit: int = 1, user_id: int | None = None) -> list[str]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute(
            """
            SELECT DISTINCT batch_id
            FROM responses
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (limit,),
        )
    else:
        cursor.execute(
            """
            SELECT DISTINCT batch_id
            FROM responses
            WHERE owner_user_id = ?
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (int(user_id), limit),
        )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


# 加载，服务于问卷数据管理流程。
def load_data_by_batches(batch_ids: list[str] | None = None, user_id: int | None = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_NAME)
    if batch_ids:
        placeholder = ",".join(["?"] * len(batch_ids))
        if user_id is None:
            query = f"SELECT * FROM responses WHERE batch_id IN ({placeholder})"
            params = batch_ids
        else:
            query = f"SELECT * FROM responses WHERE batch_id IN ({placeholder}) AND owner_user_id = ?"
            params = [*batch_ids, int(user_id)]
        df = pd.read_sql(query, conn, params=params)
    else:
        if user_id is None:
            df = pd.read_sql("SELECT * FROM responses", conn)
        else:
            df = pd.read_sql("SELECT * FROM responses WHERE owner_user_id = ?", conn, params=[int(user_id)])
    conn.close()
    return df


# 加载，服务于问卷数据管理流程。
def load_analysis_history(user_id: int | None = None) -> list[dict[str, Any]]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute(
            """
            SELECT id, batch_ids, created_at
            FROM analysis_history
            ORDER BY id DESC
            """
        )
    else:
        cursor.execute(
            """
            SELECT id, batch_ids, created_at
            FROM analysis_history
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (int(user_id),),
        )
    rows = cursor.fetchall()

    if user_id is None:
        cursor.execute(
            """
            SELECT DISTINCT batch_id
            FROM responses
            ORDER BY rowid DESC
            """
        )
    else:
        cursor.execute(
            """
            SELECT DISTINCT batch_id
            FROM responses
            WHERE owner_user_id = ?
            ORDER BY rowid DESC
            """,
            (int(user_id),),
        )
    batch_rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        try:
            batch_ids = json.loads(row[1]) if row[1] else []
            if not isinstance(batch_ids, list):
                batch_ids = []
        except Exception:
            batch_ids = []

        history.append(
            {
                "id": row[0],
                "batch_ids": batch_ids,
                "created_at": row[2],
                "source": "analysis",
            }
        )

    existing_batches = {
        tuple(item["batch_ids"])
        for item in history
        if item.get("batch_ids")
    }

    synthetic_id = -1
    for row in batch_rows:
        batch_id = row[0]
        if not batch_id:
            continue
        batch_key = (batch_id,)
        if batch_key in existing_batches:
            continue
        history.append(
            {
                "id": synthetic_id,
                "batch_ids": [batch_id],
                "created_at": "仅上传未生成报告",
                "source": "upload",
            }
        )
        synthetic_id -= 1

    return history


# 加载，服务于问卷数据管理流程。
def load_analysis_by_id(analysis_id: int, user_id: int | None = None) -> dict[str, Any] | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if user_id is None:
        cursor.execute("SELECT result FROM analysis_history WHERE id = ?", (analysis_id,))
    else:
        cursor.execute("SELECT result FROM analysis_history WHERE id = ? AND user_id = ?", (analysis_id, int(user_id)))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row[0])


# 创建，服务于问卷数据管理流程。
def create_analysis_task(
    task_id: str,
    batch_ids: list[str],
    include_nlp: bool,
    include_llm: bool,
    performance_mode: str = "balanced",
    chart_overrides: dict[str, str] | None = None,
    user_id: int | None = None,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO analysis_tasks (
            task_id, batch_ids, include_nlp, include_llm, performance_mode, chart_overrides,
            status, analysis_id, error, created_at, updated_at, progress, stage, user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            json.dumps(batch_ids, ensure_ascii=False),
            1 if include_nlp else 0,
            1 if include_llm else 0,
            performance_mode,
            json.dumps(chart_overrides or {}, ensure_ascii=False),
            "queued",
            now,
            now,
            0.0,
            "queued",
            int(user_id) if user_id is not None else None,
        ),
    )
    conn.commit()
    conn.close()


# 更新，服务于问卷数据管理流程。
def update_analysis_task_status(task_id: str, status: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE analysis_tasks
        SET status = ?, updated_at = ?
        WHERE task_id = ?
        """,
        (status, now, task_id),
    )
    conn.commit()
    conn.close()


# 更新，服务于问卷数据管理流程。
def update_analysis_task_progress(
    task_id: str,
    progress: float,
    stage: str,
    status: str | None = None,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clamped = max(0.0, min(float(progress), 100.0))
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if status:
        cursor.execute(
            """
            UPDATE analysis_tasks
            SET progress = ?, stage = ?, status = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (clamped, stage, status, now, task_id),
        )
    else:
        cursor.execute(
            """
            UPDATE analysis_tasks
            SET progress = ?, stage = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (clamped, stage, now, task_id),
        )
    conn.commit()
    conn.close()


# 处理异步任务，服务于问卷数据管理流程。
def complete_analysis_task(task_id: str, analysis_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE analysis_tasks
        SET status = ?, analysis_id = ?, error = NULL, updated_at = ?, progress = 100, stage = ?
        WHERE task_id = ?
        """,
        ("completed", analysis_id, now, "completed", task_id),
    )
    conn.commit()
    conn.close()


# 处理异步任务，服务于问卷数据管理流程。
def fail_analysis_task(task_id: str, error: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE analysis_tasks
        SET status = ?, error = ?, updated_at = ?, stage = ?
        WHERE task_id = ?
        """,
        ("failed", str(error), now, "failed", task_id),
    )
    conn.commit()
    conn.close()


# 获取，服务于问卷数据管理流程。
def get_analysis_task(task_id: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT task_id, batch_ids, include_nlp, include_llm, performance_mode, chart_overrides, status,
               analysis_id, error, created_at, updated_at, progress, stage, user_id
        FROM analysis_tasks
        WHERE task_id = ?
        """,
        (task_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None

    try:
        batch_ids = json.loads(row[1]) if row[1] else []
    except Exception:
        batch_ids = []
    try:
        chart_overrides = json.loads(row[5]) if row[5] else {}
    except Exception:
        chart_overrides = {}

    return {
        "task_id": row[0],
        "batch_ids": batch_ids,
        "include_nlp": bool(row[2]),
        "include_llm": bool(row[3]),
        "performance_mode": str(row[4] or "balanced"),
        "chart_overrides": chart_overrides,
        "status": row[6],
        "analysis_id": row[7],
        "error": row[8],
        "created_at": row[9],
        "updated_at": row[10],
        "progress": float(row[11] or 0.0),
        "stage": str(row[12] or ""),
        "user_id": int(row[13]) if row[13] is not None else None,
    }


# 处理用户，服务于问卷数据管理流程。
def user_owns_batches(user_id: int, batch_ids: list[str]) -> bool:
    if not batch_ids:
        return False
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    placeholder = ",".join(["?"] * len(batch_ids))
    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT batch_id)
        FROM responses
        WHERE owner_user_id = ? AND batch_id IN ({placeholder})
        """,
        (int(user_id), *batch_ids),
    )
    row = cursor.fetchone()
    conn.close()
    owned_count = int(row[0] or 0) if row else 0
    return owned_count == len(set(batch_ids))


# 删除，服务于问卷数据管理流程。
def delete_analysis_history(analysis_id: int, user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM analysis_history
        WHERE id = ? AND user_id = ?
        """,
        (int(analysis_id), int(user_id)),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# 获取，服务于问卷数据管理流程。
def get_nlp_summary_cache(cache_key: str) -> dict[str, Any] | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT payload
        FROM nlp_summary_cache
        WHERE cache_key = ?
        """,
        (cache_key,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


# 生成摘要，服务于问卷数据管理流程。
def set_nlp_summary_cache(cache_key: str, payload: dict[str, Any]) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO nlp_summary_cache (cache_key, payload, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            payload = excluded.payload,
            updated_at = excluded.updated_at
        """,
        (cache_key, json.dumps(payload, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()


# 创建，服务于问卷数据管理流程。
def create_chat_session(
    user_id: int,
    batch_ids: list[str] | None = None,
    title: str | None = None,
) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_title = str(title or "").strip() or "新会话"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO chat_sessions (user_id, batch_ids, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            json.dumps(batch_ids or [], ensure_ascii=False),
            clean_title[:80],
            now,
            now,
        ),
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return int(session_id)


# 获取，服务于问卷数据管理流程。
def get_chat_session(session_id: int, user_id: int) -> dict[str, Any] | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, batch_ids, title, created_at, updated_at
        FROM chat_sessions
        WHERE id = ? AND user_id = ?
        """,
        (int(session_id), int(user_id)),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    try:
        batch_ids = json.loads(row[2]) if row[2] else []
        if not isinstance(batch_ids, list):
            batch_ids = []
    except Exception:
        batch_ids = []
    return {
        "id": int(row[0]),
        "user_id": int(row[1]),
        "batch_ids": batch_ids,
        "title": row[3] or "新会话",
        "created_at": row[4],
        "updated_at": row[5],
    }


# 追加，服务于问卷数据管理流程。
def append_chat_message(
    session_id: int,
    user_id: int,
    role: str,
    content: str,
) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO chat_messages (session_id, user_id, role, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (int(session_id), int(user_id), str(role), str(content), now),
    )
    msg_id = cursor.lastrowid
    cursor.execute(
        """
        UPDATE chat_sessions
        SET updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (now, int(session_id), int(user_id)),
    )
    conn.commit()
    conn.close()
    return int(msg_id)


# 获取，服务于问卷数据管理流程。
def get_chat_messages(session_id: int, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT m.id, m.role, m.content, m.created_at
        FROM chat_messages m
        INNER JOIN chat_sessions s ON s.id = m.session_id
        WHERE m.session_id = ? AND s.user_id = ? AND m.user_id = ?
        ORDER BY m.id ASC
        LIMIT ?
        """,
        (int(session_id), int(user_id), int(user_id), int(limit)),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": int(row[0]),
            "role": str(row[1] or ""),
            "content": row[2] or "",
            "created_at": row[3],
        }
        for row in rows
    ]


# 列出，服务于问卷数据管理流程。
def list_chat_sessions(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            s.id,
            s.title,
            s.batch_ids,
            s.created_at,
            s.updated_at,
            (
                SELECT content FROM chat_messages
                WHERE session_id = s.id AND role = 'user'
                ORDER BY id DESC LIMIT 1
            ) AS last_question,
            (
                SELECT content FROM chat_messages
                WHERE session_id = s.id AND role = 'assistant'
                ORDER BY id DESC LIMIT 1
            ) AS last_answer,
            (
                SELECT COUNT(1) FROM chat_messages
                WHERE session_id = s.id
            ) AS message_count
        FROM chat_sessions s
        WHERE s.user_id = ?
        ORDER BY s.updated_at DESC
        LIMIT ?
        """,
        (int(user_id), int(limit)),
    )
    rows = cursor.fetchall()
    conn.close()

    sessions: list[dict[str, Any]] = []
    for row in rows:
        try:
            batch_ids = json.loads(row[2]) if row[2] else []
            if not isinstance(batch_ids, list):
                batch_ids = []
        except Exception:
            batch_ids = []
        sessions.append(
            {
                "id": int(row[0]),
                "title": row[1] or "新会话",
                "batch_ids": batch_ids,
                "created_at": row[3],
                "updated_at": row[4],
                "last_question": row[5] or "",
                "last_answer": row[6] or "",
                "message_count": int(row[7] or 0),
            }
        )
    return sessions


# 更新，服务于问卷数据管理流程。
def update_chat_session_title(session_id: int, user_id: int, title: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE chat_sessions
        SET title = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
        """,
        (str(title or "新会话")[:80], now, int(session_id), int(user_id)),
    )
    conn.commit()
    conn.close()
