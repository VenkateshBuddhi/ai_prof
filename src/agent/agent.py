# src/agent/agent.py
"""ConversationAgent: a LangGraph-orchestrated text conversation over ChatGroq
and the capability tools. The LiveKit worker drives this object by feeding it
transcribed text and speaking its replies.

Orchestration lives in src/agent/graph.py (StateGraph: agent <-> tools). This
class owns the running message history, the caller's AgentSession, and the
public interface used by chat.py / smoke tests.

Usage (text):
    agent = ConversationAgent()
    await agent.start(phone_number="+15550192834")   # optional patient lookup
    reply = await agent.send("I hurt my knee and need to see someone")
"""
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src import observability
from src.database.medplum_client import get_medplum_client
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.state import AgentSession, get_or_create_session
from src.agent.graph import build_tools, build_graph, DEFAULT_MODEL

logger = logging.getLogger("ConversationAgent")


class ConversationAgent:
    def __init__(
        self,
        session: Optional[AgentSession] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400,
    ):
        self.session = session or AgentSession()
        get_or_create_session(self.session.session_id)  # register

        # Tool-call trace of the most recent turn (populated by the tool wrappers).
        self._tool_log: List[Dict[str, Any]] = []
        self.last_tool_calls: List[Dict[str, Any]] = []

        tools = build_tools(self.session, self._tool_log)
        # Pass model through as-is (may be None); build_graph resolves GROQ_MODEL
        # from the environment after .env has been loaded.
        self._graph = build_graph(model, temperature, max_tokens, tools)

        # Running conversation as LangChain messages (mirrors the old self.history).
        self.messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]

    async def start(self, phone_number: Optional[str] = None) -> str:
        """Resolve caller context via Medplum phone lookup (text/testing path)."""
        if phone_number and not self.session.context.fhir_patient_id:
            medplum = get_medplum_client()
            patient = await medplum.find_patient_by_phone(phone_number) if medplum else None
            if patient:
                self.session.context.fhir_patient_id = patient.get("patient_id")
                self.session.context.fhir_organization_id = patient.get("organization_id")
                self.session.context.first_name = patient.get("first_name")
                self.session.context.last_name = patient.get("last_name")
                self.session.context.phone = phone_number
        return self._begin()

    async def start_with_context(self) -> str:
        """Greet for a session whose context was resolved externally (LiveKit +
        Medplum). Does no lookup of its own — the caller has already populated
        self.session.context (patient_id, tenant_id, FHIR ids, names)."""
        return self._begin()

    def _begin(self) -> str:
        context_msg = self._patient_context_message()
        if context_msg:
            self.messages.append(SystemMessage(content=context_msg))
        greeting = self._greeting()
        self.messages.append(AIMessage(content=greeting))
        return greeting

    def _patient_context_message(self) -> Optional[str]:
        c = self.session.context
        if not (c.patient_id or c.fhir_patient_id):
            return None
        name = f"{c.first_name or ''} {c.last_name or ''}".strip() or "unknown"
        return (
            f"Caller is an identified patient: {name} "
            f"(patient_id={c.patient_id}, fhir_patient_id={c.fhir_patient_id}, "
            f"tenant_id={c.tenant_id}). Only act within this patient's records."
        )

    def _greeting(self) -> str:
        name = self.session.context.first_name
        if name and name != "Unregistered":
            return f"Hi {name}, this is the clinic's scheduling assistant. How can I help you today?"
        return "Hi, this is the clinic's scheduling assistant. How can I help you today?"

    async def send(self, user_text: str) -> str:
        """Process one user turn through the graph and return the reply text.

        Healthcare error boundary: a transient failure (LLM/EHR network blip)
        yields a safe, retryable message instead of raising — the session (or
        the live call) stays alive."""
        observability.bind_correlation(self.session.session_id)
        observability.record_turn(self.session.session_id)
        self._tool_log.clear()
        self.messages.append(HumanMessage(content=user_text))

        try:
            result = await self._graph.ainvoke({"messages": self.messages})
        except Exception:  # noqa: BLE001
            logger.exception("Graph invocation failed; returning safe fallback")
            fallback = ("I'm sorry, I'm having trouble connecting right now. "
                        "Could you say that again in a moment?")
            self.messages.append(AIMessage(content=fallback))
            self.last_tool_calls = list(self._tool_log)
            return fallback

        self.messages = result["messages"]
        self.last_tool_calls = list(self._tool_log)

        for message in reversed(self.messages):
            if isinstance(message, AIMessage):
                content = message.content
                # ChatGroq may return content as a list of blocks; normalise to text.
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part) for part in content
                    )
                return content or ""
        return ""
