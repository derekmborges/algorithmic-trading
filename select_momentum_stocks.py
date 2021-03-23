from google.cloud import storage
from scipy import stats
import numpy as np
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns
from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices

def chunks(l, n):
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

def select_momentum_stocks():
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
        data_group = api.get_barset(','.join(symbol_group), '1D', limit=125).df
        for symbol in symbol_group:
            data[symbol] = data_group[symbol]
    
    all_df = pd.DataFrame()

    def momentum_score(ts):
        x = np.arange(len(ts))
        log_ts = np.log(ts)
        regress = stats.linregress(x, log_ts)
        annualized_slope = (np.power(np.exp(regress[0]), 252) -1) * 100
        return annualized_slope * (regress[2] ** 2)
    
    def trend_score(ts):
        array = ts.to_numpy()
        result = np.polyfit(range(0, len(array)), array, 1)
        slope = result[-2]
        return float(slope)

    c = 0
    for symbol in data.keys():
        df = data[symbol]
        df = df.loc[df['close'] > 0]
        if len(df.index) >= 40:
            df['symbol'] = symbol
            momentum_window_large = 125
            minimum_momentum_large = 40
            momentum_window_small = 20

            # 125-day momentum score
            df['momentum_125'] = df.groupby('symbol')['close'].rolling(
                momentum_window_large,
                min_periods=minimum_momentum_large
            ).apply(momentum_score).reset_index(level=0, drop=True)

            # 20-day momentum score
            df['momentum_20'] = df.groupby('symbol')['close'].rolling(
                momentum_window_small,
                min_periods=momentum_window_small
            ).apply(momentum_score).reset_index(level=0, drop=True)

            # 3-day price trend score
            df['3d_slope'] = df.groupby('symbol')['close'].rolling(3, min_periods=3)\
                .apply(trend_score).reset_index(level=0, drop=True)
            all_df = all_df.append(df)
        c += 1
        if c % 100 == 0:
            print(f'{c}/{len(data.keys())}')
    print(f'{c}/{len(data.keys())}')


    portfolio_size = 10
    top_momentum_stocks = all_df.loc[all_df.index == all_df.index.max()]
    top_momentum_stocks = top_momentum_stocks[top_momentum_stocks['momentum_20'] > 0]
    top_momentum_stocks = top_momentum_stocks[top_momentum_stocks['3d_slope'] > 0]
    top_momentum_stocks = top_momentum_stocks.sort_values(by='momentum_125', ascending=False).head(portfolio_size)

    universe = top_momentum_stocks['symbol'].tolist()
    df_universe = all_df.loc[all_df['symbol'].isin(universe)]
    df_universe = df_universe.pivot_table(
        index=df_universe.index,
        columns='symbol',
        values='close',
        aggfunc='sum'
    )


    # Calculate expected returns and sample covariance
    mu = expected_returns.mean_historical_return(df_universe)
    S = risk_models.sample_cov(df_universe)

    # Optomize the porfolio for maximal Sharpe ratio
    ef = EfficientFrontier(mu, S)
    weights = ef.max_sharpe()
    cleaned_weights = ef.clean_weights()

    portfolio_value = float(api.get_account().portfolio_value) * 0.95
    # Allocate
    latest_prices = get_latest_prices(df_universe)
    da = DiscreteAllocation(
        cleaned_weights,
        latest_prices,
        total_portfolio_value=portfolio_value
    )

    allocation = da.lp_portfolio()[0]

    # Put the stocks and number of shares into a DataFrame
    symbol_list, num_shares_list = [], []
    for symbol, num_shares in allocation.items():
        symbol_list.append(symbol)
        num_shares_list.append(num_shares)
    
    df_buy = all_df.loc[all_df['symbol'].isin(symbol_list)]
    df_buy = df_buy.loc[df_buy.index == all_df.index.max()].sort_values(by='symbol')
    df_buy['qty'] = num_shares_list
    df_buy['amount_held'] = df_buy['close'] * df_buy['qty']
    df_buy = df_buy.loc[df_buy['qty'] != 0]
    return df_buy
