import requests
import string
import time
import pytz
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from google.cloud import storage
from google.cloud import bigquery

# Function to turn a datetime object into unix
def unix_time_millis(date):
    dt = date.replace(hour=6)
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds() * 1000.0)

# Get start and end dates
try:
    start_date = sys.argv[1]
except IndexError:
    print('Error: Must provide start date:')
    print('>>> python3 get_historical_data.py YYYY-MM-DD')
    print('OR')
    print('>>> python3 get_historical_data.py YYYY-MM-DD YYYY-MM-DD')
    start_date = None
try:
    end_date = sys.argv[2]
except IndexError:
    end_date = start_date

if start_date and end_date:
    # Make list of all dates to process
    dates = pd.date_range(start_date, end_date, freq='d')

    # Create BigQuery client and reference dataset/table
    client = bigquery.Client()
    dataset_id = 'stock_data'
    table_id = 'daily_quote_data'

    # Filter out dates that already have data in the table
    new_dates = []
    sql_dates = """
        SELECT DISTINCT date FROM `splendid-cirrus-302501.stock_data.daily_quote_data`
        ORDER BY date
    """
    existing_dates = client.query(sql_dates).to_dataframe()['date'].values
    
    for date in dates:
        if date not in existing_dates:
            new_dates.append(date)

    if not new_dates:
        print('None of the dates in the provided list are missing data.')
    else:
        print(f'Retrieving missing data from {new_dates[0]} to {new_dates[len(new_dates)-1]}...')
        # Get TD Ameritrade API key
        storage_client = storage.Client()
        bucket = storage_client.get_bucket('derek-algo-trading-bucket')
        blob = bucket.blob('td-ameritrade-key.txt')
        api_key = blob.download_as_text()

        # store uppercase alphabet
        alpha = list(string.ascii_uppercase)

        # Loop through each letter and get the stocks on that page
        # and store them in a list
        symbols = []
        for each in alpha:
            url = 'http://eoddata.com/stocklist/NYSE/{}.html'.format(each)
            resp = requests.get(url)
            site = resp.content
            soup = BeautifulSoup(site, 'html.parser')
            table = soup.find('table', {'class': 'quotes'})
            for row in table.findAll('tr')[1:]:
                symbols.append(row.findAll('td')[0].text.rstrip())
        # Clean the symbols of extra characters
        symbols_clean = []
        for each in symbols:
            each = each.replace('.', '-')
            symbols_clean.append((each.split('-')[0]))
        
        # Remove duplicate symbols caused by cleaning
        symbols_unique = []
        for each in symbols_clean:
            if each not in symbols_unique:
                symbols_unique.append(each)

        for date in new_dates:
            print('========================')
            print(f"Processing {date.strftime('%Y-%m-%d')}")
            print('Each letter will appear as it completes retrieving data...')
            currentLetter = symbols_unique[0][0]
            data_list = []
            for symbol in symbols_unique:
                if symbol[0] != currentLetter:
                    print(currentLetter)
                    currentLetter = symbol[0]
                req_url = f'https://api.tdameritrade.com/v1/marketdata/{symbol}/pricehistory?apikey={api_key}'
                params = {
                    'periodType': 'month',
                    'frequencyType': 'daily',
                    'frequency': '1',
                    'startDate': unix_time_millis(date),
                    'endDate': unix_time_millis(date),
                    'needExtendedHoursData': 'true'
                }
                for key in params.keys():
                    req_url = f'{req_url}&{key}={params[key]}'
                response = requests.get(url=req_url)

                # Check for status code 400, likely the market was not open that day
                if response.status_code == 400:
                    break

                data_list.append(response.json())
                time.sleep(.5)
            
            if data_list:
                print('Z')
            else:
                print(f"Skipping {date.strftime('%Y-%m-%d')}, market was closed.\n")
                continue

            # Create a list for each data point and loop through the json, adding the data to the lists
            print('Building DataFrame...')
            symbl_l, open_l, high_l, low_l, close_l, volume_l, date_l = [], [], [], [], [], [], []
            for data in data_list:
                try:
                    symbol_name = data['symbol']
                except KeyError:
                    symbol_name = np.NaN
                try:
                    for each in data['candles']:
                        symbl_l.append(symbol_name)
                        open_l.append(each['open'])
                        high_l.append(each['high'])
                        low_l.append(each['low'])
                        close_l.append(each['close'])
                        volume_l.append(each['volume'])
                        date_l.append(each['datetime'])
                except KeyError:
                    pass

            df = pd.DataFrame({
                'date': date_l,
                'symbol': symbl_l,
                'openPrice': open_l,
                'closePrice': close_l, 
                'lowPrice': low_l,
                'highPrice': high_l,
                'totalVolume': volume_l
            })

            # Convert date column from epoch
            df['date'] = pd.to_datetime(df['date'], unit='ms')
            df['date'] = df['date'].dt.date

            # Add to bigquery
            dataset_ref = client.dataset(dataset_id)
            table_ref = dataset_ref.table(table_id)

            job_config = bigquery.LoadJobConfig()
            job_config.autodetect = True
            job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
            job.result()
            print(f'Data uploaded for {date}\n')
