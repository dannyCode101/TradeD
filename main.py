import MetaTrader5 as mt5

mt5.initialize()

account = 40610362
password = "MyDeriv123!"
server = "Deriv-Demo"

if not mt5.login(account,password, server):
    print("NOT WORKING")
    mt5.shutdown()
    exit()

info = mt5.account_info()


symbols = mt5.symbols_get()

crash = "Crash 1000 Index"

lot = 0.2


def open_trade(symbol, lot, order_type, sl_value, tp_value, deviation=20):
    price = mt5.symbol_info_tick(symbol)

    if order_type == mt5.ORDER_TYPE_BUY:
        order_price = price.ask
        sl = sl_value
        tp = tp_value
        print("buy")
    elif order_type == mt5.ORDER_TYPE_SELL:
        order_price = price.bid
        sl = sl_value
        tp = tp_value
        print("sell")

    print("order")
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": order_price,
        "sl": sl,
        "tp": tp,
        "deviation": deviation,
        "magic": 234000,
        "comment": "python script open",
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request)
    print(result)
    if result is None:
        print("order_send() failed, result is None")



open_trade(crash,0.2,mt5.ORDER_TYPE_BUY,4500.00,5100.00)
open_trade(crash,1.0,mt5.ORDER_TYPE_SELL, 5100.00,4500.00)