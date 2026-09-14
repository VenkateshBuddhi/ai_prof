# src/api/routers/voice.py — mint a LiveKit token so the browser can talk to the agent
import asyncio
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = logging.getLogger("VoiceAPI")


class TokenBody(BaseModel):
    identity: Optional[str] = None
    name: Optional[str] = None
    room: Optional[str] = None


@router.post("/token")
async def voice_token(body: TokenBody):
    """Return a LiveKit URL + access token for the patient AI Assistant page.
    The `livekit_worker` (auto-dispatch, or dispatched into the room) answers.
    Requires LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET."""
    url = os.environ.get("LIVEKIT_URL")
    key = os.environ.get("LIVEKIT_API_KEY")
    secret = os.environ.get("LIVEKIT_API_SECRET")
    if not (url and key and secret):
        raise HTTPException(503, "LiveKit credentials not configured in environment")

    from livekit import api as lk

    identity = body.identity or f"web-{uuid.uuid4().hex[:8]}"
    room = body.room or f"web-{uuid.uuid4().hex[:8]}"
    token = (
        lk.AccessToken(key, secret)
        .with_identity(identity)
        .with_name(body.name or identity)
        .with_grants(lk.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True))
        .to_jwt()
    )

    # Dispatch the agent into this room so the browser caller is answered.
    # LiveKit REST API requires HTTP(S) protocol rather than WSS.
    agent_name = os.environ.get("LIVEKIT_AGENT_NAME", "healthcare-intake")
    http_url = url.replace("wss://", "https://").replace("ws://", "http://")
    
    try:
        lkapi = lk.LiveKitAPI(http_url, key, secret)
        try:
            await asyncio.wait_for(
                lkapi.agent_dispatch.create_dispatch(
                    lk.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
                ),
                timeout=2.5,
            )
            logger.info("Agent dispatch created for room=%s agent=%s", room, agent_name)
        finally:
            await lkapi.aclose()
    except Exception as e:  # noqa: BLE001
        logger.warning("agent dispatch optional warning: %s (%s)", type(e).__name__, str(e))

    return {"url": url, "token": token, "room": room, "identity": identity, "agent": agent_name}
