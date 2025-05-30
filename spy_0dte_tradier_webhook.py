from flask import Flask, request, jsonify
import csv
import os
from datetime import datetime

app = Flask(__name__)

# --- Log to CSV Function ---
def log_to_csv(signal, symbol, qty, price, total, balance, pnl):
    file_path = "/tmp/trades.csv"  # Use /tmp for container compatibility
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode="a", newline="") as csv_file:
        fieldnames = ["timestamp", "signal", "option_symbol", "quantity", "price", "total_spent", "cash_balance", "pnl"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal": signal,
            "option_symbol": symbol,
            "quantity": qty,
            "price": price,
            "total_spent": total,
            "cash_balance": balance,
            "pnl": pnl
        })

# --- Webhook Endpoint ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received data:", data)

    signal = data.get("signal", "").lower()
    if signal not in ["buy", "sell"]:
        return jsonify({"status": "error", "message": "Invalid signal"})

    # Dummy trade log
    log_to_csv(
        signal=signal,
        symbol="SPYTEST",
        qty=1,
        price=1.00,
        total=100.00,
        balance=9900.00,
        pnl=0.00
    )

    return jsonify({"status": "success", "message": "logged to sheet"})

# --- Run on Render ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
