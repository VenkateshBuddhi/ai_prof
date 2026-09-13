# app.py
import os
import urllib.parse
from fastapi import FastAPI, Request, WebSocket, Response
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import uvicorn
import logging
from src.voice.pipeline import VoicePipeline


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

print("\n" + "="*60)
print("             FASTAPI SERVER STARTUP DIAGNOSTICS")
print("="*60)

if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'").strip('"')
    print("[SUCCESS] Loaded variables from .env file.")
else:
    print("[WARNING] No local .env file found.")

# Validate required variables
REQUIRED_KEYS = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER", "SUPABASE_URL", "SUPABASE_KEY"]
missing = [k for k in REQUIRED_KEYS if not os.environ.get(k)]
if missing:
    print(f"⚠️  Missing keys: {', '.join(missing)}")
else:
    print("[SUCCESS] All database credentials loaded successfully.")

# Check PUBLIC_URL mapping
PUBLIC_URL = os.environ.get("PUBLIC_URL")
if PUBLIC_URL:
    print(f"[SUCCESS] Webhook base routed via public tunnel: {PUBLIC_URL}")
else:
    print("[WARNING] 'PUBLIC_URL' is missing from .env.")
print("="*60 + "\n")

# Logger settings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AppServer")

app = FastAPI(title="Outbound & Inbound Healthcare Voice Agent")

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

# =====================================================================
# DYNAMIC URL RESOLVER
# =====================================================================
def get_public_url(request: Request) -> str:
    if PUBLIC_URL:
        return PUBLIC_URL.rstrip("/")
    forwarded_proto = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "127.0.0.1:8000")
    return f"{forwarded_proto}://{host}"

# =====================================================================
# DIAGNOSTIC TEST ROUTE
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def diagnostic_homepage():
    return """
    <html>
        <head><title>Voice Agent Status</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 100px; background-color: #f4f6f9;">
            <div style="display: inline-block; padding: 30px; background: white; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h1 style="color: #2ec4b6;">🟢 Server is Running!</h1>
                <p style="font-size: 18px; color: #555;">Your FastAPI database-linked web server is online and successfully receiving connections.</p>
                <p style="color: #888;">If you can see this page using your <b>Ngrok URL</b>, then your tunnel is working perfectly!</p>
            </div>
        </body>
    </html>
    """

# =====================================================================
# INBOUND ROUTE
# =====================================================================
@app.post("/inbound-call")
async def handle_inbound_call(request: Request):
    logger.info("👉 Incoming POST request received on /inbound-call")
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown_sid")
    from_number = form_data.get("From", "anonymous")
    
    safe_phone = urllib.parse.quote(from_number)
    base_url = get_public_url(request)
    ws_host = base_url.replace("https://", "").replace("http://", "")
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{ws_host}/media-stream?call_sid={call_sid}&amp;phone={safe_phone}&amp;direction=inbound" />
    </Connect>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")

# =====================================================================
# OUTBOUND ROUTES & TRIGGER
# =====================================================================
@app.post("/make-outbound-call")
async def make_outbound_call(request: Request):
    logger.info("👉 Request received on /make-outbound-call")
    try:
        body = await request.json()
        to_phone = body.get("to_phone")
        
        if not to_phone:
            return JSONResponse(status_code=400, content={"error": "Missing 'to_phone' parameter."})
        
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
            return JSONResponse(status_code=500, content={"error": "Twilio Credentials are not configured."})
        
        public_base = get_public_url(request)
        safe_phone = urllib.parse.quote(to_phone)
        twiml_handler_url = f"{public_base}/outbound-twiml?phone={safe_phone}"
        
        twilio_api_url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json"
        
        payload = {
            "To": to_phone,
            "From": TWILIO_PHONE_NUMBER,
            "Url": twiml_handler_url
        }
        
        async with httpx.AsyncClient() as client:
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            response = await client.post(twilio_api_url, data=payload, auth=auth)
            
            if response.status_code in [200, 201]:
                call_data = response.json()
                logger.info(f"Outbound Call successfully triggered to {to_phone}. CallSid: {call_data.get('sid')}")
                return {"success": True, "call_sid": call_data.get("sid")}
            else:
                logger.error(f"Twilio API Rejected Call: {response.status_code} - {response.text}")
                return JSONResponse(status_code=500, content={"error": "Twilio API transaction failed", "details": response.text})
                
    except Exception as e:
        logger.error(f"Failed to initiate outbound call: {str(e)}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/outbound-twiml")
async def handle_outbound_twiml(request: Request):
    logger.info("👉 Incoming POST request received on /outbound-twiml")
    params = request.query_params
    phone = params.get("phone", "anonymous")
    
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown_sid")
    
    safe_phone = urllib.parse.quote(phone)
    base_url = get_public_url(request)
    ws_host = base_url.replace("https://", "").replace("http://", "")
    
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{ws_host}/media-stream?call_sid={call_sid}&amp;phone={safe_phone}&amp;direction=outbound" />
    </Connect>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")

# =====================================================================
# BI-DIRECTIONAL WEBSOCKET STREAM HANDLER
# =====================================================================
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    
    params = websocket.query_params
    call_sid = params.get("call_sid")
    phone = urllib.parse.unquote(params.get("phone", ""))
    direction = params.get("direction", "inbound")
    
    logger.info(f"👉 WebSocket handshake connected on /media-stream?direction={direction}")
    
    if not call_sid:
        logger.error("Websocket rejected: No CallSid found.")
        await websocket.close(code=1008)
        return
        
    pipeline = VoicePipeline(call_sid=call_sid, phone_number=phone, direction=direction)
    
    try:
        await pipeline.handle_inbound_stream(websocket)
    except Exception as e:
        logger.error(f"WebSocket session error: {str(e)}")
    finally:
        logger.info(f"WebSocket closed cleanly for Call: {call_sid}")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)