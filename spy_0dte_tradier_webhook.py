@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received data:", data)

    signal = data.get("signal", "").lower()
    if signal not in ["buy", "sell"]:
        return jsonify({"status": "error", "message": "Invalid signal"})

    # Instead of calling Tradier, just log to Google Sheet directly
    log_to_google_sheets(
        signal=signal,
        symbol="SPYTEST",
        qty=1,
        price=1.00,
        total=100.00,
        balance=9900.00,
        pnl=0.00
    )

    return jsonify({"status": "success", "test": "sheet_only"})
