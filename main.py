# main.py
import os
import threading
import sys
import signal

# Import your modules
# (These imports do NOT start anything because both files guard their runners with if __name__ == '__main__')
import sms
from ussd import app as ussd_app

def run_sms():
    # Runs the CSV watcher + SMS sender 
    sms.watch_csv_and_send()

def run_ussd():
    # Runs the Flask app that Africa's Talking calls via your ngrok URL
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    ussd_app.run(host="0.0.0.0", port=port, debug=debug)

def main():
    # Start SMS watcher in a daemon thread
    t = threading.Thread(target=run_sms, name="sms-watcher", daemon=True)
    t.start()
    print("[MAIN] SMS watcher started in background thread.")

    #graceful Ctrl-C
    def handle_sigint(sig, frame):
        print("\n[MAIN] Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    # Run USSD server (blocking)
    print("[MAIN] Starting USSD Flask server...")
    run_ussd()

if __name__ == "__main__":
    main()
