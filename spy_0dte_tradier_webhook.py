from flask import Flask, request, jsonify
import requests
import datetime
import os

app = Flask(__name__)

# === Configuration ===
TRADIER_TOKEN = os.environ.get("TRADIER_TOKEN")
ACCOUNT_ID = os.environ.get("ACCOUNT_ID")
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}
BASE_URL = "https://sandbox.tradier.com/v1"

# === Tradier Helpers ===
def get_spy_price():
    url = f"{BASE_URL}/markets/quotes?symbols=SPY"
    res = requests.get(url, headers=HEADERS)
    return float(res.json()["quotes"]["quote"]["last"])

def get_cash_balance():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances"
    res = requests.get(url, headers=HEADERS)
    return float(res.json()["balances"]["cash_available"])

def get_today_expiry():
    return datetime.datetime.now().strftime("%y%m%d")  # e.g., 250530

def close_all_positions():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions"
    res = requests.get(url, headers=HEADERS).json()
    if "positions" not in res or not res["positions"]:
        return

    for pos in res["positions"]["position"]:
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
        requests.post(f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders", headers=HEADERS, data=payload)

def place_option_order(signal):
    spy_price = get_spy_price()
    expiry = get_today_expiry()

    strike = round(spy_price) - 1 if signal == "sell" else round(spy_price)
    right = "P" if signal == "sell" else "C"
    option_symbol = f"SPY{expiry}{right}{strike:08d}"

    cash = get_cash_balance()
    estimated_price = 1.00
    contracts = int(cash // (estimated_price * 100))
    if contracts == 0:
        print("Not enough cash to trade.")
        return

    print(f"Placing {signal.upper()} order: {contracts}x {option_symbol}")
    payload = {
        "class": "option",
        "symbol": option_symbol,
        "side": "buy_to_open",
        "quantity": contracts,
        "type": "market",
        "duration": "day"
    }
    res = requests.post(f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders", headers=HEADERS, data=payload)
    print(res.text)

# === Webhook Endpoint ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("Received data:", data)

    signal = data.get("signal", "").lower()
    if signal not in ["buy", "sell"]:
        return jsonify({"status": "error", "message": "Invalid signal"})

    try:
        close_all_positions()
        place_option_order(signal)
        return jsonify({"status": "success", "message": f"Executed {signal} order"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# === Render requirement ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
