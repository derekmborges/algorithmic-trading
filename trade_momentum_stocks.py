from requests.exceptions import HTTPError
import websocket
import json
import math
import _thread
import requests
from google.cloud import storage
import alpaca_trade_api as tradeapi
# from alpaca_trade_api import REST
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
pd.set_option('mode.chained_assignment', None)
import btalib
import time
from pytz import timezone
import ta.trend

# Get Alpaca API key and secret
storage_client = storage.Client.from_service_account_json('./splendid-cirrus-302501-7e3faab608d2.json')
bucket = storage_client.get_bucket('derek-algo-trading-bucket')
blob = bucket.blob('alpaca-api-key.txt')
api_key = blob.download_as_text()
blob = bucket.blob('alpaca-secret-key.txt')
secret_key = blob.download_as_text()
base_url = 'https://paper-api.alpaca.markets'
api = tradeapi.REST(api_key, secret_key, base_url, 'v2')

session = requests.session()

# Price windows to filter stocks
min_share_price = 2.0
max_share_price = 13.0

# Minimum previous-day dollar volume for a stock
min_last_dv = 500000

# Stop limit
default_stop = 0.95

# How much of the portfolio to allocate to a position
risk = 0.001

def chunks(l, n):
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

def get_1000m_history_data(symbols):
    print('Getting historical data...')
    minute_history = {}
    c = 0
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    for symbol_group in symbols_chunked:
        minute_bars = api.get_barset(','.join(symbol_group), 'minute', limit=1000).df
        for symbol in symbol_group:
            minute_history[symbol] = minute_bars[symbol]
            c += 1
            print('{}/{}'.format(c, len(symbols)))
    print('Success.')
    return minute_history

def get_tickers():
    print('Getting current ticker data...')
    assets = api.list_assets()
    symbols = [asset.symbol for asset in assets if asset.tradable]

    day_bars = {}
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    for symbol_group in symbols_chunked:
        day_group = api.get_barset(','.join(symbol_group), '1D', limit=1)
        for symbol in symbol_group:
            day_bars[symbol] = day_group[symbol]

    tickers = []
    for symbol in symbols[:250]:
        try:
            prevDay = day_bars[symbol][0]
            prevVolume = prevDay.v
            changePerc = (prevDay.h - prevDay.l) / prevDay.l * 100
            lastTrade = api.get_last_trade(symbol)
            lastPrice = lastTrade.price
            if (
                lastPrice >= min_share_price and
                lastPrice <= max_share_price and
                prevVolume * lastPrice > min_last_dv and
                changePerc >= 3.5
            ):
                tickers.append({
                    'ticker': symbol,
                    'prevClose': prevDay.c,
                    'volume': prevVolume
                })
        except Exception:
            pass
    print('Success.')
    return tickers

def find_stop(current_value, minute_history, now):
    series = minute_history['low'][-100:] \
                .dropna().resample('5min').min()
    series = series[now.floor('1D'):]
    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if (low_index) > 0:
        return series[low_index[-1]] - 0.01
    return current_value * default_stop

