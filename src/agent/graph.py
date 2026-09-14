# src/agent/graph.py
"""LangGraph wiring for the conversational agent.

Builds LangChain StructuredTools from the existing Pydantic schemas + capability
coroutines (src/agent/executor.py `_REGISTRY`), then compiles a StateGraph:

    START -> agent -> (tool_calls?) -> tools -> agent -> ... -> END

The tool/DB/schema layers are untouched; this module only adapts them to
LangGraph. Tools are built per-session so each capability receives the caller's
AgentSession (patient_id, state) without exposing it to the model.
"""
import json
import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger("AgentGraph")

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END, MessagesState

from src.agent.state import AgentSession
from src.agent.executor import _REGISTRY
from src.agent.tools import TOOLS_SCHEMA

# Reuse the JSON tool descriptions so wording lives in one place.
_TOOL_DESCRIPTIONS: Dict[str, str] = {t["name"]: t["description"] for t in TOOLS_SCHEMA}

# Fallback only; the real value is read from GROQ_MODEL at build_graph() time so
# it never freezes to an import-time snapshot before .env is loaded.
DEFAULT_MODEL = "openai/gpt-oss-120b"


def build_tools(session: AgentSession, tool_log: List[Dict[str, Any]]) -> List[StructuredTool]:
    """Wrap each (Pydantic model, capability coroutine) as an async LangChain tool
    bound to `session`. Every call is appended to `tool_log` for test/debug
    visibility (surfaced as ConversationAgent.last_tool_calls)."""

    def _make(name: str, model_cls, handler: Callable[..., Awaitable[Dict[str, Any]]]) -> StructuredTool:
        async def _run(**kwargs) -> str:
            validated = model_cls(**kwargs)
            result = await handler(validated, session)
            tool_log.append({"name": name, "args": kwargs, "result": result})
            return json.dumps(result, default=str)

        return StructuredTool.from_function(
            coroutine=_run,
            name=name,
            description=_TOOL_DESCRIPTIONS.get(name, name),
            args_schema=model_cls,
        )

    return [_make(name, model_cls, handler) for name, (model_cls, handler) in _REGISTRY.items()]


def _chat_models(temperature: float, max_tokens: int):
    """Build the ordered LLM chain (primary first, others as fallbacks). Provider
    order is set by LLM_PRIMARY (gemini|groq, default gemini); each is included
    only if its API key is present. Read at call time so .env is loaded."""
    providers = {}
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        gemini_model = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
        # max_retries=0 → a quota/error 429 fails FAST and falls back to Groq
        # immediately (no multi-second retry storm). Gemini's free tier is only
        # ~20 requests/day, so fast fallback matters.
        providers["gemini"] = (f"gemini:{gemini_model}", ChatGoogleGenerativeAI(
            model=gemini_model, temperature=temperature, max_output_tokens=max_tokens,
            google_api_key=gemini_key, max_retries=0,
        ))
    if os.environ.get("GROQ_API_KEY"):
        groq_model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
        providers["groq"] = (f"groq:{groq_model}", ChatGroq(
            model=groq_model, temperature=temperature, max_tokens=max_tokens, max_retries=6,
        ))
    primary = os.environ.get("LLM_PRIMARY", "gemini").lower()
    order = [primary] + [p for p in ("gemini", "groq") if p != primary]
    return [providers[p] for p in order if p in providers]


def build_graph(model_name: Optional[str], temperature: float, max_tokens: int, tools: List[StructuredTool]):
    """Compile the agent/tools StateGraph. The LLM is a Gemini→Groq fallback chain:
    if Gemini errors (quota/rate-limit/etc.) LangChain automatically retries on Groq.
    (`model_name` is accepted for compat but provider selection is env-driven.)"""
    models = _chat_models(temperature, max_tokens)
    if not models:
        raise RuntimeError("No LLM configured — set GEMINI_API_KEY and/or GROQ_API_KEY")
    logger.info("LLM chain: %s", " -> ".join(label for label, _ in models))
    bound = [m.bind_tools(tools) for _, m in models]
    llm_with_tools = bound[0].with_fallbacks(bound[1:]) if len(bound) > 1 else bound[0]
    tools_by_name = {t.name: t for t in tools}

    async def agent_node(state: MessagesState) -> Dict[str, Any]:
        response = await llm_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    async def tool_node(state: MessagesState) -> Dict[str, Any]:
        last = state["messages"][-1]
        out: List[ToolMessage] = []
        for call in last.tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                content = json.dumps({"success": False, "error": f"unknown_tool:{call['name']}"})
            else:
                try:
                    content = await tool.ainvoke(call["args"])
                except Exception as e:  # noqa: BLE001
                    logger.error("Tool %s raised: %s", call["name"], type(e).__name__, exc_info=True)
                    content = json.dumps({"success": False, "error": f"tool_error:{type(e).__name__}"})
            out.append(ToolMessage(content=content, name=call["name"], tool_call_id=call["id"]))
        return {"messages": out}

    def should_continue(state: MessagesState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile()
