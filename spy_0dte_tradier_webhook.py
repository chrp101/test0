import os
import datetime
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
TRADIER_TOKEN = os.getenv("Xq6IBE2AvGg9jLBtqED658mXgYMO")
ACCOUNT_ID = os.getenv("VA20184697")
BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

# Helper Functions
def get_spy_price():
    url = f"{BASE_URL}/markets/quotes?symbols=SPY"
    res = requests.get(url, headers=HEADERS)
    try:
        data = res.json()
        return float(data["quotes"]["quote"]["last"])
    except Exception as e:
        print("Error fetching SPY price:", e)
        print("Raw response:", res.text)
        raise

def get_cash_balance():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances"
    res = requests.get(url, headers=HEADERS)
    try:
        data = res.json()
        print("Balance API Response:", data)
        balances = data.get("balances", {})
        cash = balances.get("cash_available") or balances.get("total_cash")
        if cash is None:
            raise ValueError("Cash balance not found in API response")
        return float(cash)
    except Exception as e:
        print("Error retrieving cash balance:", e)
        raise

def get_today_expiry():
    return datetime.datetime.now().strftime("%y%m%d")  # e.g., '250530'

def close_all_positions():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions"
    res = requests.get(url, headers=HEADERS)
    try:
        data = res.json()
        positions = data.get("positions", {}).get("position")
        if not positions:
            print("✅ No positions to close.")
            return
        if isinstance(positions, dict):
            positions = [positions]
        for pos in positions:
            symbol = pos["symbol"]
            qty = int(pos["quantity"])
            side = "sell_to_close" if pos["long"] else "buy_to_close"
            close_url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders"
            payload = {
                "class": "option",
                "symbol": symbol,
                "side": side,
                "quantity": qty,
                "type": "market",
                "duration": "day"
            }
            requests.post(close_url, headers=HEADERS, data=payload)
    except Exception as e:
        print("Error closing positions:", e)
        print("Raw response:", res.text)

def place_option_order(signal):
    try:
        spy_price = get_spy_price()
        expiry = get_today_expiry()
        strike = round(spy_price) - 1 if signal == "sell" else round(spy_price)
        right = "P" if signal == "sell" else "C"
        option_symbol = f"SPY{expiry}{right}{strike:08d}"

        cash = get_cash_balance()
        estimated_price = 1.00  # Assume $100 per contract
        contracts = int(cash // (estimated_price * 100))
        if contracts == 0:
            print("⚠️ Not enough cash to trade.")
            return

        print(f"🚀 Placing {signal.upper()} order: {contracts}x {option_symbol}")
        payload = {
            "class": "option",
            "symbol": option_symbol,
            "side": "buy_to_open",
            "quantity": contracts,
            "type": "market",
            "duration": "day"
        }
        url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders"
        res = requests.post(url, headers=HEADERS, data=payload)
        print(res.text)
    except Exception as e:
        print("Error placing order:", e)

# Webhook Endpoint
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        signal = data.get("signal", "").lower()
        if signal not in ["buy", "sell"]:
            return jsonify({"status": "error", "message": "Invalid signal"})

        print("Received data:", data)
        close_all_positions()
        place_option_order(signal)
        return jsonify({"status": "success", "message": f"{signal} order placed"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Optional Debug Endpoint
@app.route("/debug")
def debug():
    try:
        balances = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances", headers=HEADERS).json()
        quotes = requests.get(f"{BASE_URL}/markets/quotes?symbols=SPY", headers=HEADERS).json()
        positions = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions", headers=HEADERS).json()
        return jsonify({
            "timestamp": str(datetime.datetime.now()),
            "balances_api": balances,
            "quotes_api": quotes,
            "positions_api": positions
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
