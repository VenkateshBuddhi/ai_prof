# src/agent/executor.py
"""Validate raw LLM tool arguments through Pydantic, then dispatch to the
matching capability. Returns a JSON-serialisable dict in all cases (validation
errors are returned to the model so it can recover, not raised)."""
import logging
import time
from typing import Any, Dict

from pydantic import ValidationError

from src import observability
from src.agent.state import AgentSession
from src.agent import capabilities as caps
from src.agent.schemas import (
    SearchDoctorsInput,
    CheckAvailabilityInput,
    CreateAppointmentInput,
    RescheduleAppointmentInput,
    CancelAppointmentInput,
    GetQuestionnaireInput,
    SubmitQuestionnaireResponseInput,
    LookupPatientInput,
    RegisterPatientInput,
    GetAppointmentInput,
    TransferToHumanInput,
    EndCallInput,
)

logger = logging.getLogger("AgentExecutor")

# name -> (input model, capability coroutine)
_REGISTRY = {
    "search_doctors": (SearchDoctorsInput, caps.search_doctors),
    "check_availability": (CheckAvailabilityInput, caps.check_availability),
    "create_appointment": (CreateAppointmentInput, caps.create_appointment),
    "reschedule_appointment": (RescheduleAppointmentInput, caps.reschedule_appointment),
    "cancel_appointment": (CancelAppointmentInput, caps.cancel_appointment),
    "get_questionnaire": (GetQuestionnaireInput, caps.get_questionnaire),
    "submit_questionnaire_response": (SubmitQuestionnaireResponseInput, caps.submit_questionnaire_response),
    "lookup_patient": (LookupPatientInput, caps.lookup_patient),
    "register_patient": (RegisterPatientInput, caps.register_patient),
    "get_appointment": (GetAppointmentInput, caps.get_appointment),
    "transfer_to_human": (TransferToHumanInput, caps.transfer_to_human),
    "end_call": (EndCallInput, caps.end_call),
}


async def execute_tool(name: str, args: Dict[str, Any], session: AgentSession) -> Dict[str, Any]:
    entry = _REGISTRY.get(name)
    if not entry:
        return {"success": False, "error": f"unknown_tool:{name}"}

    input_model, handler = entry
    try:
        validated = input_model(**(args or {}))
    except ValidationError as e:
        logger.warning(f"Tool {name} arg validation failed: {e}")
        observability.record_tool(session.session_id, name, False, 0.0)
        return {"success": False, "error": "invalid_arguments", "details": e.errors()}

    started = time.perf_counter()
    try:
        result = await handler(validated, session)
    except Exception as e:
        logger.error(f"Tool {name} execution error: {e}", exc_info=True)
        observability.record_tool(session.session_id, name, False, (time.perf_counter() - started) * 1000)
        return {"success": False, "error": str(e)}
    observability.record_tool(
        session.session_id, name, bool(result.get("success")), (time.perf_counter() - started) * 1000
    )
    return result
