def log_to_google_sheets(signal, symbol, qty, price, total, balance, pnl):
    import requests
    import os
    webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK")
    print("Google Sheets webhook URL:", webhook_url)

    payload = {
        "signal": signal,
        "option_symbol": symbol,
        "quantity": qty,
        "price": price,
        "total_spent": total,
        "cash_balance": balance,
        "pnl": pnl
    }

    res = requests.post(webhook_url, json=payload)
    print("Google Sheet response:", res.text)
