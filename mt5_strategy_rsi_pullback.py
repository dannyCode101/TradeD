
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

# === CONFIG ===
ACCOUNT = 40610362
PASSWORD = "MyDeriv123!"
SERVER = "Deriv-Demo"
SL_PIPS = 15
TP_PIPS = 30
RSI_PERIOD = 14
EMA_PERIOD = 200

# === INIT ===
print("Connecting to MetaTrader 5...")
mt5.initialize()
if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed.")
    mt5.shutdown()
    exit()
print("✅ Connected to MT5.\n")

# === HELPERS ===
def get_chart(symbol, timeframe, months=12):
    date_to = datetime.now()
    date_from = date_to - timedelta(days=30 * months)
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None:
        print(f"❌ No data for {symbol}")
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def backtest_rsi_pullback(symbol):
    df = get_chart(symbol, mt5.TIMEFRAME_M15, months=12)
    if df.empty:
        print("❌ Not enough data")
        return

    symbol_info = mt5.symbol_info(symbol)
    pip_size = 10 * symbol_info.point
    digits = symbol_info.digits

    df['EMA200'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['close'], RSI_PERIOD)

    wins = 0
    losses = 0
    trades = []

    for i in range(EMA_PERIOD + RSI_PERIOD + 1, len(df) - 20):
        close = df['close'].iloc[i]
        ema = df['EMA200'].iloc[i]
        rsi = df['RSI'].iloc[i]

        entry_price = close
        direction = None

        if close > ema and rsi < 30:
            direction = 'buy'
            sl = entry_price - SL_PIPS * pip_size
            tp = entry_price + TP_PIPS * pip_size
        elif close < ema and rsi > 70:
            direction = 'sell'
            sl = entry_price + SL_PIPS * pip_size
            tp = entry_price - TP_PIPS * pip_size

        if direction:
            result = None
            for j in range(i + 1, i + 20):
                high = df['high'].iloc[j]
                low = df['low'].iloc[j]
                if direction == 'buy':
                    if low <= sl:
                        result = 'loss'
                        break
                    if high >= tp:
                        result = 'win'
                        break
                elif direction == 'sell':
                    if high >= sl:
                        result = 'loss'
                        break
                    if low <= tp:
                        result = 'win'
                        break

            if result == 'win':
                wins += 1
            elif result == 'loss':
                losses += 1

            trades.append({
                'time': df['time'].iloc[i],
                'entry': round(entry_price, digits),
                'sl': round(sl, digits),
                'tp': round(tp, digits),
                'direction': direction,
                'result': result
            })

    print(f"✅ {symbol}: {wins} wins / {losses} losses")
    return pd.DataFrame(trades)

# === MULTI SYMBOL TEST ===
symbols = ["GBPJPY", "EURUSD", "USDCAD", "XAUUSD", "AUDJPY"]
for s in symbols:
    print(f"\n📈 Strategy 2 RSI Pullback Backtest: {s}")
    results = backtest_rsi_pullback(s)
    if results is not None:
        print(results.tail())
