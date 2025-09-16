from flask import Flask, request, jsonify
from binance.client import Client
import os
import time

# ---------- FLASK APP ----------
def start_flask():
    app = Flask(__name__)

    # ---------- BINANCE API KEYS ----------
    API_KEY = os.environ.get("BINANCE_API_KEY")
    API_SECRET = os.environ.get("BINANCE_API_SECRET")
    client = Client(API_KEY, API_SECRET)

    # ---------- SETTINGS ----------
    MAX_OPEN_TRADES = 5
    open_trades = {}  # symbol -> position info

    # ---------- HELPER FUNCTIONS ----------
    def calculate_quantity(symbol, trade_size_type, trade_amount, equity_size, price):
        """Calculate order size based on % of equity or fixed USD"""
        if trade_size_type.lower() == "percent":
            usd_value = equity_size * (trade_amount / 100)
        else:  # Fixed USD
            usd_value = trade_amount
        qty = round(usd_value / price, 6)  # adjust precision as needed
        return qty

    def place_order(action, symbol, margin_type, leverage, trade_size_type, trade_amount, equity_size):
        """Place Binance Futures order"""
        # Check max trades
        if len(open_trades) >= MAX_OPEN_TRADES and action in ["buy", "sell"]:
            print(f"Max open trades reached, skipping {symbol} {action}")
            return

        price = float(client.futures_mark_price(symbol=symbol)["markPrice"])
        qty = calculate_quantity(symbol, trade_size_type, trade_amount, equity_size, price)

        # Set leverage & margin type
        client.futures_change_leverage(symbol=symbol, leverage=int(leverage))
        client.futures_change_margin_type(symbol=symbol, marginType=margin_type.upper())

        # Place order
        if action == "buy":
            client.futures_create_order(symbol=symbol, side="BUY", type="MARKET", quantity=qty)
            open_trades[symbol] = {"side": "LONG", "qty": qty}
        elif action == "sell":
            client.futures_create_order(symbol=symbol, side="SELL", type="MARKET", quantity=qty)
            open_trades[symbol] = {"side": "SHORT", "qty": qty}
        elif action == "exit_long" and symbol in open_trades and open_trades[symbol]["side"] == "LONG":
            client.futures_create_order(symbol=symbol, side="SELL", type="MARKET", quantity=open_trades[symbol]["qty"])
            del open_trades[symbol]
        elif action == "exit_short" and symbol in open_trades and open_trades[symbol]["side"] == "SHORT":
            client.futures_create_order(symbol=symbol, side="BUY", type="MARKET", quantity=open_trades[symbol]["qty"])
            del open_trades[symbol]
        else:
            print(f"No action taken for {symbol} - {action}")
            return

        print(f"Order executed: {symbol} {action}, qty={qty}")

    # ---------- FLASK WEBHOOK ----------
    @app.route("/webhook", methods=["POST"])
    def webhook():
        data = request.json
        print("Webhook received:", data)
        try:
            # All values come from Pine Script
            action = data["action"]
            symbol = data["symbol"]
            margin_type = data["margin_type"]
            leverage = data["leverage"]
            trade_size_type = data["trade_size_type"]
            trade_amount = data["trade_amount"]
            equity_size = data["equity_size"]

            place_order(action, symbol, margin_type, leverage, trade_size_type, trade_amount, equity_size)
            return jsonify({"status": "success"})
        except Exception as e:
            print("Error:", e)
            return jsonify({"status": "error", "message": str(e)}), 400

    app.run(host="0.0.0.0", port=8080)

# ================= AUTO-RESTART LOOP =================
while True:
    try:
        print("Starting Flask server...")
        start_flask()
    except Exception as e:
        print("Bot crashed, restarting in 5 seconds...", e)
        time.sleep(5)
