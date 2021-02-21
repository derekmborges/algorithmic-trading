import sys
import math
import time as t
from datetime import datetime as dt, timedelta
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from helpers import is_market_open, portfolio_input
from stock_finder import get_10_best_active_stocks
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

def obv_strategy(symbols_arg, portfolio_amount):
    # Retrieve API Key
    from secrets import ALPHA_VANTAGE_TOKEN
    from alpha_vantage.timeseries import TimeSeries
    from alpha_vantage.techindicators import TechIndicators
    ts = TimeSeries(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')
    ti = TechIndicators(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')

    # If no symbols were passed in
    # Retrieve top volatile stocks from Yahoo Finance
    try:
        symbols = symbols_arg.split(',')
    except IndexError:
        print('No symbol(s) provided. Retrieving top 10 from Yahoo Finance...')
        symbols = get_10_best_active_stocks()
    print(symbols)
    confirmation = input('Are these the stocks you want to test? (Y/n): ')
    if confirmation.lower() != 'y':
        return

    interval = '1min'
    current_time = dt.now().time()
    trading_day = dt.strftime(dt.now() if current_time.hour > 20 else dt.now() - timedelta(1), '%Y-%m-%d')
    
    results = {}
    holdings = {}

    portfolio = float(portfolio_amount)
    position_size = portfolio / len(symbols)
    print(f"Testing a portfolio of $%.2f across {len(symbols)} stock{'s' if len(symbols) > 1 else ''}" % portfolio)
    
    for symbol in symbols:
        if len(symbols) > 2 and  symbols.index(symbol) % 2 == 0:
            print('Waiting 1 minute to ensure API availability...')
            t.sleep(60)
        print('===================================')
        print(f'Trading {symbol} using {interval} intervals on {trading_day}...\n')

        # Get json object with the intraday data
        try:
            intraday, _ = ts.get_intraday(symbol=symbol,interval=interval, outputsize='full')
        except ValueError:
            print(f'Error: {symbol} not found.\n')
            continue
        intraday = intraday.sort_index()
        print(intraday.index)
        intraday = intraday[intraday.index.to_series().between(f'{trading_day} 00:00:00', f'{trading_day} 23:59:59')]

        # Get OBV data
        obv_data, _ = ti.get_obv(symbol=symbol, interval=interval)
        obv_data = obv_data.sort_index()
        obv_data['OBV_EMA'] = obv_data['OBV'].ewm(span=20).mean()
        
        stock_data = pd.concat([intraday, obv_data], axis=1, join="inner")
        print(stock_data)

        Transactions = {}
        transaction_holder = {}
        position = None
        stop_loss_price = None
        initial_loss_percentage = 0.98
        trailing_loss_percentage = 0.96

        Transactions[trading_day] = []
        for i in range(0, len(stock_data.index)):
            datetime = stock_data.index[i]
            interval_date, interval_time = str(datetime).split(' ')

            if is_market_open(stock_data.index[i]):
                close_price = stock_data['4. close'][datetime]
                obv = stock_data['OBV'][datetime]
                obv_ema = stock_data['OBV_EMA'][datetime]

                if not position and obv > obv_ema:
                    shares = math.floor(position_size / close_price)
                    transaction_holder = { 'Buy': close_price, 'Buy Time': interval_time, 'Quantity': shares }
                    position = close_price
                    stop_loss_price = close_price * initial_loss_percentage
                    print(f'Buy triggered by: {obv} > {obv_ema}')
                    print(f'Buy {shares} shares on {interval_date} at {interval_time}: $%.2f' % close_price)
                    print('Set stop loss to $%.2f' % stop_loss_price)

                # If at least 2 indicators from the last 3 intervals tell it to sell
                elif position and obv < obv_ema:
                    transaction_holder['Sell'] = close_price
                    transaction_holder['Sell Time'] = interval_time
                    Transactions[interval_date].append(transaction_holder)
                    print(f'Sell triggered by: {obv} < {obv_ema}')
                    print(f'Sell on {interval_date} at {interval_time}: $%.2f' % close_price)
                    net_profit = (close_price * transaction_holder['Quantity']) - (transaction_holder['Buy'] * transaction_holder['Quantity'])
                    percentage = ((close_price - transaction_holder['Buy']) / transaction_holder['Buy']) * 100
                    print('Profit/Loss: ${0} ({1}%)\n'.format(('%.2f' % net_profit), ('%.2f' % percentage)))
                    position = None
                    transaction_holder = {}
                
                # Sell if its holding and the price has dropped to our stop loss
                elif position and close_price <= stop_loss_price:
                    transaction_holder['Sell'] = close_price
                    transaction_holder['Sell Time'] = interval_time
                    Transactions[interval_date].append(transaction_holder)
                    print('Sell triggered by stop loss $%.2f' % stop_loss_price)
                    print(f'Sell on {interval_date} at {interval_time}: $%.2f' % close_price)
                    net_profit = (close_price * transaction_holder['Quantity']) - (transaction_holder['Buy'] * transaction_holder['Quantity'])
                    percentage = ((close_price - transaction_holder['Buy']) / transaction_holder['Buy']) * 100
                    print('Profit/Loss: ${0} ({1}%)\n'.format(('%.2f' % net_profit), ('%.2f' % percentage)))
                    position = None
                    transaction_holder = {}

                # Update trailing stop loss if price is rising
                elif position and close_price > position and (close_price * trailing_loss_percentage) > stop_loss_price:
                    position = close_price
                    stop_loss_price = close_price * trailing_loss_percentage
                    print('Updated trailing stop loss to $%.2f' % stop_loss_price)

                # If the market's about to close, sell remaining positions
                if position and interval_time == '15:59:00':
                    transaction_holder['Sell'] = close_price
                    transaction_holder['Sell Time'] = interval_time
                    Transactions[interval_date].append(transaction_holder)
                    print('Sell triggered by market closing')
                    print(f'Sell on {interval_date} at {interval_time}: $%.2f' % close_price)
                    net_profit = (close_price * transaction_holder['Quantity']) - (transaction_holder['Buy'] * transaction_holder['Quantity'])
                    percentage = ((close_price - transaction_holder['Buy']) / transaction_holder['Buy']) * 100
                    print('Profit/Loss: ${0} ({1}%)\n'.format(('%.2f' % net_profit), ('%.2f' % percentage)))
                    position = None
                    transaction_holder = {}
        print()

        # Calculate total results for the symbol on the day
        total_profits = 0
        if len(Transactions[trading_day]) > 0:
            for transaction in Transactions[trading_day]:
                num_shares = transaction['Quantity']
                buy = transaction['Buy']
                if 'Sell' in transaction.keys():
                    sell = transaction['Sell']
                    total_profits += (sell * num_shares) - (buy * num_shares)
                else:
                    holdings[symbol] = transaction
        results[symbol] = total_profits

    # END SYMBOL LOOP

    # Display results
    print(f'\nTOTAL GAINS ON {trading_day}:')
    updated_portfolio = portfolio
    for symbol in results.keys():
        updated_portfolio += results[symbol]
        print(f'{symbol}: $%.2f' % results[symbol])
    print()

    print('On {0}, I turned ${1} into ${2}'.format(trading_day, ('%.2f' % portfolio), ('%.2f' % updated_portfolio)))
    if len(holdings.keys()) > 0:
        print("I'm still holding:")
        for symbol in holdings.keys():
            print(f'{symbol}: $%.2f' % (holdings[symbol]['Quantity'] * holdings[symbol]['Buy']))

    plot.figure(figsize=(15, 6))
    plot.bar(results.keys(), results.values())
    plot.title(f'Results from {trading_day}')
    plot.xlabel('Symbols')
    plot.ylabel('Net Gain/Loss ($)')
    plot.show()

obv_strategy(sys.argv[1], portfolio_input())
