import numpy as np
import pandas as pd
import requests
import math
import xlsxwriter
from scipy import stats
from helpers import portfolio_input, chunks

# Retrieve stocks
stocks = pd.read_csv('sp_500_stocks.csv')

# Retrieve API Key
from secrets import IEX_CLOUD_API_TOKEN

# Split up 500 stocks into groups of 100
symbol_groups = list(chunks(stocks['Ticker'], 100))
symbol_strings = []
for i in range(0, len(symbol_groups)):
    symbol_strings.append(','.join(symbol_groups[i]))

# Create DataFrame
columns = [
    'Ticker',
    'Price',
    'Price-to-Earnings Ratio',
    'Number of Shares to Buy'
]
final_dataframe = pd.DataFrame(columns = columns)

# Make a Batch API call for each group of symbols
for symbol_string in symbol_strings:
    batch_api_url = f"https://sandbox.iexapis.com/stable/stock/market/batch/?symbols={symbol_string}&types=quote&token={IEX_CLOUD_API_TOKEN}"
    data = requests.get(batch_api_url).json()

    for symbol in symbol_string.split(','):
        final_dataframe = final_dataframe.append(
            pd.Series([
                symbol,
                data[symbol]['quote']['latestPrice'],
                data[symbol]['quote']['peRatio'],
                'N/A'
            ],
            index = columns),
            ignore_index = True
        )

# Select 50 best value stocks
final_dataframe.sort_values('Price-to-Earnings Ratio', inplace = True)
final_dataframe = final_dataframe[final_dataframe['Price-to-Earnings Ratio'] >= 0]
final_dataframe = final_dataframe[:50]
final_dataframe.reset_index(drop = True, inplace = True)


########################################################################
################# Calculate the amount of shares to buy ################
########################################################################

portfolio_size = portfolio_input()
position_size = float(portfolio_size) / len(final_dataframe.index)

for i in final_dataframe.index:
    final_dataframe.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / final_dataframe.loc[i, 'Price'])
print(final_dataframe)


