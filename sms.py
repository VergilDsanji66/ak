# -*- coding: utf-8 -*-
from __future__ import print_function

# ---------------------------------------------------------------------
# ABSOLUTELY DISABLE proxies for all Requests usage (Windows-safe)
# Do this before anything else that could import requests.
# ---------------------------------------------------------------------
import requests as _r, os as _os
_r.sessions.Session.trust_env = False
_os.environ.update({
    "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "*",
    "http_proxy": "", "https_proxy": "", "all_proxy": "", "no_proxy": "*",
    "REQUESTS_CA_BUNDLE": "", "CURL_CA_BUNDLE": "", "SSL_CERT_FILE": ""
})
# ---------------------------------------------------------------------

# ---- Optional deep debug (set True to see sockets/hosts) -----------
DEBUG_HTTP = False
if DEBUG_HTTP:
    import logging, http.client as http_client
    http_client.HTTPConnection.debuglevel = 1
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.DEBUG)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)
# --------------------------------------------------------------------

# ---------- Standard imports ----------
import time
import csv
import hashlib
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from datetime import datetime, timezone
import os

# ---------- Config ----------
CSV_PATH = os.getenv("CSV_PATH", r"C:\dev_Projects\Python\ak\status_current.csv")
EVENTS_LOG_PATH = os.getenv("EVENTS_LOG_PATH", r"C:\dev_Projects\Python\ak\events_log.csv")
LOCATION_STR = "bridge near thoyandou"

# Africa's Talking (from .env)
load_dotenv()
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY  = os.getenv("AT_API_KEY")
# If your sandbox sender/short-code is provisioned, set it via env:
# e.g., AT_SENDER=21817 or your sandbox senderId
SENDER      =  "21817"

# In SANDBOX you must use simulator numbers
RECIPIENTS = [
    "+27821234567",
    "+254713999999"
]

SEND_ON_STATUS_CHANGE = True
SEND_ON_START         = True
SEND_ENABLED          = True   # set False for DRY-RUN

# ---------- Utilities ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def ensure_events_log(path: str):
    """Create events CSV with header if missing."""
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "detection_time_iso",
                "source_timestamp",
                "status",
                "water_level_m",
                "last_status_prev",
                "signature",
                "note"
            ])

def log_event(path: str,
              detection_time_iso: str,
              source_timestamp: str,
              status: str,
              water_level_m: Optional[float],
              last_status_prev: Optional[str],
              signature: Optional[str],
              note: str):
    """Append a single decision-trigger row to events log."""
    ensure_events_log(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            detection_time_iso,
            source_timestamp or "",
            status or "",
            f"{water_level_m:.3f}" if water_level_m is not None else "",
            last_status_prev or "",
            signature or "",
            note
        ])

