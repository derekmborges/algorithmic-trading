import time as t
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from indicators.cci_indicator import cci_check
from indicators.macd_indicator import macd_check
from indicators.rsi_indicator import rsi_check
from helpers import is_market_open
from dateutil.parser import parse
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

# Retrieve API Key
from secrets import ALPHA_VANTAGE_TOKEN
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.techindicators import TechIndicators
ts = TimeSeries(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')
ti = TechIndicators(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')

# For now, only work with one stock
symbol = 'KO'
intervals = [
    '1min',
    '5min',
    '15min'
]

for interval in intervals:
    print('===================================')
    print(f'Trading using {interval} intervals')

    # Get json object with the intraday data and another with the call's metadata
    intraday, meta_data = ts.get_intraday(symbol=symbol,interval=interval, outputsize='full')
    intraday = intraday.sort_index()

    # Get MACD data
    macd_data, meta_data = ti.get_macd(symbol=symbol, interval=interval)
    macd_data = macd_data.sort_index()

    # Get RSI data
    rsi_data, meta_data = ti.get_rsi(symbol=symbol, interval=interval)
    rsi_data = rsi_data.sort_index()
    
    # Get CCI data
    cci_data, meta_data = ti.get_cci(symbol=symbol, interval=interval)
    cci_data = cci_data.sort_index()

    stock_data = pd.concat([intraday, macd_data, rsi_data, cci_data], axis=1, join="inner")
    # stock_data = intraday
    # print(stock_data)

    # Buy = []
    # Sell = []
    prev_date = None
    Transactions = {}
    transaction_holder = {}
    position = None
    stop_loss_price = None
    initial_loss_percentage = 0.98
    trailing_loss_percentage = 0.95

    for i in range(0, len(stock_data.index)):
        datetime = stock_data.index[i]
        
        if is_market_open(datetime):
            date, time = str(datetime).split(' ')
            if date != prev_date and date not in Transactions.keys():
                Transactions[date] = []
            close_price = stock_data['4. close'][datetime]
            indicators_triggered = []
 
            macd = stock_data['MACD'][datetime]
            signal = stock_data['MACD_Signal'][datetime]
            if macd_check(macd, signal, position):
                indicators_triggered.append('MACD')

            rsi = stock_data['RSI'][datetime]
            prev_rsi = stock_data['RSI'][stock_data.index[i-1]] if i > 0 else None
            if rsi_check(rsi, prev_rsi, position):
                indicators_triggered.append('RSI')

            cci = stock_data['CCI'][datetime]
            prev_cci = stock_data['CCI'][stock_data.index[i-1]] if i > 0 else None
            if cci_check(cci, prev_cci):
                indicators_triggered.append('CCI')

            if len(indicators_triggered) >= 2:
                if position:
                    transaction_holder['Sell'] = close_price
                    transaction_holder['Sell Time'] = time
                    Transactions[date].append(transaction_holder)
                    transaction_holder = None
                    position = None
                else:
                    transaction_holder = { 'Buy': close_price, 'Buy Time': time }
                    position = close_price
                    stop_loss_price = close_price * initial_loss_percentage
            elif position and close_price <= stop_loss_price:
                transaction_holder['Sell'] = close_price
                transaction_holder['Sell Time'] = time
                Transactions[date].append(transaction_holder)
                transaction_holder = None
                position = None
            else:
                if position and close_price > position:
                    position = close_price
                    stop_loss_price = position * trailing_loss_percentage

            prev_date = date

    # Display all transactions for each day
    print('\n============RESULTS============\n')
    for date in Transactions.keys():
        print(f'{date}\n-------------------------')
        for transaction in Transactions[date]:
            buy = transaction['Buy']
            buy_time = transaction['Buy Time']
            print(f'Buy at {buy_time}: $%.2f' % buy)

            if 'Sell' in transaction.keys():
                sell = transaction['Sell']
                sell_time = transaction['Sell Time']
                net_gain = sell - buy
                print(f'Sell at {sell_time}: $%.2f' % sell)
                print('Gain/Loss: $%.2f' % net_gain)
            print()
        print()

    # Wait for 1 minute to allow for API usage
    t.sleep(60)
