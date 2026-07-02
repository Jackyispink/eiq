import os
import shutil
import uuid
from typing import Any

from fastapi import BackgroundTasks, Body, FastAPI, File, Header, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.data.database import (
    append_chat_message,
    complete_analysis_task,
    create_auth_token,
    create_chat_session,
    create_user,
    create_analysis_task,
    delete_analysis_history,
    fail_analysis_task,
    generate_batch_id,
    get_analysis_task,
    get_chat_messages,
    get_chat_session,
    get_latest_batch_ids,
    get_user_by_token,
    init_db,
    list_chat_sessions,
    load_analysis_by_id,
    load_analysis_history,
    load_cached_analysis,
    save_analysis_history,
    save_to_db,
    update_analysis_task_progress,
    update_chat_session_title,
    update_analysis_task_status,
    user_owns_batches,
    verify_user,
)
from backend.data.loader import load_file
from backend.data.standardizer import smart_standardize
from backend.llm.llm_analyzer import analyze_with_llm, chat_with_data
from backend.pipeline.agent_orchestrator import AgentContext, describe_agent_design
from backend.pipeline.analysis_pipeline import run_analysis
from backend.pipeline.langchain_agent import summarize_langchain_agent


init_db()

app = FastAPI(title="Survey Analysis API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# 提取，服务于接口服务流程。
def _extract_token(authorization: str | None) -> str:
    raw = str(authorization or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("bearer "):
        return raw[7:].strip()
    return raw


# 处理用户，服务于接口服务流程。
def _resolve_user(authorization: str | None) -> dict[str, Any] | None:
    token = _extract_token(authorization)
    return get_user_by_token(token) if token else None


# 接收注册请求，创建用户并返回登录令牌。
@app.post("/auth/register")
async def auth_register(body: dict):
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", "")).strip()
    ok, message = create_user(username, password)
    if not ok:
        return {"error": message}
    user = verify_user(username, password)
    if not user:
        return {"error": "register failed"}
    token = create_auth_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "username": user["username"]}}


# 接收登录请求，校验用户并返回访问令牌。
@app.post("/auth/login")
async def auth_login(body: dict):
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", "")).strip()
    user = verify_user(username, password)
    if not user:
        return {"error": "invalid username or password"}
    token = create_auth_token(user["id"])
    return {"token": token, "user": {"id": user["id"], "username": user["username"]}}


