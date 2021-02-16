import requests
import statistics
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from indicators.cci_indicator import cci_check
from indicators.macd_indicator import macd_check
from indicators.rsi_indicator import rsi_check
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

# For now, only work with one stock
symbol = 'AAPL'
time_ranges = [
    '1d',
    '5dm',
]
results_columns = ['Time Range', 'Net Gain', 'Percentage Gain']
results = pd.DataFrame(columns = results_columns)

# Retrieve API Key
from secrets import IEX_CLOUD_API_TOKEN
base_api_url = 'https://www.alphavantage.co/query'

# Create DataFrame
columns = [
    'Date',
    'Close',
    'MACD',
    'Signal',
    'CCI',
    'CCI Boundary',
    'RSI',
    'Buy Signal',
    'Sell Signal'
]

for time_range in time_ranges:
    print(f'Trading across last {time_range}...')
    df = pd.DataFrame(columns = columns)
    stock_data = {}

    

    # Retrieve stock data
    indicators = ['macd', 'cci', 'rsi']

    for indicator in indicators:
        api_url = f"{base_api_url}/stock/{symbol}/indicator/{indicator}?range={time_range}&token={IEX_CLOUD_API_TOKEN}"
        data = requests.get(api_url).json()
        if not 'chart' in stock_data.keys():
            stock_data['chart'] = data['chart']
        stock_data[indicator] = data['indicator']

    for period in range(0, len(stock_data['chart'])):
        df = df.append(
            pd.Series([
                stock_data['chart'][period]['date'],
                stock_data['chart'][period]['close'],
                stock_data['macd'][0][period],
                stock_data['macd'][1][period],
                stock_data['cci'][0][period],
                0.0,
                stock_data['rsi'][0][period],
                np.NaN,
                np.NaN
            ],
            index=columns),
            ignore_index=True
        )

    # Simulate buying and selling across the historic timeline
    Buy = []
    Sell = []
    position = None
    stop_loss_price = None

    for i in range(0, len(df)):
        close_price = df['Close'][i]
        indicators_triggered = []

        cci = df['CCI'][i]
        prev_cci = df['CCI'][i-1] if i > 0 else None
        if cci_check(cci, prev_cci):
            indicators_triggered.append('cci')
        
        macd = df['MACD'][i]
        signal = df['Signal'][i]
        if macd_check(macd, signal, position):
            indicators_triggered.append('macd')

        rsi = df['RSI'][i]
        prev_rsi = df['RSI'][i-1] if i > 0 else None
        if rsi_check(rsi, prev_rsi, position):
            indicators_triggered.append('rsi')

        if len(indicators_triggered) >= 1:
            if position:
                # print("Selling shares at $%.2f\n" % (close_price))
                Buy.append(np.NaN)
                Sell.append(close_price)
                position = None
            else:
                # print("Buying shares at $%.2f" % (close_price))
                Buy.append(close_price)
                Sell.append(np.NaN)
                position = close_price
                stop_loss_price = close_price * 0.98
        elif position and close_price <= stop_loss_price:
            # print("Triggering stop loss sell at $%.2f\n" % (close_price))
            Buy.append(np.NaN)
            Sell.append(close_price)
            position = None
        else:
            Buy.append(np.NaN)
            Sell.append(np.NaN)

            # Possibly update trailing stop loss
            if position and close_price > position:
                position = close_price
                stop_loss_price = position * 0.98

    # Create buy and sell columns
    df['Buy Signal Price'] = Buy
    df['Sell Signal Price'] = Sell

    # Determine Profits/Losses for each time range
    net_profits = []
    percentage_deltas = []
    buy_price_holder = None
    for day in range(0, len(df)):
        # If there was a buy, store's its price
        if df['Buy Signal Price'][day] > 0:
            buy_price_holder = df['Buy Signal Price'][day]
        # If there's a sell after a buy
        elif buy_price_holder and df['Sell Signal Price'][day] > 0:
            # Calculate net profit
            net_profits.append(df['Sell Signal Price'][day] - buy_price_holder)
            # Calculate percentage gained/lost
            percentage_deltas.append(((df['Sell Signal Price'][day] / buy_price_holder) - 1) * 100 )

            # Reset buy price holder
            buy_price_holder = None

    # Build results for each time range
    if net_profits and percentage_deltas:
        print(f'Total trades: {len(net_profits)}')
        results = results.append(
            pd.Series([
                time_range,
                round(sum(net_profits), 2),
                round(statistics.mean(percentage_deltas), 2)
            ], index=results_columns),
            ignore_index=True
        )
    else:
        results = results.append(
            pd.Series([
                time_range,
                0,
                0
            ], index=results_columns),
            ignore_index=True
        )
        # results[time_range] = {
        #     'Net Gain': round(sum(net_profits), 2),
        #     'Percentage Gain': round(statistics.mean(percentage_deltas), 2)
        # }

        # Plot Buy and Sell Signal Prices
        # plot.figure(figsize=(15, 6))
        # plot.scatter(df.index, df['Buy Signal Price'], color = 'green', label = 'Buy', marker = '^', alpha = 1)
        # plot.scatter(df.index, df['Sell Signal Price'], color = 'red', label = 'Sell', marker = 'v', alpha = 1)
        # plot.plot(df['Close'], label = 'Close Price', alpha = 0.35)
        # plot.title('Close Price Buy & Sell Signals')
        # plot.xlabel('Date')
        # plot.xticks(rotation = 45)
        # plot.ylabel('Close Price USD ($)')
        # plot.legend(loc = 'upper left')
        # plot.show()

    
print('-----------RESULTS-----------')
print(f'Symbol: {symbol}\n')
for i in results.index:
    print(f"Time Range: {results['Time Range'][i]}")
    print('---------------------')
    if results['Net Gain'][i] != np.NaN:
        print(f"Net Gain: ${results['Net Gain'][i]}")
        print(f"Percentage Gain: {results['Percentage Gain'][i]}%")
    else:
        print(f'No trades were executed.')
    print('\n')

# Determine best and worst result
# best = None
# worst = None
# for time_range in time_ranges:
#     if results[time_range]:
#         if best is None or worst is None:
#             best = ( time_range, results[time_range]['Percentage Gain'] )
#             worst = ( time_range, results[time_range]['Percentage Gain'] )
#         else:
#             if results[time_range]['Percentage Gain'] > best[1]:
#                 best = ( time_range, results[time_range]['Percentage Gain'] )
#             if results[time_range]['Percentage Gain'] < worst[1]:
#                 worst = ( time_range, results[time_range]['Percentage Gain'] )
# print(f"Best: {best[0]} = {best[1]}%")
# print(f"Worst: {worst[0]} = {worst[1]}%")

plot.figure(figsize=(15, 6))
plot.bar(results['Time Range'], results['Net Gain'])
plot.title('Results')
plot.xlabel('Time Ranges')
plot.ylabel('Net Gain/Loss Per Share ($)')
plot.show()
