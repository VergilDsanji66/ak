import os
import csv
import time
from datetime import datetime
from collections import deque
from flask import Flask, request, make_response

app = Flask(__name__)

# -------------------------------------------------
# Config (override via environment variables)
# -------------------------------------------------
LOG_PATH = os.getenv("USSD_LOG_PATH", "ussd_logs.csv")
# CSV with running status updates (timestamp,report,water_level_m)
STATUS_CSV_PATH = os.getenv("STATUS_CSV_PATH", "/status_current.csv")

# Legacy fallbacks (kept in case CSV is missing/empty)
BRIDGE_STATUS = os.getenv("BRIDGE_STATUS", "SAFE")  # SAFE | WARNING | DANGER
LAST_ALERT = os.getenv("LAST_ALERT", "No alert issued yet.")

# Ensure log file exists with header
LOG_HEADERS = [
    "ts_iso",
    "ts_ms",
    "session_id",
    "phone_number",
    "service_code",
    "text",
    "menu_action",
    "detail",
    "result",
]


def init_log():
    try:
        if not os.path.exists(LOG_PATH):
            with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(LOG_HEADERS)
    except Exception as e:
        print(f"[LOG INIT] Failed to prepare log file: {e}")


def log_event(
    session_id, phone_number, service_code, text, menu_action, detail, result
):
    try:
        ts_ms = int(time.time() * 1000)
        ts_iso = datetime.utcfromtimestamp(ts_ms / 1000.0).isoformat() + "Z"
        row = [
            ts_iso,
            ts_ms,
            session_id,
            phone_number,
            service_code,
            text,
            menu_action,
            detail,
            result,
        ]
        with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        print(f"[LOG WRITE] Failed to write row: {e}")


init_log()


# -------------------------------------------------
# Helpers for dynamic content (CSV-driven)
# -------------------------------------------------
def _tail_status_rows(path: str, n: int = 2):
    """
    Return up to the last n rows from the status CSV as a list of dicts
    with keys: timestamp, report, water_level_m. Latest row is last.
    """
    rows = deque(maxlen=n)
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Expect headers: timestamp,report,water_level_m
            for r in reader:
                # Normalize/strip
                rows.append(
                    {
                        "timestamp": (r.get("timestamp") or "").strip(),
                        "report": (r.get("report") or "").strip().upper(),
                        "water_level_m": (r.get("water_level_m") or "").strip(),
                    }
                )
    except FileNotFoundError:
        print(f"[STATUS CSV] File not found: {path}")
    except Exception as e:
        print(f"[STATUS CSV] Error reading {path}: {e}")
    return list(rows)


def _format_status_message(report: str, level: str, when: str, current: bool) -> str:
    """
    Map report -> human message similar to your previous logic.
    current=True for 'current status' message; False for 'previous/last status'.
    """
    prefix = "Current status" if current else "Previous status"
    # Default when timestamp missing
    when_str = f" at {when}" if when else ""
    lvl_str = f" (level {level} m)" if level else ""

    if report == "DANGER":
        return f"{prefix}{when_str}: DANGER — Bridge CLOSED. Do NOT cross{lvl_str}."
    elif report == "WARNING":
        return (
            f"{prefix}{when_str}: WARNING — Water rising. Cross with caution{lvl_str}."
        )
    elif report == "SAFE":
        return f"{prefix}{when_str}: SAFE — Bridge open{lvl_str}."
    elif report:
        # Unknown/other code present
        return f"{prefix}{when_str}: {report}{lvl_str}."
    else:
        # No report available
        return f"{prefix}: No status available."


def get_current_and_previous_status():
    """
    Read last and previous rows from STATUS_CSV_PATH.
    Returns (current_msg, previous_msg).
    Falls back to env-based messages if CSV missing/empty.
    """
    rows = _tail_status_rows(STATUS_CSV_PATH, n=2)

    # Determine current (last row) and previous (second-last row if present)
    current = rows[-1] if rows else None
    previous = (
        rows[0] if len(rows) == 2 else None
    )  # if two rows, first is previous (older)

    if current:
        cur_msg = _format_status_message(
            current.get("report", ""),
            current.get("water_level_m", ""),
            current.get("timestamp", ""),
            current=True,
        )
    else:
        # Fallback to env BRIDGE_STATUS
        cur_msg = _format_status_message(
            BRIDGE_STATUS.upper().strip(), "", "", current=True
        )

    if previous:
        prev_msg = _format_status_message(
            previous.get("report", ""),
            previous.get("water_level_m", ""),
            previous.get("timestamp", ""),
            current=False,
        )
    else:
        # Fallback to env LAST_ALERT text (kept for compatibility)
        prev_msg = f"Previous status: {os.getenv('LAST_ALERT', LAST_ALERT)}"

    return cur_msg, prev_msg


