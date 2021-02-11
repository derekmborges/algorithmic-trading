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

########################################################################
############ High Quality (More Realistic) Momentum Strategy ###########
########################################################################

# hqm = High Quality Momentum
hqm_columns = [
    'Ticker',
    'Price',
    'Number of Shares to Buy',
    'One-Year Price Return',
    'One-Year Return Percentile',
    'Six-Month Price Return',
    'Six-Month Return Percentile',
    'Three-Month Price Return',
    'Three-Month Return Percentile',
    'One-Month Price Return',
    'One-Month Return Percentile',
    'HQM Score'
]
hqm_dataframe = pd.DataFrame(columns = hqm_columns)

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
        hqm_dataframe = hqm_dataframe.append(
            pd.Series([
                symbol,
                data[symbol]['price'],
                'N/A',
                data[symbol]['stats']['year1ChangePercent'],
                'N/A',
                data[symbol]['stats']['month6ChangePercent'],
                'N/A',
                data[symbol]['stats']['month3ChangePercent'],
                'N/A',
                data[symbol]['stats']['month1ChangePercent'],
                'N/A',
                'N/A'
            ],
            index = hqm_columns),
            ignore_index = True
        )


# Calculate momentum percentiles

time_periods = [
    'One-Year',
    'Six-Month',
    'Three-Month',
    'One-Month'
]

# Zero out the value of Price Return if it's None
for row in hqm_dataframe.index:
    for time_period in time_periods:
        if hqm_dataframe.loc[row, f'{time_period} Price Return'] == None:
            hqm_dataframe.loc[row, f'{time_period} Price Return'] = 0

# Calculate Percentile scores for each price return
for row in hqm_dataframe.index:
    for time_period in time_periods:
        change_col = f'{time_period} Price Return'
        percentile_col = f'{time_period} Return Percentile'
        hqm_dataframe.loc[row, percentile_col] = score(hqm_dataframe[change_col], hqm_dataframe.loc[row, change_col]) / 100

# Calculate the Mean Momentum
for row in hqm_dataframe.index:
    momentum_percentiles = []
    for time_period in time_periods:
        momentum_percentiles.append(hqm_dataframe.loc[row, f'{time_period} Return Percentile'])
    hqm_dataframe.loc[row, 'HQM Score'] = mean(momentum_percentiles)

# Select top 50 HQM stocks
hqm_dataframe.sort_values('HQM Score', ascending = False, inplace = True)
hqm_dataframe = hqm_dataframe[:50]
hqm_dataframe.reset_index(drop = True, inplace = True)


########################################################################
################# Calculate the amount of shares to buy ################
########################################################################

portfolio_size = portfolio_input()
position_size = float(portfolio_size) / len(hqm_dataframe.index)

for i in hqm_dataframe.index:
    hqm_dataframe.loc[i, 'Number of Shares to Buy'] = math.floor(position_size / hqm_dataframe.loc[i, 'Price'])


########################################################################
####################### Format the Excel output ########################
########################################################################

# Create ExcelWriter and convert DataFrame to Excel
writer = pd.ExcelWriter('momentum_strategy.xlsx', engine = 'xlsxwriter')
hqm_dataframe.to_excel(writer, 'Momentum Strategy', index = False)

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
    'D': ['One-Year Price Return', percent_template],
    'E': ['One-Year Return Percentile', percent_template],
    'F': ['Six-Month Price Return', percent_template],
    'G': ['Six-Month Return Percentile', percent_template],
    'H': ['Three-Month Price Return', percent_template],
    'I': ['Three-Month Return Percentile', percent_template],
    'J': ['One-Month Price Return', percent_template],
    'K': ['One-Month Return Percentile', percent_template],
    'L': ['HQM Score', percent_template]
}

# Format data in each column
for column in column_formats.keys():
    # Format column header
    writer.sheets['Momentum Strategy'].write(f'{column}1', column_formats[column][0], column_formats[column][1])

    # Format column data
    writer.sheets['Momentum Strategy'].set_column(f'{column}:{column}', 25, column_formats[column][1])

# Save to file
writer.save()
