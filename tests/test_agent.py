# tests/test_agent.py — Milestone: LangGraph orchestration (ConversationAgent)
from langchain_core.messages import AIMessage

from src.agent.agent import ConversationAgent
from src.agent.state import AgentSession, PersistentUserContext


def test_greeting_generic_vs_named():
    assert "Hi," in ConversationAgent()._greeting()
    ctx = PersistentUserContext(first_name="John", fhir_patient_id="p1")
    named = ConversationAgent(session=AgentSession(context=ctx))._greeting()
    assert "Hi John" in named


def test_patient_context_message():
    assert ConversationAgent()._patient_context_message() is None
    ctx = PersistentUserContext(first_name="John", last_name="Doe", fhir_patient_id="p1", tenant_id="t1")
    msg = ConversationAgent(session=AgentSession(context=ctx))._patient_context_message()
    assert "John Doe" in msg and "p1" in msg


async def test_start_with_context_appends_greeting():
    ctx = PersistentUserContext(first_name="John", fhir_patient_id="p1")
    agent = ConversationAgent(session=AgentSession(context=ctx))
    greeting = await agent.start_with_context()
    assert "John" in greeting
    assert isinstance(agent.messages[-1], AIMessage)


async def test_send_returns_last_ai_message(monkeypatch):
    agent = ConversationAgent()

    class FakeGraph:
        async def ainvoke(self, state):
            return {"messages": state["messages"] + [AIMessage(content="Here are your options.")]}

    agent._graph = FakeGraph()
    reply = await agent.send("I need a cardiologist")
    assert reply == "Here are your options."


async def test_send_error_boundary(monkeypatch):
    agent = ConversationAgent()

    class BoomGraph:
        async def ainvoke(self, state):
            raise RuntimeError("llm down")

    agent._graph = BoomGraph()
    reply = await agent.send("hello")
    assert "trouble connecting" in reply.lower()
