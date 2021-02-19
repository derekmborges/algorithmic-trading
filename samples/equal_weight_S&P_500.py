import numpy as np
import pandas as pd
import requests
import xlsxwriter
import math
from helpers import portfolio_input, chunks

# Retrieve stocks
stocks = pd.read_csv('sp_500_stocks.csv')

# Retrieve API Key
from secrets import IEX_CLOUD_API_TOKEN

########################################################################
#################### Retrieve stock data from API ######################
########################################################################

# Create a Pandas DataFrame to store the stock data
columns = [ 'Ticker', 'Stock Price', 'Market Capitalization', 'Number of Shares to Buy' ]
final_dataframe = pd.DataFrame(columns = columns)

# Split up 500 stocks into groups of 100
symbol_groups = list(chunks(stocks['Ticker'], 100))
symbol_strings = []
for i in range(0, len(symbol_groups)):
    symbol_strings.append(','.join(symbol_groups[i]))

# Make a Batch API call for each group of symbols
for symbol_string in symbol_strings:
    batch_api_url = f"https://sandbox.iexapis.com/stable/stock/market/batch/?symbols={symbol_string}&types=quote&token={IEX_CLOUD_API_TOKEN}"
    data = requests.get(batch_api_url).json()

    # Add each symbol's data to the DataFrame
    for symbol in symbol_string.split(','):
        final_dataframe = final_dataframe.append(
            pd.Series(
                [
                    symbol,
                    data[symbol]['quote']['latestPrice'],
                    data[symbol]['quote']['marketCap'],
                    'N/A'
                ],
                index=columns
            ),
            ignore_index=True
        )
# Optionally print the data
print(final_dataframe)


########################################################################
################# Calculate the amount of shares to buy ################
########################################################################

# Retrieve the user's portfolio value ($$$)
portfolio_size = portfolio_input()

# Calculate the position size required for each stock
position_size = float(portfolio_size) / len(final_dataframe.index)

# Calculate the number of shares to buy based on the stock price
# and store it in the DataFrame
for i in range(0, len(final_dataframe.index)):
    final_dataframe.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / final_dataframe.loc[i, 'Stock Price'])

########################################################################
####################### Format the Excel output ########################
########################################################################

# Create ExcelWriter and convert DataFrame to Excel
writer = pd.ExcelWriter('recommended_trades.xlsx', engine='xlsxwriter')
final_dataframe.to_excel(writer, 'Recommended Trades', index=False)

# Colors for formatting
background_color = '#0a0a23'
font_color = '#ffffff'

# Create formats
string_format = writer.book.add_format(
    {
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)
dollar_format = writer.book.add_format(
    {
        'num_format': '$0.00',
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)
integer_format = writer.book.add_format(
    {
        'num_format': '0',
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)

column_formats = {
    'A': ['Ticker', string_format],
    'B': ['Stock Price', dollar_format],
    'C': ['Market Capitalization', dollar_format],
    'D': ['Number of Shares to Buy', integer_format]
}
for column in column_formats.keys():
    writer.sheets['Recommended Trades'].write(f'{column}1', column_formats[column][0], column_formats[column][1])
    writer.sheets['Recommended Trades'].set_column(f'{column}:{column}', 18, column_formats[column][1])
writer.save()