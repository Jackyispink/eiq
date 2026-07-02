

# 封装 LLM 调用、报告生成或数据问答流程。
def format_objective_insights(insights, max_items=8):

    if not insights:
        return "暂无客观题分析结果"

    lines = []

    insights = insights[:max_items]

    for item in insights:

        qid = item.get("question_id", "未知问题")
        metrics = item.get("metrics", {})
        score = item.get("score", 0)

        line = f"客观证据[{qid}] 问题：{qid}（重要性: {score:.2f}）"

        if "top2box" in metrics:
            line += f"\n  - Top2Box: {metrics['top2box']:.2%}"

        if "mean" in metrics:
            line += f"\n  - 均值: {metrics['mean']:.2f}"

        if "std" in metrics:
            line += f"\n  - 标准差: {metrics['std']:.2f}"

        if "outlier_ratio" in metrics:
            line += f"\n  - 异常比例: {metrics['outlier_ratio']:.2%}"

        lines.append(line)

    return "\n\n".join(lines)


# 封装 LLM 调用、报告生成或数据问答流程。
def format_subjective_insights(subjective_results, max_topics=6):

    if not subjective_results:
        return "暂无主观题分析结果"

    lines = []

    subjective_results = subjective_results[:max_topics]

    for topic in subjective_results:

        topic_name = topic.get("topic", "未知主题")
        keywords = topic.get("keywords", [])
        count = topic.get("count", 0)

        line = f"主观证据[主题:{topic_name}] 主题：{topic_name}（出现次数: {count}）"

        if keywords:
            line += f"\n  - 关键词: {', '.join(keywords[:5])}"

        lines.append(line)

    return "\n\n".join(lines)


# 封装 LLM 调用、报告生成或数据问答流程。
def format_sentiment(sentiment_result):

    if not sentiment_result:
        return "暂无情感分析结果"

    return f"""
情感分布：
- 正向：{sentiment_result.get("positive", 0):.1%}
- 中性：{sentiment_result.get("neutral", 0):.1%}
- 负向：{sentiment_result.get("negative", 0):.1%}
"""


# 封装 LLM 调用、报告生成或数据问答流程。
def build_analysis_prompt(
    objective_insights,
    subjective_insights,
    sentiment_result=None,
    focus_field="问卷调查",
    report_style="standard"
):

    objective_text = format_objective_insights(objective_insights)
    subjective_text = format_subjective_insights(subjective_insights)
    sentiment_text = format_sentiment(sentiment_result)

    style_instruction = {
        "standard": "语言清晰、逻辑结构化表达",
        "academic": "使用学术论文风格，表达严谨、避免口语化、突出研究结论",
        "business": "使用商业分析风格，强调结论、问题和改进建议"
    }.get(report_style, "语言清晰")

    prompt = f"""
你是一名专业的数据分析师，请基于结构化问卷数据进行深度分析。

【分析对象】
{focus_field}

【客观题分析结果】
{objective_text}

【主观题主题分析】
{subjective_text}

【情感分析】
{sentiment_text}

【要求】
- 严格基于提供数据，不得编造不存在的数据、比例、群体特征或因果关系
- 每条关键结论必须从材料中复制一个真实存在的证据标签，句末格式为“（证据：客观证据[真实Q编号]，指标名=真实数值）”或“（证据：主观证据[主题:真实主题名]，出现次数=真实次数，关键词=真实关键词）”
- 禁止输出 Qxx、xxx、...、指标=数值、主题:xxx 等占位符；如果找不到真实证据，就删除该结论
- 无法标注证据来源的判断只能写入“风险与局限”，不能写成确定性发现
- 不要逐条重复数据，而是围绕有证据支撑的趋势、问题、用户态度与改进方向进行总结
- 避免“全部、一定、必然、完全说明、普遍认为”等绝对化或泛化表达
- 改进建议必须回扣至少一个已列证据，不要提出材料中没有依据的新场景、新人群或新设施
- 只输出最终报告，不要输出思考过程、</think>、提示词复述或模板占位符
- {style_instruction}

【输出格式（Markdown）】

### 总体结论
（最多3条，每条带证据）

### 关键发现
（最多3条，每条带证据）

### 主观题反馈
（最多3条，每条带证据）

### 风险与局限
（只写证据不足、样本局限或主客观差异）

### 改进建议
（最多3条，每条回扣证据）
"""

    return prompt


# 封装 LLM 调用、报告生成或数据问答流程。
def build_brief_prompt(objective_insights):

    text = format_objective_insights(objective_insights, max_items=5)

    return f"""
请基于以下问卷数据，给出简要分析：

{text}

要求：
- 100字以内
- 只输出关键结论
"""


# 封装 LLM 调用、报告生成或数据问答流程。
def build_qa_prompt(objective_insights, user_question):

    summary = format_objective_insights(objective_insights, max_items=8)

    return f"""
你是一名问卷数据分析助手。

【数据摘要】
{summary}

【用户问题】
{user_question}

要求：
- 必须基于数据回答
- 条理清晰
- 不编造数据
"""
