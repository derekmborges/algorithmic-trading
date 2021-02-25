import requests
import statistics
import math
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from helpers import chunks
from indicators.rsi_indicator import rsi_check
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

# For now, only work with one stock
symbol = 'AAPL'
time_range = '6m'

# Retrieve API Key
from secrets import IEX_CLOUD_API_TOKEN

# Create DataFrame
columns = ['Date', 'Close', 'RSI', 'RSI Lower Boundary', 'RSI Upper Boundary', 'Buy Signal', 'Sell Signal']
df = pd.DataFrame(columns=columns)

# Retrieve RSI data
api_url = f"https://sandbox.iexapis.com/stable/stock/{symbol}/indicator/rsi?range={time_range}&token={IEX_CLOUD_API_TOKEN}"
data = requests.get(api_url).json()
period = len(data['chart'])
print(f'Periods in report: {period}')

for period in range(0, period):
    df = df.append(
        pd.Series([
            data['chart'][period]['date'],
            data['chart'][period]['close'],
            data['indicator'][0][period],
            30.0,
            70.0,
            np.NaN,
            np.NaN
        ],
        index=columns),
        ignore_index=True
    )

# Plot RSI data
plot.figure(figsize=(15, 6))
plot.plot(df.index, df['RSI'], label = 'RSI')
plot.plot(df['RSI Lower Boundary'], label = 'Lower Bound', color = 'blue', alpha = 0.2)
plot.plot(df['RSI Upper Boundary'], label = 'Upper Bound', color = 'blue', alpha = 0.2)
plot.legend(loc = 'upper left')
plot.show()

def buy_sell(data):
    Buy = []
    Sell = []
    position = None

    for i in range(0, len(data)):
        rsi = df['RSI'][i]

        if (rsi_check(rsi, position)):
            if position:
                print("Selling shares at $%.2f\n" % (data['Close'][i]))
                Buy.append(np.NaN)
                Sell.append(data['Close'][i])
                position = None
            else:
                print("Buying shares at $%.2f" % (data['Close'][i]))
                Buy.append(data['Close'][i])
                Sell.append(np.NaN)
                position = 1
        else:
            Buy.append(np.NaN)
            Sell.append(np.NaN)

    return (Buy, Sell)

# Create buy and sell columns
a = buy_sell(df)
df['Buy Signal Price'] = a[0]
df['Sell Signal Price'] = a[1]

# Determine Profits/Losses for each stock price
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

# Print trading results for strategy
if net_profits and percentage_deltas:
    print(f'The strategy made a net gain of ${round(sum(net_profits), 2)}')
    print(f'The strategy gained/lost an average of {round(statistics.mean(percentage_deltas), 2)}%')

    # Plot Buy and Sell Signal Prices
    plot.figure(figsize=(15, 6))
    plot.scatter(df.index, df['Buy Signal Price'], color = 'green', label = 'Buy', marker = '^', alpha = 1)
    plot.scatter(df.index, df['Sell Signal Price'], color = 'red', label = 'Sell', marker = 'v', alpha = 1)
    plot.plot(df['Close'], label = 'Close Price', alpha = 0.35)
    plot.title('Close Price Buy & Sell Signals')
    plot.xlabel('Date')
    plot.xticks(rotation = 45)
    plot.ylabel('Close Price USD ($)')
    plot.legend(loc = 'upper left')
    plot.show()

    for i in range(0, len(df)):
        if df['Buy Signal Price'][i] > 0:
            df.loc[i, 'Buy Signal'] = df['RSI'][i]
        if df['Sell Signal Price'][i] > 0:
            df.loc[i, 'Sell Signal'] = df['RSI'][i]

    plot.figure(figsize=(15, 6))
    plot.scatter(df.index, df['Buy Signal'], color = 'green', label = 'Buy', marker = '^', alpha = 1)
    plot.scatter(df.index, df['Sell Signal'], color = 'red', label = 'Sell', marker = 'v', alpha = 1)
    plot.plot(df['RSI'], label = 'RSI', alpha = 0.35)
    plot.plot(df['RSI Upper Boundary'], color = 'blue', alpha = 0.1)
    plot.plot(df['RSI Lower Boundary'], color = 'blue', alpha = 0.1)
    plot.title('RSI Buy & Sell Signals')
    plot.legend(loc = 'upper left')
    plot.show()

else:
    print(f'The strategy did not execute any trades in the {time_range} timeframe.')
