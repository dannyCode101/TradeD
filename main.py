import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta

mt5.initialize()

account = 40610362
password = "MyDeriv123!"
server = "Deriv-Demo"

if not mt5.login(account, password, server):
    print("NOT WORKING")
    mt5.shutdown()
    exit()

def open_trade(symbol, lot, order_type, sl_value=None, tp_value=None, deviation=20):
    price = mt5.symbol_info_tick(symbol)

    if order_type == mt5.ORDER_TYPE_BUY:
        order_price = price.ask
    elif order_type == mt5.ORDER_TYPE_SELL:
        order_price = price.bid

    else:
        print("Invalid order type")
        return

    print("sending order...")

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": order_price,
        "deviation": deviation,
        "magic": 234000,
        "comment": "python script open",
        "type_time": mt5.ORDER_TIME_GTC,
    }

    if sl_value is not None:
        request["sl"] = sl_value
    if tp_value is not None:
        request["tp"] = tp_value

    result = mt5.order_send(request)
    print(result)
    if result is None:
        print("order_send() failed, result is None")

def get_chart(symbol, timeframe, bars=1000):
    time_from = datetime.now()

    rates = mt5.copy_rates_from(symbol, timeframe, time_from, bars)
   
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df



crash1000 = "Crash 1000 Index"
for i in range(0, 10):

    open_trade(crash1000, 50.00, mt5.ORDER_TYPE_BUY)

    open_trade(crash1000, 50.00, mt5.ORDER_TYPE_BUY, 4500.00, 5100.00)
