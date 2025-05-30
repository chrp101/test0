from flask import Flask, request, jsonify
import requests
import datetime

app = Flask(__name__)

# --- CONFIGURATION ---
TRADIER_TOKEN = "Xq6IBE2AvGg9jLBtqED658mXgYMO"
ACCOUNT_ID = "VA20184697"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}
BASE_URL = "https://sandbox.tradier.com/v1"

# --- HELPER FUNCTIONS ---
def get_spy_price():
    url = f"{BASE_URL}/markets/quotes?symbols=SPY"
    res = requests.get(url, headers=HEADERS)
    try:
        return float(res.json()["quotes"]["quote"]["last"])
    except Exception as e:
        print("Error fetching SPY price:", e)
        print("Raw response:", res.text)
        raise

def get_cash_balance():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances"
    res = requests.get(url, headers=HEADERS)
    try:
        return float(res.json()["balances"]["cash_available"])
    except Exception as e:
        print("Error fetching balance:", e)
        print("Raw response:", res.text)
        raise

def get_today_expiry():
    return datetime.datetime.now().strftime("%y%m%d")

def get_option_symbol(signal):
    expiry = get_today_expiry()
    right = "put" if signal == "sell" else "call"
    url = f"{BASE_URL}/markets/options/chains?symbol=SPY&expiration=20{expiry}&greeks=false"
    res = requests.get(url, headers=HEADERS)
    try:
        chains = res.json().get("options", {}).get("option", [])
        for opt in chains:
            if opt["option_type"] == right:
                return opt["symbol"]
    except Exception as e:
        print("Error fetching option chain:", e)
        print("Raw response:", res.text)
    return None

def close_all_positions():
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions"
    res = requests.get(url, headers=HEADERS)
    try:
        positions = res.json().get("positions")
        if positions is None:
            return
        for pos in positions["position"]:
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
    option_symbol = get_option_symbol(signal)
    if not option_symbol:
        print("No valid option symbol found.")
        return

    cash = get_cash_balance()
    estimated_price = 1.00  # $100 per contract
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
    try:
        print("Order response:", res.json())
    except:
        print("Order failed. Raw response:", res.text)

# --- WEBHOOK ---
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
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

# --- RUN ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
