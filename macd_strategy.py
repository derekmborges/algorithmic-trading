import requests
import statistics
import math
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from helpers import chunks
from indicators.macd_indicator import macd_check
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

# Retrieve stocks
# stocks = pd.read_csv('sp_500_stocks.csv')

# For now, only work with AAPL stock
symbol = 'AAPL'
time_range = '1y'

# Retrieve API Key
from secrets import IEX_CLOUD_API_TOKEN

# Create DataFrame
columns = ['Date', 'Close', 'MACD', 'Signal']
df = pd.DataFrame(columns=columns)

# Retrieve MACD data
api_url = f"https://sandbox.iexapis.com/stable/stock/{symbol}/indicator/macd?range={time_range}&token={IEX_CLOUD_API_TOKEN}"
data = requests.get(api_url).json()
days = len(data['chart'])
# print(f'Days in report: {days}')

for day in range(0, days):
    df = df.append(
        pd.Series([
            data['chart'][day]['date'],
            data['chart'][day]['close'],
            data['indicator'][0][day] if data['indicator'][0][day] else 0,
            data['indicator'][1][day] if data['indicator'][1][day] else 0
        ],
        index=columns),
        ignore_index=True
    )

# Filter out the first few rows that don't have MACD values
df = df[df['MACD'] > 0]
# print(f'Length of MACD data: {len(df.index)}')

# Set the date as the index
df = df.set_index(pd.DatetimeIndex(df['Date'].values))

# Plot Price data
plot.figure(figsize=(12.2, 4.5))
plot.plot(df['Close'], label='Close')
plot.title('Close Price History')
plot.xlabel('Date')
plot.xticks(rotation = 45)
plot.ylabel('Price USD ($)')
plot.show()

# Plot MACD data
plot.figure(figsize=(15, 6))
plot.plot(df.index, df['MACD'], label = f'{symbol} MACD', color = 'red')
plot.plot(df.index, df['Signal'], label = 'Signal Line', color = 'blue')
plot.legend(loc = 'upper left')
plot.show()

def buy_sell(data):
    Buy = []
    Sell = []
    position = None
    
    for i in range(0, len(data)):
        macd = data['MACD'][i]
        signal = data['Signal'][i]
        if macd_check(macd, signal, position):
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
