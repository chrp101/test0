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
        print("Checking for existing positions...")
        res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions", headers=HEADERS)
        print(f"Positions API response status: {res.status_code}")
        
        if not res.ok:
            print(f"Error getting positions: {res.text}")
            return False
            
        data = res.json()
        print(f"Positions API response: {data}")
        
        # Handle different response formats from Tradier API
        if "positions" not in data:
            print("No 'positions' key in response - likely no positions")
            return True
            
        positions_data = data["positions"]
        
        # Handle null or empty positions
        if not positions_data or positions_data == "null":
            print("No positions to close")
            return True
            
        # Extract position array
        if isinstance(positions_data, dict):
            positions = positions_data.get("position", [])
        else:
            positions = positions_data
            
        if not positions:
            print("No positions found in response")
            return True
            
        # Ensure positions is a list
        if not isinstance(positions, list):
            positions = [positions]
        
        print(f"Found {len(positions)} position(s) to close")
        
        success_count = 0
        for i, pos in enumerate(positions):
            try:
                print(f"Processing position {i+1}: {pos}")
                
                symbol = pos.get("symbol")
                quantity = pos.get("quantity")
                
                if not symbol or quantity is None:
                    print(f"Skipping invalid position: {pos}")
                    continue
                
                qty = abs(int(float(quantity)))  # Handle string quantities
                if qty == 0:
                    print(f"Skipping zero quantity position: {symbol}")
                    continue
                
                # Determine correct side based on position type
                if float(quantity) > 0:  # Long position
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
                
                if close_res.ok:
                    order_data = close_res.json()
                    print(f"Close order placed successfully: {order_data}")
                    success_count += 1
                else:
                    print(f"Error closing position {symbol}: Status {close_res.status_code}, Response: {close_res.text}")
                    
            except Exception as pos_error:
                print(f"Error processing individual position: {pos_error}")
                continue
        
        print(f"Successfully placed {success_count} close orders out of {len(positions)} positions")
        
        # Wait a moment for orders to process
        if success_count > 0:
            print("Waiting for close orders to process...")
            time.sleep(3)
        
        return True  # Return True even if some positions failed to close
        
    except Exception as e:
        print(f"Error in close_all_positions: {e}")
        import traceback
        traceback.print_exc()
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
        print(f"Starting to place {signal} order...")
        
        # Get SPY price
        spy_price = get_spy_price()
        if spy_price is None:
            print("Could not get SPY price")
            return False
        print(f"Current SPY price: ${spy_price:.2f}")
            
        # Get today's expiry
        expiry = get_today_expiry()
        print(f"Using expiry: {expiry}")
        
        # Determine strike and option type based on signal
        if signal == "sell":
            # For sell signal, buy puts slightly OTM
            strike = round(spy_price) - 1
            right = "P"
        else:  # buy signal
            # For buy signal, buy calls at or near the money
            strike = round(spy_price)
            right = "C"
        
        print(f"Strike: {strike}, Option type: {right}")
        
        # Format option symbol properly
        option_symbol = f"SPY{expiry}{right}{strike:08d}"
        print(f"Option symbol: {option_symbol}")
        
        # Check if this option exists by trying to get a quote
        print("Checking if option exists...")
        try:
            quote_res = requests.get(f"{BASE_URL}/markets/quotes?symbols={option_symbol}", headers=HEADERS)
            if quote_res.ok:
                quote_data = quote_res.json()
                print(f"Option quote response: {quote_data}")
            else:
                print(f"Warning: Could not get quote for {option_symbol}: {quote_res.text}")
        except Exception as quote_error:
            print(f"Warning: Error getting option quote: {quote_error}")
        
        # Get current option price for better quantity calculation
        option_price = get_option_price(option_symbol)
        print(f"Estimated option price: ${option_price:.2f}")
        
        # Get cash balance
        cash = get_cash_balance()
        print(f"Available cash: ${cash:.2f}")
        
        if cash <= 0:
            print("No cash available")
            return False
            
        # Calculate number of contracts (each contract = 100 shares)
        # Use a more conservative approach - start with 1 contract or 10% of cash
        max_contracts_by_cash = int((cash * 0.1) // (option_price * 100))
        contracts = max(1, min(max_contracts_by_cash, 5))  # At least 1, max 5 for safety
        
        estimated_cost = option_price * contracts * 100
        print(f"Contracts to buy: {contracts}")
        print(f"Estimated total cost: ${estimated_cost:.2f}")
        
        if estimated_cost > cash:
            print(f"Estimated cost (${estimated_cost:.2f}) exceeds available cash (${cash:.2f})")
            contracts = 1  # Try with just 1 contract
            estimated_cost = option_price * 100
            print(f"Reducing to 1 contract, estimated cost: ${estimated_cost:.2f}")
            
            if estimated_cost > cash:
                print("Not enough cash even for 1 contract")
                return False
        
        payload = {
            "class": "option",
            "symbol": option_symbol,
            "side": "buy_to_open",
            "quantity": contracts,
            "type": "market",
            "duration": "day"
        }
        
        print(f"Order payload: {payload}")
        
        print(f"Placing {signal.upper()} order to Tradier...")
        order_res = requests.post(f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders", headers=HEADERS, data=payload)
        
        print(f"Order response status: {order_res.status_code}")
        print(f"Order response headers: {dict(order_res.headers)}")
        
        if order_res.ok:
            order_data = order_res.json()
            print(f"Order placed successfully!")
            print(f"Full response: {order_data}")
            order_id = order_data.get('order', {}).get('id', 'Unknown')
            print(f"Order ID: {order_id}")
            return True
        else:
            print(f"Error placing order!")
            print(f"Status code: {order_res.status_code}")
            print(f"Response text: {order_res.text}")
            
            # Try to parse error response
            try:
                error_data = order_res.json()
                print(f"Error JSON: {error_data}")
            except:
                print("Could not parse error response as JSON")
            
            return False
            
    except Exception as e:
        print(f"Exception in place_option_order: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Try to close existing positions first (but don't fail if this doesn't work)
        close_success = close_all_positions()
        if not close_success:
            print("Warning: Failed to close existing positions, but continuing with new order...")
        
        # Place new option order
        if not place_option_order(signal):
            error_msg = f"Failed to place {signal} order"
            print(error_msg)
            return jsonify({"status": "error", "message": error_msg}), 500
        
        success_msg = f"{signal.upper()} order placed successfully"
        if not close_success:
            success_msg += " (warning: existing positions may not have been closed)"
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

@app.route("/debug", methods=["GET"])
def debug_info():
    """Debug endpoint to check account status"""
    try:
        debug_data = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "tradier_token_set": bool(TRADIER_TOKEN),
                "account_id_set": bool(ACCOUNT_ID),
                "base_url": BASE_URL
            }
        }
        
        # Test positions API
        try:
            pos_res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/positions", headers=HEADERS)
            debug_data["positions_api"] = {
                "status_code": pos_res.status_code,
                "response": pos_res.json() if pos_res.ok else pos_res.text
            }
        except Exception as e:
            debug_data["positions_api"] = {"error": str(e)}
        
        # Test balances API
        try:
            bal_res = requests.get(f"{BASE_URL}/accounts/{ACCOUNT_ID}/balances", headers=HEADERS)
            debug_data["balances_api"] = {
                "status_code": bal_res.status_code,
                "response": bal_res.json() if bal_res.ok else bal_res.text
            }
        except Exception as e:
            debug_data["balances_api"] = {"error": str(e)}
        
        # Test quotes API
        try:
            quote_res = requests.get(f"{BASE_URL}/markets/quotes?symbols=SPY", headers=HEADERS)
            debug_data["quotes_api"] = {
                "status_code": quote_res.status_code,
                "response": quote_res.json() if quote_res.ok else quote_res.text
            }
        except Exception as e:
            debug_data["quotes_api"] = {"error": str(e)}
        
        return jsonify(debug_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-close", methods=["POST"])
def test_close():
    """Test endpoint to manually trigger position closing"""
    try:
        result = close_all_positions()
        return jsonify({
            "success": result,
            "message": "Position closing completed" if result else "Position closing failed"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-order", methods=["POST"])
def test_order():
    """Test endpoint to manually test order placement"""
    try:
        data = request.get_json() or {}
        signal = data.get("signal", "buy").lower()
        
        if signal not in ["buy", "sell"]:
            return jsonify({"error": "Invalid signal. Use 'buy' or 'sell'"}), 400
            
        result = place_option_order(signal)
        return jsonify({
            "success": result,
            "message": f"{signal} order completed" if result else f"{signal} order failed"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Starting TradingView to Tradier webhook server...")
    print(f"Tradier Token configured: {bool(TRADIER_TOKEN)}")
    print(f"Account ID configured: {bool(ACCOUNT_ID)}")
    app.run(host="0.0.0.0", port=5000, debug=False)