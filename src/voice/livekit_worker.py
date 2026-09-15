# src/voice/livekit_worker.py
"""LiveKit Agents worker — replaces the Twilio media-stream layer.

Architecture:
    Cellular caller -> Twilio SIP trunk -> LiveKit SIP gateway -> LiveKit room
      -> this worker (Deepgram STT + Silero VAD + Cartesia TTS)
      -> Agent.llm_node bridges each user turn into our LangGraph
         ConversationAgent (src/agent) which runs the real LLM + scheduling tools
      -> reply text -> Cartesia TTS -> caller.

Twilio here is ONLY a SIP trunk; all real-time media/turn-taking is LiveKit's.
Medplum resolves patient identity + hospital compartment before the conversation
and receives the transcript afterward.

Run:
    uv run python -m src.voice.livekit_worker dev      # local dev
    uv run python -m src.voice.livekit_worker start     # production

Required environment:
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET     (LiveKit server)
    DEEPGRAM_API_KEY                                     (STT)
    CARTESIA_API_KEY                                     (TTS)
    GROQ_API_KEY                                         (agent LLM)
    MEDPLUM_CLIENT_ID / MEDPLUM_CLIENT_SECRET            (FHIR scheduling engine)
Optional:
    LIVEKIT_AGENT_NAME    explicit-dispatch name matching your SIP dispatch rule
    CARTESIA_VOICE        Cartesia voice id
    ESCALATION_TRANSFER_TO  tel:/sip: URI for human transfers
    MEDPLUM_DEFAULT_ORG   Organization id to attach newly-registered patients to
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,  # LiveKit session (STT/VAD/LLM/TTS orchestrator)
    ConversationItemAddedEvent,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm as lk_llm,
)
from livekit.plugins import cartesia, deepgram, silero

from src import observability
from src.agent.agent import ConversationAgent
from src.agent.state import AgentSession as AgentStateSession  # our Pydantic state (aliased to avoid clash)
from src.agent.state import PersistentUserContext
from src.agent.prompts import SYSTEM_PROMPT
from src.database.medplum_client import MedplumClient, get_medplum_client

logger = logging.getLogger("LiveKitWorker")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")


def _load_env() -> None:
    """Parse `.env` into the environment. The LiveKit CLI does NOT auto-load it,
    so the worker (and its spawned job subprocesses, which inherit the env) rely
    on this. Mirrors the loader used by the other entry points."""
    if not os.path.exists(_ENV_PATH):
        return
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


# Optional Cartesia voice override. Leave unset to use the plugin's default voice,
# which is matched to the sonic-3 model (the old sonic-english id is incompatible).
CARTESIA_VOICE = os.environ.get("CARTESIA_VOICE")

# Latency mitigation: if a turn takes longer than this, speak a filler so the
# caller isn't left in silence during multi-step tool/EHR work. Threshold is read
# from FILLER_AFTER_SECONDS at call time (default 4s — only genuinely slow tool
# turns get a filler, not every reply). Set FILLER_AFTER_SECONDS=0 to disable.
_FILLER_PHRASE = os.environ.get("FILLER_PHRASE", "One moment…")

# LiveKit SIP standard participant-attribute keys (set by the SIP gateway).
_ATTR_CALLER_NUMBER = "sip.phoneNumber"        # the external caller's number (inbound)
_ATTR_TRUNK_NUMBER = "sip.trunkPhoneNumber"    # the number that was dialed


# ---------------------------------------------------------------------------
# The Agent: bridges LiveKit turns into our LangGraph ConversationAgent.
# ---------------------------------------------------------------------------
class _BridgeLLM(lk_llm.LLM):
    """Placeholder LLM. LiveKit's AgentSession skips the whole response step when
    `llm is None` (agent_activity: 'skip response if no llm is set'), so we must
    give it a non-None LLM for `llm_node` to be invoked at all. Generation is done
    entirely in HealthcareIntakeAgent.llm_node, so this .chat() is never called."""

    def chat(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError("Generation is handled by llm_node, not _BridgeLLM.chat().")


class HealthcareIntakeAgent(Agent):
    """LiveKit Agent whose "LLM" is our LangGraph orchestrator. STT/VAD/TTS and
    interruption handling are provided by the enclosing AgentSession; reasoning
    and tool execution stay entirely in src/agent.

    Escalation: when the brain runs the `transfer_to_human` tool, we set
    `pending_transfer` so the entrypoint performs a real SIP transfer once the
    farewell has finished playing (see the agent_state_changed handler)."""

    def __init__(self, brain: ConversationAgent):
        # A (never-invoked) LLM is required so AgentSession runs the response step
        # and calls our llm_node override; instructions serve as documentation.
        super().__init__(instructions=SYSTEM_PROMPT, llm=_BridgeLLM())
        self._brain = brain
        self.pending_transfer = False
        self.pending_hangup = False

    async def llm_node(self, chat_ctx, tools, model_settings):  # type: ignore[override]
        """Called once per completed user turn. Feed the transcript into the
        LangGraph brain and stream the reply text out to TTS."""
        user_text = self._latest_user_text(chat_ctx)
        if not user_text.strip():
            logger.info("USER turn had no text; skipping.")
            return

        logger.info("USER: %s", user_text)
        # Latency mitigation (§5.10): the brain may run several LLM + EHR round
        # trips before it can answer. Rather than leave the caller in silence,
        # speak a short filler only if the turn is genuinely slow (multi-step
        # tool/EHR work), not on every reply. Tunable via FILLER_AFTER_SECONDS
        # (0 disables).
        send_task = asyncio.create_task(self._brain.send(user_text))
        try:
            filler_after = float(os.environ.get("FILLER_AFTER_SECONDS", "4"))
        except ValueError:
            filler_after = 4.0
        if filler_after > 0:
            done, _ = await asyncio.wait({send_task}, timeout=filler_after)
            if not done:
                try:
                    self.session.say(_FILLER_PHRASE, add_to_chat_ctx=False)
                except Exception:  # noqa: BLE001 - filler is best-effort
                    logger.debug("filler say failed", exc_info=True)
        try:
            reply = await send_task
        except Exception:  # healthcare error boundary: never crash the call
            logger.exception("Agent brain failed on a turn")
            yield ("I'm sorry, I hit a problem on my end. Let me connect you "
                   "with a member of our team.")
            return

        # Show which tools ran this turn (name + success), no PHI.
        for call in self._brain.last_tool_calls:
            logger.info("  tool %s -> success=%s", call["name"], call["result"].get("success"))

        # If the brain decided to escalate this turn, flag it; the transfer is
        # executed after the farewell is spoken.
        if any(
            c["name"] == "transfer_to_human" and c["result"].get("success")
            for c in self._brain.last_tool_calls
        ):
            logger.info("Escalation requested; will transfer after farewell.")
            self.pending_transfer = True

        # End the call after the closing line if the brain signalled completion.
        if any(
            c["name"] == "end_call" and c["result"].get("success")
            for c in self._brain.last_tool_calls
        ):
            logger.info("Call end requested; will hang up after closing line.")
            self.pending_hangup = True

        logger.info("AGENT: %s", reply)
        if reply:
            yield reply

    @staticmethod
    def _latest_user_text(chat_ctx) -> str:
        for item in reversed(chat_ctx.items):
            if getattr(item, "role", None) == "user":
                return item.text_content or ""
        return ""


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------
def prewarm(proc: JobProcess) -> None:
    """Warm everything a call needs up-front, so nothing heavy blocks the audio path."""
    # VAD is reused across calls.
    proc.userdata["vad"] = silero.VAD.load()
    # Import the heavy LLM/provider modules NOW (protobuf, google-genai, groq):
    # importing them inside the first LLM turn stalls the event loop ~700ms and
    # delays the greeting the caller hears.
    try:
        from src.agent import graph as _graph  # noqa: F401

        providers = []
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: F401

            providers.append("gemini")
        if os.environ.get("GROQ_API_KEY"):
            from langchain_groq import ChatGroq  # noqa: F401

            providers.append("groq")
        logger.info("Prewarmed LLM providers: %s", ", ".join(providers) or "none configured")
    except Exception:  # noqa: BLE001
        # Prewarm must never kill the worker: the entrypoint fails loudly with a
        # clear message if no LLM is actually configured.
        logger.warning("LLM prewarm skipped (will try again per call).")


def _extract_caller_number(participant: rtc.RemoteParticipant) -> Optional[str]:
    attrs = getattr(participant, "attributes", None)
    if not isinstance(attrs, dict):
        # e.g. console mode provides a mock participant with no real attributes.
        return None
    value = attrs.get(_ATTR_CALLER_NUMBER) or attrs.get(_ATTR_TRUNK_NUMBER)
    return value if isinstance(value, str) and value else None


async def _resolve_context(phone: Optional[str], medplum: Optional[MedplumClient]) -> PersistentUserContext:
    """Resolve caller identity from Medplum BEFORE the conversation loop:
    phone -> FHIR Patient + managing Organization (the compartment every tool is
    scoped to). Fail-open so an EHR outage cannot block an incoming call — the
    caller is simply treated as unidentified."""
    context = PersistentUserContext(phone=phone)
    if not phone or not medplum:
        return context

    fhir = await medplum.find_patient_by_phone(phone)
    if fhir:
        context.fhir_patient_id = fhir.get("patient_id")
        context.fhir_organization_id = fhir.get("organization_id")
        context.first_name = fhir.get("first_name")
        context.last_name = fhir.get("last_name")
    return context


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    # A SIP inbound call materialises as a participant joining the room.
    participant = await ctx.wait_for_participant()
    phone = _extract_caller_number(participant)
    logger.info("Call connected (room=%s, identified=%s)", ctx.room.name, bool(phone))

    # --- Identity + tenant isolation resolved up front -----------------------
    medplum = get_medplum_client()
    context = await _resolve_context(phone, medplum)

    # --- Build the LangGraph brain with the resolved context -----------------
    brain = ConversationAgent(session=AgentStateSession(context=context))
    # Start per-call metrics + correlation (traceability §5.35, usage §5.36).
    observability.start_call(brain.session.session_id, channel="voice")
    greeting = await brain.start_with_context()

    # --- Transcript capture (kept in memory, only written to Medplum) --------
    transcript: List[Dict[str, str]] = []

    tts_kwargs: Dict[str, Any] = {"model": "sonic-3"}
    if CARTESIA_VOICE:
        tts_kwargs["voice"] = CARTESIA_VOICE
    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="en-US", interim_results=True),
        tts=cartesia.TTS(**tts_kwargs),
        vad=ctx.proc.userdata["vad"],
    )

    @session.on("user_input_transcribed")
    def _on_transcript(ev) -> None:
        # Live STT output — shows whether the mic/Deepgram is capturing speech.
        marker = "FINAL" if getattr(ev, "is_final", False) else "…"
        logger.info("STT[%s]: %s", marker, ev.transcript)

    @session.on("conversation_item_added")
    def _on_item(ev: ConversationItemAddedEvent) -> None:
        # Not every conversation item is a chat message (e.g. AgentHandoff);
        # only user/assistant messages carry text_content.
        role = getattr(ev.item, "role", None)
        text = getattr(ev.item, "text_content", None)
        if text and role in ("user", "assistant"):
            transcript.append({
                "role": role,
                "text": text,
                "at": datetime.now(timezone.utc).isoformat(),
            })

    # --- Post-call writeback -------------------------------------------------
    async def _on_shutdown() -> None:
        # Transcript → Communication.
        if medplum and transcript and context.fhir_patient_id:
            body = _format_transcript(transcript)
            await medplum.create_communication(
                patient_id=context.fhir_patient_id,
                organization_id=context.fhir_organization_id,
                transcript=body,
                summary=f"AI voice intake call, {len(transcript)} turns.",
            )
        # Per-call metrics summary → log + AuditEvent (observability §5.36/5.40).
        await observability.write_call_audit(
            brain.session.session_id,
            patient_id=context.fhir_patient_id,
            organization_id=context.fhir_organization_id,
        )
        observability.pop_call(brain.session.session_id)

    ctx.add_shutdown_callback(_on_shutdown)

    agent = HealthcareIntakeAgent(brain)

    # --- Human escalation → real SIP transfer --------------------------------
    # Fire once the farewell has been spoken (agent leaves the "speaking" state),
    # so the caller hears "connecting you now" before the leg is transferred.
    async def _do_transfer() -> None:
        transfer_to = os.environ.get("ESCALATION_TRANSFER_TO")
        if not transfer_to:
            logger.warning("Escalation requested but ESCALATION_TRANSFER_TO is not set; cannot transfer.")
            return
        try:
            await ctx.transfer_sip_participant(participant, transfer_to, play_dialtone=True)
            logger.info("SIP transfer to human completed.")
        except Exception:  # noqa: BLE001
            logger.exception("SIP transfer failed")

    async def _do_hangup() -> None:
        try:
            await ctx.delete_room()
            logger.info("Call ended (room deleted).")
        except Exception:  # noqa: BLE001
            logger.exception("Hangup failed")

    @session.on("agent_state_changed")
    def _on_state(ev) -> None:
        # Fire once the closing line has been spoken (agent leaves "speaking").
        if ev.old_state != "speaking":
            return
        if agent.pending_transfer:
            agent.pending_transfer = False
            asyncio.create_task(_do_transfer())
        elif agent.pending_hangup:
            agent.pending_hangup = False
            asyncio.create_task(_do_hangup())

    # --- Go live -------------------------------------------------------------
    await session.start(
        agent=agent,
        room=ctx.room,
        room_options=rtc.RoomOptions(),
    )
    # Speak the greeting produced by the brain (barge-in enabled).
    await session.say(greeting, allow_interruptions=True)


def _format_transcript(turns: List[Dict[str, str]]) -> str:
    speaker = {"user": "Patient", "assistant": "Assistant"}
    lines = [f"{speaker.get(t['role'], t['role'])}: {t['text']}" for t in turns]
    return "\n".join(lines)


WORKER_PORT_ENV = "LIVEKIT_WORKER_PORT"
DEFAULT_WORKER_PORT = 8081


def _port_is_free(port: int) -> bool:
    """True when nothing else is bound to ``port`` on this machine.

    Mirrors the worker's own bind semantics closely enough to catch the
    "another worker is already running" case before LiveKit's CLI aborts.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Windows: without SO_EXCLUSIVEADDRUSE a bind can succeed on a port a
        # second process still holds, hiding the conflict this check looks for.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("", port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def resolve_worker_port(default: int = DEFAULT_WORKER_PORT) -> int:
    """Pick the worker's HTTP port, failing loudly instead of silently.

    The LiveKit worker serves health/token endpoints on ``options.port``
    (8081). Starting a second worker without stopping the first aborts with
    ``OSError: [Errno 10048] error while attempting to bind on address
    ('::', 8081)`` and *no visible output* — which looks exactly like a blank,
    hung worker while calls fail with no agent to answer.

    ``LIVEKIT_WORKER_PORT`` overrides the port (needed to run a second worker,
    e.g. one for SIP and one for the browser playground on the same machine).
    """
    raw = os.environ.get(WORKER_PORT_ENV, "").strip()
    port = default
    if raw:
        try:
            port = int(raw)
        except ValueError:
            raise SystemExit(f"{WORKER_PORT_ENV}={raw!r} is not a port number.")
        if not 1 <= port <= 65535:
            raise SystemExit(f"{WORKER_PORT_ENV}={port} is out of range (1-65535).")
    if _port_is_free(port):
        return port
    raise SystemExit(
        f"Port {port} is already in use, so the worker cannot start.\n"
        "  Another LiveKit worker (or an unrelated app) is holding it. Fix it with either:\n"
        "    * stop the other process, e.g.  Get-Process python | Stop-Process -Force\n"
        f"    * or start this worker on a free port:  $env:{WORKER_PORT_ENV}='8082'\n"
        f"      (PowerShell;  set {WORKER_PORT_ENV}=8082  in cmd.exe)"
    )


if __name__ == "__main__":
    _load_env()  # populate os.environ from .env before the CLI spawns job subprocesses
    from src.logging_setup import setup_logging
    setup_logging()  # LiveKit's CLI also configures logging; this sets our levels/format first
    options = WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm)
    # Dispatch mode:
    #   default -> explicit dispatch as "healthcare-intake" (matches the SIP
    #              dispatch rule in src/voice/livekit_sip_setup.py).
    #   LIVEKIT_AGENT_NAME="" (empty) -> auto-dispatch: the agent joins EVERY room,
    #              which is what the browser Agents Playground / a plain web client
    #              needs (no SIP dispatch rule involved).
    agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "healthcare-intake")
    if agent_name:
        options.agent_name = agent_name
    # Bind the worker's HTTP port up front: a port conflict otherwise aborts with
    # an OSError and no visible output (a second worker still running looks like
    # a blank terminal). See resolve_worker_port for the override.
    options.port = resolve_worker_port()
    logger.info(
        "Starting LiveKit worker on port %s (agent_name=%r)",
        options.port,
        agent_name or "<auto-dispatch>",
    )
    cli.run_app(options)
