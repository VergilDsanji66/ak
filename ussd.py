import os
import csv
import time
from datetime import datetime
from flask import Flask, request, make_response

app = Flask(__name__)

# -------------------------------------------------
# Config (override via environment variables)
# -------------------------------------------------
LOG_PATH = os.getenv("USSD_LOG_PATH", "ussd_logs.csv")
# Simulated state injected from your Node-RED or env
BRIDGE_STATUS = os.getenv("BRIDGE_STATUS", "SAFE")  # SAFE | WARNING | DANGER
LAST_ALERT = os.getenv("LAST_ALERT", "No alert issued yet.")

# Ensure log file exists with header
LOG_HEADERS = [
    "ts_iso", "ts_ms", "session_id", "phone_number", "service_code",
    "text", "menu_action", "detail", "result"
]

def init_log():
    try:
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(LOG_HEADERS)
    except Exception as e:
        print(f"[LOG INIT] Failed to prepare log file: {e}")

def log_event(session_id, phone_number, service_code, text, menu_action, detail, result):
    try:
        ts_ms = int(time.time() * 1000)
        ts_iso = datetime.utcfromtimestamp(ts_ms / 1000.0).isoformat() + "Z"
        row = [ts_iso, ts_ms, session_id, phone_number, service_code, text, menu_action, detail, result]
        with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        print(f"[LOG WRITE] Failed to write row: {e}")

init_log()

# -------------------------------------------------
# Helpers for dynamic content
# -------------------------------------------------
def get_bridge_status():
    """Return human-readable bridge status text based on BRIDGE_STATUS."""
    status = (os.getenv("BRIDGE_STATUS", BRIDGE_STATUS) or "").upper().strip()
    if status == "DANGER":
        return "DANGER: Bridge closed. Do NOT cross."
    elif status == "WARNING":
        return "WARNING: Water rising. Cross with caution."
    else:
        return "SAFE: Bridge open."

def get_last_alert():
    return os.getenv("LAST_ALERT", LAST_ALERT)

def ussd_response(body: str):
    """Force text/plain for Africa's Talking."""
    resp = make_response(body, 200)
    resp.headers["Content-Type"] = "text/plain; charset=utf-8"
    return resp

# -------------------------------------------------
# Healthcheck (optional)
# -------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return ussd_response("OK")

# -------------------------------------------------
# USSD Logic (accept GET too for quick testing)
# Africa's Talking will POST: sessionId, serviceCode, phoneNumber, text
# -------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def ussd():
    session_id   = request.values.get("sessionId", "")
    service_code = request.values.get("serviceCode", "")
    phone_number = request.values.get("phoneNumber", "")
    text         = (request.values.get("text", "") or "").strip()

    print(f"[USSD] session={session_id} code={service_code} phone={phone_number} text='{text}'")

    # MAIN MENU
    if text == "":
        response = (
            "CON Flood Alert Service\n"
            "1. Check current bridge status\n"
            "2. Receive last flood warning\n"
            "3. Confirm receipt of warning\n"
            "4. Report flooding at my location\n"
            "5. Exit"
        )
        log_event(session_id, phone_number, service_code, text, "MAIN", "", "OK")
        return ussd_response(response)

    # 1) Check current bridge status
    if text == "1":
        status_msg = get_bridge_status()
        response = f"END {status_msg}"
        log_event(session_id, phone_number, service_code, text, "CHECK_STATUS", status_msg, "END")
        return ussd_response(response)

    # 2) Receive last flood warning
    if text == "2":
        last = get_last_alert()
        response = f"END Last alert: {last}"
        log_event(session_id, phone_number, service_code, text, "LAST_ALERT", last, "END")
        return ussd_response(response)

    # 3) Confirm receipt of warning
    if text == "3":
        response = (
            "CON Confirm you received the latest warning?\n"
            "1. Yes, I received it\n"
            "2. No, send again"
        )
        log_event(session_id, phone_number, service_code, text, "CONFIRM_MENU", "", "CON")
        return ussd_response(response)
    if text == "3*1":
        response = "END Thank you. Your confirmation has been logged."
        log_event(session_id, phone_number, service_code, text, "CONFIRM_YES", "received=true", "END")
        return ussd_response(response)
    if text == "3*2":
        last = get_last_alert()
        response = f"END Resent: {last}"
        log_event(session_id, phone_number, service_code, text, "CONFIRM_RESEND", last, "END")
        return ussd_response(response)

    # 4) Report flooding at my location
    if text == "4":
        response = (
            "CON Report flooding:\n"
            "1. Water rising\n"
            "2. Bridge flooded\n"
            "3. False alarm / water receding"
        )
        log_event(session_id, phone_number, service_code, text, "REPORT_MENU", "", "CON")
        return ussd_response(response)

    if text in ("4*1", "4*2", "4*3"):
        choice = {"4*1": "Water rising", "4*2": "Bridge flooded", "4*3": "False alarm / receding"}[text]
        response = (
            "CON Add landmark near you (choose):\n"
            "1. School\n"
            "2. Clinic\n"
            "3. Market\n"
            "4. Other"
        )
        log_event(session_id, phone_number, service_code, text, "REPORT_SEVERITY", choice, "CON")
        return ussd_response(response)

    # Landmark selection
    if text.count("*") == 2 and text.startswith("4*"):
        parts = text.split("*")
        if len(parts) == 3 and parts[1] in {"1","2","3"} and parts[2] in {"1","2","3","4"}:
            severity_map = {"1": "Water rising", "2": "Bridge flooded", "3": "False alarm / receding"}
            landmark_map = {"1": "School", "2": "Clinic", "3": "Market", "4": "Other"}
            severity = severity_map.get(parts[1], "Unknown")
            landmark = landmark_map.get(parts[2], "Other")
            summary = f"{severity} near {landmark}"
            response = "END Thank you. Your report has been logged."
            log_event(session_id, phone_number, service_code, text, "REPORT_SUBMIT", summary, "END")
            return ussd_response(response)

    # 5) Exit
    if text == "5":
        response = "END Goodbye."
        log_event(session_id, phone_number, service_code, text, "EXIT", "", "END")
        return ussd_response(response)

    # Fallback
    response = "END Invalid choice"
    log_event(session_id, phone_number, service_code, text, "INVALID", "", "END")
    return ussd_response(response)

# -------------------------------------------------
# Run the app
# -------------------------------------------------
if __name__ == "__main__":
    # For local testing; in production, run via gunicorn/uwsgi
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
