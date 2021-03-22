from google.cloud import storage
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from datetime import datetime

def unix_time_sec(dt):
    epoch = datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds())

def chunks(l, n):
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

def select_day_trade_stocks(event, context):
    # Get Alpaca API key and secret
    storage_client = storage.Client()
    bucket = storage_client.get_bucket('derek-algo-trading-bucket')
    blob = bucket.blob('alpaca-api-key.txt')
    api_key = blob.download_as_text()
    blob = bucket.blob('alpaca-secret-key.txt')
    secret_key = blob.download_as_text()
    base_url = 'https://paper-api.alpaca.markets'
    api = REST(api_key, secret_key, base_url, 'v2')

    # Get all stocks
    assets = api.list_assets('active')
    symbols = [asset.symbol for asset in assets if asset.tradable]

    # Get past 50 days data for all stocks
    data = {}
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    for symbol_group in symbols_chunked:
        print(f'Retrieving {len(symbol_group)} symbol data')
        data_group = api.get_barset(','.join(symbol_group), '1D', limit=50).df
        for symbol in symbol_group:
            data[symbol] = data_group[symbol]
    
    result_df = pd.DataFrame()

    for symbol in data.keys():
        df = data[symbol]
        df = df.loc[df['close'] > 0]
        if len(df.index) >= 50:
            # Calculate day change percent
            dayChange = []
            for i in df.index:
                try:
                    high = df['high'][i]
                    low = df['low'][i]
                    if low and low > 0:
                        dayChange.append(round(((high - low) / low) * 100, 2))
                    else:
                        dayChange.append(0)
                except KeyError:
                    dayChange.append(0)

            # Calculate averages
            df['dayChange'] = dayChange
            df['averageDayChange10'] = df['dayChange'].ewm(span=10).mean()
            df['averageVolume50'] = df['volume'].ewm(span=50).mean()
            df['averageVolume10'] = df['volume'].ewm(span=10).mean()
            df['symbol'] = symbol
    
            # Add most recent row
            i = len(df.index) - 1
            result_df = result_df.append(df.iloc[i])
    
    # Filter stocks by high volatility criteria
    filtered_df = result_df.query(
        'averageDayChange10>4.5 & averageVolume50>4000000 & averageVolume10>4000000 & close>=5'
    )

    # Sort descending by averageDayChange10
    sorted_df = filtered_df.sort_values('averageDayChange10', ascending=False)

    # Grab top 5 stocks
    selected_stocks = sorted_df[:5]
    print(selected_stocks)
    symbols = list(selected_stocks['symbol'].values)
    print(symbols)

    # Store them in Alpaca watchlist
    watchlist = api.get_watchlist_by_name('day-trade-stocks')
    api.update_watchlist(watchlist.id, symbols=symbols)
    print('Success')

select_day_trade_stocks(None, None)