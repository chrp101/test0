from flask import Flask, request, jsonify
import requests
import os
import datetime

app = Flask(__name__)

# ✅ Load environment variables from Render
TRADIER_TOKEN = os.environ.get("TRADIER_TOKEN")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}
BASE_URL = "https://sandbox.tradier.com/v1"

# --- Helper: Get SPY price
def get_spy_price():
    url = f"{BASE_URL}/markets/quotes?symbols=SPY"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return float(res.json()["quotes"]["quote"]["last"])

# --- Helper: Get cash balance
def get_cash_balance():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    return float(res.json()["balances"]["cash_available"])

# --- Helper: Get today's expiration date
def get_today_expiry():
    return datetime.datetime.now().strftime("%y%m%d")  # e.g., '250531'

# --- Helper: Close all open options
def close_all_positions():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions"
    res = requests.get(url, headers=HEADERS)
    res.raise_for_status()
    data = res.json()

    if not data.get("positions"):
        print("✅ No open positions to close.")
        return

    for pos in data["positions"]["position"]:
        symbol = pos["symbol"]
        qty = int(pos["quantity"])
        side = "sell_to_close" if pos["long"] else "buy_to_close"
        payload = {
            "class": "option",
            "symbol": symbol,
            "side": side,
            "quantity": qty,
            "type": "market",
            "duration": "day"
        }
        close_url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders"
        requests.post(close_url, headers=HEADERS, data=payload)
        print(f"🛑 Closed: {side} {qty}x {symbol}")

# --- Helper: Place new option order
def place_option_order(signal):
    spy_price = get_spy_price()
    expiry = get_today_expiry()

    # Logic: buy puts near spot if sell signal, calls if buy signal
    strike = round(spy_price) - 1 if signal == "sell" else round(spy_price)
    right = "P" if signal == "sell" else "C"
    option_symbol = f"SPY{expiry}{right}{strike:08d}"

    cash = get_cash_balance()
    estimated_price = 1.00  # $100 per contract
    contracts = int(cash // (estimated_price * 100))
    if contracts == 0:
        print("❌ Not enough cash to trade.")
        return

    print(f"🟢 Placing {signal.upper()} order: {contracts}x {option_symbol}")
    payload = {
        "class": "option",
        "symbol": option_symbol,
        "side": "buy_to_open",
        "quantity": contracts,
        "type": "market",
        "duration": "day"
    }
    order_url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders"
    res = requests.post(order_url, headers=HEADERS, data=payload)
    print(f"📦 Tradier response: {res.text}")
    res.raise_for_status()

# --- Webhook endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("📩 Incoming webhook:", data)

        signal = data.get("signal", "").lower()
        if signal not in ["buy", "sell"]:
            return jsonify({"status": "error", "message": "Invalid signal"})

        close_all_positions()
        place_option_order(signal)

        return jsonify({"status": "success", "message": f"{signal} order executed"})

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Main
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
