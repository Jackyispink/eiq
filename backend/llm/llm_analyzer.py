from __future__ import annotations

import os
import re

from openai import OpenAI

from backend.config import (
    DEFAULT_LLM_SOURCE,
    GPU_MODE,
    LOCAL_LLM_MAX_NEW_TOKENS,
    LOCAL_LLM_PATH,
    OPENAI_API_KEY,
    USE_LOCAL_LLM,
)
from backend.llm.prompt_builder import (
    build_analysis_prompt,
    build_brief_prompt,
    build_qa_prompt,
)


_api_client = None
_local_tokenizer = None
_local_model = None
_local_device = "cpu"


# 封装 LLM 调用、报告生成或数据问答流程。
def _normalize_llm_source(llm_source: str | None) -> str:
    source = (llm_source or DEFAULT_LLM_SOURCE or "api").strip().lower()
    if source in {"local", "local_lora", "lora"}:
        return "local_lora"
    return "api"


# 封装 LLM 调用、报告生成或数据问答流程。
def _local_model_available() -> bool:
    return bool(USE_LOCAL_LLM and LOCAL_LLM_PATH and os.path.isdir(LOCAL_LLM_PATH))


# 封装 LLM 调用、报告生成或数据问答流程。
def _get_api_client():
    global _api_client
    if _api_client is None:
        _api_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://chat.intern-ai.org.cn/api/v1/",
        )
    return _api_client


# 封装 LLM 调用、报告生成或数据问答流程。
def _get_local_model():
    global _local_model, _local_tokenizer, _local_device
    if _local_model is not None and _local_tokenizer is not None:
        return _local_model, _local_tokenizer, _local_device

    if not _local_model_available():
        raise RuntimeError(f"Local LoRA model path not found: {LOCAL_LLM_PATH}")

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        raise RuntimeError(f"Missing local LLM dependencies: {exc}") from exc

    if GPU_MODE == "FORCE_CPU":
        _local_device = "cpu"
        device_map = None
    else:
        _local_device = "cuda" if torch.cuda.is_available() else "cpu"
        device_map = "auto" if _local_device == "cuda" else None

    _local_tokenizer = AutoTokenizer.from_pretrained(LOCAL_LLM_PATH, trust_remote_code=True)
    _local_model = AutoModelForCausalLM.from_pretrained(
        LOCAL_LLM_PATH,
        trust_remote_code=True,
        torch_dtype=torch.float16 if _local_device == "cuda" else torch.float32,
        device_map=device_map,
    )
    if device_map is None:
        _local_model = _local_model.to(_local_device)
    _local_model.eval()
    return _local_model, _local_tokenizer, _local_device


# 封装 LLM 调用、报告生成或数据问答流程。
def _run_local_chat(prompt: str) -> str:
    model, tokenizer, device = _get_local_model()
    try:
        import torch
    except Exception as exc:
        raise RuntimeError(f"PyTorch unavailable for local LLM: {exc}") from exc

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=3072)
    if device == "cuda":
        inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=LOCAL_LLM_MAX_NEW_TOKENS,
            do_sample=True,
            temperature=0.3,
            top_p=0.9,
            repetition_penalty=1.05,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    text = tokenizer.decode(output[0], skip_special_tokens=True)
    if text.startswith(prompt):
        text = text[len(prompt) :].strip()
    return text.strip()


