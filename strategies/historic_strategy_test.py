import sys
import math
import statistics
import time as t
from datetime import datetime as dt, timedelta
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from indicators.cci_indicator import cci_check
from indicators.macd_indicator import macd_check
from indicators.rsi_indicator import rsi_check
from indicators.stoch_indicator import stoch_check
from indicators.vwap_indicator import vwap_check
from helpers import is_market_open, portfolio_input
from yahoo_finance_stocks import get_10_best_active_stocks
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

def main(args, portfolio_amount):
    # Retrieve API Key
    from secrets import ALPHA_VANTAGE_TOKEN
    from alpha_vantage.timeseries import TimeSeries
    from alpha_vantage.techindicators import TechIndicators
    ts = TimeSeries(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')
    ti = TechIndicators(key=ALPHA_VANTAGE_TOKEN, output_format='pandas')

    # If no symbols were passed in
    # Retrieve top volatile stocks from Yahoo Finance
    try:
        symbols = args[1].split(',')
    except IndexError:
        print('No symbol provided. Retrieving top 10 from Yahoo Finance...')
        symbols = get_10_best_active_stocks()
    print(symbols)
    confirmation = input('Are these the stocks you want to test? (Y/n): ')
    if confirmation.lower() != 'y':
        return

    interval = '1min'
    # Default to yesterday because we don't have realtime data
    # trading_day = dt.strftime((dt.now() - timedelta(1)), '%Y-%m-%d')
    current_time = dt.now().time()
    trading_day = dt.strftime(dt.now() if current_time.hour > 20 else dt.now() - timedelta(1), '%Y-%m-%d')
    results = {}
    holdings = {}

    portfolio = float(portfolio_amount)
    position_size = portfolio / len(symbols)
    print(f"Testing a portfolio of $%.2f across {len(symbols)} stock{'s' if len(symbols) > 1 else ''}" % portfolio)
    
    for symbol in symbols:
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
        intraday = intraday[intraday.index.to_series().between(f'{trading_day} 09:00:00', f'{trading_day} 18:00:00')]

        # Get MACD data
        macd_data, _ = ti.get_macd(symbol=symbol, interval=interval)
        macd_data = macd_data.sort_index()

        # Get RSI data
        rsi_data, _ = ti.get_rsi(symbol=symbol, interval=interval)
        rsi_data = rsi_data.sort_index()
        
        # Get CCI data
        cci_data, _ = ti.get_cci(symbol=symbol, interval=interval)
        cci_data = cci_data.sort_index()

        # Get OBV data
        obv_date, _ = ti.get_obv(symbol=symbol, interval=interval)
        obv_date = obv_date.sort_index()

        # Get VWAP data
        # vwap_data, _ = ti.get_vwap(symbol=symbol, interval=interval)
        # vwap_data = vwap_data.sort_index()

        # Get the Stochastic Oscillator data
        # stoch_data, _ = ti.get_stoch(symbol=symbol, interval=interval)
        # stoch_data = stoch_data.sort_index()

        stock_data = pd.concat([intraday, macd_data, rsi_data, cci_data, obv_date], axis=1, join="inner")
        # print(stock_data)

        Transactions = {}
        transaction_holder = {}
        position = None
        stop_loss_price = None
        initial_loss_percentage = 0.98
        trailing_loss_percentage = 0.96

        Transactions[trading_day] = []
        trade_triggers = {}
        for i in range(0, len(stock_data.index)):
            datetime = stock_data.index[i]
            interval_date, interval_time = str(datetime).split(' ')
            trade_triggers[interval_time] = { 'Buy': {}, 'Sell': {} }

            if is_market_open(stock_data.index[i]):
                times = [
                    interval_time,
                    str(stock_data.index[i-1]).split(' ')[1],
                    str(stock_data.index[i-2]).split(' ')[1],
                ]
                close_price = stock_data['4. close'][datetime]

                macd = stock_data['MACD'][datetime]
                prev_macd = stock_data['MACD'][stock_data.index[i-1]]
                signal = stock_data['MACD_Signal'][datetime]
                prev_signal = stock_data['MACD_Signal'][stock_data.index[i-1]]
                macd_action = macd_check(macd, prev_macd, signal, prev_signal, position)
                if macd_action:
                    trade_triggers[interval_time][macd_action]['MACD'] = { 'MACD': macd, 'MACD Signal': signal }

                rsi = stock_data['RSI'][datetime]
                prev_rsi = stock_data['RSI'][stock_data.index[i-1]]
                rsi_action = rsi_check(rsi, prev_rsi, position)
                if rsi_action:
                    trade_triggers[interval_time][rsi_action]['RSI'] = rsi

                cci = stock_data['CCI'][datetime]
                prev_cci = stock_data['CCI'][stock_data.index[i-1]]
                cci_action = cci_check(cci, prev_cci, position)
                if cci_action:
                    trade_triggers[interval_time][cci_action]['CCI'] = { 'CCI': cci, 'CCI_PREV': prev_cci }

                vwap = stock_data['VWAP'][datetime]
                vwap_action = vwap_check(vwap, close_price, position)
                if vwap_action:
                    trade_triggers[interval_time][vwap_action]['VWAP'] = { 'VWAP': vwap }
                
                # stoch = stock_data['SlowK'][datetime]
                # if stoch_check(stoch, position):
                    # trade_triggers[interval_time].append({ 'STOCH': stoch })
                
                total_buy_triggers = {}
                total_sell_triggers = {}
                print(f'Gathering triggers from {times[0]}, {times[1]}, and {times[2]}')
                for time in times:
                    for indicator in trade_triggers[time]['Buy'].keys():
                        total_buy_triggers[indicator] = trade_triggers[time]['Buy'][indicator]
                    for indicator in trade_triggers[time]['Sell'].keys():
                        total_sell_triggers[indicator] = trade_triggers[time]['Sell'][indicator]

                if position:
                    print(f'{interval_time} Sell Triggers:', trade_triggers[interval_time]['Sell'])
                else:
                    print(f'{interval_time} Buy Triggers:', trade_triggers[interval_time]['Buy'])

                # If at least 2 indicators from the last 3 intervals tell it to buy
                if not position and len(total_buy_triggers.keys()) >= 2:
                    shares = math.floor(position_size / close_price)
                    transaction_holder = { 'Buy': close_price, 'Buy Time': interval_time, 'Quantity': shares }
                    position = close_price
                    stop_loss_price = close_price * initial_loss_percentage
                    print(f'Buy triggered by: {total_buy_triggers}')
                    print(f'Buy {shares} shares on {interval_date} at {interval_time}: $%.2f' % close_price)
                    print('Set stop loss to $%.2f' % stop_loss_price)

                # If at least 2 indicators from the last 3 intervals tell it to sell
                elif position and len(total_sell_triggers.keys()) >= 2:
                    transaction_holder['Sell'] = close_price
                    transaction_holder['Sell Time'] = interval_time
                    Transactions[interval_date].append(transaction_holder)
                    print(f'Sell triggered by: {total_sell_triggers}')
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

main(sys.argv, portfolio_input())
