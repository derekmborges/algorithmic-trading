from datetime import datetime, timedelta
from time import time
from typing import Dict
from btalib.indicators.cci import cci
from btalib.indicators.obv import obv
from btalib.indicators.rsi import rsi
from google.cloud import storage
import math
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from scipy.stats import linregress
import detect_pattern as pattern

# Get Alpaca API key and secret
storage_client = storage.Client()
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = REST(api_key, secret_key, base_url, 'v2')

bars = api.get_barset('AAPL', '1D', 5)['AAPL']

print(bars)