# 封装 LLM 调用、报告生成或数据问答流程。
def _run_api_chat(prompt: str) -> str:
    response = _get_api_client().chat.completions.create(
        model="intern-latest",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


# 封装 LLM 调用、报告生成或数据问答流程。
def _chat(prompt: str, llm_source: str | None = None) -> tuple[str, str]:
    source = _normalize_llm_source(llm_source)

    if source == "local_lora":
        try:
            return _run_local_chat(prompt), "local_lora"
        except Exception as exc:
            if OPENAI_API_KEY:
                fallback = _run_api_chat(prompt)
                return f"{fallback}\n\n[info] local_lora failed, fallback to api: {exc}", "api"
            return f"LLM local_lora failed: {exc}", "local_lora"

    if not OPENAI_API_KEY and _local_model_available():
        try:
            return _run_local_chat(prompt), "local_lora"
        except Exception as exc:
            return f"LLM api unavailable and local_lora failed: {exc}", "api"

    try:
        return _run_api_chat(prompt), "api"
    except Exception as exc:
        if _local_model_available():
            try:
                fallback = _run_local_chat(prompt)
                return f"{fallback}\n\n[info] api failed, fallback to local_lora: {exc}", "local_lora"
            except Exception as exc2:
                return f"LLM api/local_lora both failed: {exc}; {exc2}", "api"
        return f"LLM API failed: {exc}", "api"


INVALID_REPORT_PATTERNS = (
    "</think>",
    "Qxx",
    "xxx",
    "主题:xxx",
    "指标=数值",
    "出现次数 = ...",
    "出现次数=...",
    "证据 [主题: ...",
    "证据：主观证据 [主题: ...",
)


def _sanitize_report_text(report: str | None) -> str:
    text = str(report or "").strip()
    text = re.sub(r"(?is)<think>.*?</think>", "", text).strip()
    text = text.replace("</think>", "").strip()
    return text


def _is_invalid_report(report: str | None) -> bool:
    text = str(report or "")
    if len(text.strip()) < 80:
        return True
    return any(pattern in text for pattern in INVALID_REPORT_PATTERNS)


def _metric_summary(metrics: dict) -> str:
    allowed = ("mean", "std", "top2box", "max_ratio", "normalized_entropy", "outlier", "distribution")
    parts = []
    for key in allowed:
        if key in metrics:
            parts.append(f"{key}={metrics.get(key)}")
    return ", ".join(parts)


def _build_evidence_bound_fallback_report(
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    focus_field: str = "Survey Analysis",
) -> str:
    objectives = list(objective_insights or [])[:5]
    subjects = list(subjective_insights or [])[:8]

    lines = [f"### 总体结论", ""]
    if objectives:
        item = objectives[0]
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        metric_text = _metric_summary(metrics) or f"重要性={item.get('score', 0):.4f}"
        lines.append(
            f"- 现有客观题结果显示，{qtext} 是本次 {focus_field} 中需要关注的指标之一"
            f"（证据：客观证据[{qid}]，{metric_text}）。"
        )
    if subjects:
        item = subjects[0]
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:3])
        lines.append(
            f"- 主观反馈主要集中在“{topic}”相关内容，说明该主题在开放回答中具有较高可见度"
            f"（证据：主观证据[主题:{topic}]，出现次数={count}，关键词={keywords}）。"
        )

    lines.extend(["", "### 关键发现", ""])
    for item in objectives[:3]:
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        metric_text = _metric_summary(metrics) or f"重要性={item.get('score', 0):.4f}"
        lines.append(f"- {qtext} 可作为结构化分析中的重点观察项（证据：客观证据[{qid}]，{metric_text}）。")

    lines.extend(["", "### 主观题反馈", ""])
    for item in subjects[:5]:
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:3])
        lines.append(f"- “{topic}”是开放回答中的主要主题之一（证据：主观证据[主题:{topic}]，出现次数={count}，关键词={keywords}）。")

    coverage_terms = []
    for item in subjects[:8]:
        topic = str(item.get("topic", "")).strip()
        keywords = [str(k).strip() for k in item.get("keywords", [])[:3] if str(k).strip()]
        if topic:
            coverage_terms.append(topic)
        coverage_terms.extend(keywords)
    unique_terms = []
    for term in coverage_terms:
        if term and term not in unique_terms:
            unique_terms.append(term)
    if unique_terms:
        lines.extend(["", "### 证据覆盖", ""])
        lines.append(
            "- Top主题和关键词覆盖："
            + "、".join(unique_terms[:18])
            + f"（证据：主观证据[主题:{subjects[0].get('topic', '')}]，出现次数={subjects[0].get('count', '')}，关键词={', '.join(str(k) for k in subjects[0].get('keywords', [])[:3])}）。"
        )

    lines.extend(
        [
            "",
            "### 风险与局限",
            "",
            "- 以上结论仅基于当前结构化指标、主题和关键词，不能扩展为未被材料覆盖的人群特征或因果解释。",
            "",
            "### 改进建议",
            "",
        ]
    )
    if objectives:
        item = objectives[0]
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        metric_text = _metric_summary(metrics) or f"重要性={item.get('score', 0):.4f}"
        lines.append(f"- 优先围绕“{qtext}”开展后续复核和细分分析（证据：客观证据[{qid}]，{metric_text}）。")
    if subjects:
        item = subjects[0]
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:3])
        lines.append(f"- 围绕“{topic}”主题补充追问或访谈，以验证开放回答中的具体诉求（证据：主观证据[主题:{topic}]，出现次数={count}，关键词={keywords}）。")
    return "\n".join(lines)


