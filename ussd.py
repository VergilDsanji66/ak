import os
from flask import Flask, request

app = Flask(__name__)

# -------------------------------
# USSD Logic Route
# -------------------------------
@app.route("/", methods=['POST'])
def ussd():
    # Read the variables sent via POST from Africa's Talking API
    session_id = request.values.get("sessionId", None)
    service_code = request.values.get("serviceCode", None)
    phone_number = request.values.get("phoneNumber", None)
    text = request.values.get("text", "")

    # USSD menu logic
    if text == "":
        # First request
        response = "CON Flood Alert Service \n"
        response += "1. Check Current bridge status \n"
        response += "2. Receive last flood \n"
        response += "3. Confirm receipt of warning \n"
        response += "4. Report flooding at my location \n"
        response += "5. Exit"

    elif text == "1":
        # First level response
        response = "CON Choose account information you want to view \n"
        response += "1. Account number"

    elif text == "2":
        # Terminal response
        response = "END Your phone number is " + phone_number

    elif text == "1*1":
        # Second level response
        account_number = "ACC1001"
        response = "END Your account number is " + account_number

    else:
        response = "END Invalid choice"

    return response

# -------------------------------
# Run the app
# -------------------------------
if __name__ == "__main__":
    # Host 0.0.0.0 allows external access (e.g., via ngrok or deployment)
    app.run(host="0.0.0.0", port=5000, debug=True)
