import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
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

symbols_config = {
    "GBPJPYm": {
        "SL_PIPS": 100,
        "TP_PIPS": 100,
        "risk_per_trade": 0.05,
    },
    "XAUUSDm": {
        "SL_PIPS": 2000,
        "TP_PIPS": 2000,
        "risk_per_trade": 0.2,
    }
}

print("Connecting to MetaTrader 5...")
mt5.initialize()
if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed.")
    mt5.shutdown()
    exit()
print("✅ Connected to MT5.")

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def simulate_trade(entry, sl, tp, highs, lows, direction):
    for i, (high, low) in enumerate(zip(highs, lows)):
        if direction == 'buy':
            if low <= sl and high >= tp:
                return 'loss', i + 1
            elif low <= sl:
                return 'loss', i + 1
            elif high >= tp:
                return 'win', i + 1
        elif direction == 'sell':
            if high >= sl and low <= tp:
                return 'loss', i + 1
            elif high >= sl:
                return 'loss', i + 1
            elif low <= tp:
                return 'win', i + 1
    return None, 0

def get_chart(symbol, timeframe, months=12):
    date_to = datetime.now()
    date_from = date_to - timedelta(days=months * 30)  # approx. N months back

    # MT5 max bars per request is usually ~10,000
    MAX_BARS = 10000
    timeframe_min = timeframe_to_minutes(timeframe)

    all_data = []
    current_to = date_to

    while current_to > date_from:
        current_from = current_to - timedelta(minutes=MAX_BARS * timeframe_min)
        if current_from < date_from:
            current_from = date_from

        rates = mt5.copy_rates_range(symbol, timeframe, current_from, current_to)
        if rates is not None and len(rates) > 0:
            df_chunk = pd.DataFrame(rates)
            all_data.append(df_chunk)

        current_to = current_from

    if not all_data:
        print("❌ No data found")
        return pd.DataFrame()

    df = pd.concat(all_data, ignore_index=True)
    df.drop_duplicates(subset='time', inplace=True)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.sort_values('time', inplace=True)
    return df.reset_index(drop=True)

def timeframe_to_minutes(tf):
    return {
        mt5.TIMEFRAME_M1: 1,
        mt5.TIMEFRAME_M5: 5,
        mt5.TIMEFRAME_M15: 15,
        mt5.TIMEFRAME_M30: 30,
        mt5.TIMEFRAME_H1: 60,
        mt5.TIMEFRAME_H4: 240,
        mt5.TIMEFRAME_D1: 1440
    }.get(tf, 1)  # default to 1 min if unknown

def run_backtest(symbol, config):
    df = get_chart(symbol, mt5.TIMEFRAME_M15, months=12)
    if df.empty:
        print("❌ Not enough data")
        return

    symbol_info = mt5.symbol_info(symbol)
    pip_size = 10 * symbol_info.point
    digits = symbol_info.digits

    df['EMA200'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['close'], RSI_PERIOD)

    balance = 1000
    wins = 0
    losses = 0
    total_pips = 0
    trades = []
    last_loss_time = None

    for i in range(0, len(df)):
        time_now = df['time'].iloc[i]
        hour = time_now.hour
        minute = time_now.minute
        weekday = time_now.weekday()

        # Only continue if it's Monday (0) or Tuesday (1)
        if weekday not in [0, 1]:
            continue

        # Allow between 15:00–15:59, 16:00:00, 20:00–20:59, and 21:00:00
        allowed = (
            hour in [15,16, 21, 20] 
        )

        if not allowed:
            continue
        close = df['close'].iloc[i]
        ema = df['EMA200'].iloc[i]
        rsi = df['RSI'].iloc[i]

        entry_price = close
        direction = None
        sl_pips = config["SL_PIPS"]
        tp_pips = config["TP_PIPS"]
        risk = config["risk_per_trade"]
        spread_adjustment = SPREAD_PIPS * pip_size
        sl = tp = None

        if close > ema and rsi > 75:
            direction = 'buy'
            entry_price += spread_adjustment
            sl = entry_price - sl_pips * pip_size
            tp = entry_price + tp_pips * pip_size
        else:
            direction = None

        if direction:
            highs = df['high'].iloc[i + 1:i + 1000].values
            lows = df['low'].iloc[i + 1:i + 1000].values

            result, bars_ahead = simulate_trade(entry_price, sl, tp, highs, lows, direction)
            if result is None:
                result = 'open'

            if result:
                risk_amount = balance * risk
                lot_value_per_pip = risk_amount / sl_pips
                profit = tp_pips * lot_value_per_pip
                loss = -tp_pips * lot_value_per_pip

                if result == 'win':
                    wins += 1
                    balance += profit
                    total_pips += tp_pips
                elif result == 'loss':
                    losses += 1
                    balance += loss
                    total_pips -= sl_pips
                    last_loss_time = time_now

                if i + bars_ahead < len(df):
                    time_closed = df['time'].iloc[i + bars_ahead]
                else:
                    time_closed = None

                trades.append({
                    'time': time_now,
                    'time_closed': time_closed,
                    'entry': round(entry_price, digits),
                    'sl': round(sl, digits),
                    'tp': round(tp, digits),
                    'direction': direction,
                    'result': result,
                    'balance_after': round(balance, 2)
                })

    print(f"\n📊 Backtest Summary for {symbol}")
    print(f"✅ Wins: {wins} | ❌ Losses: {losses}")
    print(f"🏦 Final Balance: {round(balance, 2)} (Starting: 100)")
    print(f"📈 Net Pips: {total_pips}")
    if wins + losses > 0:
        print(f"📊 Win Rate: {round(100 * wins / (wins + losses), 2)}%")
        expectancy = round((wins / (wins + losses)) * tp_pips + (losses / (wins + losses)) * -sl_pips, 2)
        print(f"📉 Expectancy (Avg Pips/Trade): {expectancy}")

    return pd.DataFrame(trades)

print("Testing ... ")
for symbol, config in symbols_config.items():
    results = run_backtest(symbol, config)

    if results is not None:
        results.to_csv(f"{symbol}_2results.csv", index=False)
        print(results.tail())
