from flask import Flask, request, jsonify
import requests
import datetime
import os

app = Flask(__name__)

# --- CONFIGURATION ---
TRADIER_TOKEN = os.getenv("Xq6IBE2AvGg9jLBtqED658mXgYMO")
ACCOUNT_ID = os.getenv("VA20184697")
BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

# --- Tradier Helpers ---
def get_spy_price():
    url = f"{BASE_URL}/markets/quotes?symbols=SPY"
    res = requests.get(url, headers=HEADERS)
    try:
        data = res.json()
        return float(data["quotes"]["quote"]["last"])
    except Exception as e:
        print("Error fetching SPY price:", e)
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
            return {"success": False, "message": "Not enough cash to trade."}

        print(f"Placing {signal.upper()} order: {contracts}x {option_symbol}")
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
        return {"success": True, "response": res.text}

    except Exception as e:
        print("Error placing order:", e)
        return {"success": False, "message": str(e)}

# --- Webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("Received data:", data)

        signal = data.get("signal", "").lower()
        if signal not in ["buy", "sell"]:
            return jsonify({"status": "error", "message": "Invalid signal"})

        result = place_option_order(signal)
        if not result["success"]:
            return jsonify({"status": "error", "message": result["message"]})

        return jsonify({"status": "success", "message": "Order placed", "response": result["response"]})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Optional: test endpoint
@app.route("/debug")
def debug():
    return jsonify({
        "timestamp": str(datetime.datetime.now()),
        "config": {
            "tradier_token_set": bool(TRADIER_TOKEN),
            "account_id_set": bool(ACCOUNT_ID),
            "base_url": BASE_URL
        },
        "balances_api": requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances", headers=HEADERS).json(),
        "quotes_api": requests.get(f"{BASE_URL}/markets/quotes?symbols=SPY", headers=HEADERS).json(),
        "positions_api": requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions", headers=HEADERS).json()
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
