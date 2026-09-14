# src/agent/
"""Self-contained conversational agent (text-based LLM + capability tools).

This package is deliberately decoupled from the voice layer so the full
scheduling / intake conversation can be exercised from the terminal (chat.py /
smoke_test.py) without placing a phone call. The LiveKit worker
(`src/voice/livekit_worker.py`) drives the same `ConversationAgent` /
`execute_tool` / `TOOLS_SCHEMA` surface on real calls.
"""
from src.agent.agent import ConversationAgent
from src.agent.executor import execute_tool
from src.agent.tools import TOOLS_SCHEMA
from src.agent.state import AgentSession, ConversationState, PersistentUserContext, SESSION_STORE

__all__ = [
    "ConversationAgent",
    "execute_tool",
    "TOOLS_SCHEMA",
    "AgentSession",
    "ConversationState",
    "PersistentUserContext",
    "SESSION_STORE",
]
