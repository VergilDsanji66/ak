# -*- coding: utf-8 -*-
from __future__ import print_function

# ---- Kill ALL proxies & SSL overrides for this process ----
import os
for var in [
    "HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy",
    "ALL_PROXY","all_proxy","NO_PROXY","no_proxy",
    "REQUESTS_CA_BUNDLE","SSL_CERT_FILE","CURL_CA_BUNDLE"
]:
    os.environ.pop(var, None)
# And explicitly tell Requests to never proxy:
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

# ---------- Imports ----------
import time
import csv
import hashlib
from typing import Optional, Tuple, Dict, Any
from dotenv import load_dotenv
import africastalking

# ---------- Config ----------
# Point to your Node-RED file that is overwritten with: header + latest row
CSV_PATH = os.getenv("CSV_PATH", r"C:\dev_Projects\Python\ak\status_current.csv")

# Hard-coded location text (not taken from anywhere else)
LOCATION_STR = "bridge near thoyandou"

# Africa's Talking (load from .env)
load_dotenv()
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY  = os.getenv("AT_API_KEY")

# Sandbox: use only simulator numbers from your dashboard
RECIPIENTS = ["+27821234567", "+254713999999"]
SENDER     = "21817"

SEND_ON_STATUS_CHANGE = True
SEND_ON_START         = True

# ---------- SMS client ----------
class SMS:
    def __init__(self):
        if not AT_API_KEY:
            raise RuntimeError("AT_API_KEY is empty. Put it in your .env or env vars.")
        africastalking.initialize(AT_USERNAME, AT_API_KEY)
        self.sms = africastalking.SMS

    def send_text(self, text: str):
        try:
            print(f"[SMS] Sending to {RECIPIENTS}: {text}")
            resp = self.sms.send(text, RECIPIENTS, SENDER)
            print("[SMS] Africa's Talking response:", resp, flush=True)
        except Exception as e:
            print("[SMS] Error while sending:", repr(e), flush=True)

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
                # Skip empty rows
                if not row:
                    continue
                # Normalize keys we care about
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
    """
    Produce a stable signature of just the latest row (so header changes don't matter).
    """
    if not row:
        return None
    sig_str = f"{row.get('timestamp','')}|{row.get('report','')}|{row.get('water_level_m','')}"
    return hashlib.sha1(sig_str.encode("utf-8")).hexdigest()

# ---------- Messaging templates ----------
def make_message(report: str, level_val: float) -> Optional[str]:
    r = (report or "").strip().upper()
    lvl = f"{level_val:.3f}"

    if r == "SAFE":
        # Only on transition to SAFE (handled by caller)
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

# ---------- Watcher loop ----------
def watch_csv_and_send(poll_sec: float = 0.3):
    print(f"[BOOT] AT_USERNAME: {AT_USERNAME}")
    print(f"[BOOT] AT_API_KEY set?: {bool(AT_API_KEY)}")
    print(f"[BOOT] Watching: {os.path.abspath(CSV_PATH)}")
    if AT_USERNAME == "sandbox":
        print("[BOOT] SANDBOX mode: use SMS Simulator numbers", flush=True)

    sms_client = SMS()

    last_sig: Optional[str] = None
    last_status: Optional[str] = None

    # Initial read
    init_row = read_latest_row(CSV_PATH)
    print(f"[INIT] Latest row: {init_row}")

    if init_row:
        init_status = (init_row.get("report") or "").strip().upper()
        init_level  = parse_level(init_row.get("water_level_m") or "")
        if SEND_ON_START and init_status and init_level is not None:
            # Send a startup message that matches the current status
            text = make_message(init_status, init_level)
            if text:
                sms_client.send_text(text)
                last_status = init_status
                print(f"[INIT] Sent startup status: {init_status}")
        last_sig = latest_row_signature(init_row)

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

                print(f"[WATCH] Change detected → status={status} level={level} last_status={last_status}")

                if status and level is not None:
                    if SEND_ON_STATUS_CHANGE:
                        # SAFE: only send when transitioning to SAFE from something else
                        if status == "SAFE":
                            if last_status != "SAFE":
                                text = make_message(status, level)
                                if text:
                                    sms_client.send_text(text)
                                last_status = status
                            else:
                                print("[WATCH] Still SAFE → not sending.")
                        else:
                            # WARNING or DANGER: send only on transition to this status
                            if status != last_status:
                                text = make_message(status, level)
                                if text:
                                    sms_client.send_text(text)
                                last_status = status
                            else:
                                print("[WATCH] Status unchanged → not sending.")
                    else:
                        # Always send on any change to the row
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
