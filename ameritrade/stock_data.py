import os
import csv
import pandas as pd
from pprint import pprint
from alpha_vantage.timeseries import TimeSeries
from alpha_vantage.techindicators import TechIndicators
from secrets import ALPHA_VANTAGE_TOKEN

from pandas.core.frame import DataFrame

def get_stock_data(symbol, interval, slice='year1month1'):
    file_path = f'data/{symbol}_{slice}_{interval}.csv'

    # If the backup doesn't exist, go get it and store it locally
    if not os.path.exists(file_path):
        # Create directory if it doesn't exist
        if not os.path.exists('data'):
            os.mkdir('data')

        # Retrieve CSV data from API and save it to local file
        ts = TimeSeries(key=ALPHA_VANTAGE_TOKEN, output_format='csv')
        with open(file_path, 'w') as new_file:
            reader, _ = ts.get_intraday_extended(symbol=symbol, interval=interval, slice=slice)
            for row in reader:
                new_file.write(','.join(row))
                new_file.write('\n')
        
        # Load the newly created CSV and update it with calculated indicators
        data = pd.read_csv(file_path)

        # Check if data is not empty
        if len(data.index) > 0:
            data = data.set_index(pd.DatetimeIndex(data['time'].values))
            data = data.sort_index()
            data = _calculate_obv_data(data)
            data.to_csv(file_path)
        else:
            return None

    # Load the CSV file, sort it by the time, and return the specified date's data
    data = pd.read_csv(file_path)
    if len(data.index) > 0:
        data = data.set_index(pd.DatetimeIndex(data['time'].values))
        data = data.drop(columns=['time', 'Unnamed: 0'])
        return data
    else:
        return None

def _calculate_obv_data(df: DataFrame):
    OBV = []
    OBV.append(0)

    for i in range(1, len(df.close)):
        if df.close[i] > df.close[i-1]:
            OBV.append(OBV[-1] + df.volume[i])
        elif df.close[i] < df.close[i-1]:
            OBV.append(OBV[-1] - df.volume[i])
        else:
            OBV.append(OBV[-1])
    
    df['OBV'] = OBV
    df['OBV_EMA'] = df['OBV'].ewm(span=20).mean()
    return df

def get_stock_data_on_date(symbol, interval, slice, date):
    data = get_stock_data(symbol, interval, slice)
    symbol_date_data = data[data.index.to_series().between(f'{date} 00:00:00', f'{date} 23:59:59')]
    if len(symbol_date_data.index) > 0:
        return symbol_date_data
    return None