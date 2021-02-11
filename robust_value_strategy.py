import numpy as np
import pandas as pd
import requests
import math
import xlsxwriter
from scipy.stats import percentileofscore as score
from statistics import mean
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
    'Number of Shares to Buy',
    'Price-to-Earnings Ratio',
    'PE Percentile',
    'Price-to-Book Ratio',
    'PB Percentile',
    'Price-to-Sales Ratio',
    'PS Percentile',
    'EV/EBITDA',
    'EV/EBITDA Percentile',
    'EV/GP',
    'EV/GP Percentile',
    'RV Score'
]
# rv = Robust Value
rv_dataframe = pd.DataFrame(columns = columns)

# Make a Batch API call for each group of symbols
for symbol_string in symbol_strings:
    batch_api_url = f"https://sandbox.iexapis.com/stable/stock/market/batch/?symbols={symbol_string}&types=quote,advanced-stats&token={IEX_CLOUD_API_TOKEN}"
    data = requests.get(batch_api_url).json()

    for symbol in symbol_string.split(','):
        try:
            ev_to_ebitda = data[symbol]['advanced-stats']['enterpriseValue'] / data[symbol]['advanced-stats']['EBITDA']
        except TypeError:
            ev_to_ebitda = np.NaN
        
        try:
            ev_to_gp = data[symbol]['advanced-stats']['enterpriseValue'] / data[symbol]['advanced-stats']['grossProfit']
        except TypeError:
            ev_to_gp = np.NaN

        rv_dataframe = rv_dataframe.append(
            pd.Series([
                symbol,
                data[symbol]['quote']['latestPrice'],
                'N/A',
                data[symbol]['quote']['peRatio'],
                'N/A',
                data[symbol]['advanced-stats']['priceToBook'],
                'N/A',
                data[symbol]['advanced-stats']['priceToSales'],
                'N/A',
                ev_to_ebitda,
                'N/A',
                ev_to_gp,
                'N/A',
                'N/A'
            ],
            index = columns),
            ignore_index = True
        )

# Fix null data
for column in ['Price-to-Earnings Ratio','Price-to-Book Ratio','Price-to-Sales Ratio','EV/EBITDA','EV/GP']:
    rv_dataframe[column].fillna(rv_dataframe[column].mean(), inplace = True)
# print(rv_dataframe)
assert len(rv_dataframe[rv_dataframe.isnull().any(axis=1)]) == 0


########################################################################
##################### Calculate Value Percentiles ######################
########################################################################

# Calculate ratio percentiles
metrics = {
    'Price-to-Earnings Ratio': 'PE Percentile',
    'Price-to-Book Ratio': 'PB Percentile',
    'Price-to-Sales Ratio': 'PS Percentile',
    'EV/EBITDA': 'EV/EBITDA Percentile',
    'EV/GP': 'EV/GP Percentile'
}
for metric in metrics.keys():
    for row in rv_dataframe.index:
        rv_dataframe.loc[row, metrics[metric]] = score(rv_dataframe[metric], rv_dataframe.loc[row, metric]) / 100

# Calculate Robust Value Score
for row in rv_dataframe.index:
    value_percentiles = []
    for metric in metrics.keys():
        value_percentiles.append(rv_dataframe.loc[row, metrics[metric]])
    rv_dataframe.loc[row, 'RV Score'] = mean(value_percentiles)


# Select 50 best value stocks
rv_dataframe.sort_values('RV Score', inplace = True)
rv_dataframe = rv_dataframe[:50]
rv_dataframe.reset_index(drop = True, inplace = True)


########################################################################
################# Calculate the amount of shares to buy ################
########################################################################

portfolio_size = portfolio_input()
position_size = float(portfolio_size) / len(rv_dataframe.index)

for i in rv_dataframe.index:
    rv_dataframe.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / rv_dataframe.loc[i, 'Price'])
# print(rv_dataframe)


########################################################################
####################### Format the Excel output ########################
########################################################################

# Create ExcelWriter and convert DataFrame to Excel
writer = pd.ExcelWriter('value_strategy.xlsx', engine = 'xlsxwriter')
rv_dataframe.to_excel(writer, 'Value Strategy', index = False)

# Colors for formatting
background_color = '#0a0a23'
font_color = '#ffffff'

# Create formats
string_template = writer.book.add_format(
    {
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)
dollar_template = writer.book.add_format(
    {
        'num_format': '$0.00',
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)
integer_template = writer.book.add_format(
    {
        'num_format': '0',
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)
float_template = writer.book.add_format(
    {
        'num_format': '0.0',
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)
percent_template = writer.book.add_format(
    {
        'num_format': '0.0%',
        'font_color': font_color,
        'bg_color': background_color,
        'border': 1
    }
)

# Create column_formats dictionary
column_formats = {
    'A': ['Ticker', string_template],
    'B': ['Price', dollar_template],
    'C': ['Number of Shares to Buy', integer_template],
    'D': ['Price-to-Earnings Ratio', float_template],
    'E': ['PE Percentile', percent_template],
    'F': ['Price-to-Book Ratio', float_template],
    'G': ['PB Percentile', percent_template],
    'H': ['Price-to-Sales Ratio', float_template],
    'I': ['PS Percentile', percent_template],
    'J': ['EV/EBITDA', float_template],
    'K': ['EV/EBITDA Percentile', percent_template],
    'L': ['EV/GP', float_template],
    'M': ['EV/GP Percentile', percent_template],
    'N': ['RV Score', percent_template]
}

# Format data in each column
for column in column_formats.keys():
    # Format column header
    writer.sheets['Value Strategy'].write(f'{column}1', column_formats[column][0], column_formats[column][1])

    # Format column data
    writer.sheets['Value Strategy'].set_column(f'{column}:{column}', 22, column_formats[column][1])

# Save to file
writer.save()
