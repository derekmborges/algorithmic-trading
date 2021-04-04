from datetime import datetime, timedelta
from time import time
from typing import Dict
from btalib.indicators.cci import cci
from btalib.indicators.obv import obv
from btalib.indicators.rsi import rsi
from google.cloud import storage
import math
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from scipy.stats import linregress
import detect_pattern as pattern

def chunks(l, n):
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

def select_swing_stocks(date: datetime, position_data: Dict, portfolio_amount: float):
    # Get Alpaca API key and secret
    storage_client = storage.Client()
    bucket = storage_client.get_bucket('derek-algo-trading-bucket')
    blob = bucket.blob('alpaca-api-key.txt')
    api_key = blob.download_as_text()
    blob = bucket.blob('alpaca-secret-key.txt')
    secret_key = blob.download_as_text()
    base_url = 'https://paper-api.alpaca.markets'
    api = REST(api_key, secret_key, base_url, 'v2')

    # Get all stocks
    assets = api.list_assets('active')
    symbols = [asset.symbol for asset in assets if asset.tradable]

    # Display currently held positions
    if position_data:
        print('Current positions:')
    position_symbols = list(position_data.keys())
    for symbol in position_symbols:
        current_price = float(position_data[symbol]['current_price'])
        entry_price = float(position_data[symbol]['avg_entry_price'])
        current_percent = (current_price - entry_price) / entry_price * 100
        print('{}: {}%'.format(symbol, '%.2f' % current_percent))
    print()

    # Get past 1000 days data for all stocks
    data = {}
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    previous_day = datetime.isoformat(pd.Timestamp(date - timedelta(days=1)))
    for symbol_group in symbols_chunked:
        print(f'Retrieving {len(symbol_group)} symbol data')
        data_group = api.get_barset(','.join(symbol_group), '1D', end=previous_day, limit=1000).df
        for symbol in symbol_group:
            data[symbol] = data_group[symbol]
    
    buy_df = pd.DataFrame()
    sell_df = pd.DataFrame()
    hold_df = pd.DataFrame()

    c = 0
    for symbol in data.keys():
        df = pd.DataFrame(data[symbol])
        df = df.loc[df['close'] > 0]
        if symbol not in position_symbols and len(df) == 1000:
            df['symbol'] = symbol
            df['bullish'] = pattern.detect_bullish_patterns(df)
            buy_df = buy_df.append(df.loc[df.index == df.index.max()])
        
        elif symbol in position_symbols:
            print(f'\nCurrently holding {symbol}:')
            df['symbol'] = symbol
            df['qty'] = int(position_data[symbol]['qty'])
            df['market_value'] = float(position_data[symbol]['market_value'])
            
            latest_rsi = rsi(df).df.tail(1)['rsi'][0]
            latest_cci = cci(df).df.tail(1)['cci'][0]
            purchase_price = float(position_data[symbol]['avg_entry_price'])
            latest_price = float(position_data[symbol]['current_price'])
            df['purchase_price'] = purchase_price
            df['latest_price'] = latest_price

            # If it has dropped below the entry price, GET IT OUT
            if latest_price < purchase_price:
                print(f'Price ${latest_price} is below entry ${purchase_price}: SELL')
                sell_df = sell_df.append(df.loc[df.index == df.index.max()])
            # Or if the RSI or CCI are too high, GET IT OUT
            elif latest_rsi >= 70 or latest_cci >= 100:
                print(f'Overbought, RSI={latest_rsi}, CCI={latest_cci}: SELL')
                sell_df = sell_df.append(df.loc[df.index == df.index.max()])

            # If price is at/above entry
            # Check if the swing is still swinging
            elif latest_price >= purchase_price:
                print(f'Price ${latest_price} is at/above entry ${purchase_price}')
                obv_df = obv(df).df
                obv_df['obv_ema'] = obv_df['obv'].ewm(span=20).mean()

                # Is the OBV still above it's EMA
                if obv_df.tail(1)['obv'][0] > obv_df.tail(1)['obv_ema'][0]:
                    print('OBV is still above OBV_EMA')
                    slope = linregress(
                        [0, 1, 2],
                        obv_df.tail(3)['obv'].tolist()
                    ).slope
                    if slope > 0:
                        print(f'OBV is increasing with a slope of {slope}: HOLD')
                        hold_df = hold_df.append(df.loc[df.index == df.index.max()])
                    else:
                        print('OBV is above EMA but not increasing: SELL')
                        sell_df = sell_df.append(df.loc[df.index == df.index.max()])
                else:
                    print('OBV is no longer above EMA: SELL')
                    sell_df = sell_df.append(df.loc[df.index == df.index.max()])

            print()

        c += 1
        if c % 100 == 0:
            print(f'{c}/{len(data.keys())}')
    print(f'{c}/{len(data.keys())}\n')
    
    # END SCREENING SECTION
    
    # Consolidate results
    # print('DECISION:\n')
    hold_stocks = hold_df.loc[hold_df.index == hold_df.index.max()]
    # if not hold_stocks.empty:
        # print(f'Hold {len(hold_stocks)}:\n' + '\n'.join(hold_stocks['symbol'].tolist()) + '\n')
    
    sell_stocks = sell_df.loc[sell_df.index == sell_df.index.max()]
    # if not sell_stocks.empty:
        # print(f'Sell {len(sell_stocks)}:\n' + '\n'.join(sell_stocks['symbol'].tolist()) + '\n')

    portfolio_size = 20
    purchase_size = portfolio_size - len(hold_stocks)

    # If there's room in the portfolio to buy more
    if purchase_size > 0:
        print(f'We can purchase {purchase_size} new stocks today.')
        buy_stocks = buy_df.loc[buy_df.index == buy_df.index.max()]
        buy_stocks = buy_stocks[buy_stocks['bullish'] != '']
        buy_stocks = buy_stocks.sort_values(by='volume', ascending=False).head(purchase_size)
        holding_value = sum(hold_stocks['market_value'].tolist()) if not hold_stocks.empty else 0.0
        available_funds = portfolio_amount - holding_value
        print(f'Available funds to buy: ${available_funds}')
        
        # For now this will create equal-weight positions
        funds_per_stock = available_funds / len(buy_stocks)

        # Calculate quantity to buy for each stock
        buy_qty = []
        symbols = buy_stocks['symbol'].tolist()
        prices = buy_stocks['close'].tolist()
        for i in range(0, len(symbols)):
            price = prices[i]
            qty = math.floor(funds_per_stock / price)
            buy_qty.append(qty)
        
        buy_stocks['qty'] = buy_qty
        buy_stocks['market_value'] = buy_stocks['close'] * buy_stocks['qty']
    
    else:
        print('There is no room to buy.')
        buy_stocks = pd.DataFrame()

    return (buy_stocks, sell_stocks, hold_stocks)
