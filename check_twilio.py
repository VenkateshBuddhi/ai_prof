# check_twilio.py
import os
import httpx

# Load .env variables manually
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

# Twilio variables
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER")
target_phone = "+918328565512"

print("="*70)
print("             TWILIO TRIAL ACCOUNT DIAGNOSTICS")
print("="*70)

if not account_sid or not auth_token:
    print("❌ Error: Missing Twilio Credentials in .env file.")
    exit(1)

auth = (account_sid, auth_token)

# 1. Check Twilio Active purchased Phone Numbers
incoming_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/IncomingPhoneNumbers.json"
# 2. Check Twilio Verified Outbound Caller IDs
verified_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/OutgoingCallerIds.json"

with httpx.Client() as client:
    # Query Purchased Numbers
    inc_resp = client.get(incoming_url, auth=auth)
    # Query Verified Recipient IDs
    ver_resp = client.get(verified_url, auth=auth)

    if inc_resp.status_code != 200 or ver_resp.status_code != 200:
        print("❌ API Authentication Failed! Check your Account SID or Auth Token.")
        print(f"Incoming Code: {inc_resp.status_code}, Verified Code: {ver_resp.status_code}")
        exit(1)

    purchased_numbers = [num["phone_number"] for num in inc_resp.json().get("incoming_phone_numbers", [])]
    verified_numbers = [num["phone_number"] for num in ver_resp.json().get("outgoing_caller_ids", [])]

    print("\n--- [1/2] PURCHASED TWILIO NUMBERS ---")
    if purchased_numbers:
        for num in purchased_numbers:
            status = "✅ MATCHES .env" if num == twilio_phone else "⚠️ Configured differently in .env"
            print(f" * {num} ({status})")
    else:
        print(" ❌ No active Twilio numbers found on this account!")

    print("\n--- [2/2] VERIFIED OUTBOUND RECIPIENTS ---")
    if verified_numbers:
        is_target_verified = False
        for num in verified_numbers:
            if num == target_phone:
                is_target_verified = True
                print(f" * {num} ✅ READY TO CALL (Verified)")
            else:
                print(f" * {num}")
        
        if not is_target_verified:
            print(f"\n❌ ALERT: Your destination number {target_phone} is NOT verified!")
            print("To fix this, you must verify this caller ID in your Twilio Console.")
    else:
        print(" ❌ No verified Caller IDs found. You cannot place calls to any phone.")

print("="*70 + "\n")