# 根据请求令牌返回当前登录用户信息。
@app.get("/auth/me")
async def auth_me(authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    return {"user": user}


# 返回系统的 Agent 规划和工具编排设计信息。
@app.get("/agent/design")
async def get_agent_design(
    include_nlp: bool = True,
    include_llm: bool = True,
    performance_mode: str = "balanced",
    large_scale: bool = False,
):
    context = AgentContext(
        include_nlp=include_nlp,
        include_llm=include_llm,
        performance_mode=performance_mode,
        large_scale=large_scale,
    )
    return {
        "agent_design": describe_agent_design(),
        "langchain_agent": summarize_langchain_agent(context),
    }


# 构建，服务于接口服务流程。
def _build_fast_cache(batch_id: str, user_id: int) -> None:
    try:
        cached = load_cached_analysis([batch_id], analysis_mode="fast", user_id=user_id)
        if cached:
            return
        result_data = run_analysis(
            batch_ids=[batch_id],
            include_nlp=False,
            include_llm=False,
            performance_mode="fast",
        )
        if result_data.get("error"):
            return
        save_analysis_history([batch_id], result_data, user_id=user_id)
    except Exception:
        return


# 执行，服务于接口服务流程。
def _run_analysis_task(
    task_id: str,
    batch_ids: list[str],
    user_id: int,
    include_nlp: bool,
    include_llm: bool,
    chart_overrides: dict[str, str],
    llm_source: str,
    performance_mode: str,
) -> None:
    update_analysis_task_progress(task_id, 2, "queued", status="running")
    try:
        if include_llm and not include_nlp:
            update_analysis_task_progress(task_id, 20, "loading_cached_nlp")
            cached_deep = load_cached_analysis(batch_ids, analysis_mode="deep", user_id=user_id)
            if cached_deep:
                update_analysis_task_progress(task_id, 70, "generating_llm_report")
                objective_insights = [
                    {
                        "question_id": item.get("question_id", ""),
                        "question_text": item.get("question_text", ""),
                        "metrics": item.get("features", {}),
                        "score": item.get("score", 0.0),
                    }
                    for item in (cached_deep.get("top_insights") or [])
                    if item.get("question_type") != "text"
                ]
                if not objective_insights:
                    objective_insights = [
                        {
                            "question_id": qid,
                            "question_text": info.get("question_text", ""),
                            "metrics": info.get("features", {}),
                            "score": info.get("final_score", 0.0),
                        }
                        for qid, info in (cached_deep.get("scores") or {}).items()
                        if info.get("question_type") != "text"
                    ]
                subjective_insights = cached_deep.get("topics") or []
                sentiment_result = cached_deep.get("sentiment") or {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
                cached_deep["llm_analysis"] = analyze_with_llm(
                    objective_insights=objective_insights[:12],
                    subjective_insights=subjective_insights,
                    sentiment_result=sentiment_result,
                    llm_source=llm_source,
                )
                cached_deep["llm_source"] = llm_source
                update_analysis_task_progress(task_id, 90, "saving_result")
                analysis_id = save_analysis_history(batch_ids, cached_deep, user_id=user_id)
                complete_analysis_task(task_id, analysis_id)
                return
            include_nlp = True

        # 更新进度，服务于接口服务流程。
        def _progress_hook(progress: float, stage: str) -> None:
            update_analysis_task_progress(task_id, progress, stage)

        result_data = run_analysis(
            batch_ids=batch_ids,
            include_nlp=include_nlp,
            include_llm=include_llm,
            chart_overrides=chart_overrides,
            llm_source=llm_source,
            performance_mode=performance_mode,
            progress_callback=_progress_hook,
        )
        if result_data.get("error"):
            fail_analysis_task(task_id, str(result_data["error"]))
            return

        analysis_id = save_analysis_history(batch_ids, result_data, user_id=user_id)
        complete_analysis_task(task_id, analysis_id)
    except Exception as exc:
        fail_analysis_task(task_id, str(exc))


# 接收问卷文件，完成读取、标准化、入库和批次生成流程。
@app.post("/upload")
async def upload_files(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    files: list[UploadFile] = File(...),
):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}

    batch_id = generate_batch_id()
    success_count = 0

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        df_raw = load_file(file_path)
        if df_raw.empty:
            continue

        df_std = smart_standardize(df_raw, batch_id=batch_id, source_name=file.filename)
        if df_std.empty:
            continue

        save_to_db(df_std, batch_id, owner_user_id=user["id"])
        success_count += 1

    if success_count == 0:
        return {"error": "No valid questionnaire rows were parsed from upload files."}

    background_tasks.add_task(_build_fast_cache, batch_id, user["id"])

    return {
        "message": f"Uploaded {success_count} file(s) successfully.",
        "batch_id": batch_id,
    }


# 创建或复用分析任务，驱动问卷增量分析流程。
@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    body: Any = Body(default=None),
):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    batch_ids = body.get("batch_ids") if isinstance(body, dict) else None
    include_nlp = bool(body.get("include_nlp", False)) if isinstance(body, dict) else False
    include_llm = bool(body.get("include_llm", False)) if isinstance(body, dict) else False
    llm_source = str(body.get("llm_source", "api")).strip().lower() if isinstance(body, dict) else "api"
    if llm_source not in {"api", "local_lora"}:
        llm_source = "api"
    performance_mode = str(body.get("performance_mode", "fast")).lower() if isinstance(body, dict) else "fast"
    if performance_mode not in {"fast", "balanced", "accurate"}:
        performance_mode = "fast"
    chart_overrides = body.get("chart_overrides", {}) if isinstance(body, dict) else {}
    if not isinstance(chart_overrides, dict):
        chart_overrides = {}

    if not batch_ids:
        batch_ids = get_latest_batch_ids(limit=1, user_id=user["id"])
        if not batch_ids:
            return {"error": "No uploaded batch found."}
    if not user_owns_batches(user["id"], batch_ids):
        return {"error": "forbidden: batch is not owned by current user"}

    if not include_nlp and not include_llm and not chart_overrides:
        cached_result = load_cached_analysis(batch_ids, analysis_mode="fast", user_id=user["id"])
        if cached_result:
            cached_result["is_small_sample"] = cached_result.get("sample_size", 0) < 30
            cached_result["cache_hit"] = True
            return {
                "status": "completed",
                "task_id": None,
                "analysis_id": cached_result.get("analysis_id"),
                "result": cached_result,
                "cache_hit": True,
            }

    task_id = f"task_{uuid.uuid4().hex[:10]}"
    create_analysis_task(
        task_id=task_id,
        batch_ids=batch_ids,
        include_nlp=include_nlp,
        include_llm=include_llm,
        performance_mode=performance_mode,
        chart_overrides=chart_overrides,
        user_id=user["id"],
    )
    background_tasks.add_task(
        _run_analysis_task,
        task_id,
        batch_ids,
        user["id"],
        include_nlp,
        include_llm,
        chart_overrides,
        llm_source,
        performance_mode,
    )
    return {
        "status": "queued",
        "task_id": task_id,
        "batch_ids": batch_ids,
        "message": "Analysis task created.",
        "llm_source": llm_source,
        "performance_mode": performance_mode,
        "progress": 0,
        "stage": "queued",
    }


