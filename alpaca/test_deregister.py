import requests
from google.cloud import storage
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
pd.set_option('mode.chained_assignment', None)
import time
from pytz import timezone
import ta.trend
import discord_webhook

# Get Alpaca API key and secret
storage_client = storage.Client()
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = tradeapi.REST(api_key, secret_key, base_url, 'v2')

session = requests.session()

def run():
    # conn = tradeapi.stream2.StreamConn(base_url=base_url, key_id=api_key, secret_key=secret_key)
    conn = tradeapi.StreamConn(base_url=base_url, key_id=api_key, secret_key=secret_key)

    symbols = [ 'AAPL', 'MSFT', 'TSLA' ]

    channels = ['trade_updates']
    for symbol in symbols:
        symbol_channels = ['AM.{}'.format(symbol)]
        channels += symbol_channels
    print('Watching {} symbols.'.format(len(symbols)))

    count = {
        'AAPL': -1,
        'MSFT': 0,
        'TSLA': 1
    }

    @conn.on(r'^AM\..+$')
    async def on_bar(connection, channel, data):
        symbol = data.symbol
        if symbol in symbols:
            count[symbol] += 1
            print(f'{symbol}: {count[symbol]}')
            if count[symbol] > 3:
                symbols.remove(symbol)
                if len(symbols) <= 0:
                    print(conn)
                    conn.close(renew=False)
                    print('Stream connection closed.')
                conn.deregister(['AM.{}'.format(symbol)])
                print(f'Stopped watching {symbol}.')
    
    @conn.on(r'close')
    async def on_close():
        print('On close')

    run_ws(conn, channels)
    print('Trading completed!')

def run_ws(conn, channels):
    try:
        conn.run(channels)
    except Exception as e:
        print(e)
        conn.close()
        run_ws(conn, channels)

if __name__ == "__main__":
    run()