def _finalize_report(
    report: str | None,
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    focus_field: str = "Survey Analysis",
) -> str:
    text = _sanitize_report_text(report)
    if _is_invalid_report(text):
        return _build_evidence_bound_fallback_report(
            objective_insights=objective_insights,
            subjective_insights=subjective_insights,
            sentiment_result=sentiment_result,
            focus_field=focus_field,
        )
    return text


# 封装 LLM 调用、报告生成或数据问答流程。
def analyze_with_llm(
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    focus_field="Survey Analysis",
    report_style="standard",
    llm_source: str | None = None,
):
    objective_lines = []
    for item in (objective_insights or [])[:12]:
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        score = item.get("score", 0)
        parts = [f"题号={qid}", f"重要性={score:.4f}", f"题目={qtext}"]
        if "mean" in metrics:
            parts.append(f"均值={metrics.get('mean'):.4f}")
        if "std" in metrics:
            parts.append(f"标准差={metrics.get('std'):.4f}")
        if "top2box" in metrics:
            parts.append(f"Top2Box={metrics.get('top2box'):.4f}")
        if "max_ratio" in metrics:
            parts.append(f"最高选项占比={metrics.get('max_ratio'):.4f}")
        if "distribution" in metrics:
            parts.append(f"选项分布={metrics.get('distribution')}")
        objective_lines.append("- 客观证据[" + qid + "] " + " | ".join(parts))

    subjective_lines = []
    for item in (subjective_insights or [])[:12]:
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:6])
        subjective_lines.append(f"- 主观证据[主题:{topic}] 主题={topic} | 出现次数={count} | 关键词={keywords}")

    prompt = f"""
你是一名严谨的问卷数据分析师。请基于系统已经整理好的结构化证据生成问卷分析报告。

分析对象：{focus_field}

【客观题重点指标】
{chr(10).join(objective_lines) if objective_lines else "无"}

【主观题Top主题】
{chr(10).join(subjective_lines) if subjective_lines else "无"}

【情绪分布】
{sentiment_result or {}}

【强约束要求】
1. 只能依据上方证据写结论，禁止编造不存在的数据、比例、群体特征或因果关系。
2. 每个主要结论必须从上方材料中复制一个真实存在的证据标签，句末格式为“（证据：客观证据[真实Q编号]，指标名=真实数值）”或“（证据：主观证据[主题:真实主题名]，出现次数=真实次数，关键词=真实关键词）”。
3. 禁止输出 Qxx、xxx、...、指标=数值、主题:xxx 等占位符；如果找不到真实证据，就删除该结论。
4. 没有明确证据标签和指标值支撑的内容，只能写在“风险与局限”中，不能写成确定性发现。
5. 不要把少数观点概括为整体结论；当证据不足时使用“部分样本”“现有结果显示”“可能反映”等保守表述。
6. 避免“全部、必然、一定、完全说明、普遍认为”等绝对化或泛化表达。
7. 如客观题与主观题存在潜在差异，需要指出“存在主客观反馈差异”，不要强行得出单一结论。
8. 改进建议必须回扣至少一个已列证据，不要提出材料中没有依据的新场景、新人群或新设施。
9. 只输出最终报告，不要输出思考过程、</think>、提示词复述或“强约束要求”原文。
10. 输出中文 Markdown 报告，包含：总体结论、关键发现、主观题反馈、风险与局限、改进建议。每个部分最多3条，避免冗长推断。
"""
    result, _ = _chat(prompt, llm_source=llm_source)
    return _finalize_report(result, objective_insights, subjective_insights, sentiment_result, focus_field)


def analyze_plain_with_llm(
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    llm_source: str | None = None,
):
    objective_lines = []
    for item in (objective_insights or [])[:12]:
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        metric_text = ", ".join(
            f"{key}={value}"
            for key, value in metrics.items()
            if key in {"mean", "std", "top2box", "outlier", "max_ratio", "normalized_entropy", "distribution"}
        )
        objective_lines.append(f"客观证据[{qid}] {qtext} {metric_text}".strip())

    subjective_lines = []
    for item in (subjective_insights or [])[:12]:
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:6])
        subjective_lines.append(f"主观证据[主题:{topic}] topic={topic} count={count} keywords={keywords}".strip())

    prompt = f"""
请根据下面的问卷分析材料，直接生成一份问卷分析报告。

客观题材料：
{chr(10).join(objective_lines) if objective_lines else "无"}

主观题材料：
{chr(10).join(subjective_lines) if subjective_lines else "无"}

情绪分布：
{sentiment_result or {}}

请输出完整报告。
"""
    result, _ = _chat(prompt, llm_source=llm_source)
    return _sanitize_report_text(result) or "LLM produced empty plain report."


