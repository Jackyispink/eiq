from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


# 编排问卷增量式分析流水线流程。
@dataclass(frozen=True)
class AgentToolSpec:
    """Metadata for a callable analysis capability."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    mode: str = "tool_call"

    # 处理，服务于增量分析流水线流程。
    def to_langchain_tool(self, handler: ToolHandler | None = None) -> Any:
        """Return a LangChain StructuredTool when langchain_core is installed."""
        try:
            from langchain_core.tools import StructuredTool
        except Exception as exc:
            raise RuntimeError("LangChain is not installed in this environment.") from exc

        # 处理，服务于增量分析流水线流程。
        def _fallback(**kwargs: Any) -> dict[str, Any]:
            if handler:
                return handler(kwargs)
            return {"tool": self.name, "status": "declared", "input": kwargs}

        return StructuredTool.from_function(
            func=_fallback,
            name=self.name,
            description=self.description,
        )


# 编排问卷增量式分析流水线流程。
@dataclass
class AgentTask:
    name: str
    mode: str
    description: str
    reason: str
    expected_output: str
    dependencies: list[str] = field(default_factory=list)


# 编排问卷增量式分析流水线流程。
@dataclass
class AgentContext:
    include_nlp: bool
    include_llm: bool
    performance_mode: str = "fast"
    has_subjective_text: bool = True
    large_scale: bool = False


# 编排问卷增量式分析流水线流程。
@dataclass
class ReActStep:
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: str
    status: str = "completed"


# 编排问卷增量式分析流水线流程。
class AgentToolRegistry:
    # 初始化，服务于增量分析流水线流程。
    def __init__(self) -> None:
        self._tools: dict[str, AgentToolSpec] = {}

    # 处理，服务于增量分析流水线流程。
    def register(self, spec: AgentToolSpec) -> None:
        self._tools[spec.name] = spec

    # 获取，服务于增量分析流水线流程。
    def get(self, name: str) -> AgentToolSpec:
        if name not in self._tools:
            raise KeyError(f"Agent tool not registered: {name}")
        return self._tools[name]

    # 列出，服务于增量分析流水线流程。
    def list_tools(self) -> list[AgentToolSpec]:
        return list(self._tools.values())

    # 处理，服务于增量分析流水线流程。
    def langchain_tools(self) -> list[Any]:
        return [tool.to_langchain_tool() for tool in self.list_tools()]


# 编排问卷增量式分析流水线流程。
class SurveyAnalysisPlanner:
    """Rule-grounded planner for survey analysis agent decisions."""

    # 初始化，服务于增量分析流水线流程。
    def __init__(self, registry: AgentToolRegistry) -> None:
        self.registry = registry

    # 处理，服务于增量分析流水线流程。
    def plan(self, context: AgentContext) -> list[AgentTask]:
        tasks = [
            AgentTask(
                name="structured_analysis",
                mode=self.registry.get("structured_analysis").mode,
                description=self.registry.get("structured_analysis").description,
                reason="Questionnaire data always needs deterministic statistics before semantic reasoning.",
                expected_output="Objective question features, scores and ranked insights.",
            ),
            AgentTask(
                name="chart_generation",
                mode=self.registry.get("chart_generation").mode,
                description=self.registry.get("chart_generation").description,
                reason="Charts are selected after structured scores identify the most informative questions.",
                expected_output="Recommended chart payloads for dashboard and report views.",
                dependencies=["structured_analysis"],
            ),
        ]

        if context.include_nlp and context.has_subjective_text:
            tasks.insert(
                1,
                AgentTask(
                    name="semantic_analysis",
                    mode=self.registry.get("semantic_analysis").mode,
                    description=self.registry.get("semantic_analysis").description,
                    reason="Subjective answers require sentiment, keyword and topic tools before synthesis.",
                    expected_output="Topic clusters, keyword distribution and sentiment evidence.",
                    dependencies=["structured_analysis"],
                ),
            )

        if context.include_nlp and context.include_llm:
            tasks.append(
                AgentTask(
                    name="report_generation",
                    mode=self.registry.get("report_generation").mode,
                    description=self.registry.get("report_generation").description,
                    reason="The report agent should only run after objective and semantic evidence is available.",
                    expected_output="Markdown analysis report grounded in selected insights.",
                    dependencies=["structured_analysis", "semantic_analysis"],
                )
            )

        tasks.append(
            AgentTask(
                name="quality_audit",
                mode=self.registry.get("quality_audit").mode,
                description=self.registry.get("quality_audit").description,
                reason="The final answer needs a lightweight self-check for coverage and explainability.",
                expected_output="Quality metrics and execution guard metadata.",
                dependencies=[task.name for task in tasks],
            )
        )
        return tasks


# 编排问卷增量式分析流水线流程。
class ReActAgentExecutor:
    """Produces a ReAct-style decision trace for planned tool calls."""

    # 初始化，服务于增量分析流水线流程。
    def __init__(self, registry: AgentToolRegistry) -> None:
        self.registry = registry

    # 处理，服务于增量分析流水线流程。
    def trace(self, plan: list[AgentTask], context: AgentContext) -> list[ReActStep]:
        completed: set[str] = set()
        steps: list[ReActStep] = []
        for task in plan:
            unmet = [dep for dep in task.dependencies if dep not in completed]
            if unmet:
                steps.append(
                    ReActStep(
                        thought=f"Cannot call {task.name} until dependencies are finished.",
                        action="wait",
                        action_input={"missing_dependencies": unmet},
                        observation="Task postponed by dependency guard.",
                        status="skipped",
                    )
                )
                continue

            tool = self.registry.get(task.name)
            action_input = {
                "include_nlp": context.include_nlp,
                "include_llm": context.include_llm,
                "performance_mode": context.performance_mode,
                "large_scale": context.large_scale,
            }
            steps.append(
                ReActStep(
                    thought=task.reason,
                    action=tool.name,
                    action_input=action_input,
                    observation=f"{task.expected_output} Tool mode: {tool.mode}.",
                )
            )
            completed.add(task.name)
        return steps


# 构建，服务于增量分析流水线流程。
def build_default_tool_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    registry.register(
        AgentToolSpec(
            name="structured_analysis",
            mode="deterministic_tool_call",
            description="Run question type detection, objective statistics, feature extraction and scoring.",
            input_schema={"batch_ids": "list[str]", "top_n": "int"},
            output_schema={"scores": "dict", "top_insights": "list"},
        )
    )
    registry.register(
        AgentToolSpec(
            name="semantic_analysis",
            mode="nlp_tool_call",
            description="Run sentiment analysis, keyword extraction and topic summarization for text answers.",
            input_schema={"subjective_texts": "list[str]", "profile": "dict"},
            output_schema={"sentiment": "dict", "topics": "list", "keywords": "list"},
        )
    )
    registry.register(
        AgentToolSpec(
            name="chart_generation",
            mode="visualization_tool_call",
            description="Select chart types and generate visualization payloads from ranked question evidence.",
            input_schema={"question_features": "list[dict]", "chart_overrides": "dict"},
            output_schema={"charts": "list", "report_charts": "list"},
        )
    )
    registry.register(
        AgentToolSpec(
            name="report_generation",
            mode="llm_tool_call",
            description="Call the LLM report generator with objective, semantic and sentiment evidence.",
            input_schema={"objective_insights": "list", "semantic_insights": "list", "sentiment": "dict"},
            output_schema={"llm_analysis": "markdown", "llm_source": "str"},
        )
    )
    registry.register(
        AgentToolSpec(
            name="quality_audit",
            mode="self_reflection",
            description="Check evidence coverage, report explainability and performance guard metadata.",
            input_schema={"result": "dict"},
            output_schema={"quality_metrics": "dict", "performance_guard": "dict"},
        )
    )
    return registry


# 构建，服务于增量分析流水线流程。
def build_agent_plan(context: AgentContext) -> list[AgentTask]:
    registry = build_default_tool_registry()
    return SurveyAnalysisPlanner(registry).plan(context)


# 构建，服务于增量分析流水线流程。
def build_task_plan(include_nlp: bool, include_llm: bool) -> list[AgentTask]:
    """Backward-compatible entry point used by older code."""
    return build_agent_plan(AgentContext(include_nlp=include_nlp, include_llm=include_llm))


# 处理异步任务，服务于增量分析流水线流程。
def serialize_task_trace(
    plan: list[AgentTask],
    status: str = "completed",
    context: AgentContext | None = None,
) -> list[dict[str, Any]]:
    context = context or AgentContext(include_nlp=True, include_llm=True)
    registry = build_default_tool_registry()
    react_steps = ReActAgentExecutor(registry).trace(plan, context)

    rows: list[dict[str, Any]] = []
    for task, step in zip(plan, react_steps):
        rows.append(
            {
                "task": task.name,
                "mode": task.mode,
                "description": task.description,
                "reason": task.reason,
                "dependencies": task.dependencies,
                "expected_output": task.expected_output,
                "react": {
                    "thought": step.thought,
                    "action": step.action,
                    "action_input": step.action_input,
                    "observation": step.observation,
                },
                "status": step.status if step.status != "completed" else status,
            }
        )
    return rows


# 处理，服务于增量分析流水线流程。
def describe_agent_design() -> dict[str, Any]:
    registry = build_default_tool_registry()
    return {
        "agent_type": "LangChain-compatible Planner-ReAct tool-calling agent",
        "planner": "SurveyAnalysisPlanner",
        "executor": "ReActAgentExecutor",
        "tool_calling": [tool.name for tool in registry.list_tools()],
        "langchain_adapter": "backend.pipeline.langchain_agent.build_langchain_agent",
        "langchain_factory": "langchain.agents.create_agent",
        "decision_policy": "Rule-grounded autonomous planning based on NLP, LLM, scale and performance context.",
    }
