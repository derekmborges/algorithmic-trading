import websocket
import json
import math
import _thread
from google.cloud import storage
from alpaca_trade_api import REST
from datetime import datetime
import numpy as np
import pandas as pd
pd.set_option('mode.chained_assignment', None)
import btalib

# Get Alpaca API key and secret
storage_client = storage.Client.from_service_account_json('./splendid-cirrus-302501-7e3faab608d2.json')
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = REST(api_key, secret_key, base_url, 'v2')

# Load the selected stocks from the watchlist
symbols = []
watchlist = api.get_watchlist_by_name('Primary Watchlist')
for asset in watchlist.assets:
    symbols.append(asset['symbol'])

# Get the current cash amount
portfolio = api.get_account()
cash = float(portfolio.cash)
individual_cash = cash / len(symbols)
positions = api.list_positions()

print('TRADING DETAILS')
print('=======================================')
print('Today\'s stocks: {}'.format(', '.join(symbols)))
print('Available cash: $%.2f' % cash)
if positions:
    print('Current positions:')
    for position in positions:
        print(f'> {position.symbol}: ${position.market_value}')
print('=======================================')
print()

# Get 5Min candlestick data and calculate OBV and OBV_EMA
print('Initializing bot...')
bars_group = api.get_barset(','.join(symbols), '5Min', limit=1000).df
symbol_bars = {}
for symbol in symbols:
    df = bars_group[symbol]
    obv = btalib.obv(df).df
    df['obv'] = obv['obv']
    df['obv_ema'] = df['obv'].ewm(span=20).mean()
    # df['time'] = df.index.values
    symbol_bars[symbol] = df
    latest_dt = df.index[len(df.index) - 1]
    print(f'Latest 5Min bar for {symbol}: {latest_dt}')

def on_open(ws):
    print('Authenticating with API...')
    auth_data = {
        "action": "authenticate",
        "data": {
            "key_id": api_key,
            "secret_key": secret_key
        }
    }
    ws.send(json.dumps(auth_data))
    streams = ["AM.{}".format(symbol) for symbol in symbols]
    listen_data = {
        "action": "listen",
        "data": {
            "streams": streams
        }
    }
    ws.send(json.dumps(listen_data))

def process_bar(data):
    symbol = data['T']
    end_dt = datetime.fromtimestamp(data['e']/1000.0)

    # Only care about 5min bars
    if end_dt.minute % 5 == 0:    
        # Display bar info
        open, high, low, close, volume = data['o'], data['h'], data['l'], data['c'], data['v']
        print('{0}: {1} - close=${2} , volume={3}'.format(end_dt, symbol, ('%.2f' % close), volume))

        # Load the symbol's past 5min bars
        df = symbol_bars[symbol]

        try:
            # Add bar to DataFrame
            row = pd.Series({
                'open': open,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
                'obv': np.nan,
                'obv_ema': np.nan
            }, name=end_dt)
            df = df.append(row)

            # Recalculate OBV
            obv = btalib.obv(df).df
            df['obv'] = obv['obv']
            df['obv_ema'] = df['obv'].ewm(span=20).mean()

            # Store updated DataFrame
            symbol_bars[symbol] = df
        except Exception as ex:
            print('Error:', ex)
        
        process_trade(symbol)
        print('\n')

def process_trade(symbol):
    # Update available cash
    cash = float(api.get_account().cash)

    # Retrieve a position if the bot is holding
    try:
        position = api.get_position(symbol)
    except:
        position = None

    try:
        df = symbol_bars[symbol]
        last = len(df.index) - 1
        obv = df['obv'][last]
        obv_ema = df['obv_ema'][last]
        close_price = df['close'][last]
    
        # Look to buy
        if not position and close_price > 0:
            print(f'Not holding {symbol}')
            print(f'{obv} > {obv_ema} = {obv > obv_ema}')
            if obv > obv_ema:
                # Check if there's already an order
                current_order = None
                orders = api.list_orders()
                if orders:
                    for order in orders:
                        if order.symbol == symbol and order.side == 'buy':
                            current_order = order
                
                qty = math.floor(individual_cash / close_price)
                # If there's not already an order out there and if there's cash available
                if not current_order and individual_cash > 0:
                    api.submit_order(
                        symbol=symbol,
                        side='buy',
                        type='market',
                        qty=str(qty),
                        time_in_force='day',
                        order_class='simple',
                        # take_profit=dict(
                        #     limit_price=str(close_price * 1.5)
                        # ),
                        # stop_loss=dict(
                        #     stop_price=str(stop_loss_price),
                        #     limit_price=str(stop_loss_price),
                        # )
                    )
                    print(f'Submitted BUY order for {qty} shares of {symbol}')
                elif current_order:
                    api.replace_order(order.id, qty=str(qty))
                    print(f'Replaced BUY order for {qty} shares of {symbol}')
                else:
                    print('Not enough cash to buy right now...')

        elif close_price > 0:
            current_price = float(position.current_price)
            buy_price = float(position.avg_entry_price)
            stop_loss = float(position.avg_entry_price) * 0.98
            print(f'Currently holding {position.symbol}')
            print(f'{obv} < {obv_ema} = {obv < obv_ema}')

            # Cancel any open sell orders
            orders = api.list_orders()
            if orders:
                for order in orders:
                    if order.symbol == symbol and order.side == 'sell':
                        api.cancel_order(order.id)

            # Look to sell
            if obv < obv_ema:
                api.submit_order(
                    symbol=symbol,
                    side='sell',
                    type='market',
                    qty=position.qty,
                    time_in_force='day'
                )
                print(f'Submitted SELL order for {position.qty} shares of {symbol}')

            # Sell if its holding and the price has dropped to the stop loss
            elif current_price <= stop_loss:
                api.submit_order(
                    symbol=symbol,
                    side='sell',
                    type='market',
                    qty=position.qty,
                    time_in_force='day'
                )
                print(f'Submitted STOP LOSS SELL order for {position.qty} shares of {symbol}')

            # Update trailing stop loss if price is rising
            elif current_price > buy_price and (current_price * 0.96) > stop_loss:
                pass
        # If the market's about to close, sell remaining positions
        # TODO POSSIBLY

    except Exception as ex:
        print('Error:', ex)


def on_message(ws, message):
    response = dict(json.loads(message))

    if response['stream'] == 'authorization':
        print('Socket', response['data']['status'])

    elif response['stream'] == 'listening':
        print('Listening to 5-minute bar streams...')
        print('----------------------------------')

    elif 'AM' in response['stream']:
        data = response['data']
        _thread.start_new_thread(process_bar(data))

    else:
        print('Unknown response:', response)

socket_url = 'wss://data.alpaca.markets/stream'
ws = websocket.WebSocketApp(socket_url, on_open=on_open, on_message=on_message)
ws.run_forever()
