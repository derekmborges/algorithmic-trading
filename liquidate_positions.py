import time
from google.cloud import storage
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
import discord_webhook

# Get Alpaca API key and secret
storage_client = storage.Client()
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = REST(api_key, secret_key, base_url, 'v2')

positions = api.list_positions()

alert = '**End of Week Liquidations**\n\n**Sell**\n'

# Market sell every position
for position in positions:
    symbol = position.symbol
    qty = position.qty
    api.submit_order(
        symbol=symbol, qty=str(qty), side='sell',
        type='market', time_in_force='day'
    )
    alert += f'{symbol}: {qty}\n'

discord_webhook._send_messsage(alert)

print('Waiting for orders to fill...')
time.sleep(60)
positions = api.list_positions()
assert not positions
print('Success.')
