from google.cloud import storage
import alpaca_trade_api as tradeapi

# Get Alpaca API key and secret
storage_client = storage.Client()
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = tradeapi.REST(api_key, secret_key, base_url, 'v2')

watchlist = api.get_watchlist_by_name('paper-trade-stocks')
api.update_watchlist(watchlist.id, symbols=[])
