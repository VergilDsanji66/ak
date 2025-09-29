from __future__ import print_function
from dotenv import load_dotenv

# (keeping your original imports)
from email import message
import os
from token import AT
from urllib import response
import africastalking
import time  # ✅ for the watcher loop
from typing import Optional  # ✅ for type hints

# ---------------------------
# Config
# ---------------------------
# If your CSV sits next to this .py file, you can alternatively use:
# CSV_PATH = os.getenv("CSV_PATH", os.path.join(os.path.dirname(__file__), "status_current.csv"))
CSV_PATH = os.getenv("CSV_PATH", r"C:\dev_Projects\Python\ak\status_current.csv")
ORDER = ["SAFE", "WARNING", "DANGER"]  # strict cycle

# ---------------------------
# Africa's Talking setup
# ---------------------------
load_dotenv()  # loads .env file in current working dir

AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY")

class SMS:
    def __init__(self):
        self.username = AT_USERNAME
        self.api_key = AT_API_KEY

        africastalking.initialize(self.username, self.api_key)
        self.sms = africastalking.SMS

    def send(self):
        recipents = ["+27821234567", "+254713999999"]
        message = "Works"
        sender = "21823"

        try:
            response = self.sms.send(message, recipents, sender)
            print(response)
        except Exception as e:
            print('Encountered an error while sending: %s' % str(e))

    # ✅ small helper so the watcher can send arbitrary text without changing your .send()
    def send_text(self, text: str):
        recipents = ["+27821234567", "+254713999999"]  # same list you already use
        sender = "21823"
        try:
            resp = self.sms.send(text, recipents, sender)
            print("Africa's Talking response:", resp, flush=True)
        except Exception as e:
            print('Encountered an error while sending: %s' % str(e))

# ---------------------------
# CSV helpers (same logic as your other code)
# ---------------------------
def read_cell(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.readline().strip()
    except FileNotFoundError:
        return None

def parse_status(line: str) -> Optional[str]:
    """Parse CSV first token into SAFE, WARNING, or DANGER."""
    if not line:
        return None
    head = line.split(":", 1)[0].strip().upper()
    return head if head in ORDER else None

# ---------------------------
# Watcher loop (no Flask)
# ---------------------------
def watch_csv_and_send(sms_client: SMS):
    print(f"Watching {CSV_PATH} for changes...")
    if AT_USERNAME == "sandbox":
        print("AT in SANDBOX mode. Use simulator numbers from your dashboard.", flush=True)

    last_mtime = 0.0
    expected_idx: Optional[int] = None  # tracks the next allowed status in ORDER

    while True:
        try:
            st = os.stat(CSV_PATH)
            if st.st_mtime != last_mtime:
                last_mtime = st.st_mtime
                line = read_cell(CSV_PATH)
                status = parse_status(line)

                if status is None:
                    # not a recognized status; ignore
                    time.sleep(0.2)
                    continue

                if expected_idx is None:
                    # first time we see the file, accept whatever is there and set the cycle
                    print(line, flush=True)
                    sms_client.send_text(line)
                    expected_idx = (ORDER.index(status) + 1) % len(ORDER)
                else:
                    expected = ORDER[expected_idx]
                    if status == expected:
                        print(line, flush=True)
                        sms_client.send_text(line)
                        expected_idx = (expected_idx + 1) % len(ORDER)
                    # else: out-of-order change; ignore until it matches the expected next status
        except FileNotFoundError:
            # file not yet present; keep waiting
            pass

        time.sleep(0.2)

# ---------------------------
# Main entry
# ---------------------------
if __name__ == '__main__':
    # Start watching the CSV and send SMS when the sequence advances
    watch_csv_and_send(SMS())
    # If you ever want the old one-shot behavior instead, comment the line above
    # and uncomment the line below:
    # SMS().send()
