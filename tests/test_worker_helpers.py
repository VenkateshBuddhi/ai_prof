# tests/test_worker_helpers.py — Milestone: LiveKit worker bridge (pure helpers)
from types import SimpleNamespace
from unittest.mock import MagicMock

from livekit.agents import llm

import src.voice.livekit_worker as w


def test_extract_caller_number():
    real = SimpleNamespace(attributes={"sip.phoneNumber": "+15550192834"})
    assert w._extract_caller_number(real) == "+15550192834"

    trunk = SimpleNamespace(attributes={"sip.trunkPhoneNumber": "+18005551212"})
    assert w._extract_caller_number(trunk) == "+18005551212"

    # console-style mock participant -> no real attributes -> None
    assert w._extract_caller_number(MagicMock()) is None
    assert w._extract_caller_number(SimpleNamespace(attributes={})) is None


def test_latest_user_text():
    ctx = SimpleNamespace(items=[
        SimpleNamespace(role="assistant", text_content="hi"),
        SimpleNamespace(role="user", text_content="book a cardiologist"),
    ])
    assert w.HealthcareIntakeAgent._latest_user_text(ctx) == "book a cardiologist"
    # non-message item without text_content must not crash the scan
    empty = SimpleNamespace(items=[SimpleNamespace(role="system")])
    assert w.HealthcareIntakeAgent._latest_user_text(empty) == ""


def test_format_transcript():
    turns = [{"role": "user", "text": "hello"}, {"role": "assistant", "text": "hi there"}]
    out = w._format_transcript(turns)
    assert "Patient: hello" in out and "Assistant: hi there" in out


def test_bridge_llm_is_valid_but_unused():
    bridge = w._BridgeLLM()
    assert isinstance(bridge, llm.LLM)
    try:
        bridge.chat(chat_ctx=None)
        assert False, "chat() should not be used"
    except NotImplementedError:
        pass
