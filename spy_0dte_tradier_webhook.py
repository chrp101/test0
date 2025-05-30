from flask import Flask, request, jsonify
import requests
import datetime

app = Flask(__name__)

# CONFIGURATION
TRADIER_TOKEN = "YOUR_SANDBOX_TOKEN"
ACCOUNT_ID = "YOUR_SANDBOX_ACCOUNT_ID"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}
BASE_URL = "https://sandbox.tradier.com/v1"

# --- Helper Functions ---
def get_spy_price():
    url = f"{BASE_URL}/markets/quotes?symbols=SPY"
    res = requests.get(url, headers=HEADERS)
    return float(res.json()["quotes"]["quote"]["last"])

def get_cash_balance():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances"
    res = requests.get(url, headers=HEADERS)
    return float(res.json()["balances"]["cash_available"])

def get_today_expiry():
    return datetime.datetime.now().strftime("%Y-%m-%d")  # Format: YYYY-MM-DD

def get_option_symbol(signal):
    expiry = get_today_expiry()
    right = "put" if signal == "sell" else "call"
    url = f"{BASE_URL}/markets/options/chains?symbol=SPY&expiration={expiry}&greeks=false"
    res = requests.get(url, headers=HEADERS)
    chains = res.json().get("options", {}).get("option", [])

    for opt in chains:
        if opt["option_type"] == right:
            return opt["symbol"]
    return None

def close_all_positions():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions"
    res = requests.get(url, headers=HEADERS).json()
    if "positions" not in res or res["positions"] is None:
        return

    for pos in res["positions"]["position"]:
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

def place_option_order(signal):
    option_symbol = get_option_symbol(signal)
    if not option_symbol:
        print("No valid option symbol found.")
        return

    cash = get_cash_balance()
    estimated_price = 1.00  # Assumed $1 per contract = $100 total per contract
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
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders"
    res = requests.post(url, headers=HEADERS, data=payload)
    print(res.text)

# --- Webhook Endpoint ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        signal = data.get("signal", "").lower()

        if signal not in ["buy", "sell"]:
            return jsonify({"status": "error", "message": "Invalid signal"}), 400

        close_all_positions()
        place_option_order(signal)

        return jsonify({"status": "success", "signal": signal})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Render Host Setup ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
