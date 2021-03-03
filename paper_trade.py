import secrets
import websocket
import json
import pytz
import math
from google.cloud import bigquery
from alpaca_trade_api import REST
from datetime import datetime
import numpy as np
import pandas as pd
pd.set_option('mode.chained_assignment', None)

base_url = 'https://paper-api.alpaca.markets'
api = REST(secrets.ALPACA_API_KEY, secrets.ALPACA_SECRET_KEY, base_url, 'v2')

# Load the selected stocks from BigQuery
client = bigquery.Client()
sql_symbols = """
    SELECT symbol
    FROM `splendid-cirrus-302501.stock_data.selected_stocks`
"""
symbols = client.query(sql_symbols).to_dataframe()['symbol'].values

# Get the current portfolio amount
portfolio = api.get_account()
cash = float(portfolio.portfolio_value)
individual_cash = cash / len(symbols)

print('TRADING DETAILS')
print('====================')
print('Today\'stocks: {}'.format(', '.join(symbols)))
print('Today\'s portfolio: $%.2f' % cash)
print('====================')
print()

# Get 5Min candlestick data and calculate OBV and OBV_EMA
print('Initializing bot...')
bars_group = api.get_barset(','.join(symbols), '5Min', limit=125).df
symbol_bars = {}
for symbol in symbols:
    obv = [0]
    df = bars_group[symbol]
    for i in range(1, len(df.index)):
        if df['close'][i] > df['close'][i-1]:
            obv.append(obv[-1] + df['volume'][i])
        elif df['close'][i] < df['close'][i-1]:
            obv.append(obv[-1] - df['volume'][i])
        else:
            obv.append(obv[-1])
    
    df['obv'] = obv
    df['obv_ema'] = df['obv'].ewm(span=20).mean()
    symbol_bars[symbol] = df

def on_open(ws):
    print('Authenticating with API...')
    auth_data = {
        "action": "authenticate",
        "data": {
            "key_id": secrets.ALPACA_API_KEY,
            "secret_key": secrets.ALPACA_SECRET_KEY
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

def process_bar(symbol, data):
    end_dt = datetime.fromtimestamp(data['e']).astimezone(pytz.timezone('US/Eastern'))
    # Only care about 5min bars
    if end_dt.minute % 5 == 0:    
        # Display bar info
        open, high, low, close, volume = data['o'], data['h'], data['l'], data['c'], data['v']
        print('{0}: {1} - close=${2} , volume={3}'.format(end_dt, symbol, ('%.2f' % close), volume))

        # Load the symbol's past 5min bars
        df = pd.DataFrame(symbol_bars[symbol])

        # Set OBV equal to previous 5min's value
        previous_i = len(df.index) - 1
        obv = df['obv'][previous_i]

        # Calculate new OBV
        if close > df['close'][previous_i]:
            obv += volume
        elif close < df['close'][previous_i]:
            obv -= volume

        # Add bar to DataFrame
        df = df.append({
            'time': end_dt,
            'open': open,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
            'obv': obv,
            'obv_ema': np.nan
        })
        df['obv_ema'] = df['obv'].ewm(span=20).mean()
        
        # Store updated DataFrame
        symbol_bars[symbol] = df

symbol_positions = {}
for symbol in symbols:
    symbol_positions[symbol] = {}
def process_trade(symbol):
    # Retrieve a position if the bot is holding
    try:
        position = api.get_position(symbol)
    except:
        position = None

    df = symbol_bars[symbol]
    last = len(df.index) - 1
    obv = df['obv'][last]
    obv_ema = df['obv_ema'][last]
    current_price = position.current_price if position else df['close'][last]
    buy_price = symbol_positions[symbol]['buy_price'] if position else None
    stop_loss = symbol_positions[symbol]['stop_loss'] if position else None

    if not position and obv > obv_ema:
        qty = math.floor(individual_cash / current_price)
        stop_loss_price = current_price * 0.98
        order = api.submit_order(
            symbol=symbol,
            side='buy',
            type='market',
            qty=str(qty),
            time_in_force='day',
            order_class='bracket',
            stop_loss=dict(
                stop_price=str(stop_loss_price),
                limit_price=str(stop_loss_price),
            )
        )
        symbol_positions[symbol]['order'] = order
        symbol_positions[symbol]['buy_price'] = current_price
        symbol_positions[symbol]['stop_loss'] = stop_loss_price
        print(f'Submitted BUY order for {qty} shares of {symbol}')
    
    elif position and obv < obv_ema:
        order = api.submit_order(
            symbol=symbol,
            side='sell',
            type='market',
            qty=position.qty,
            time_in_force='day'
        )
        symbol_positions[symbol]['order'] = order
        print(f'Submitted SELL order for {position.qty} shares of {symbol}')

    # Sell if its holding and the price has dropped to our stop loss
    elif position and current_price <= stop_loss:
        order = api.submit_order(
            symbol=symbol,
            side='sell',
            type='market',
            qty=position.qty,
            time_in_force='day'
        )
        symbol_positions[symbol]['order'] = order
        print(f'Submitted STOP LOSS SELL order for {position.qty} shares of {symbol}')

    # Update trailing stop loss if price is rising
    elif position and current_price > buy_price and (current_price * 0.96) > stop_loss:
        symbol_positions[symbol]['stop_loss'] = current_price * 0.96

    # If the market's about to close, sell remaining positions
    # TODO POSSIBLY


def on_message(ws, message):
    response = dict(json.loads(message))

    if response['stream'] == 'authorization':
        print('Socket', response['data']['status'])

    elif response['stream'] == 'listening':
        print('Listening to minute bar streams...')
        print('----------------------------------')

    elif 'AM' in response['stream']:
        print(response['stream']) # Debug
        symbol = response['stream'].split('.')[1]
        process_bar(symbol=symbol, data=response['data'])
        process_trade(symbol=symbol)

    else:
        print('Unknown response:', response)
        

def on_error(ws, error):
    print('error:')
    print(error)

socket_url = 'wss://data.alpaca.markets/stream'
ws = websocket.WebSocketApp(socket_url, on_open=on_open, on_message=on_message)
ws.run_forever()
