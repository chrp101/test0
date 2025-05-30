from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# 🔧 Logs trade details to your Google Sheet
def log_to_google_sheets(signal, symbol, qty, price, total, balance, pnl):
    webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK")
    print("Google Sheets webhook URL:", webhook_url)

    payload = {
        "signal": signal,
        "option_symbol": symbol,
        "quantity": qty,
        "price": price,
        "total_spent": total,
        "cash_balance": balance,
        "pnl": pnl
    }

    try:
        res = requests.post(webhook_url, json=payload)
        print("Google Sheet response:", res.text)
    except Exception as e:
        print("Error sending to Google Sheets:", str(e))

# 🔁 Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received alert:", data)

    signal = data.get("signal", "").lower()
    if signal not in ["buy", "sell"]:
        return jsonify({"status": "error", "message": "Invalid signal"})

    # 👇 Log a dummy trade to Google Sheets
    log_to_google_sheets(
        signal=signal,
        symbol="SPYTEST",
        qty=1,
        price=1.00,
        total=100.00,
        balance=9900.00,
        pnl=0.00
    )

    return jsonify({"status": "success", "message": "logged to sheet"})

# ✅ Required for Render to expose the port
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