def run(tickers, market_open_dt, market_close_dt):
    conn = tradeapi.StreamConn(base_url=base_url, key_id=api_key, secret_key=secret_key)
    # conn = tradeapi.stream2.StreamConn(base_url=base_url, key_id=api_key, secret_key=secret_key)

    # Update initial state with info from tickers
    volume_today = {}
    prev_closes = {}
    for ticker in tickers:
        symbol = ticker['ticker']
        prev_closes[symbol] = ticker['prevClose']
        volume_today[symbol] = ticker['volume']
    
    symbols = [ticker['ticker'] for ticker in tickers]
    print('Tracking {} symbols.'.format(len(symbols)))
    minute_history = get_1000m_history_data(symbols)

    portfolio_value = float(api.get_account().portfolio_value)

    open_orders = {}
    positions = {}

    # Cancel any open orders
    existing_orders = api.list_orders(limit=500)
    for order in existing_orders:
        if order.symbol in symbols:
            api.cancel_order(order.id)
    
    stop_prices = {}
    latest_cost_basis = {}

    # Track any positions bought during previous executions
    existing_positions = api.list_positions()
    for position in existing_positions:
        if position.symbol in symbols:
            positions[position.symbol] = float(position.qty)
            # Recalculate cost basis and stop price
            latest_cost_basis[position.symbol] = float(position.cost_basis)
            stop_prices[position.symbol] = (
                float(position.cost_basis) * default_stop
            )
    
    # Keep track of what is being bought/sold
    target_prices = {}
    partial_fills = {}

    # Subscribe to trade updates to keep track of the portfolio
    @conn.on(r'trade_update')
    async def handle_trade_update(conn, channel, data):
        symbol = data.order['symbol']
        last_order = open_orders.get(symbol)
        if not last_order:
            event = data.event
            if event == 'partial_fill':
                qty = int(data.order['filled_qty'])
                if data.order['side'] == 'sell':
                    qty = qty * -1
                positions[symbol] = (
                    positions.get(symbol, 0) - partial_fills.get(symbol, 0)
                )
                partial_fills[symbol] = qty
                positions[symbol] += qty
                open_orders[symbol] = data.order
            elif event == 'fill':
                qty = int(data.order['filled_qty'])
                if data.order['side'] == 'sell':
                    qty = qty * -1
                positions[symbol] = (
                    positions.get(symbol, 0) - partial_fills.get(symbol, 0)
                )
                partial_fills[symbol] = 0
                positions[symbol] += qty
                open_orders[symbol] = None
            elif event == 'canceled' or event == 'rejected':
                partial_fills[symbol] = 0
                open_orders[symbol] = None
    
    # Replace aggregated 1Sec bars with incoming 1Min bars
    @conn.on(r'AM$')
    async def handle_minute_bar(conn, channel, data):
        symbol = data.symbol
        ts = data.start
        print('{}: {}'.format(ts, symbol))
        ts -= timedelta(microseconds=ts.microsecond)
        minute_history[data.symbol].loc[ts] = [
            data.open,
            data.high,
            data.low,
            data.close,
            data.volume
        ]
        volume_today[data.symbol] += data.volume

        # Next, check for existing orders for the stock
        existing_order = open_orders.get(symbol)
        if existing_order is not None:
            # Make sure order is not too old
            submission_ts = existing_order.submitted_at.astimezone(
                timezone('America/New_York')
            )
            order_lifetime = ts - submission_ts
            # Cancel order if it's more than 1 minute old
            if order_lifetime.seconds // 60 > 1:
                api.cancel_order(existing_order.id)
            return
        
        # Now check for buy/sell conditions
        since_market_open = ts - market_open_dt
        until_market_close = market_close_dt - ts

        # Check at 9:45AM for a buy signal
        if (
            since_market_open.minutes > 15 and
            since_market_open.minutes < 60
        ):
            # Already holding shares?
            position = positions.get(symbol, 0)
            if position > 0:
                return

            # Check how high the price went in 15 minutes
            lower = market_open_dt
            upper = lower + timedelta(minutes=15)
            high_15min = 0
            try:
                high_15min = minute_history[symbol][lower:upper]['high'].max()
            except Exception as e:
                # Because data is aggregating in realtime,
                # sometimes the datetime index is not there
                # until it gets healed by the minute bars
                return
            
            # Get the change percent since yesterday's market close
            daily_pct_change = (
                (data.close - prev_closes[symbol]) / prev_closes[symbol]
            )
            if (
                daily_pct_change > .04 and
                data.close > high_15min and
                volume_today[symbol] > 30000
            ):
                # Check for a positive, increasing MACD
                hist = ta.trend.macd(
                    minute_history[symbol]['close'].dropna(),
                    window_fast=12,
                    window_slow=26
                )
                if (
                    hist[-1] < 0 or
                    not (hist[-3] < hist[-2] < hist[-1])
                ):
                    return
                
                hist = ta.trend.macd(
                    minute_history[symbol]['close'].dropna(),
                    window_fast=40,
                    window_slow=60
                )
                if hist[-1] < 0 or np.diff(hist)[-1] < 0:
                    return
                
                stop_price = find_stop(data.close, minute_history[symbol], ts)
                stop_prices[symbol] = stop_price

                target_prices[symbol] = data.close + (
                    (data.close - stop_price) * 3
                )
                shares_to_buy = portfolio_value * risk // (
                    data.close - stop_price
                )
                if shares_to_buy == 0:
                    shares_to_buy = 1
                shares_to_buy -= positions.get(symbol , 0)
                if shares_to_buy <= 0:
                    return
                
                print('Submitting buy for {} shares of {} at {}'.format(
                    shares_to_buy, symbol, data.close
                ))
                try:
                    o = api.submit_order(
                        symbol=symbol, qty=str(shares_to_buy), side='buy',
                        type='limit', time_in_force='day',
                        limit_price=str(data.close)
                    )
                    open_orders[symbol] = o
                    latest_cost_basis[symbol] = data.close
                except Exception as e:
                    print(e)
                return
        
        # Check for liquidation signals
        if (
            since_market_open.minutes >= 24 and
            until_market_close.minutes > 15
        ):
            position = positions.get(symbol, 0)
            if position == 0:
                return
            
            # Sell for loss if price is below stop price
            # Sell for loss if price is below purchase and MACD < 0
            # Sell for profit if it's above target price
            hist = ta.trend.macd(
                minute_history[symbol]['close'].dropna(),
                window_fast=13,
                window_slow=21
            )
            if (
                data.close <= stop_prices[symbol] or
                (data.close >= target_prices[symbol] and hist[-1] <= 0) or
                (data.close <= latest_cost_basis[symbol] and hist[-1] <= 0)
            ):
                print('Submitting sell for {} shares of {} at {}'.format(
                    position, symbol, data.close
                ))
                try:
                    o = api.submit_order(
                        symbol=symbol, qty=str(position), side='sell',
                        type='limit', time_in_force='day',
                        limit_price=str(data.close)
                    )
                    open_orders[symbol] = o
                    latest_cost_basis[symbol]
                except Exception as e:
                    print(e)
            return
        
        # Check for end of day
        elif until_market_close.seconds // 60 <= 15:
            # Liquidate remaining positions
            try:
                position = api.get_position(symbol)
            except Exception as e:
                # Indicates that it has no position
                return
            print('Trading over, liquidating remaining position in {}'.format(symbol))
            api.submit_order(
                symbol=symbol, qty=position.qty, side='sell',
                type='market', time_in_force='day'
            )
            symbols.remove(symbol)
            if len(symbols) <= 0:
                conn.close()
            conn.deregister([
                # 'A.{}'.format(symbol),
                'AM.{}'.format(symbol)
            ])
    
    
    channels = ['trade_updates']
    for symbol in symbols:
        # symbol_channels = ['A.{}'.format(symbol), 'AM.{}'.format(symbol)]
        symbol_channels = ['AM.{}'.format(symbol)]
        channels += symbol_channels
    print('Watching {} symbols.'.format(len(symbols)))
    run_ws(conn, channels)

def run_ws(conn, channels):
    try:
        conn.run(channels)
    except Exception as e:
        print(e)
        conn.close()
        run_ws(conn, channels)

if __name__ == "__main__":
    # get the market open time
    nyc = timezone('America/New_York')
    today = datetime.today().astimezone(nyc)
    today_str = today.strftime('%Y-%m-%d')
    calendar = api.get_calendar(start=today_str, end=today_str)[0]
    market_open = today.replace(
        hour=calendar.open.hour,
        minute=calendar.open.minute,
        second=0
    ).astimezone(nyc)
    market_close = today.replace(
        hour=calendar.close.hour,
        minute=calendar.close.minute,
        second=0
    ).astimezone(nyc)

    # Wait until just before we might want to trade
    since_market_open = today - market_open
    while since_market_open.seconds // 60 <= 14:
        time.sleep(1)
        since_market_open = today - market_open
    
    run(get_tickers(), market_open, market_close)