def analyze_prompt_only_with_llm(
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    llm_source: str | None = None,
):
    objective_lines = []
    for item in (objective_insights or [])[:12]:
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        metric_text = ", ".join(
            f"{key}={value}"
            for key, value in metrics.items()
            if key in {"mean", "std", "top2box", "outlier", "max_ratio", "normalized_entropy"}
        )
        objective_lines.append(f"客观证据[{qid}] {qtext} {metric_text}".strip())

    subjective_lines = []
    for item in (subjective_insights or [])[:12]:
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:6])
        subjective_lines.append(f"主观证据[主题:{topic}] topic={topic} count={count} keywords={keywords}".strip())

    prompt = f"""
请根据下面的问卷分析材料生成一份分析报告。

客观题材料：
{chr(10).join(objective_lines) if objective_lines else "无"}

主观题材料：
{chr(10).join(subjective_lines) if subjective_lines else "无"}

情绪分布：
{sentiment_result or {}}

要求：
1. 只能依据上述材料写结论，不得编造不存在的数据、比例或样本特征。
2. 每条关键发现、主观题反馈和改进建议都必须从材料中复制一个真实存在的证据标签，句末格式为“（证据：客观证据[真实Q编号]，指标名=真实数值）”或“（证据：主观证据[主题:真实主题名]，出现次数=真实次数，关键词=真实关键词）”。
3. 禁止输出 Qxx、xxx、...、指标=数值、主题:xxx 等占位符；如果找不到真实证据，就删除该结论。
4. 如果某个判断无法标注上述证据，请不要把它写成结论；只能放入“局限说明”。
5. 如果材料不足，请使用“部分样本显示”“从现有结果看”等保守表述。
6. 不要把少数意见概括为整体结论。
7. 避免“全部、一定、必然、完全说明、普遍认为”等绝对化或泛化表达。
8. 只输出最终报告，不要输出思考过程、</think>、提示词复述或“问题：”。
9. 输出结构化 Markdown 报告，包含：总体结论、关键发现、主观题反馈、风险与局限、改进建议。每个部分最多3条。
"""
    result, _ = _chat(prompt, llm_source=llm_source)
    return _finalize_report(result, objective_insights, subjective_insights, sentiment_result)


def analyze_agent_only_with_llm(
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    focus_field="Survey Analysis",
    llm_source: str | None = None,
):
    objective_lines = []
    for item in (objective_insights or [])[:12]:
        qid = item.get("question_id", "")
        qtext = item.get("question_text", "")
        metrics = item.get("metrics", {}) or {}
        score = item.get("score", 0)
        line = f"- {qid} | 重要性={score:.4f} | {qtext}"
        if "mean" in metrics:
            line += f" | 均值={metrics.get('mean'):.4f}"
        if "std" in metrics:
            line += f" | 标准差={metrics.get('std'):.4f}"
        if "top2box" in metrics:
            line += f" | Top2Box={metrics.get('top2box'):.4f}"
        if "distribution" in metrics:
            line += f" | 分布={metrics.get('distribution')}"
        objective_lines.append(line)

    subjective_lines = []
    for item in (subjective_insights or [])[:12]:
        topic = item.get("topic", "")
        count = item.get("count", "")
        keywords = ", ".join(str(k) for k in item.get("keywords", [])[:6])
        subjective_lines.append(f"- 主题={topic} | 出现次数={count} | 关键词={keywords}")

    prompt = f"""
你是一名问卷分析助手。下面是系统已经整理好的结构化分析上下文，请生成报告。

分析对象：{focus_field}

【客观题重点指标】
{chr(10).join(objective_lines) if objective_lines else "无"}

【主观题Top主题】
{chr(10).join(subjective_lines) if subjective_lines else "无"}

【情绪分布】
{sentiment_result or {}}

请输出：
1. 总体结论
2. 主要发现
3. 主观题反馈
4. 改进建议
"""
    result, _ = _chat(prompt, llm_source=llm_source)
    return _sanitize_report_text(result) or "LLM produced empty agent-only report."


# 封装 LLM 调用、报告生成或数据问答流程。
def analyze_brief(objective_insights):
    prompt = build_brief_prompt(objective_insights)
    result, _ = _chat(prompt, llm_source="api")
    return result


# 封装 LLM 调用、报告生成或数据问答流程。
def chat_with_data(objective_insights, user_question, llm_source: str | None = None):
    prompt = build_qa_prompt(objective_insights, user_question)
    return _chat(prompt, llm_source=llm_source)
