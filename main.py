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

    if (sl_value is not None):
        request["sl"] = sl_value
    if (tp_value is not None):
        request["tp"] = tp_value

    result = mt5.order_send(request)
    print(result)
    if result is None:
        print("order_send() failed, result is None")

def get_chart(symbol, timeframe, bars=1000):
    try:
        time_from = datetime.now()

        rates = mt5.copy_rates_from(symbol, timeframe, time_from, bars)
    
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    except:
        return ""

def save_chart_date(symbol,arr, bars = 100):
    names = []
    try:
        for a in arr:
            timeframe = a[0]
            name = symbol + " " + a[1] + ".csv"
            value = get_chart(symbol=symbol, timeframe=timeframe, bars=bars)
            value.to_csv(name,index=False)
            names.append(name)
        return names
    except:
        print("No Valid Input !")
        return

def view_open_trades():
    positions = mt5.positions_get()
    print(positions)
    if (positions is None) or (positions == ()):
        print("No open positions")
        return
    positions_df = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    print(positions_df)

def close_trade(ticket):
    positions = mt5.positions_get()

    position = next((p for p in positions if p.ticket == ticket), None)

    symbol = position.symbol
    volume = position.volume
    order_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = mt5.symbol_info_tick(symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask

    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "position": ticket,
        "price": price,
        "deviation": 20,
        "magic": 234000,
        "comment": "python script close",
        "type_time": mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(close_request)
    print(f"Close result for ticket {ticket}: {result}")

def app():
    while True:
        print("\nOptions:")
        print("1: Open Trade")
        print("2: View Open Trades")
        print("3: Close Trade")
        print("4: Send to AI Trader")
        print("5: Exit")

        choice = input("Select an option : ").strip()

        if choice == "1":
            try:
                symbol = input("Enter symbol : ").strip()
                lot = float(input("Enter Lot Size : ").strip())
                type = input("Buy/Sell: ").strip()
                sl_input = input("Enter stoploss (if any) : ").strip()
                tp_input = input("Enter takeprofit (if any) : ").strip()

                sl = float(sl_input) if sl_input else None
                tp = float(tp_input) if tp_input else None

                try:
                    if type.lower() == "buy":
                        open_trade(symbol, lot, mt5.ORDER_TYPE_BUY,sl_value=sl, tp_value=tp)
                    elif type.lower() == "sell":
                        open_trade(symbol, lot, mt5.ORDER_TYPE_SELL,sl_value=sl, tp_value=tp)
                except:
                    print("\nError opening Trade")
            except:
                print("\nError with that value !")
                
        elif choice == "2":
            view_open_trades()
        elif choice == "3":
            try:
                ticket = int(input("Ticket you want to close: ").strip())
                close_trade(ticket=ticket)
            except:
                print("Invalid Ticket error")
        elif choice == "4":
            symbol = input("Enter symbol : ").strip()
            arr = [ [mt5.TIMEFRAME_H1, "Hour 1"], [mt5.TIMEFRAME_M5, "Min 5"], [mt5.TIMEFRAME_M15, "Min 15"]]
            save_chart_date(symbol=symbol,arr=arr, bars=200)

        elif choice == "5":
            print("Closing App")
            break
        else:
            print("Invalid Choice")

app()
