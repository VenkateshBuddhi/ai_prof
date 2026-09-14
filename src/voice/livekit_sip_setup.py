# src/voice/livekit_sip_setup.py
"""Provision the LiveKit side of the telephony path (one-time / idempotent).

Creates:
  1. a SIP **inbound trunk** — accepts the SIP calls your Twilio trunk sends;
  2. a SIP **dispatch rule** — routes each inbound call into its own room and
     dispatches this agent (by name) to handle it.

After running this, finish on the Twilio side (console, not code): point your
Elastic SIP Trunk's ORIGINATION URI at LiveKit's SIP host, e.g.
    sip:<your-project>.sip.livekit.cloud
so calls to your Twilio number are delivered to LiveKit → this dispatch rule →
`src/voice/livekit_worker.py`.

Run:
    uv run python -m src.voice.livekit_sip_setup                 # create if missing
    uv run python -m src.voice.livekit_sip_setup --list          # show current config
    uv run python -m src.voice.livekit_sip_setup --recreate      # delete + recreate

Environment (from .env):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET   (required)
    TWILIO_PHONE_NUMBER   the number callers dial (E.164). Falls back to --number.
    LIVEKIT_AGENT_NAME    the agent to dispatch (default: healthcare-intake).
                          MUST match WorkerOptions.agent_name in the worker.
    SIP_TRUNK_AUTH_USERNAME / SIP_TRUNK_AUTH_PASSWORD   optional inbound auth
                          (recommended; must match Twilio origination credentials).
"""
from __future__ import annotations

import argparse
import asyncio
import os

from livekit import api

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

TRUNK_NAME = "ai-prof-inbound"
RULE_NAME = "ai-prof-inbound-rule"
DEFAULT_AGENT_NAME = "healthcare-intake"
ROOM_PREFIX = "call-"


def _load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


def _lk() -> api.LiveKitAPI:
    for k in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        if not os.environ.get(k):
            raise SystemExit(f"Missing {k} in environment/.env")
    return api.LiveKitAPI()  # reads LIVEKIT_URL / API_KEY / API_SECRET


async def _list(lk: api.LiveKitAPI) -> None:
    trunks = await lk.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    rules = await lk.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
    print("Inbound trunks:")
    for t in trunks.items:
        print(f"  {t.sip_trunk_id}  name={t.name!r}  numbers={list(t.numbers)}")
    print("Dispatch rules:")
    for r in rules.items:
        agents = []
        if r.room_config and r.room_config.agents:
            agents = [a.agent_name for a in r.room_config.agents]
        print(f"  {r.sip_dispatch_rule_id}  name={r.name!r}  trunks={list(r.trunk_ids)}  agents={agents}")


async def _delete_existing(lk: api.LiveKitAPI) -> None:
    trunks = await lk.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    for t in trunks.items:
        if t.name == TRUNK_NAME:
            await lk.sip.delete_sip_trunk(api.DeleteSIPTrunkRequest(sip_trunk_id=t.sip_trunk_id))
            print(f"Deleted trunk {t.sip_trunk_id}")
    rules = await lk.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
    for r in rules.items:
        if r.name == RULE_NAME:
            await lk.sip.delete_sip_dispatch_rule(api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=r.sip_dispatch_rule_id))
            print(f"Deleted dispatch rule {r.sip_dispatch_rule_id}")


async def _ensure_trunk(lk: api.LiveKitAPI, number: str) -> str:
    existing = await lk.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    for t in existing.items:
        if t.name == TRUNK_NAME:
            print(f"Inbound trunk already exists: {t.sip_trunk_id}")
            return t.sip_trunk_id

    trunk = api.SIPInboundTrunkInfo(
        name=TRUNK_NAME,
        numbers=[number] if number else [],
    )
    # Optional inbound auth (recommended). Must match Twilio origination creds.
    user = os.environ.get("SIP_TRUNK_AUTH_USERNAME")
    pw = os.environ.get("SIP_TRUNK_AUTH_PASSWORD")
    if user and pw:
        trunk.auth_username = user
        trunk.auth_password = pw

    created = await lk.sip.create_sip_inbound_trunk(api.CreateSIPInboundTrunkRequest(trunk=trunk))
    print(f"Created inbound trunk {created.sip_trunk_id} (numbers={list(created.numbers)}, auth={'yes' if user and pw else 'none'})")
    return created.sip_trunk_id


async def _ensure_rule(lk: api.LiveKitAPI, trunk_id: str, agent_name: str) -> str:
    existing = await lk.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
    for r in existing.items:
        if r.name == RULE_NAME:
            print(f"Dispatch rule already exists: {r.sip_dispatch_rule_id}")
            return r.sip_dispatch_rule_id

    req = api.CreateSIPDispatchRuleRequest(
        name=RULE_NAME,
        trunk_ids=[trunk_id],
        # Each caller gets their own room (call-XXXX).
        rule=api.SIPDispatchRule(
            dispatch_rule_individual=api.SIPDispatchRuleIndividual(room_prefix=ROOM_PREFIX),
        ),
        # Dispatch our agent into that room. agent_name must match the worker's
        # WorkerOptions.agent_name (LIVEKIT_AGENT_NAME).
        room_config=api.RoomConfiguration(
            agents=[api.RoomAgentDispatch(agent_name=agent_name)],
        ),
    )
    created = await lk.sip.create_sip_dispatch_rule(req)
    print(f"Created dispatch rule {created.sip_dispatch_rule_id} -> agent {agent_name!r}, rooms {ROOM_PREFIX}*")
    return created.sip_dispatch_rule_id


async def _run(list_only: bool, recreate: bool, number: str) -> None:
    lk = _lk()
    try:
        if list_only:
            await _list(lk)
            return
        if recreate:
            await _delete_existing(lk)

        agent_name = os.environ.get("LIVEKIT_AGENT_NAME", DEFAULT_AGENT_NAME)
        if not number:
            print("WARNING: no phone number set (TWILIO_PHONE_NUMBER or --number); "
                  "trunk will accept any inbound number.")
        trunk_id = await _ensure_trunk(lk, number)
        await _ensure_rule(lk, trunk_id, agent_name)

        print("\nDone. Next steps:")
        print(f"  1. Run the worker with a matching agent name:")
        print(f"       LIVEKIT_AGENT_NAME={agent_name} uv run python -m src.voice.livekit_worker start")
        print(f"  2. In Twilio, point your Elastic SIP Trunk ORIGINATION URI at your LiveKit SIP host")
        print(f"     (Project Settings -> the sip: URI, e.g. sip:<project>.sip.livekit.cloud).")
        print(f"  3. Call {number or 'your Twilio number'} — the dispatch rule sends it to the agent.")
    finally:
        await lk.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision LiveKit SIP inbound trunk + dispatch rule")
    parser.add_argument("--list", action="store_true", help="Show current trunks/rules and exit")
    parser.add_argument("--recreate", action="store_true", help="Delete existing ai-prof trunk/rule first")
    parser.add_argument("--number", help="Inbound number (E.164); defaults to TWILIO_PHONE_NUMBER")
    args = parser.parse_args()

    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    number = args.number or os.environ.get("TWILIO_PHONE_NUMBER", "")
    asyncio.run(_run(args.list, args.recreate, number))


if __name__ == "__main__":
    main()
