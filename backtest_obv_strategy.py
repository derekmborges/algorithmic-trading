import sys
import math
import pandas as pd
from pandas.plotting import register_matplotlib_converters
from helpers import is_market_open, portfolio_input
from stock_finder import get_10_best_active_stocks
from stock_data import get_stock_data
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

def backtest_obv_strategy(args):
    # If no symbols were passed in
    # Retrieve top active stocks from Yahoo Finance
    try:
        symbols = args[1].split(',')
    except IndexError:
        print('No symbol(s) provided. Retrieving top 10 from Yahoo Finance...')
        symbols = get_10_best_active_stocks()
    
    portfolio_amount = portfolio_input('Enter cash amount to give each stock: ')

    try:
        splices = args[2].split(',')
    except IndexError:
        splices = ['year1month1']

    interval = '5min'
    results = {}
    
    print('\nBACKTESTING CONFIRMATION:')
    print('----------------------------------')
    print(f'Cash: $%.2f' % float(portfolio_amount))
    print(f"Stocks: {', '.join(symbols)}")
    print(f"Splices: {', '.join(splices)}")
    print(f'Interval: {interval}')
    print('----------------------------------')
    confirmation = input('Continue? (Y/n): ')
    if confirmation.lower() != 'y':
        return

    for splice in splices:
        results[splice] = {}
        total_cash = 0
        for symbol in symbols:
            print('===================================')
            historic_data = get_stock_data(symbol, interval, splice)
            if type(historic_data) is not pd.DataFrame:
                print(f'Error: {symbol} not found.\n')
                continue
            print(f'Trading {symbol} using {interval} intervals...')
            cash = float(portfolio_amount)
            results[splice][symbol] = {}
            Transactions = {}
            transaction_holder = {}
            position = None
            stop_loss_price = None
            initial_loss_percentage = 0.98
            trailing_loss_percentage = 0.96

            for i in range(0, len(historic_data.index)):
                datetime = historic_data.index[i]
                interval_date, interval_time = str(datetime).split(' ')
                if interval_date not in Transactions.keys():
                    Transactions[interval_date] = []

                if is_market_open(historic_data.index[i]):
                    close_price = historic_data['close'][datetime]
                    obv = historic_data['OBV'][datetime]
                    obv_ema = historic_data['OBV_EMA'][datetime]

                    if not position and obv > obv_ema:
                        shares = math.floor(cash / close_price)
                        transaction_holder = { 'Buy': close_price, 'Buy Time': interval_time, 'Quantity': shares }
                        position = close_price
                        stop_loss_price = close_price * initial_loss_percentage
                        # print(f'Buy triggered by: {obv} > {obv_ema}')
                        # print(f'Buy {shares} shares on {interval_date} at {interval_time}: $%.2f' % close_price)
                        # print('Set stop loss to $%.2f' % stop_loss_price)

                    # If at least 2 indicators from the last 3 intervals tell it to sell
                    elif position and obv < obv_ema:
                        transaction_holder['Sell'] = close_price
                        transaction_holder['Sell Time'] = interval_time
                        Transactions[interval_date].append(transaction_holder)
                        # print(f'Sell triggered by: {obv} < {obv_ema}')
                        # print(f'Sell on {interval_date} at {interval_time}: $%.2f' % close_price)
                        net_profit = (close_price * transaction_holder['Quantity']) - (transaction_holder['Buy'] * transaction_holder['Quantity'])
                        percentage = ((close_price - transaction_holder['Buy']) / transaction_holder['Buy']) * 100
                        # print('Profit/Loss: ${0} ({1}%)\n'.format(('%.2f' % net_profit), ('%.2f' % percentage)))
                        position = None
                        transaction_holder = {}
                    
                    # Sell if its holding and the price has dropped to our stop loss
                    elif position and close_price <= stop_loss_price:
                        transaction_holder['Sell'] = close_price
                        transaction_holder['Sell Time'] = interval_time
                        Transactions[interval_date].append(transaction_holder)
                        # print('Sell triggered by stop loss $%.2f' % stop_loss_price)
                        # print(f'SL Sell on {interval_date} at {interval_time}: $%.2f' % close_price)
                        net_profit = (close_price * transaction_holder['Quantity']) - (transaction_holder['Buy'] * transaction_holder['Quantity'])
                        percentage = ((close_price - transaction_holder['Buy']) / transaction_holder['Buy']) * 100
                        # print('Profit/Loss: ${0} ({1}%)\n'.format(('%.2f' % net_profit), ('%.2f' % percentage)))
                        position = None
                        transaction_holder = {}

                    # Update trailing stop loss if price is rising
                    elif position and close_price > position and (close_price * trailing_loss_percentage) > stop_loss_price:
                        position = close_price
                        stop_loss_price = close_price * trailing_loss_percentage
                        # print('Updated trailing stop loss to $%.2f' % stop_loss_price)

                    # If the market's about to close, sell remaining positions
                    if position and interval_time == '15:59:00':
                        transaction_holder['Sell'] = close_price
                        transaction_holder['Sell Time'] = interval_time
                        Transactions[interval_date].append(transaction_holder)
                        # print('Sell triggered by market closing')
                        # print(f'MC Sell on {interval_date} at {interval_time}: $%.2f' % close_price)
                        net_profit = (close_price * transaction_holder['Quantity']) - (transaction_holder['Buy'] * transaction_holder['Quantity'])
                        percentage = ((close_price - transaction_holder['Buy']) / transaction_holder['Buy']) * 100
                        # print('Profit/Loss: ${0} ({1}%)\n'.format(('%.2f' % net_profit), ('%.2f' % percentage)))
                        position = None
                        transaction_holder = {}
                
                # Check for end of day
                elif interval_time == '16:00:00':
                    # Calculate total results for the day
                    day_profits = 0
                    if len(Transactions[interval_date]) > 0:
                        for transaction in Transactions[interval_date]:
                            num_shares = transaction['Quantity']
                            buy = transaction['Buy']
                            sell = transaction['Sell']
                            day_profits += (sell * num_shares) - (buy * num_shares)
                    updated_cash = cash + day_profits
                    profit_percent = ((updated_cash - cash) / cash) * 100
                    results[splice][symbol][interval_date] = profit_percent
                    cash = updated_cash
                    # Display day result
                    print('{0}: {1}% (${2}), balance: ${3}'.format(interval_date, ('%.2f' % profit_percent), ('%.2f' % day_profits), '%.2f' % cash))

            total_cash += cash
            print()
            # plot.figure(figsize=(15, 6))
            # plot.bar(results[splice][symbol].keys(), results[splice][symbol].values())
            # plot.title(f'{symbol} Results')
            # plot.xlabel('Date')
            # plot.xticks(rotation = 60)
            # plot.ylabel('Net % Gain')
            # plot.show()
            # input('hit Enter to test next symbol')

        # END SYMBOLS LOOP

        

        # Calculate total percentages for all days in splice
        cash = float(portfolio_amount)
        splice_percents = []
        for symbol in results[splice].keys():
            splice_percent = 0
            for date in results[splice][symbol].keys():
                splice_percent += results[splice][symbol][date]
            cash *= 1 + (splice_percent / 100)
            splice_percents.append(splice_percent)

        
        # plot.figure(figsize=(15, 6))
        # plot.bar(results[splice].keys(), splice_percents)
        # plot.title(f'Backtesting Results')
        # plot.xlabel('Symbol')
        # plot.xticks(rotation = 45)
        # plot.ylabel('Net % Gain')
        # plot.show()
        print(f'{splice} SUMMARY:')
        original_cash = float(portfolio_amount) * len(results[splice].keys())
        print('${0} --> ${1}'.format('%.2f' % original_cash, '%.2f' % total_cash))
        print('{}% return'.format('%.2f' % ((total_cash - original_cash) / original_cash * 100)))

    # END SPLICES LOOP

    # Get total cash at the end

    # total_percents = []
    # for splice in results.keys():
    #     total_percent = 0
    #     for symbol in results[splice]:
    #         for date in results[splice][symbol].keys():
    #             total_percent += results[splice][symbol][date]
    #     total_percents.append(total_percent)
    # plot.figure(figsize=(15, 6))
    # plot.bar(results.keys(), total_percents)
    # plot.title(f'Backtesting Results')
    # plot.xlabel('Symbol')
    # plot.xticks(rotation = 45)
    # plot.ylabel('Net % Gain')
    # plot.show()
    

backtest_obv_strategy(sys.argv)
