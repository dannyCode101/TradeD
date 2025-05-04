
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

# === CONFIG ===
ACCOUNT = 40610362
PASSWORD = "MyDeriv123!"
SERVER = "Deriv-Demo"
SYMBOL = "GBPJPY"
SL_PIPS = 10
RR_RATIO = 2.5
EMA_FAST = 50
EMA_SLOW = 200

# === INIT ===
print("Connecting to MetaTrader 5...")
mt5.initialize()
if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed.")
    mt5.shutdown()
    exit()
print("✅ Connected to MT5.\n")

# === HELPERS ===
def get_chart(symbol, timeframe, months=36):
    from datetime import timedelta
    date_to = datetime.now()
    date_from = date_to - timedelta(days=30 * months)
    rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
    if rates is None:
        print(f"❌ No data for {symbol}")
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def is_bullish_engulfing(prev, curr):
    return prev['close'] < prev['open'] and curr['close'] > curr['open'] and curr['close'] > prev['open'] and curr['open'] < prev['close']

def backtest_strategy(symbol, sl_pips=15, rr_ratio=2):
    df = get_chart(symbol, mt5.TIMEFRAME_M15, months=12)

    if df.empty:
        print("❌ Not enough historical data.")
        return

    symbol_info = mt5.symbol_info(symbol)
    pip_size = 10 * symbol_info.point
    digits = symbol_info.digits

    df['EMA_FAST'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['EMA_SLOW'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()

    trades = []
    wins = 0
    losses = 0
    in_position = False

    for i in range(EMA_SLOW + 2, len(df) - 20):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        prev_ema_fast = df['EMA_FAST'].iloc[i - 1]
        prev_ema_slow = df['EMA_SLOW'].iloc[i - 1]
        curr_ema_fast = df['EMA_FAST'].iloc[i]
        curr_ema_slow = df['EMA_SLOW'].iloc[i]

        entry_price = curr['close']
        sl = tp = None
        direction = None

        # Bullish Crossover Entry with Pullback
        if (prev_ema_fast < prev_ema_slow) and (curr_ema_fast > curr_ema_slow):
            # Wait for pullback and bullish engulfing
            for j in range(i + 1, i + 20):
                prev_c = df.iloc[j - 1]
                curr_c = df.iloc[j]
                if is_bullish_engulfing(prev_c, curr_c):
                    entry_price = curr_c['close']
                    sl = entry_price - sl_pips * pip_size
                    tp = entry_price + sl_pips * rr_ratio * pip_size
                    direction = 'buy'
                    break

        # Bearish Crossover Entry with Pullback
        elif (prev_ema_fast > prev_ema_slow) and (curr_ema_fast < curr_ema_slow):
            for j in range(i + 1, i + 20):
                prev_c = df.iloc[j - 1]
                curr_c = df.iloc[j]
                if is_bullish_engulfing(curr_c, prev_c):  # inverted engulfing pattern
                    entry_price = curr_c['close']
                    sl = entry_price + sl_pips * pip_size
                    tp = entry_price - sl_pips * rr_ratio * pip_size
                    direction = 'sell'
                    break

        # Simulate trade outcome
        if direction:
            result = None
            for k in range(j + 1, j + 20):
                high = df['high'].iloc[k]
                low = df['low'].iloc[k]
                if direction == 'buy':
                    if low <= sl:
                        result = 'loss'
                        break
                    if high >= tp:
                        result = 'win'
                        break
                else:
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
                'direction': direction,
                'entry': round(entry_price, digits),
                'sl': round(sl, digits),
                'tp': round(tp, digits),
                'result': result
            })

    print(f"✅ Backtest complete: {wins} wins / {losses} losses")
    return pd.DataFrame(trades)

# === RUN BACKTEST ===
print("GBPJPY")
results = backtest_strategy("GBPJPY", sl_pips=SL_PIPS, rr_ratio=RR_RATIO)
print("EURUSD")
results = backtest_strategy("EURUSD", sl_pips=SL_PIPS, rr_ratio=RR_RATIO)
print("USDCAD")
results = backtest_strategy("USDCAD", sl_pips=SL_PIPS, rr_ratio=RR_RATIO)
print("XAUUSD")
results = backtest_strategy("XAUUSD", sl_pips=SL_PIPS, rr_ratio=RR_RATIO)
print("AUDJPY")
results = backtest_strategy("AUDJPY", sl_pips=SL_PIPS, rr_ratio=RR_RATIO)
if results is not None:
    print(results.tail())
