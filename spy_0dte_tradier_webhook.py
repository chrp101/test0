from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime
import time

app = Flask(__name__)

# Configuration
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}
BASE_URL = "https://sandbox.tradier.com/v1"

def get_spy_price():
    """Get current SPY price"""
    try:
        res = requests.get(f"{BASE_URL}/markets/quotes?symbols=SPY", headers=HEADERS)
        res.raise_for_status()
        quotes = res.json().get("quotes", {})
        quote = quotes["quote"] if isinstance(quotes, dict) else quotes[0]
        return float(quote["last"])
    except Exception as e:
        print(f"Error getting SPY price: {e}")
        return None

def get_cash_balance():
    """Get available cash balance"""
    try:
        res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances", headers=HEADERS)
        res.raise_for_status()
        return float(res.json()["balances"]["cash_available"])
    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0

def get_today_expiry():
    """Get today's expiry in YYMMDD format"""
    return datetime.now().strftime("%y%m%d")

def close_all_positions():
    """Close all existing positions"""
    try:
        res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions", headers=HEADERS)
        res.raise_for_status()
        data = res.json()
        
        # Handle case where no positions exist
        if "positions" not in data or not data["positions"]:
            print("No positions to close")
            return True
            
        positions = data["positions"].get("position", [])
        if not isinstance(positions, list):
            positions = [positions]
        
        for pos in positions:
            symbol = pos["symbol"]
            qty = abs(int(pos["quantity"]))  # Use absolute value
            
            # Determine correct side based on position type
            if pos["quantity"] > 0:  # Long position
                side = "sell_to_close"
            else:  # Short position
                side = "buy_to_close"
            
            payload = {
                "class": "option",
                "symbol": symbol,
                "side": side,
                "quantity": qty,
                "type": "market",
                "duration": "day"
            }
            
            print(f"Closing position: {symbol}, {qty} contracts, {side}")
            close_res = requests.post(f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders", headers=HEADERS, data=payload)
            if not close_res.ok:
                print(f"Error closing position {symbol}: {close_res.text}")
        
        # Wait a moment for orders to process
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"Error closing positions: {e}")
        return False

def get_option_price(option_symbol):
    """Get current option price for better quantity calculation"""
    try:
        res = requests.get(f"{BASE_URL}/markets/quotes?symbols={option_symbol}", headers=HEADERS)
        res.raise_for_status()
        quotes = res.json().get("quotes", {})
        quote = quotes["quote"] if isinstance(quotes, dict) else quotes[0]
        
        # Use mid price if available, otherwise use last price
        if "bid" in quote and "ask" in quote and quote["bid"] and quote["ask"]:
            return (float(quote["bid"]) + float(quote["ask"])) / 2
        elif "last" in quote and quote["last"]:
            return float(quote["last"])
        else:
            return 1.00  # Fallback estimate
    except Exception as e:
        print(f"Error getting option price for {option_symbol}: {e}")
        return 1.00  # Fallback estimate

def place_option_order(signal):
    """Place option order based on signal"""
    try:
        spy_price = get_spy_price()
        if spy_price is None:
            print("Could not get SPY price")
            return False
            
        expiry = get_today_expiry()
        
        # Determine strike and option type based on signal
        if signal == "sell":
            # For sell signal, buy puts slightly OTM
            strike = round(spy_price) - 1
            right = "P"
        else:  # buy signal
            # For buy signal, buy calls at or near the money
            strike = round(spy_price)
            right = "C"
        
        # Format option symbol properly
        option_symbol = f"SPY{expiry}{right}{strike:08d}"
        
        # Get current option price for better quantity calculation
        option_price = get_option_price(option_symbol)
        
        cash = get_cash_balance()
        if cash <= 0:
            print("No cash available")
            return False
            
        # Calculate number of contracts (each contract = 100 shares)
        # Leave some buffer by using 90% of available cash
        contracts = int((cash * 0.9) // (option_price * 100))
        
        if contracts == 0:
            print(f"Not enough cash. Available: ${cash:.2f}, Option price estimate: ${option_price:.2f}")
            return False
        
        payload = {
            "class": "option",
            "symbol": option_symbol,
            "side": "buy_to_open",
            "quantity": contracts,
            "type": "market",
            "duration": "day"
        }
        
        print(f"Placing {signal.upper()} order:")
        print(f"  Symbol: {option_symbol}")
        print(f"  Contracts: {contracts}")
        print(f"  Estimated cost: ${option_price * contracts * 100:.2f}")
        
        order_res = requests.post(f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders", headers=HEADERS, data=payload)
        
        if order_res.ok:
            order_data = order_res.json()
            print(f"Order placed successfully. Order ID: {order_data.get('order', {}).get('id', 'Unknown')}")
            return True
        else:
            print(f"Error placing order: {order_res.text}")
            return False
            
    except Exception as e:
        print(f"Error placing option order: {e}")
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle TradingView webhook"""
    try:
        # Parse incoming JSON data
        if request.is_json:
            data = request.get_json()
        else:
            data = json.loads(request.data.decode('utf-8'))
            
        print(f"Received alert at {datetime.now()}: {data}")
        
        # Extract signal from webhook data
        signal = data.get("signal", "").lower().strip()
        
        if signal not in ["buy", "sell"]:
            error_msg = f"Invalid signal: '{signal}'. Expected 'buy' or 'sell'"
            print(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 400
        
        # Validate environment variables
        if not TRADIER_TOKEN or not ACCOUNT_ID:
            error_msg = "Missing TRADIER_TOKEN or ACCOUNT_ID environment variables"
            print(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
        
        print(f"Processing {signal.upper()} signal...")
        
        # Close existing positions first
        if not close_all_positions():
            error_msg = "Failed to close existing positions"
            print(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
        
        # Place new option order
        if not place_option_order(signal):
            error_msg = f"Failed to place {signal} order"
            print(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
        
        success_msg = f"{signal.upper()} order placed successfully"
        print(success_msg)
        return jsonify({"status": "success", "message": success_msg})
        
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in request: {e}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 400
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(error_msg)
        return jsonify({"status": "error", "message": error_msg}), 500

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "tradier_configured": bool(TRADIER_TOKEN and ACCOUNT_ID)
    })

if __name__ == "__main__":
    print("Starting TradingView to Tradier webhook server...")
    print(f"Tradier Token configured: {bool(TRADIER_TOKEN)}")
    print(f"Account ID configured: {bool(ACCOUNT_ID)}")
    app.run(host="0.0.0.0", port=5000, debug=False)