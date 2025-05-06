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

symbols_config = {
    "GBPJPYm":{
        "SL_PIPS" : 100,
        "TP_PIPS" : 100,
        "risk_per_trade" : 0.05,
    },
    "XAUUSDm":{
        "SL_PIPS" : 1000,
        "TP_PIPS" : 1000,
        "risk_per_trade" : 0.05,
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
    """
    Accurately simulate trade outcome by walking forward in time.
    Stops at the first candle where either TP or SL is hit.
    """

    for high, low in zip(highs, lows):
        if direction == 'buy':
            # SL below, TP above
            if low <= sl and high >= tp:
                # Both hit same candle — assume worst case: SL hit first
                return 'loss'
            elif low <= sl:
                return 'loss'
            elif high >= tp:
                return 'win'

        elif direction == 'sell':
            # SL above, TP below
            if high >= sl and low <= tp:
                # Both hit same candle — assume worst case: SL hit first
                return 'loss'
            elif high >= sl:
                return 'loss'
            elif low <= tp:
                return 'win'

    return None  # Neither hit, even after entire simulation

def get_chart(symbol, timeframe, months=36):
    date_to = datetime.now()
    all_data = []

    for m in range(0, months, 6):
        chunk_to = date_to - timedelta(days=m*30)
        chunk_from = chunk_to - timedelta(days=180)

        rates = mt5.copy_rates_range(symbol, timeframe, chunk_from, chunk_to)

        if rates is not None and len(rates) > 0:
            df_chunk = pd.DataFrame(rates)
            all_data.append(df_chunk)

    if not all_data:
        print("❌ No data found over the selected period")
        return pd.DataFrame()

    df = pd.concat(all_data, ignore_index=True)
    df.drop_duplicates(subset='time', inplace=True)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.sort_values('time', inplace=True)
    return df.reset_index(drop=True)

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

    balance = 100
    wins = 0
    losses = 0
    total_pips = 0
    trades = []
    last_loss_time = None

    for i in range(EMA_PERIOD + RSI_PERIOD + 1, len(df)):
        time_now = df['time'].iloc[i]

        # Skip trades if last LOSS was less than 2 hours ago
        if last_loss_time and (time_now - last_loss_time) < timedelta(hours=2):
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
        

        if close > ema and rsi < RSI_OVERSOLD:
            direction = 'buy'
            entry_price += spread_adjustment
            sl = entry_price - sl_pips * pip_size
            tp = entry_price + tp_pips * pip_size

        elif close < ema and rsi > RSI_OVERBOUGHT:
            direction = 'sell'
            entry_price -= spread_adjustment
            sl = entry_price + sl_pips * pip_size
            tp = entry_price - tp_pips * pip_size

        if direction:
            highs = df['high'].iloc[i+1:i+100].values
            lows = df['low'].iloc[i+1:i+100].values

            result = simulate_trade(entry_price, sl, tp, highs, lows, direction)

            if result:
                risk_amount = balance * risk
                lot_value_per_pip = risk_amount / sl_pips
                profit = tp_pips * lot_value_per_pip
                loss = -tp_pips * lot_value_per_pip

                if result == 'win':
                    wins += 1
                    balance += profit
                    total_pips += tp_pips
                else:
                    losses += 1
                    balance += loss
                    total_pips -= sl_pips
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
        results.to_csv(f"{symbol}_results.csv", index=False)
        print(results.tail())
        
