import MetaTrader5 as mt5
import pandas as pd
import time
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# === CONFIG ===
ACCOUNT = 40610362
PASSWORD = "MyDeriv123!"
SERVER = "Deriv-Demo"
SYMBOL = "XAUUSD"
SL_PIPS = 100
TP_PIPS = 100
RSI_PERIOD = 14
EMA_PERIOD = 200
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 25
SPREAD_PIPS = 2
RISK_PER_TRADE = 0.05
CHECK_INTERVAL = 30  # seconds

EMAIL_ADDRESS = "dannyTbot123@gmail.com"
EMAIL_PASSWORD = "atnq kgdy bchn cvku"
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
last_loss_time = None

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
    return round(risk_amount / sl_pips, 2)

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

def update_last_loss_time():
    global last_loss_time
    history = mt5.history_deals_get(datetime.now() - timedelta(days=7), datetime.now())
    for deal in reversed(history or []):
        if deal.comment == "RSI-EMA bot" and deal.entry == 1 and deal.profit < 0:
            last_loss_time = datetime.fromtimestamp(deal.time)
            break

def check_for_trades():
    global last_loss_time
    update_last_loss_time()
    if last_loss_time and datetime.now() - last_loss_time < timedelta(hours=2):
        print("⏱️ Skipping due to recent loss cooldown.")
        return

    df = get_chart(SYMBOL, mt5.TIMEFRAME_M15, bars=300)
    if df.empty or len(df) < EMA_PERIOD + RSI_PERIOD:
        return

    df["EMA200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["RSI"] = calculate_rsi(df["close"], RSI_PERIOD)

    symbol_info = mt5.symbol_info(SYMBOL)
    pip_size = 10 * symbol_info.point
    digits = symbol_info.digits
    balance = mt5.account_info().balance

    close = df["close"].iloc[-1]
    ema = df["EMA200"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    timestamp = df["time"].iloc[-1]

    signal_id = f"{timestamp}-{round(close, digits)}"
    if signal_id in executed_signals:
        return

    direction = None
    entry_price = close

    if close > ema and rsi < RSI_OVERSOLD:
        direction = "buy"
        entry_price += SPREAD_PIPS * pip_size
    elif close < ema and rsi > RSI_OVERBOUGHT:
        direction = "sell"
        entry_price -= SPREAD_PIPS * pip_size

    if direction:
        sl = entry_price - SL_PIPS * pip_size if direction == "buy" else entry_price + SL_PIPS * pip_size
        tp = entry_price + TP_PIPS * pip_size if direction == "buy" else entry_price - TP_PIPS * pip_size
        order_type = mt5.ORDER_TYPE_BUY if direction == "buy" else mt5.ORDER_TYPE_SELL
        lot_size = calculate_lot_size(balance, SL_PIPS, RISK_PER_TRADE)

        result = open_trade(SYMBOL, lot_size, order_type, sl, tp)
        executed_signals.add(signal_id)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            send_email(
                subject="📈 Trade Opened",
                body=f"{direction.upper()} trade opened on {SYMBOL}\nEntry: {entry_price}\nSL: {sl}\nTP: {tp}\nLot: {lot_size}"
            )

def monitor_closed_trades():
    global last_loss_time
    deals = mt5.history_deals_get(datetime.today() - timedelta(days=1), datetime.today())
    if deals is None:
        return
    for deal in deals:
        if deal.comment == "RSI-EMA bot" and deal.entry == 1:
            send_email(
                subject="📉 Trade Closed",
                body=f"Trade closed on {SYMBOL}\nProfit: {deal.profit} USD\nTicket: {deal.ticket}"
            )
            if deal.profit < 0:
                last_loss_time = datetime.fromtimestamp(deal.time)

def get_chart2(symbol, timeframe, months=12):
    date_to = datetime.now()
    date_from = date_to - timedelta(days=30 * months)
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None:
        print(f"❌ No data for {symbol}")
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def run_backtest():
    print("\n📊 Running 12-Month Backtest for", SYMBOL)
    df = get_chart2(SYMBOL, mt5.TIMEFRAME_M15, months=12)
    if df.empty or len(df) < EMA_PERIOD + RSI_PERIOD + 30:
        print("❌ Not enough historical data.")
        return

    df["EMA200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    df["RSI"] = calculate_rsi(df["close"], RSI_PERIOD)

    symbol_info = mt5.symbol_info(SYMBOL)
    pip_size = 10 * symbol_info.point
    digits = symbol_info.digits

    balance = 100.0
    wins = 0
    losses = 0
    total_pips = 0
    last_loss_time = None

    for i in range(EMA_PERIOD + RSI_PERIOD + 1, len(df) - 30):
        time_now = df["time"].iloc[i]
        if last_loss_time and (time_now - last_loss_time) < timedelta(hours=2):
            continue

        close = df["close"].iloc[i]
        ema = df["EMA200"].iloc[i]
        rsi = df["RSI"].iloc[i]

        entry_price = close
        direction = None

        if close > ema and rsi < RSI_OVERSOLD:
            direction = "buy"
            entry_price += SPREAD_PIPS * pip_size
            sl = entry_price - SL_PIPS * pip_size
            tp = entry_price + TP_PIPS * pip_size
        elif close < ema and rsi > RSI_OVERBOUGHT:
            direction = "sell"
            entry_price -= SPREAD_PIPS * pip_size
            sl = entry_price + SL_PIPS * pip_size
            tp = entry_price - TP_PIPS * pip_size
        else:
            continue

        highs = df["high"].iloc[i+1:i+30].values
        lows = df["low"].iloc[i+1:i+30].values

        result = None
        for high, low in zip(highs, lows):
            if direction == "buy":
                if low <= sl:
                    result = "loss"
                    break
                if high >= tp:
                    result = "win"
                    break
            elif direction == "sell":
                if high >= sl:
                    result = "loss"
                    break
                if low <= tp:
                    result = "win"
                    break

        if result:
            risk_amount = balance * RISK_PER_TRADE
            lot_value_per_pip = risk_amount / SL_PIPS
            profit = TP_PIPS * lot_value_per_pip
            loss = -SL_PIPS * lot_value_per_pip
            
            if result == "win":
                balance += TP_PIPS * lot_value_per_pip
                total_pips += TP_PIPS
                wins += 1
            else:
                balance -= SL_PIPS * lot_value_per_pip
                total_pips -= SL_PIPS
                losses += 1
                last_loss_time = time_now

    print(f"\n📊 Backtest Summary for {SYMBOL}")
    print(f"✅ Wins: {wins} | ❌ Losses: {losses}")
    print(f"🏦 Final Balance: {round(balance, 2)} (Starting: 100.0)")
    print(f"📈 Net Pips: {total_pips}")
    total_trades = wins + losses
    if total_trades > 0:
        win_rate = round(100 * wins / total_trades, 2)
        expectancy = round((wins / total_trades) * TP_PIPS + (losses / total_trades) * -SL_PIPS, 2)
        print(f"📊 Win Rate: {win_rate}%")
        print(f"📉 Expectancy (Avg Pips/Trade): {expectancy}")
              
        
update_last_loss_time()
print(last_loss_time)
run_backtest()
while True:
    try:
        check_for_trades()
        monitor_closed_trades()
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("Error in loop:", e)
        time.sleep(60)

