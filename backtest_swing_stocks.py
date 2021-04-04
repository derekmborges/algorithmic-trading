import math
import statistics
from typing import Text
from helpers import portfolio_input
import sys
import time
from pytz import timezone
from datetime import datetime
from google.cloud import storage
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from select_historic_swing_stocks import select_swing_stocks
import discord_webhook

# Get Alpaca API key and secret
storage_client = storage.Client()
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = REST(api_key, secret_key, base_url, 'v2')

nyc = timezone('America/New_York')

def get_open_price(date: datetime, symbol: Text) -> float:
    today = datetime.isoformat(pd.Timestamp(date))
    bar = api.get_barset(symbol, '1D', start=today, end=today, limit=1).df
    return bar[symbol]['open'][bar.index.max()]

def buy_stock(date: datetime, symbol: Text, qty: int):
    buy_price = get_open_price(date, symbol)
    position_data[symbol] = {
        'qty': str(qty),
        'avg_entry_price': str(buy_price),
        'current_buy_price': str(buy_price),
        'market_value': str(round(buy_price * qty, 2))
    }

def sell_stock(date: datetime, symbol: Text) -> float:
    sell_price = get_open_price(date, symbol)
    entry_price = float(position_data[symbol]['avg_entry_price'])
    del position_data[symbol]
    assert symbol not in position_data.keys()
    return (sell_price - entry_price) / entry_price * 100


# Get start and end dates to test
try:
    start_str = sys.argv[1]
    start_date = datetime.strptime(start_str, '%Y-%m-%d')
    end_str = sys.argv[2]
    end_date = datetime.strptime(end_str, '%Y-%m-%d')
except IndexError:
    start_date, end_date = None
    print('Must provide start and end date in YYYY-MM-DD format')

if start_date and end_date:

    # Get portfolio amount from user
    # portfolio_amount = portfolio_input()
    portfolio_amount = float(50000)

    # Need a data structure to mimick the Broker's positions
    # Start with no positions
    position_data = {}

    # Also need to store the results for each day
    day_results = {}

    # Create a list of dates in between start and end (inclusive)
    dates = pd.date_range(start=start_date, end=end_date, freq='D', tz=nyc)

    # Trade each day
    for date in dates:
        print(f'------------------ {date.strftime("%Y-%m-%d")} ------------------')

        # Must update position prices before going into the day
        # Something that Alpaca handles for you
        if len(position_data.keys()) > 0:
            for symbol in position_data.keys():
                current_open_price = get_open_price(date, symbol)
                position_data[symbol]['current_price'] = str(current_open_price)
                position_data[symbol]['market_value'] = str(round(
                    current_open_price * int(position_data[symbol]['qty']),
                    ndigits=2
                ))

        # Call the stock selector but passing in a specific date
        buy_df, sell_df, hold_df = select_swing_stocks(
            date=date,
            position_data=position_data,
            portfolio_amount=portfolio_amount
        )

        print(f'Buying: {len(buy_df)}')
        print(f'Selling: {len(sell_df)}')
        print(f'Holding: {len(hold_df)}')
        
        # Mock Sell
        if not sell_df.empty:
            sell_df = sell_df.set_index('symbol', drop=True)
            print('\nSELL:')
            for symbol in sell_df.index:
                # latest_price = sell_df['latest_price'][symbol]
                gain = sell_stock(date, symbol)
                print('{}: {}{}%'.format(
                    symbol,
                    '+' if gain > 0 else '',
                    '%.1f' % gain
                ))
                if date in day_results.keys():
                    day_results[date].append(date)
                else:
                    day_results[date] = [ gain ]

        # Mock Buy
        if not buy_df.empty:
            buy_df = buy_df.set_index('symbol', drop=True)
            print('\nBUY:')
            for symbol in buy_df.index:
                qty = buy_df['qty'][symbol]
                price = buy_df['close'][symbol]
                buy_stock(date, symbol, qty)
                print(f'{symbol}: {qty}')
        
        print()
    
    print('\n------------------ RESULTS ------------------')
    for date in dates:
        date_str = date.strftime('%Y-%m-%d')
        print(date_str)
        if date in day_results.keys():
            gains: list = day_results[date]
            print('Best:  {}%'.format('%.2f' % (max(gains))))
            print('Worst: {}%'.format('%.2f' % (min(gains))))
            print('Avg:   {}%'.format('%.2f' % (statistics.mean(gains))))
            print('Total: {}%'.format('%.2f' % (sum(gains))))
        else:
            print('None')
