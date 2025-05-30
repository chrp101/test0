from flask import Flask, request, jsonify

app = Flask(__name__)

# Dummy Google Sheets logging test
def log_to_google_sheets(signal, symbol, qty, price, total, balance, pnl):
    import requests
    import os
    webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK")

    payload = {
        "signal": signal,
        "option_symbol": symbol,
        "quantity": qty,
        "price": price,
        "total_spent": total,
        "cash_balance": balance,
        "pnl": pnl
    }

    requests.post(webhook_url, json=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received data:", data)

    signal = data.get("signal", "").lower()
    if signal not in ["buy", "sell"]:
        return jsonify({"status": "error", "message": "Invalid signal"})

    # Instead of calling Tradier, just log to Google Sheet directly
    log_to_google_sheets(
        signal=signal,
        symbol="SPYTEST",
        qty=1,
        price=1.00,
        total=100.00,
        balance=9900.00,
        pnl=0.00
    )

    return jsonify({"status": "success", "test": "sheet_only"})

if __name__ == "__main__":
    app.run(port=5000)
