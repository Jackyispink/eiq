from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from backend.pipeline.agent_orchestrator import (
    AgentContext,
    AgentToolRegistry,
    build_default_tool_registry,
    build_agent_plan,
    serialize_task_trace,
)


LANGCHAIN_AGENT_MODEL = os.getenv("LANGCHAIN_AGENT_MODEL", "openai:gpt-4o-mini").strip()
ENABLE_LANGCHAIN_AGENT = os.getenv("ENABLE_LANGCHAIN_AGENT", "1").strip() in {"1", "true", "True", "YES", "yes"}


# 编排问卷增量式分析流水线流程。
class AgentDecisionInput(BaseModel):
    include_nlp: bool = Field(default=False, description="Whether semantic NLP tools are enabled.")
    include_llm: bool = Field(default=False, description="Whether LLM report generation is enabled.")
    performance_mode: str = Field(default="fast", description="Runtime profile: fast, balanced, or accurate.")
    large_scale: bool = Field(default=False, description="Whether the survey is large enough to trigger guards.")


# 编排问卷增量式分析流水线流程。
class ToolBindableFakeChatModel:
    """Lazy wrapper so offline LangChain Agent tests can bind tools."""

    # 编排问卷增量式分析流水线流程。
    @staticmethod
    def create() -> Any:
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        # 编排问卷增量式分析流水线流程。
        class _BindableFakeChatModel(FakeListChatModel):
            # 处理，服务于增量分析流水线流程。
            def bind_tools(self, tools: list[Any], **kwargs: Any) -> Any:
                return self

        return _BindableFakeChatModel(
            responses=[
                "Use structured_analysis first, then semantic_analysis when text evidence is enabled, "
                "then chart_generation, report_generation when LLM synthesis is requested, and quality_audit last."
            ]
        )


# 处理，服务于增量分析流水线流程。
def _langchain_import_error() -> str | None:
    try:
        import langchain
        import langchain_core
    except Exception as exc:
        return str(exc)
    return None


# 构建，服务于增量分析流水线流程。
def build_langchain_tools(registry: AgentToolRegistry | None = None) -> list[Any]:
    """Build real LangChain StructuredTool objects from the local tool registry."""
    registry = registry or build_default_tool_registry()
    try:
        from langchain_core.tools import StructuredTool
    except Exception as exc:
        raise RuntimeError("LangChain core is not installed.") from exc

    tools = []
    for spec in registry.list_tools():
        # 执行，服务于增量分析流水线流程。
        def _run(
            include_nlp: bool = False,
            include_llm: bool = False,
            performance_mode: str = "fast",
            large_scale: bool = False,
            _tool_name: str = spec.name,
            _description: str = spec.description,
        ) -> dict[str, Any]:
            return {
                "tool": _tool_name,
                "description": _description,
                "accepted": True,
                "context": {
                    "include_nlp": include_nlp,
                    "include_llm": include_llm,
                    "performance_mode": performance_mode,
                    "large_scale": large_scale,
                },
            }

        tools.append(
            StructuredTool.from_function(
                func=_run,
                name=spec.name,
                description=spec.description,
                args_schema=AgentDecisionInput,
            )
        )
    return tools


# 处理，服务于增量分析流水线流程。
def _resolve_langchain_model(model: str | None = None) -> tuple[Any, str]:
    model_name = model or LANGCHAIN_AGENT_MODEL
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if model_name == "fake" or (model_name.startswith("openai:") and not openai_key):
        return ToolBindableFakeChatModel.create(), "fake_chat_model"
    return model_name, "configured_chat_model"


# 构建，服务于增量分析流水线流程。
def build_langchain_agent(model: str | None = None) -> Any:
    """Create a LangChain Agent graph with the registered survey-analysis tools."""
    if not ENABLE_LANGCHAIN_AGENT:
        raise RuntimeError("LangChain agent is disabled by ENABLE_LANGCHAIN_AGENT.")

    try:
        from langchain.agents import create_agent
    except Exception as exc:
        raise RuntimeError("LangChain is not installed.") from exc

    system_prompt = (
        "You are a survey-analysis planning agent. Choose tools according to the available "
        "survey evidence, runtime profile, NLP setting, LLM setting, and scale guard. "
        "Prefer structured_analysis before semantic_analysis, chart_generation after scoring, "
        "report_generation only when semantic evidence is available, and quality_audit last."
    )
    resolved_model, _ = _resolve_langchain_model(model)
    return create_agent(
        model=resolved_model,
        tools=build_langchain_tools(),
        system_prompt=system_prompt,
    )


# 处理，服务于增量分析流水线流程。
def invoke_langchain_agent(context: AgentContext, goal: str | None = None) -> dict[str, Any]:
    """Invoke the LangChain Agent when dependencies and model configuration are available."""
    import_error = _langchain_import_error()
    if import_error:
        return {
            "enabled": False,
            "runtime": "missing_dependency",
            "error": import_error,
            "model": LANGCHAIN_AGENT_MODEL,
        }

    agent = build_langchain_agent()
    prompt = goal or (
        "Plan the survey analysis tool sequence for the current request. "
        f"include_nlp={context.include_nlp}, include_llm={context.include_llm}, "
        f"performance_mode={context.performance_mode}, large_scale={context.large_scale}."
    )
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    return {
        "enabled": True,
        "runtime": "langchain_create_agent",
        "model": LANGCHAIN_AGENT_MODEL,
        "result": result,
    }


# 处理，服务于增量分析流水线流程。
def summarize_langchain_agent(context: AgentContext) -> dict[str, Any]:
    """Return a lightweight status block for API responses and thesis evidence."""
    registry = build_default_tool_registry()
    import_error = _langchain_import_error()
    plan = build_agent_plan(context)
    _, model_runtime = _resolve_langchain_model() if import_error is None else (None, "unavailable")
    return {
        "enabled": ENABLE_LANGCHAIN_AGENT and import_error is None,
        "runtime": "langchain_create_agent" if import_error is None else "missing_dependency",
        "model": LANGCHAIN_AGENT_MODEL,
        "model_runtime": model_runtime,
        "agent_factory": "langchain.agents.create_agent",
        "tool_count": len(registry.list_tools()),
        "tools": [tool.name for tool in registry.list_tools()],
        "planned_tasks": [task.name for task in plan],
        "react_trace": serialize_task_trace(plan, context=context),
        "dependency_error": import_error,
    }
