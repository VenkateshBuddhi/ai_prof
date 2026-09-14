# tests/test_tool_parity.py — Milestone: tool contract stays in sync
from pydantic import BaseModel

from src.agent.executor import _REGISTRY
from src.agent.tools import TOOLS_SCHEMA


def test_registry_matches_tools_schema():
    assert set(_REGISTRY) == {t["name"] for t in TOOLS_SCHEMA}


def test_registry_entries_are_model_and_coroutine():
    import inspect
    for name, (model_cls, handler) in _REGISTRY.items():
        assert issubclass(model_cls, BaseModel), name
        assert inspect.iscoroutinefunction(handler), name


def test_tool_specs_well_formed():
    for t in TOOLS_SCHEMA:
        assert t["name"] and t["description"]
        assert t["parameters"]["type"] == "object"
        assert "properties" in t["parameters"]


def test_expected_tools_present():
    expected = {
        "search_doctors", "check_availability", "create_appointment",
        "reschedule_appointment", "cancel_appointment", "get_questionnaire",
        "submit_questionnaire_response", "lookup_patient", "register_patient",
        "get_appointment", "transfer_to_human", "end_call",
    }
    assert expected == set(_REGISTRY)
