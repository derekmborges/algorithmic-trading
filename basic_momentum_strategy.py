import numpy as np
import pandas as pd
import requests
import math
import xlsxwriter
from scipy import stats
from helpers import portfolio_input

# Retrieve stocks
stocks = pd.read_csv('sp_500_stocks.csv')

# Retrieve API Key
from secrets import IEX_CLOUD_API_TOKEN

########################################################################
#################### Retrieve stock data from API ######################
########################################################################

# Create a Pandas DataFrame to store the stock data
columns = [ 'Ticker', 'Price', 'One-Year Price Return', 'Number of Shares to Buy' ]
final_dataframe = pd.DataFrame(columns = columns)

# Method to handle the chunking
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# Split up 500 stocks into groups of 100
symbol_groups = list(chunks(stocks['Ticker'], 100))
symbol_strings = []
for i in range(0, len(symbol_groups)):
    symbol_strings.append(','.join(symbol_groups[i]))

# Make a Batch API call for each group of symbols
for symbol_string in symbol_strings:
    batch_api_url = f"https://sandbox.iexapis.com/stable/stock/market/batch/?symbols={symbol_string}&types=price,stats&token={IEX_CLOUD_API_TOKEN}"
    data = requests.get(batch_api_url).json()
    
    for symbol in symbol_string.split(','):
        final_dataframe = final_dataframe.append(
            pd.Series(
                [
                    symbol,
                    data[symbol]['price'],
                    data[symbol]['stats']['year1ChangePercent'],
                    'N/A'
                ],
                index=columns
            ),
            ignore_index=True
        )

final_dataframe.sort_values('One-Year Price Return', ascending = False, inplace = True)
final_dataframe = final_dataframe[:50]
final_dataframe.reset_index(drop = True, inplace = True)
# print(final_dataframe)


########################################################################
################# Calculate the amount of shares to buy ################
########################################################################

portfolio_size = portfolio_input()
position_size = float(portfolio_size) / len(final_dataframe.index)

for i in range(0, len(final_dataframe)):
    final_dataframe.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / final_dataframe.loc[i, 'Price'])
print(final_dataframe)
