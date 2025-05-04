import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

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

# Trade cost config
SPREAD_PIPS = 2     # realistic spread for gold
COMMISSION_PER_TRADE = 0  # flat fee (optional)
RISK_PER_TRADE = 0.05  # 3% of account balance

# === INIT ===
print("Connecting to MetaTrader 5...")
mt5.initialize()
if not mt5.login(ACCOUNT, PASSWORD, SERVER):
    print("❌ Login failed.")
    mt5.shutdown()
    exit()
print("✅ Connected to MT5.\n")

# Prompt user for starting balance
try:
    INITIAL_BALANCE = float(input("💰 Enter starting account balance (e.g. 10000): "))
except ValueError:
    print("❌ Invalid amount entered.")
    mt5.shutdown()
    exit()

# === HELPERS ===
def get_chart(symbol, timeframe, months=1):
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

def simulate_trade(entry, sl, tp, highs, lows, direction):
    """Simulates trade inside future candles to avoid bias"""
    for high, low in zip(highs, lows):
        if direction == 'buy':
            if low <= sl:
                return 'loss'
            if high >= tp:
                return 'win'
        elif direction == 'sell':
            if high >= sl:
                return 'loss'
            if low <= tp:
                return 'win'
    return None  # no hit

def backtest_gold_rsi_pullback(symbol):
    df = get_chart(symbol, mt5.TIMEFRAME_M15, months=12)
    if df.empty:
        print("❌ Not enough data")
        return

    symbol_info = mt5.symbol_info(symbol)
    pip_size = 10 * symbol_info.point
    digits = symbol_info.digits

    df['EMA200'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['close'], RSI_PERIOD)

    balance = INITIAL_BALANCE
    wins = 0
    losses = 0
    total_pips = 0
    trades = []
    last_loss_time = None

    for i in range(EMA_PERIOD + RSI_PERIOD + 1, len(df) - 30):
        time_now = df['time'].iloc[i]

        # Skip trades if last LOSS was less than 2 hours ago
        if last_loss_time and (time_now - last_loss_time) < timedelta(hours=2):
            continue

        close = df['close'].iloc[i]
        ema = df['EMA200'].iloc[i]
        rsi = df['RSI'].iloc[i]

        entry_price = close
        direction = None

        spread_adjustment = SPREAD_PIPS * pip_size
        sl = tp = None

        if close > ema and rsi < RSI_OVERSOLD:
            direction = 'buy'
            entry_price += spread_adjustment
            sl = entry_price - SL_PIPS * pip_size
            tp = entry_price + TP_PIPS * pip_size

        elif close < ema and rsi > RSI_OVERBOUGHT:
            direction = 'sell'
            entry_price -= spread_adjustment
            sl = entry_price + SL_PIPS * pip_size
            tp = entry_price - TP_PIPS * pip_size

        if direction:
            highs = df['high'].iloc[i+1:i+30].values
            lows = df['low'].iloc[i+1:i+30].values

            result = simulate_trade(entry_price, sl, tp, highs, lows, direction)

            if result:
                risk_amount = balance * RISK_PER_TRADE
                lot_value_per_pip = risk_amount / SL_PIPS
                profit = TP_PIPS * lot_value_per_pip
                loss = -SL_PIPS * lot_value_per_pip

                if result == 'win':
                    wins += 1
                    balance += profit
                    total_pips += TP_PIPS
                else:
                    losses += 1
                    balance += loss
                    total_pips -= SL_PIPS
                    last_loss_time = time_now

                trades.append({
                    'time': time_now,
                    'entry': round(entry_price, digits),
                    'sl': round(sl, digits),
                    'tp': round(tp, digits),
                    'direction': direction,
                    'result': result,
                    'balance_after': round(balance, 2)
                })

    print(f"\n📊 Backtest Summary for {symbol}")
    print(f"✅ Wins: {wins} | ❌ Losses: {losses}")
    print(f"🏦 Final Balance: {round(balance, 2)} (Starting: {INITIAL_BALANCE})")
    print(f"📈 Net Pips: {total_pips}")
    if wins + losses > 0:
        print(f"📊 Win Rate: {round(100 * wins / (wins + losses), 2)}%")
        expectancy = round((wins / (wins + losses)) * TP_PIPS + (losses / (wins + losses)) * -SL_PIPS, 2)
        print(f"📉 Expectancy (Avg Pips/Trade): {expectancy}")

    return pd.DataFrame(trades)

# === RUN BACKTEST ===
print(f"\n📈 Starting RSI Strategy Backtest on {SYMBOL}")
results = backtest_gold_rsi_pullback(SYMBOL)
if results is not None:
    results.to_csv(f"{SYMBOL}_rsi_backtest_results.csv", index=False)
    print(results.tail())
