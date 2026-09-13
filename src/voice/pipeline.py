# src/voice/pipeline.py
import os
import io
import json
import wave
import asyncio
import base64
import struct
import math
import httpx
import websockets
import logging
from typing import Optional, Tuple
from src.database.supabase_db import SupabaseClient
from src.voice.capabilities import SESSION_STORE, execute_tool, TOOLS_SCHEMA, lookup_and_register_patient, CallSession

logger = logging.getLogger("VoicePipeline")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CARTESIA_API_KEY = os.environ.get("CARTESIA_API_KEY")

SYSTEM_PROMPT = """You are an elite conversational scheduling agent.
Your core goal is to guide patients through finding medical specialists, checking calendars, confirming slots, and answering follow-up questionnaires.

CLINICAL SPECIFICITY LAWS:
1. Patient Intent Mapping: Listen carefully to physical symptoms and infer the matching department for scheduling.
   - Example: "knee pain", "shoulder pain", "broken bone" -> Map to Orthopedics.
   - Example: "chest pain", "heart racing" -> Map to Cardiology.
   - Example: "skin rash", "moles" -> Map to Dermatology.
2. Clinical Distinction Rule: You must distinguish a patient-reported symptom from an official medical diagnosis. Use cautious, objective language. Do not state what medical conditions they have. Clarify that you are scheduling a specialist to evaluate and diagnose them.
3. Concise Responses: Speak in short, simple sentences (1-2 sentences max). This is a telephone voice conversation.
4. Active States: Once an appointment is booked and verified, transition to asking the clinical pre-visit questionnaire questions to gather pre-visit context.
"""

# Audio VAD Configuration Constants
RMS_SPEECH_THRESHOLD = 1000
SILENCE_TIMEOUT_FRAMES = 40
MAX_UTTERANCE_DURATION = 8.0

# =====================================================================
# COMPATIBILITY LAYER: Pure-Python audioop fallback
# =====================================================================
try:
    import audioop
    HAS_AUDIOOP = True
except ImportError:
    HAS_AUDIOOP = False
    MULAW_TO_LINEAR_LUT = []
    for i in range(256):
        mu_byte = ~i & 0xFF
        sign = (mu_byte & 0x80)
        exponent = (mu_byte >> 4) & 0x07
        mantissa = mu_byte & 0x0F
        sample = ((mantissa << 1) + 33) << exponent
        sample -= 33
        val = -sample if sign else sample
        val = max(-32768, min(32767, val))
        MULAW_TO_LINEAR_LUT.append(val)

def safe_ulaw2lin(fragment: bytes) -> bytes:
    if HAS_AUDIOOP:
        return audioop.ulaw2lin(fragment, 2)
    samples = [MULAW_TO_LINEAR_LUT[b] for b in fragment]
    return struct.pack(f"<{len(samples)}h", *samples)

def safe_rms(fragment: bytes) -> int:
    if HAS_AUDIOOP:
        return audioop.rms(fragment, 2)
    num_samples = len(fragment) // 2
    if num_samples == 0:
        return 0
    samples = struct.unpack(f"<{num_samples}h", fragment)
    sum_squares = sum(sample * sample for sample in samples)
    return int(math.sqrt(sum_squares / num_samples))