# 查询异步分析任务的状态、进度和最终结果。
@app.get("/analyze/tasks/{task_id}")
async def get_analyze_task(task_id: str, authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    task = get_analysis_task(task_id)
    if not task:
        return {"error": "task not found"}
    if task.get("user_id") not in {None, int(user["id"])}:
        return {"error": "forbidden"}

    if task["status"] == "completed" and task.get("analysis_id"):
        result = load_analysis_by_id(int(task["analysis_id"]), user_id=user["id"])
        if result:
            result["analysis_id"] = task["analysis_id"]
            result["is_small_sample"] = result.get("sample_size", 0) < 30
            result["cache_hit"] = False
            return {
                "status": "completed",
                "task_id": task_id,
                "analysis_id": task["analysis_id"],
                "result": result,
            }

    return {
        "status": task["status"],
        "task_id": task_id,
        "analysis_id": task.get("analysis_id"),
        "performance_mode": task.get("performance_mode", "balanced"),
        "progress": task.get("progress", 0.0),
        "stage": task.get("stage", ""),
        "error": task.get("error"),
        "updated_at": task.get("updated_at"),
    }


# 查询当前用户的历史分析记录。
@app.get("/history")
async def get_history(authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    try:
        return load_analysis_history(user_id=user["id"])
    except Exception as exc:
        return {"error": f"history load failed: {exc}"}


# 按编号读取历史分析详情。
@app.get("/analysis/{analysis_id}")
async def get_analysis_by_id(analysis_id: int, authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    if analysis_id < 0:
        return {"error": "invalid analysis id"}

    result = load_analysis_by_id(analysis_id, user_id=user["id"])
    if not result:
        return {"error": "analysis not found"}
    return result


# 删除当前用户指定的历史分析记录。
@app.delete("/history/{analysis_id}")
async def delete_history_item(analysis_id: int, authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    if analysis_id < 0:
        return {"error": "invalid analysis id"}
    ok = delete_analysis_history(analysis_id, user["id"])
    if not ok:
        return {"error": "analysis not found or no permission"}
    return {"message": "deleted", "analysis_id": analysis_id}


# 基于已有分析结果处理用户追问并保存会话消息。
@app.post("/chat")
async def chat(body: dict, authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    question = body.get("question", "").strip()
    llm_source = str(body.get("llm_source", "api")).strip().lower()
    if llm_source not in {"api", "local_lora"}:
        llm_source = "api"
    session_id = body.get("session_id")
    batch_ids = body.get("batch_ids") or []

    if not question:
        return {"error": "question is required"}

    session = None
    if session_id is not None:
        try:
            session_id = int(session_id)
        except Exception:
            return {"error": "invalid session_id"}
        session = get_chat_session(session_id, user["id"])
        if not session:
            return {"error": "chat session not found"}

    if not batch_ids and session:
        batch_ids = session.get("batch_ids") or []
    if not batch_ids:
        batch_ids = get_latest_batch_ids(limit=1, user_id=user["id"])
    if not batch_ids:
        return {"error": "No uploaded batch found."}
    if not user_owns_batches(user["id"], batch_ids):
        return {"error": "forbidden: batch is not owned by current user"}

    if not session:
        title = question[:28] + ("..." if len(question) > 28 else "")
        session_id = create_chat_session(
            user_id=user["id"],
            batch_ids=batch_ids,
            title=title or "新会话",
        )
    else:
        session_id = int(session["id"])

    history_messages = get_chat_messages(session_id, user["id"], limit=20)
    recent_turns = history_messages[-8:] if history_messages else []
    history_lines = []
    for msg in recent_turns:
        role = "用户" if msg.get("role") == "user" else "助手"
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        history_lines.append(f"{role}: {content}")
    if history_lines:
        question_for_llm = (
            "【历史对话】\n"
            + "\n".join(history_lines)
            + f"\n\n【本轮新问题】\n{question}"
        )
    else:
        question_for_llm = question

    analysis_result = load_cached_analysis(batch_ids, analysis_mode="fast", user_id=user["id"])
    if not analysis_result:
        analysis_result = run_analysis(
            batch_ids=batch_ids,
            include_nlp=False,
            include_llm=False,
            performance_mode="fast",
        )
    if analysis_result.get("error"):
        return analysis_result

    objective_insights = [
        {
            "question_id": item["question_id"],
            "metrics": item["features"],
            "score": item["score"],
        }
        for item in analysis_result.get("top_insights", [])
        if item.get("question_type") != "text"
    ]

    if not objective_insights:
        fallback_scores = analysis_result.get("scores", {}) or {}
        objective_insights = [
            {
                "question_id": question_id,
                "metrics": info.get("features", {}),
                "score": info.get("final_score", 0),
            }
            for question_id, info in fallback_scores.items()
            if info.get("question_type") != "text"
        ]
        objective_insights.sort(key=lambda item: item.get("score", 0), reverse=True)
        objective_insights = objective_insights[:8]

    answer, final_llm_source = chat_with_data(objective_insights, question_for_llm, llm_source=llm_source)
    append_chat_message(session_id, user["id"], "user", question)
    append_chat_message(session_id, user["id"], "assistant", answer)
    if len(history_messages) == 0:
        title = question[:28] + ("..." if len(question) > 28 else "")
        update_chat_session_title(session_id, user["id"], title or "新会话")
    return {"answer": answer, "session_id": session_id, "batch_ids": batch_ids, "llm_source": final_llm_source}


# 列出当前用户的历史问答会话。
@app.get("/chat/sessions")
async def get_chat_sessions(authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    return {"sessions": list_chat_sessions(user["id"])}


# 读取指定问答会话的消息明细。
@app.get("/chat/sessions/{session_id}")
async def get_chat_session_detail(session_id: int, authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    if not user:
        return {"error": "unauthorized"}
    session = get_chat_session(session_id, user["id"])
    if not session:
        return {"error": "chat session not found"}
    messages = get_chat_messages(session_id, user["id"], limit=300)
    return {"session": session, "messages": messages}
