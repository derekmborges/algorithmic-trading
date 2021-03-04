import requests
import string
import time
import pytz
import pandas as pd
import numpy as np
from datetime import datetime
from bs4 import BeautifulSoup
from google.cloud import storage
from google.cloud import bigquery

# Run in the evening to retrieve stock data from today
def daily_quote_data(event, context):
    # Get TD Ameritrade API key
    storage_client = storage.Client()
    bucket = storage_client.get_bucket('derek-algo-trading-bucket')
    blob = bucket.blob('td-ameritrade-key.txt')
    api_key = blob.download_as_text()

    # Check if the market was open today
    today = datetime.today().astimezone(pytz.timezone('US/Eastern'))
    today_fmt = today.strftime('%Y-%m-%d')
    print(f'Retrieving stock data on {today_fmt}...')
    market_url = 'https://api.tdameritrade.com/v1/marketdata/EQUITY/hours'
    params = { 'apikey': api_key, 'date': today_fmt }
    response = requests.get(url=market_url, params=params).json()

    try:
        if response['equity']['EQ']['isOpen']:
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
            
            symbols_clean = []
            for each in symbols:
                each = each.replace('.', '-')
                symbols_clean.append((each.split('-')[0]))
            
            def chunks(l, n):
                n = max(1, n)
                return (l[i:i+n] for i in range(0, len(l), n))
            symbols_chunked = list(chunks(list(set(symbols_clean)), 200))
            
            def quotes_request(stocks):
                url = r"https://api.tdameritrade.com/v1/marketdata/quotes"
                params = {
                    'apikey': api_key,
                    'symbol': stocks
                }
                
                request = requests.get(url=url, params=params).json()
                time.sleep(1)
                return pd.DataFrame.from_dict(request, orient='index').reset_index(drop=True)

            df = pd.concat([quotes_request(each) for each in symbols_chunked], sort=True)
            # Add the date and format for BigQuery
            df['date'] = pd.to_datetime(today_fmt)
            df['date'] = df['date'].dt.date
            df['divDate'] = pd.to_datetime(df['divDate'])
            df['divDate'] = df['divDate'].dt.date
            df['divDate'] = df['divDate'].fillna(np.nan)

            # Remove anything without a price
            df = df.loc[df['bidPrice'] > 0]

            df = df.rename(columns={
                '52WkHigh': '_52WkHigh',
                '52WkLow': '_52WkLow'
            })

            # Add to bigquery
            client = bigquery.Client()
            dataset_id = 'stock_data'
            table_id = 'daily_quote_data'

            dataset_ref = client.dataset(dataset_id)
            table_ref = dataset_ref.table(table_id)

            job_config = bigquery.LoadJobConfig()
            job_config.autodetect = True
            job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
            job.result()
            return 'Success'

        else:
            return 'Market Not Open Today'
    except KeyError:
        return 'Not a weekday'

print(daily_quote_data(None, None))
