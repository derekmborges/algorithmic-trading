import sys
import time as t
from datetime import datetime as dt, timedelta
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from indicators.cci_indicator import cci_check
from indicators.macd_indicator import macd_check
from indicators.rsi_indicator import rsi_check
from indicators.stoch_indicator import stoch_check
from helpers import is_market_open, portfolio_input
from stock_finder import get_10_best_active_stocks
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

def main(args):
    # Retrieve API Key
    from secrets import ALPHA_VANTAGE_TOKEN
    from alpha_vantage.timeseries import TimeSeries
    from alpha_vantage.techindicators import TechIndicators
    ts = TimeSeries(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')
    ti = TechIndicators(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')

    # If no symbols were passed in
    # Retrieve 
    try:
        symbols = [args[1]]
    except IndexError:
        print('No symbol provided. Retrieving top 10 from Yahoo Finance...')
        symbols = get_10_best_active_stocks()

    print(symbols)
    confirmation = input('Are these the stocks you want to test? (Y/n): ')
    if confirmation.lower() != 'y':
        return

    interval = '1min'
    trading_day = dt.strftime((dt.now() - timedelta(1)), '%Y-%m-%d')
    results = {}

    for symbol in symbols:
        print('Waiting 1 minute to ensure API availability...')
        t.sleep(60)
        print('===================================')
        print(f'Trading {symbol} using {interval} intervals on {trading_day}')

        # Get json object with the intraday data and another with the call's metadata
        try:
            intraday, meta_data = ts.get_intraday(symbol=symbol,interval=interval, outputsize='full')
        except ValueError:
            print(f'Error: {symbol} not found.\n')
            continue
        intraday = intraday.sort_index()
        intraday = intraday[intraday.index.to_series().between(f'{trading_day} 00:00:00', f'{trading_day} 23:59:59')]

        # Get MACD data
        macd_data, meta_data = ti.get_macd(symbol=symbol, interval=interval)
        macd_data = macd_data.sort_index()

        # Get RSI data
        rsi_data, meta_data = ti.get_rsi(symbol=symbol, interval=interval)
        rsi_data = rsi_data.sort_index()
        
        # Get CCI data
        cci_data, meta_data = ti.get_cci(symbol=symbol, interval=interval)
        cci_data = cci_data.sort_index()

        # Get the Stochastic Oscillator data
        stoch_data, meta_data = ti.get_stoch(symbol=symbol, interval=interval)
        stoch_data = stoch_data.sort_index()

        stock_data = pd.concat([intraday, macd_data, rsi_data, cci_data, stoch_data], axis=1, join="inner")
        # print(stock_data)

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
                
                stoch = stock_data['SlowK'][datetime]
                if stoch_check(stoch, position):
                    indicators_triggered.append('STOCH')

                if len(indicators_triggered) >= 2:
                    if position:
                        transaction_holder['Sell'] = close_price
                        transaction_holder['Sell Time'] = time
                        Transactions[date].append(transaction_holder)
                        transaction_holder = {}
                        position = None
                    else:
                        transaction_holder = { 'Buy': close_price, 'Buy Time': time }
                        position = close_price
                        stop_loss_price = close_price * initial_loss_percentage
                elif position and close_price <= stop_loss_price:
                    transaction_holder['Sell'] = close_price
                    transaction_holder['Sell Time'] = time
                    Transactions[date].append(transaction_holder)
                    transaction_holder = {}
                    position = None
                else:
                    if position and close_price > position:
                        position = close_price
                        stop_loss_price = position * trailing_loss_percentage

                prev_date = date

        # Display all transactions for each day
        print('\n============RESULTS============\n')
        total_net_gain = 0
        for date in Transactions.keys():
            print(f'{date}\n-------------------------')
            if len(Transactions[date]) > 0:
                for transaction in Transactions[date]:
                    buy = transaction['Buy']
                    buy_time = transaction['Buy Time']
                    print(f'Buy on {date} at {buy_time}: $%.2f' % buy)

                    if 'Sell' in transaction.keys():
                        sell = transaction['Sell']
                        sell_time = transaction['Sell Time']
                        net_gain = sell - buy
                        total_net_gain += net_gain
                        # percentage = (sell / buy - 1) * 100
                        print(f'Sell on {date} at {sell_time}: $%.2f' % sell)
                        print('Gain/Loss: $%.2f' % net_gain)
                    print()
            else:
                print('No trades occurred')
            print()
        results[symbol] = total_net_gain


    # Display results
    print('\nNET GAIN')
    for symbol in results.keys():
        print(f'{symbol}: $%.2f' % results[symbol])
    plot.figure(figsize=(15, 6))
    plot.bar(results.keys(), results.values())
    plot.title('Results')
    plot.xlabel('Symbols')
    plot.ylabel('Net Gain/Loss Per Share ($)')
    plot.show()


main(sys.argv)