def get_bridge_status():
    """Return human-readable current bridge status from CSV (latest row)."""
    current_msg, _ = get_current_and_previous_status()
    return current_msg


def get_last_alert():
    """Return human-readable previous/last status from CSV (second-last row)."""
    _, previous_msg = get_current_and_previous_status()
    return previous_msg


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
    session_id = request.values.get("sessionId", "")
    service_code = request.values.get("serviceCode", "")
    phone_number = request.values.get("phoneNumber", "")
    text = (request.values.get("text", "") or "").strip()

    print(
        f"[USSD] session={session_id} code={service_code} phone={phone_number} text='{text}'"
    )

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

    # 1) Check current bridge status (NOW CSV-DRIVEN)
    if text == "1":
        status_msg = get_bridge_status()
        response = f"END {status_msg}"
        log_event(
            session_id,
            phone_number,
            service_code,
            text,
            "CHECK_STATUS",
            status_msg,
            "END",
        )
        return ussd_response(response)

    # 2) Receive last flood warning (NOW PREVIOUS ROW FROM CSV)
    if text == "2":
        last = get_last_alert()
        response = f"END {last}"
        log_event(
            session_id, phone_number, service_code, text, "LAST_ALERT", last, "END"
        )
        return ussd_response(response)

    # 3) Confirm receipt of warning
    if text == "3":
        response = (
            "CON Confirm you received the latest warning?\n"
            "1. Yes, I received it\n"
            "2. No, send again"
        )
        log_event(
            session_id, phone_number, service_code, text, "CONFIRM_MENU", "", "CON"
        )
        return ussd_response(response)
    if text == "3*1":
        response = "END Thank you. Your confirmation has been logged."
        log_event(
            session_id,
            phone_number,
            service_code,
            text,
            "CONFIRM_YES",
            "received=true",
            "END",
        )
        return ussd_response(response)
    if text == "3*2":
        last = get_bridge_status()  # resend the current status as the latest warning
        response = f"END Resent: {last}"
        log_event(
            session_id, phone_number, service_code, text, "CONFIRM_RESEND", last, "END"
        )
        return ussd_response(response)

    # 4) Report flooding at my location
    if text == "4":
        response = (
            "CON Report flooding:\n"
            "1. Water rising\n"
            "2. Bridge flooded\n"
            "3. False alarm / water receding"
        )
        log_event(
            session_id, phone_number, service_code, text, "REPORT_MENU", "", "CON"
        )
        return ussd_response(response)

    if text in ("4*1", "4*2", "4*3"):
        choice = {
            "4*1": "Water rising",
            "4*2": "Bridge flooded",
            "4*3": "False alarm / receding",
        }[text]
        response = (
            "CON Add landmark near you (choose):\n"
            "1. School\n"
            "2. Clinic\n"
            "3. Market\n"
            "4. Other"
        )
        log_event(
            session_id,
            phone_number,
            service_code,
            text,
            "REPORT_SEVERITY",
            choice,
            "CON",
        )
        return ussd_response(response)

    # Landmark selection
    if text.count("*") == 2 and text.startswith("4*"):
        parts = text.split("*")
        if (
            len(parts) == 3
            and parts[1] in {"1", "2", "3"}
            and parts[2] in {"1", "2", "3", "4"}
        ):
            severity_map = {
                "1": "Water rising",
                "2": "Bridge flooded",
                "3": "False alarm / receding",
            }
            landmark_map = {"1": "School", "2": "Clinic", "3": "Market", "4": "Other"}
            severity = severity_map.get(parts[1], "Unknown")
            landmark = landmark_map.get(parts[2], "Other")
            summary = f"{severity} near {landmark}"
            response = "END Thank you. Your report has been logged."
            log_event(
                session_id,
                phone_number,
                service_code,
                text,
                "REPORT_SUBMIT",
                summary,
                "END",
            )
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
