from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

BASE_URL = "https://sandbox.tradier.com/v1"

def get_spy_price():
    res = requests.get(f"{BASE_URL}/markets/quotes?symbols=SPY", headers=HEADERS)
    quotes = res.json().get("quotes", {})
    quote = quotes["quote"] if isinstance(quotes, dict) else quotes[0]
    return float(quote["last"])

def get_cash_balance():
    res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances", headers=HEADERS)
    return float(res.json()["balances"]["cash_available"])

def get_today_expiry():
    return datetime.now().strftime("%y%m%d")

def close_all_positions():
    res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions", headers=HEADERS).json()
    positions = res.get("positions", {}).get("position", [])
    if not isinstance(positions, list):
        positions = [positions]
    for pos in positions:
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
    est_price = 1.00
    contracts = int(cash // (est_price * 100))
    if contracts == 0:
        print("Not enough cash.")
        return

    payload = {
        "class": "option",
        "symbol": option_symbol,
        "side": "buy_to_open",
        "quantity": contracts,
        "type": "market",
        "duration": "day"
    }
    print(f"Placing {signal.upper()} order for {option_symbol}, {contracts}x")
    requests.post(f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders", headers=HEADERS, data=payload)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("Received alert:", data)
        signal = data.get("signal", "").lower()
        if signal not in ["buy", "sell"]:
            return jsonify({"status": "error", "message": "Invalid signal"})

        close_all_positions()
        place_option_order(signal)
        return jsonify({"status": "success", "message": f"{signal} order placed"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
