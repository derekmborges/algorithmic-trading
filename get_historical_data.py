import requests
import string
import time
import pytz
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from google.cloud import storage
from google.cloud import bigquery

# Run in the evening to retrieve stock data from today
def daily_candlestick_data():
    # Get TD Ameritrade API key
    storage_client = storage.Client()
    bucket = storage_client.get_bucket('derek-algo-trading-bucket')
    blob = bucket.blob('td-ameritrade-key.txt')
    api_key = blob.download_as_text()
    # print('Key: {}'.format(api_key))

    # Check if the market was open today
    today = datetime.today().astimezone(pytz.timezone('US/Eastern'))
    today_fmt = today.strftime('%Y-%m-%d')
    yesterday = datetime.today() - timedelta(1)
    market_url = 'https://api.tdameritrade.com/v1/marketdata/EQUITY/hours'
    params = { 'apikey': api_key, 'date': today_fmt }
    response = requests.get(url=market_url, params=params).json()
    # print(response)
    
    # try:
    if response['equity']['EQ']['isOpen']:
        # store uppercase alphabet
        alpha = list(string.ascii_uppercase)
        
        symbols = []

        # Loop through each letter and get the stocks on that page
        # and store them in a list
        for each in alpha:
            url = 'http://eoddata.com/stocklist/NYSE/{}.html'.format(each)
            resp = requests.get(url)
            site = resp.content
            soup = BeautifulSoup(site, 'html.parser')
            table = soup.find('table', {'class': 'quotes'})
            for row in table.findAll('tr')[1:]:
                symbols.append(row.findAll('td')[0].text.rstrip())
        
        symbols_clean = []
        for each in symbols:
            each = each.replace('.', '-')
            symbols_clean.append((each.split('-')[0]))
        
        # Function to turn a datetime object into unix
        def unix_time_millis(dt):
            epoch = datetime.utcfromtimestamp(0)
            return int((dt - epoch).total_seconds() * 1000.0)

        data_list = []
        for symbol in symbols_clean:
            req_url = f'https://api.tdameritrade.com/v1/marketdata/{symbol}/pricehistory?apikey={api_key}'
            params = {
                'periodType': 'day',
                'frequencyType': 'minute',
                'frequency': '5',
                'startDate': unix_time_millis(yesterday.replace(hour=9, minute=0, second=0)),
                'endDate': unix_time_millis(yesterday.replace(hour=18, minute=0, second=0)),
                'needExtendedHoursData': 'true'
            }
            for key in params.keys():
                req_url = f'{req_url}&{key}={params[key]}'
            response = requests.get(url=req_url)
            # print(response.json())
            # print(f'{response.status_code}')
            data_list.append(response.json())
            time.sleep(.5)
        
        # Create a list for each data point and loop through the json, adding the data to the lists
        symbl_l, open_l, high_l, low_l, close_l, volume_l, datetime_l = [], [], [], [], [], [], []
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
                    datetime_l.append(each['datetime'])
            except KeyError:
                pass

        df = pd.DataFrame({
            'datetime': datetime_l,
            'symbol': symbl_l,
            'open': open_l,
            'high': high_l,
            'low': low_l,
            'close': close_l, 
            'volume': volume_l
        })

        # Convert date column from epoch
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
        df.datetime = (df.datetime.dt.tz_localize('UTC')
                        .dt.tz_convert('US/Eastern')
                        .dt.strftime("%Y-%m-%d %H:%M:%S"))

        # Add to bigquery
        client = bigquery.Client()
        dataset_id = 'stock_data'
        table_id = 'daily_quote_data'

        dataset_ref = client.dataset(dataset_id)
        table_ref = dataset_ref.table(table_id)

        job_config = bigquery.LoadJobConfig()
        # job_config.write_disposition = 'WRITE_TRUNCATE'
        job_config.autodetect = True
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()

daily_candlestick_data()