# ---------- CSV helpers ----------
def read_latest_row(path: str) -> Optional[Dict[str, Any]]:
    """
    Reads a CSV with header: timestamp,report,water_level_m
    Returns the last (latest) non-empty data row as a dict or None if not available.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            last = None
            for row in reader:
                if not row:
                    continue
                ts = (row.get("timestamp") or "").strip()
                report = (row.get("report") or "").strip()
                level = (row.get("water_level_m") or "").strip()
                if not ts and not report and not level:
                    continue
                last = {"timestamp": ts, "report": report, "water_level_m": level}
            return last
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[CSV] Error reading CSV: {e}")
        return None

def latest_row_signature(row: Optional[Dict[str, Any]]) -> Optional[str]:
    if not row:
        return None
    sig_str = f"{row.get('timestamp','')}|{row.get('report','')}|{row.get('water_level_m','')}"
    return hashlib.sha1(sig_str.encode("utf-8")).hexdigest()

# ---------- Messaging templates ----------
def make_message(report: str, level_val: float) -> Optional[str]:
    r = (report or "").strip().upper()
    lvl = f"{level_val:.3f}"
    if r == "SAFE":
        return f"UPDATE: Water levels at {LOCATION_STR} have dropped to {lvl} m. It is now safe to cross."
    elif r == "WARNING":
        return f"WARNING: Water levels at {LOCATION_STR} have risen above {lvl} m. Cross with caution. Confirm: *384*37668#"
    elif r == "DANGER":
        return f"DANGER: Water levels at {LOCATION_STR} are above {lvl} m. Do NOT cross. Confirm: *384*37668#"
    else:
        return None

def parse_level(level_str: str) -> Optional[float]:
    try:
        return float(level_str)
    except Exception:
        return None

# ---------- SMS client (DIRECT REST; no SDK) ----------
import requests

class SMS:
    BASE_URL = "https://api.sandbox.africastalking.com" if AT_USERNAME == "sandbox" \
               else "https://api.africastalking.com"

    def __init__(self):
        if not AT_API_KEY:
            raise RuntimeError("AT_API_KEY is empty. Put it in your .env or env vars.")
        # Isolate a clean Session that never reads env/registry proxies
        requests.sessions.Session.trust_env = False
        self.session = requests.Session()
        self.session.trust_env = False
        self.headers = {
            "apiKey": AT_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def send_text(self, text: str):
        if not SEND_ENABLED:
            print(f"[SMS] (DRY-RUN) Suppressed send: {text}")
            return
        payload = {
            "username": AT_USERNAME,
            "to": ",".join(RECIPIENTS),
            "message": text,
        }
        # include sender (you said it's provisioned in sandbox)
        if SENDER:
            payload["from"] = SENDER
        try:
            url = f"{self.BASE_URL}/version1/messaging"
            print(f"[SMS] POST {url} → {payload}")
            resp = self.session.post(url, data=payload, headers=self.headers, timeout=20)
            print("[SMS] Response:", resp.status_code, resp.text[:400])
            resp.raise_for_status()
        except requests.exceptions.SSLError as e:
            print("[SMS] SSL error:", repr(e))
        except Exception as e:
            print("[SMS] Error while sending:", repr(e))

# ---------- Watcher loop ----------
def watch_csv_and_send(poll_sec: float = 0.3):
    print(f"[BOOT] AT_USERNAME: {AT_USERNAME}")
    print(f"[BOOT] AT_API_KEY set?: {bool(AT_API_KEY)}")
    print(f"[BOOT] Watching: {os.path.abspath(CSV_PATH)}")
    print(f"[BOOT] EVENTS_LOG: {os.path.abspath(EVENTS_LOG_PATH)}")
    if AT_USERNAME == "sandbox":
        print("[BOOT] SANDBOX mode: use SMS Simulator numbers", flush=True)
    print(f"[BOOT] SEND_ENABLED={SEND_ENABLED} (DRY-RUN means no SMS will be sent)")
    print("[DEBUG] Requests trust_env:", _r.sessions.Session.trust_env)

    sms_client = SMS()
    ensure_events_log(EVENTS_LOG_PATH)

    last_sig: Optional[str] = None
    last_status: Optional[str] = None

    # Initial read
    init_row = read_latest_row(CSV_PATH)
    print(f"[INIT] Latest row: {init_row}")

    if init_row:
        init_status = (init_row.get("report") or "").strip().upper()
        init_level  = parse_level(init_row.get("water_level_m") or "")
        last_sig = latest_row_signature(init_row)

        if SEND_ON_START and init_status and init_level is not None:
            text = make_message(init_status, init_level)
            if text:
                # --- LOG the startup decision trigger ---
                log_event(
                    EVENTS_LOG_PATH,
                    detection_time_iso=now_iso(),
                    source_timestamp=init_row.get("timestamp") or "",
                    status=init_status,
                    water_level_m=init_level,
                    last_status_prev=last_status,
                    signature=last_sig,
                    note="startup_status"
                )
                sms_client.send_text(text)
                last_status = init_status
                print(f"[INIT] Startup decision logged: {init_status}")

    while True:
        try:
            row = read_latest_row(CSV_PATH)
            sig = latest_row_signature(row)
            if sig is None:
                time.sleep(poll_sec)
                continue

            if sig != last_sig:
                # New data row detected
                report = (row.get("report") if row else "") or ""
                status = report.strip().upper()
                level  = parse_level((row.get("water_level_m") or "") if row else "")
                src_ts = (row.get("timestamp") if row else "") or ""

                print(f"[WATCH] Change detected → status={status} level={level} last_status={last_status}")

                if status and level is not None:
                    if SEND_ON_STATUS_CHANGE:
                        if status == "SAFE":
                            if last_status != "SAFE":
                                # --- LOG SAFE transition trigger ---
                                log_event(
                                    EVENTS_LOG_PATH, now_iso(), src_ts, status, level,
                                    last_status_prev=last_status, signature=sig,
                                    note="transition_to_SAFE"
                                )
                                text = make_message(status, level)
                                if text:
                                    sms_client.send_text(text)
                                last_status = status
                            else:
                                print("[WATCH] Still SAFE → not sending.")
                        else:
                            # WARNING or DANGER: only on transition
                            if status != last_status:
                                # --- LOG WARNING/DANGER transition trigger ---
                                log_event(
                                    EVENTS_LOG_PATH, now_iso(), src_ts, status, level,
                                    last_status_prev=last_status, signature=sig,
                                    note=f"transition_to_{status}"
                                )
                                text = make_message(status, level)
                                if text:
                                    sms_client.send_text(text)
                                last_status = status
                            else:
                                print("[WATCH] Status unchanged → not sending.")
                    else:
                        # Always send/log on any change to the row
                        log_event(
                            EVENTS_LOG_PATH, now_iso(), src_ts, status, level,
                            last_status_prev=last_status, signature=sig,
                            note="row_change_no_transition_policy"
                        )
                        text = make_message(status, level)
                        if text:
                            sms_client.send_text(text)
                        last_status = status

                    last_sig = sig
                else:
                    print("[WATCH] Missing status or level in latest row → skipping.")
                    last_sig = sig

        except Exception as e:
            print("[WATCH] Unexpected error:", repr(e))

        time.sleep(poll_sec)

# ---------- Main ----------
if __name__ == "__main__":
    watch_csv_and_send()
