# test_twilio_call.py
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

# =====================================================================
# 1. PATH-SAFE .ENV PARSER
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'").strip('"')

# Load keys
ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

# =====================================================================
# Helper function for Basic Authentication & HTTP Requests
# =====================================================================
def make_twilio_request(url, data=None):
    # Setup Basic Authentication manually using standard library
    import base64
    auth_str = f"{ACCOUNT_SID}:{AUTH_TOKEN}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    req_data = urllib.parse.urlencode(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_msg)
        except:
            return e.code, {"message": err_msg}
    except Exception as e:
        return 500, {"message": str(e)}

# =====================================================================
# CLI EXECUTION ENTRY POINT
# =====================================================================
def main():
    print("=" * 70)
    print("             TWILIO PIPELINE CLI VERIFICATION TOOL")
    print("=" * 70)

    # Validate Credential Presence
    if not ACCOUNT_SID or not AUTH_TOKEN or not TWILIO_NUMBER:
        print("❌ Error: Missing credentials in your .env file!")
        print("Please ensure your .env has:")
        print("  - TWILIO_ACCOUNT_SID")
        print("  - TWILIO_AUTH_TOKEN")
        print("  - TWILIO_PHONE_NUMBER")
        sys.exit(1)

    print(f" -> Twilio SID Loaded: {ACCOUNT_SID[:8]}...[Secured]")
    print(f" -> Twilio Trial Number: {TWILIO_NUMBER}")

    # Determine Destination Phone Number
    if len(sys.argv) > 1:
        target_number = sys.argv[1].strip()
    else:
        target_number = input("\nEnter your verified phone number (e.g., +918328565512): ").strip()

    if not target_number.startswith("+"):
        print("\n❌ Error: Number must contain country code (starting with +).")
        print("Example: +918328565512")
        sys.exit(1)

    # 1. Validate Target Number Verification Status
    print(f"\n[Step 1/2] Verifying if {target_number} is registered with Twilio...")
    check_url = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/OutgoingCallerIds.json"
    
    status, res = make_twilio_request(check_url)
    if status != 200:
        print(f"❌ Failed to reach Twilio. API Response: {res.get('message')}")
        sys.exit(1)

    verified_list = [caller["phone_number"] for caller in res.get("outgoing_caller_ids", [])]
    
    if target_number not in verified_list:
        print(f"\n❌ Error: Your target number {target_number} is NOT a verified ID on your Trial account!")
        print("Verified numbers found on this account:")
        for v in verified_list:
            print(f"  * {v}")
        print("\nFix: Go to the Twilio Console and verify your number first:")
        print(" -> https://console.twilio.com/us1/develop/phone-numbers/verified-caller-ids")
        sys.exit(1)
        
    print(f"  ✅ {target_number} is Verified and ready to test!")

    # 2. Trigger Outbound Call with Inline TwiML
    print("\n[Step 2/2] Triggering Call...")
    call_url = f"https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Calls.json"
    
    # Simple TwiML instruction that speaks a verification message directly to the recipient
    test_twiml = (
        "<Response>"
        "<Say voice='Polly.Amy'>"
        "Congratulations! Your Twilio environment integration and credentials are now configured "
        "and working properly. You are ready to run the real-time AI doctor pipeline."
        "</Say>"
        "</Response>"
    )
    
    payload = {
        "To": target_number,
        "From": TWILIO_NUMBER,
        "Twiml": test_twiml
    }

    status, res = make_twilio_request(call_url, data=payload)

    if status in [200, 201]:
        print("\n" + "=" * 70)
        print(" 🎉 SUCCESS: CALL HAS BEEN PLACED SUCCESSFULLY!")
        print(f" Call Sid: {res.get('sid')}")
        print(f" Current Status: {res.get('status')}")
        print("=" * 70)
        print("Your phone should ring in a few seconds. Answer it to hear the verification message.")
    else:
        print("\n" + "=" * 70)
        print(" ❌ OUTBOUND CALL TRANSACTION FAILED")
        print(f" Error Code: {res.get('code', 'Unknown')}")
        print(f" Message: {res.get('message')}")
        print("=" * 70)
        
        # Specific trial account help
        if res.get("code") == 21608 or res.get("code") == 573003:
            print("\nTroubleshooting tips for Trial Accounts:")
            print("1. Ensure your geo-permissions for India (+91) are turned ON:")
            print("   -> https://console.twilio.com/us1/develop/voice/settings/geo-permissions")
            print("2. Ensure your target number is verified in Verified Caller IDs.")

if __name__ == "__main__":
    main()