# =====================================================================
# Voice Pipeline Class Implementation
# =====================================================================
class VoicePipeline:
    def __init__(self, call_sid: str, phone_number: str, direction: str = "inbound"):
        self.call_sid = call_sid
        self.phone_number = phone_number
        self.direction = direction
        self.twilio_ws: websockets.WebSocketServerProtocol = None
        self.stream_sid = None
        
        # State Management
        self.is_playing = False
        self.interruption_event = asyncio.Event()
        self.tts_task = None
        self.llm_task = None

        self.audio_buffer = bytearray()
        self.silence_counter = 0
        self.speech_detected = False

        if self.call_sid not in SESSION_STORE:
            SESSION_STORE[self.call_sid] = CallSession(call_sid=self.call_sid)

        self.session = SESSION_STORE[self.call_sid]
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    async def initialize_session_context(self):
        """Step 5: Resolve context and register new patients in Supabase if needed."""
        pat_res = await lookup_and_register_patient(self.call_sid, self.phone_number)
        if pat_res["success"]:
            data = pat_res["data"]
            self.session.context.patient_id = data["id"]
            self.session.context.first_name = data["first_name"]
            self.session.context.last_name = data["last_name"]
            
            # Save profile preferences
            if "hospitals" in data and data["hospitals"]:
                self.session.context.preferred_hospital_id = data["preferred_hospital_id"]
                
            # Log registration analytics (Step 20)
            await SupabaseClient.log_analytics(self.call_sid, "patient_lookup", "status", 1.0)
            
            # Inject context snippet into LLM memory
            context_snippet = (
                f"Active Patient Profile: Name is {data['first_name']} {data['last_name']}. "
                f"Preferred Hospital ID: {data.get('preferred_hospital_id', 'None')}."
            )
            self.history.append({"role": "system", "content": context_snippet})

    async def handle_inbound_stream(self, twilio_ws: websockets.WebSocketServerProtocol):
        """Processes real-time Twilio media, measures VAD thresholds, handles barge-in, and schedules Groq tasks."""
        self.twilio_ws = twilio_ws
        await self.initialize_session_context()

        # Build dynamic prompt greeting (Step 2)
        if self.session.context.first_name and self.session.context.first_name != "Unregistered":
            greeting = f"Hello {self.session.context.first_name}, I am your clinic's assistant. How can I help you today?"
        else:
            greeting = "Hello, I am your clinic's assistant. How can I help you today?"

        self.history.append({"role": "assistant", "content": greeting})
        asyncio.create_task(self.stream_text_to_audio(greeting))

        try:
            while True:
                message_str = await twilio_ws.recv()
                if not message_str:
                    break
                
                msg = json.loads(message_str)
                event = msg.get("event")
                
                if event == "start":
                    self.stream_sid = msg["start"]["streamSid"]
                
                elif event == "media":
                    media_payload = msg["media"]["payload"]
                    raw_audio_bytes = base64.b64decode(media_payload)
                    linear_pcm = safe_ulaw2lin(raw_audio_bytes)
                    rms_energy = safe_rms(linear_pcm)
                    
                    if rms_energy > RMS_SPEECH_THRESHOLD:
                        if self.is_playing:
                            logger.info(f"[Barge-In] Energy spike ({rms_energy}) detected. Interruption triggered.")
                            await self._execute_interruption_cut()
                        
                        self.audio_buffer.extend(raw_audio_bytes)
                        self.silence_counter = 0
                        self.speech_detected = True
                    else:
                        if self.speech_detected:
                            self.audio_buffer.extend(raw_audio_bytes)
                            self.silence_counter += 1
                            buffer_duration = len(self.audio_buffer) / 8000.0
                            
                            if self.silence_counter >= SILENCE_TIMEOUT_FRAMES or buffer_duration >= MAX_UTTERANCE_DURATION:
                                logger.info(f"[Silence Handling] Triggering speech collection of {round(buffer_duration, 2)}s.")
                                captured_utterance = bytes(self.audio_buffer)
                                self.audio_buffer.clear()
                                self.silence_counter = 0
                                self.speech_detected = False
                                
                                if self.llm_task and not self.llm_task.done():
                                    self.llm_task.cancel()
                                self.llm_task = asyncio.create_task(self._process_voice_turn(captured_utterance))
                
                elif event == "stop":
                    break
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Error handling audio stream: {e}", exc_info=True)

    async def _execute_interruption_cut(self):
        self.interruption_event.set()
        self.is_playing = False
        self.audio_buffer.clear()
        self.speech_detected = False
        self.silence_counter = 0
        
        if self.tts_task and not self.tts_task.done():
            self.tts_task.cancel()
        if self.llm_task and not self.llm_task.done():
            self.llm_task.cancel()

        if self.twilio_ws and self.stream_sid:
            clear_packet = {"event": "clear", "streamSid": self.stream_sid}
            await self.twilio_ws.send(json.dumps(clear_packet))

    async def _process_voice_turn(self, raw_mulaw_bytes: bytes):
        """Processes the conversational turn: Transcription, State Evaluation, Tool Routing, and Questionnaire Tracking."""
        self.interruption_event.clear()
        try:
            # Step 3 Describe Requirement / STT conversion
            wav_payload = self._convert_mulaw_to_wav(raw_mulaw_bytes)
            transcript = await self._transcribe_with_groq_whisper(wav_payload)
            if not transcript or len(transcript.strip()) < 2:
                return
            
            logger.info(f"Patient input: '{transcript}'")
            self.history.append({"role": "user", "content": transcript})
            
            # --- EVALUATE ACTIVE CONVERSATION STATE ---
            
            # Scenario A: The questionnaire workflow is active (Steps 16-18)
            if self.session.state.questionnaire_active:
                await self._handle_questionnaire_input(transcript)
                return
                
            # Scenario B: Standard scheduling mode
            assistant_response, tool_calls = await self._query_groq_llm()
            
            if tool_calls:
                for call in tool_calls:
                    tool_name = call["name"]
                    tool_args = json.loads(call["arguments"])
                    
                    if self.interruption_event.is_set():
                        return
                    
                    # Tool execution mapped against Supabase
                    tool_output = await execute_tool(tool_name, tool_args, self.call_sid)
                    
                    # Log integration events
                    await SupabaseClient.log_analytics(self.call_sid, f"tool_{tool_name}", "execution", 1.0)
                    
                    if tool_output.get("action") == "TRANSFER" and self.twilio_ws:
                        await self.stream_text_to_audio("I am transferring you to support immediately. Please hold.")
                        await asyncio.sleep(2.0)
                        transfer_payload = {
                            "event": "transfer",
                            "streamSid": self.stream_sid,
                            "destination": tool_output["destination_sip"]
                        }
                        await self.twilio_ws.send(json.dumps(transfer_payload))
                        return
                    
                    self.history.append({
                        "role": "function",
                        "name": tool_name,
                        "content": json.dumps(tool_output)
                    })
                
                # Fetch follow-up text once tool execution updates state
                assistant_response, _ = await self._query_groq_llm()

            # Dynamic Check: Transition directly to the Pre-Visit Questionnaire if an appointment is confirmed
            if self.session.state.appointment_status == "CONFIRMED" and not self.session.state.questionnaire_active:
                await self._trigger_questionnaire_pipeline(assistant_response)
                return

            if assistant_response and not self.interruption_event.is_set():
                self.history.append({"role": "assistant", "content": assistant_response})
                self.tts_task = asyncio.create_task(self.stream_text_to_audio(assistant_response))
                await self.tts_task

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error during conversational turn: {e}", exc_info=True)

    # =====================================================================
    # PRE-VISIT QUESTIONNAIRE WORKFLOW ENGINE (Steps 15-18)
    # =====================================================================
    async def _trigger_questionnaire_pipeline(self, confirmation_speech: str):
        """Step 15 & 16: Initializes the pre-visit questionnaire state and schedules follow-up tasks."""
        logger.info("[Step 15 Follow-Up] Triggering clinical tasks & questionnaires.")
        
        # Load doctor-specific questions from Supabase
        # Hardcoding the Orthopedic specialist doctor ID mapped in SQL seed for demo integrity
        target_doc = "d3333333-3333-3333-3333-333333333333"
        questions = await SupabaseClient.load_questionnaire(target_doc)
        
        if questions:
            self.session.state.questionnaire_active = True
            self.session.state.questions = questions
            self.session.state.current_question_index = 0
            
            # Merge EHR booking confirmation with the first questionnaire screener question (Step 16)
            intro_greeting = (
                f"{confirmation_speech} Your appointment is confirmed! "
                "Dr. Jenkins has three quick questions to help prepare for your visit. "
                f"First question: {questions[0]['question_text']}"
            )
            
            self.history.append({"role": "assistant", "content": intro_greeting})
            self.tts_task = asyncio.create_task(self.stream_text_to_audio(intro_greeting))
            await self.tts_task
        else:
            # Fallback if no questions are found
            self.history.append({"role": "assistant", "content": confirmation_speech})
            self.tts_task = asyncio.create_task(self.stream_text_to_audio(confirmation_speech))
            await self.tts_task

    async def _handle_questionnaire_input(self, patient_response: str):
        """Conversationally collects and stores responses (Steps 17 & 18)."""
        idx = self.session.state.current_question_index
        questions = self.session.state.questions
        appointment_id = self.session.state.appointment_id
        
        # Step 18: Store response in Supabase
        current_q = questions[idx]
        await SupabaseClient.save_questionnaire_response(
            appointment_id=appointment_id,
            question_id=current_q["id"],
            response_text=patient_response
        )
        
        logger.info(f"[Step 18 Response Stored] Q: {current_q['question_text']} -> R: {patient_response}")
        
        # Advance index to check for remaining questions
        next_idx = idx + 1
        if next_idx < len(questions):
            self.session.state.current_question_index = next_idx
            next_q = questions[next_idx]
            next_speech = f"Got it. Next question: {next_q['question_text']}"
            
            self.history.append({"role": "assistant", "content": next_speech})
            self.tts_task = asyncio.create_task(self.stream_text_to_audio(next_speech))
            await self.tts_task
        else:
            # Questionnaire complete
            self.session.state.questionnaire_active = False
            closing_speech = "Thank you so much for completing those responses. They have been sent to Dr. Jenkins for review. We look forward to seeing you!"
            
            # Log final workflow and clinical analytics (Step 20)
            await SupabaseClient.log_analytics(self.call_sid, "questionnaire", "completion_status", 1.0)
            
            self.history.append({"role": "assistant", "content": closing_speech})
            self.tts_task = asyncio.create_task(self.stream_text_to_audio(closing_speech))
            await self.tts_task

    # =====================================================================
    # TRANSCRIPTION & SYNTHESIS CONNECTORS
    # =====================================================================
    def _convert_mulaw_to_wav(self, mulaw_bytes: bytes) -> bytes:
        linear_pcm = safe_ulaw2lin(mulaw_bytes)
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(8000)
            wav_file.writeframes(linear_pcm)
        return wav_io.getvalue()

    async def _transcribe_with_groq_whisper(self, wav_bytes: bytes) -> Optional[str]:
        url = "https://api.groq.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        files = {"file": ("input.wav", wav_bytes, "audio/wav")}
        data = {"model": "whisper-large-v3-turbo", "language": "en", "temperature": "0.0"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, files=files, data=data, timeout=5.0)
                if response.status_code == 200:
                    return response.json().get("text", "")
            except Exception as e:
                logger.error(f"Failed calling Groq Whisper API: {e}")
        return None

    async def _query_groq_llm(self) -> Tuple[Optional[str], Optional[list]]:
        url = "https://api.groq.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": self.history,
            "tools": [{"type": "function", "function": t} for t in TOOLS_SCHEMA],
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 150
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=5.0)
            if response.status_code != 200:
                return "I'm sorry, I'm experiencing system network delays. Could you repeat that?", None
            
            res_json = response.json()
            message = res_json["choices"][0]["message"]
            text_reply = message.get("content")
            tool_calls = message.get("tool_calls")
            
            pydantic_tool_calls = None
            if tool_calls:
                pydantic_tool_calls = []
                for tc in tool_calls:
                    pydantic_tool_calls.append({
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"]
                    })
            return text_reply, pydantic_tool_calls

    async def stream_text_to_audio(self, text: str):
        if not text:
            return
        self.is_playing = True
        cartesia_ws_url = f"wss://api.cartesia.ai/tts/websocket?api_key={CARTESIA_API_KEY}&v=2024-06-10"
        
        try:
            async with websockets.connect(cartesia_ws_url) as cart_ws:
                req = {
                    "model_id": "sonic-english",
                    "transcript": text,
                    "voice": {
                        "mode": "id",
                        "id": "e0e29b11-d0db-40a2-b9cf-2b62d3bc47fc"
                    },
                    "output_format": {
                        "container": "raw",
                        "encoding": "mulaw",
                        "sample_rate": 8000
                    }
                }
                await cart_ws.send(json.dumps(req))
                
                async for response_str in cart_ws:
                    if self.interruption_event.is_set():
                        break
                    resp = json.loads(response_str)
                    if "audio" in resp:
                        chunk_b64 = resp["audio"]
                        twilio_payload = {
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": chunk_b64}
                        }
                        await self.twilio_ws.send(json.dumps(twilio_payload))
                        await asyncio.sleep(0.002)
                    if resp.get("done", False):
                        break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Failure inside Cartesia: {e}")
        finally:
            self.is_playing = False