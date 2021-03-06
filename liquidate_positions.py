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
    price = position.current_price
    api.submit_order(
        symbol=symbol, qty=str(qty), side='sell',
        type='limit', limit_price=str(price), time_in_force='day'
    )
    alert += f'{symbol}: {qty}\n'

discord_webhook._send_messsage(alert)

print('Waiting for orders to fill...')
positions = api.list_positions()
while positions:
    time.sleep(60)
    open_orders = api.list_orders(status='open')
    if open_orders:
        for order in open_orders:
            qty = order.qty
            symbol = order.symbol
            try:
                print(f'Cancelling limit order for {qty} shares of {symbol}')
                api.cancel_order(order.id)
                # submit new market order
                print(f'Submitting market order for {qty} shares of {symbol}')
                api.submit_order(
                    symbol=symbol, qty=str(qty), side='sell',
                    type='market', time_in_force='day'
                )
            except Exception as e:
                print(f'Error with {symbol} order:', e)
                discord_webhook.send_error(f'Error trying to sell {symbol}:', e)
    positions = api.list_positions()

print('Success.')
