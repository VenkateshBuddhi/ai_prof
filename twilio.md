# Twilio → LiveKit (trial account, no SIP Trunking)

How to receive real phone calls into the voice agent using a **free Twilio trial
account** — via Programmable Voice `<Dial><Sip>`, which trial accounts support.
This avoids Elastic SIP Trunking (a paid product).

```
Caller's phone ──PSTN──▶ Twilio trial number
                           │  (Voice webhook returns TwiML)
                           ▼
                     <Dial><Sip> sip:+15862312153@5fsvvud7bbt.sip.livekit.cloud
                           │
                           ▼
                   LiveKit inbound trunk (matches +15862312153)
                           ▼
                   Dispatch rule ─▶ agent "healthcare-intake"
                           ▼
                   src/voice/livekit_worker.py answers
```

## Key idea (read this first)

The number inside the SIP URI — `+15862312153` — is **not** your new Twilio
number. It is the number registered on the **LiveKit inbound trunk** (created by
`src/voice/livekit_sip_setup.py`). LiveKit matches the inbound call to that trunk
by this value, so keep it as-is regardless of what your new Twilio trial number
is. (If you'd rather match your real number, re-run
`uv run python -m src.voice.livekit_sip_setup --recreate --number <your-new-number>`
and use that number in the SIP URI instead.)

Your LiveKit SIP host is `5fsvvud7bbt.sip.livekit.cloud` (from LiveKit Cloud →
Settings → SIP). Confirm it hasn't changed if you make a new LiveKit project.

## Prerequisites (already done in this repo)

- LiveKit inbound trunk + dispatch rule exist:
  `uv run python -m src.voice.livekit_sip_setup --list`
- The worker runs and registers as `healthcare-intake`.
- `.env` has `LIVEKIT_*`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, `GROQ_API_KEY`,
  `MEDPLUM_CLIENT_ID/SECRET`. (Twilio credentials are **not** needed for this path.)

## Steps (after creating the new Twilio trial account)

1. **Get a trial phone number.**
   Twilio Console → Phone Numbers → Manage → Buy a number (trial gives one free).
   Make sure it has the **Voice** capability.

2. **(Only if calling from a specific phone) verify your caller phone.**
   Trial accounts restrict *outbound* calls to verified numbers; *inbound* calls
   to your trial number generally work. If prompted, verify the phone you'll dial
   from under Phone Numbers → Verified Caller IDs.

3. **Create a TwiML Bin.**
   Console → Developer tools → TwiML Bins → Create new. Name it `livekit-sip`.
   Paste exactly:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
     <Dial answerOnBridge="true">
       <Sip>sip:+15862312153@5fsvvud7bbt.sip.livekit.cloud</Sip>
     </Dial>
   </Response>
   ```
   Save.

4. **Point the number at the TwiML Bin.**
   Phone Numbers → Manage → Active numbers → click your trial number →
   **Voice Configuration** → "A call comes in" → **TwiML Bin** → select
   `livekit-sip` → Save.

5. **(Optional) set the human-transfer target** in `.env` so escalation works on
   a real call:
   ```
   ESCALATION_TRANSFER_TO=tel:+<your-support-number>
   ```

6. **Start the worker** (explicit dispatch — default agent name matches the rule):
   ```bash
   uv run python -m src.voice.livekit_worker start
   ```
   Wait for a `registered worker id=…` line. Leave it running.

7. **Call your Twilio trial number** from your phone.
   - You'll hear the trial preamble: *"You have a trial account… press any key
     to execute your code."* Press any key.
   - Twilio then bridges to LiveKit and the agent greets you.
   - Try: *"I'd like to book a cardiologist."*

## What success looks like

- **LiveKit Cloud → Telephony/SIP logs**: the inbound call now appears (was 0).
- **Worker logs**: `Call connected … STT[FINAL]: … → USER: … → tool … -> success → AGENT: …`
- Since it's a real call, the caller number is resolved against Medplum; an
  unknown caller is offered registration, then booking → questionnaire → the
  agent says goodbye and hangs up (`end_call`).

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| "You have a trial account, press any key" then **application error** | The number still points at an old webhook, not the TwiML Bin. Re-check step 4. |
| "The service you have requested is unavailable" + LiveKit shows **0 calls** | Twilio couldn't reach LiveKit. Verify the SIP host `5fsvvud7bbt.sip.livekit.cloud` and, if it times out, change the `<Sip>` URI to `sip:+15862312153@5fsvvud7bbt.sip.livekit.cloud;transport=tcp`. |
| Account **suspended due to lack of funds** | Trial credit exhausted — this is why the previous account failed. Use a fresh trial (or add funds). |
| Call connects but **no agent answers** (silence) | Worker not running/registered, or dispatch name mismatch. Confirm `registered worker` and that the dispatch rule's agent is `healthcare-intake` (`livekit_sip_setup.py --list`). |
| Agent answers but says just "Hi" (not your name) | Expected unless your caller number exists as a Patient in Medplum. It will offer to register. |
| LiveKit shows the call but it drops immediately | Trunk number mismatch — the `<Sip>` user (`+15862312153`) must equal the inbound trunk's `numbers`. |

## Notes / limits of the trial path

- The trial preamble ("press any key") is unavoidable on trial accounts.
- Trial credit is limited (~$15) — fine for testing, not production.
- No SIP Trunking is used, so there's nothing to configure under Elastic SIP
  Trunking; everything is the number's Voice webhook (the TwiML Bin).
- SIP transfer (`transfer_to_human`) and hang-up (`end_call`) are exercised on
  this path; if transfer behaves oddly over `<Dial><Sip>`, note it and we can
  adjust (it's the one behavior that differs from a true SIP trunk).
