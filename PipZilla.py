import MetaTrader5 as mt5
import pandas as pd
import time
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import math

# === CONFIG ===
ACCOUNT = 209782758
PASSWORD = "MyExness123!"
SERVER = "Exness-MT5Trial9"
RSI_PERIOD = 14
EMA_PERIOD = 200
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 25
SPREAD_PIPS = 2
last_heartbeat_sent = None
last_checked_candle = None
last_loss_time = None

symbols_config = {
    "GBPJPYm":{
        "SL_PIPS" : 100,
        "TP_PIPS" : 100,
        "risk_per_trade" : 0.05,
        "points_for_lots" : 700,
        "last_checked_candle" : None,
        "last_loss_time" : None,
    },
    "XAUUSDm":{
        "SL_PIPS" : 1000,
        "TP_PIPS" : 1000,
        "risk_per_trade" : 0.05,
        "points_for_lots" : 1000,
        "last_checked_candle" : None,
        "last_loss_time" : None,
    }
}

EMAIL_ADDRESS = "dannyTbot123@gmail.com"
EMAIL_PASSWORD = "rqnv rjwv xadx fqnj"
EMAIL_RECIPIENT = "dannyTbot123@gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

print("Connecting to MetaTrader 5...")
mt5.initialize()
if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed.")
    mt5.shutdown()
    exit()
print("✅ Connected to MT5.")

executed_signals = set()

def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_RECIPIENT
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Email error:", e)

def get_chart(symbol, timeframe, bars=500):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    return df

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_lot_size(balance, sl_pips, risk_percent):
    risk_amount = balance * risk_percent
    raw_lot_size = risk_amount / sl_pips
    rounded_up = math.ceil(raw_lot_size * 100) / 100  # round up to 2 decimal places
    return rounded_up

def open_trade(symbol, lot, order_type, sl, tp, deviation=20):
    price_info = mt5.symbol_info_tick(symbol)
    price = price_info.ask if order_type == mt5.ORDER_TYPE_BUY else price_info.bid
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": deviation,
        "sl": sl,
        "tp": tp,
        "magic": 234000,
        "comment": "RSI-EMA bot",
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)
    print("Trade result:", result)
    return result

def get_last_loss_time(symbol):
    history = mt5.history_deals_get(datetime.now() - timedelta(days=7), datetime.now())
    if not history:
        return None

    for deal in reversed(history):
        if (
            deal.comment == "RSI-EMA bot" and
            deal.entry == 1 and
            deal.symbol == symbol and
            deal.profit < 0
        ):
            return datetime.fromtimestamp(deal.time)
    
    return None

def check_for_trades(symbol, config):
    df = get_chart(symbol, mt5.TIMEFRAME_M15, bars=300)
    if df.empty or len(df) < EMA_PERIOD + RSI_PERIOD:
        return

    # Get the latest candle's open time
    latest_candle_time = df["time"].iloc[-1]
    if config["last_checked_candle"] == latest_candle_time:
        return
    config["last_checked_candle"] = latest_candle_time

    if config["last_loss_time"] and datetime.now() - config["last_loss_time"] < timedelta(hours=2):
        print(f"[{symbol}] Skipping due to recent loss cooldown.")
        return

    # Indicator calculations
    df["EMA200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["RSI"] = calculate_rsi(df["close"], RSI_PERIOD)
    
    close = df["close"].iloc[-1]
    ema = df["EMA200"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    
    signal_id = f"{latest_candle_time}-{symbol}"
    if signal_id in executed_signals:
        return


    direction = None
    entry_price = close
    pip_size = 10 * mt5.symbol_info(symbol).point
    digits = mt5.symbol_info(symbol).digits
    sl_pips = config["SL_PIPS"]
    tp_pips = config["TP_PIPS"]
    risk = config["risk_per_trade"]

    if close > ema and rsi < RSI_OVERSOLD:
        direction = "buy"
        entry_price += SPREAD_PIPS * pip_size
    elif close < ema and rsi > RSI_OVERBOUGHT:
        direction = "sell"
        entry_price -= SPREAD_PIPS * pip_size

    if direction:
        sl = entry_price - sl_pips * pip_size if direction == "buy" else entry_price + sl_pips * pip_size
        tp = entry_price + tp_pips * pip_size if direction == "buy" else entry_price - tp_pips * pip_size
        order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        lot_size = calculate_lot_size(mt5.account_info().equity, config["points_for_lots"], risk)
        result = open_trade(symbol, lot_size, order_type, sl, tp)
        executed_signals.add(signal_id)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            send_email(f"📈 {symbol} Trade Opened", f"{direction.upper()} entry: {entry_price}, SL: {sl}, TP: {tp}")

              
def send_daily_heartbeat():
    global last_heartbeat_sent
    now = datetime.now()
    if now.hour == 0 and (last_heartbeat_sent is None or last_heartbeat_sent.date() < now.date()):
        send_email(subject="🟢 App Heartbeat", body="App still running")
        print("✅ Heartbeat email sent.")
        last_heartbeat_sent = now

print("running")
while True:
    try:
        for symbol, config in symbols_config.items():
            check_for_trades(symbol, config)
        send_daily_heartbeat()
    except Exception as e:
        print("Error in main loop:", e)
        time.sleep(60)
