import requests
from google.cloud import storage
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
pd.set_option('mode.chained_assignment', None)
import sys
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

# Price windows to filter stocks
min_share_price = 5.0
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

def get_market_bar_data(symbols, market_open_dt, market_close_dt):
    print('Getting market data...')
    open = datetime.isoformat(pd.Timestamp(market_open_dt))
    close = datetime.isoformat(pd.Timestamp(market_close_dt))
    market_data = {}
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    for symbol_group in symbols_chunked:
        minute_bars = api.get_barset(','.join(symbol_group), '15Min', start=open, end=close, limit=1000).df
        for symbol in symbol_group:
            market_data[symbol] = minute_bars[symbol]
    print('Success.')
    return market_data

def get_1000m_history_data(symbols, market_open_dt):
    print('Getting historical data 1000 minutes before', market_open_dt.strftime('%Y-%m-%d'))
    open = datetime.isoformat(pd.Timestamp(market_open_dt))
    minute_history = {}
    c = 0
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    for symbol_group in symbols_chunked:
        minute_bars = api.get_barset(','.join(symbol_group), '15Min', until=open, limit=1000).df
        for symbol in symbol_group:
            minute_history[symbol] = minute_bars[symbol]
            c += 1
            print('{}/{}'.format(c, len(symbols)))
    print('Success.')
    return minute_history

def get_tickers(market_open_dt):
    print('Getting tickers from', market_open_dt.strftime('%Y-%m-%d'))
    assets = api.list_assets()
    symbols = [asset.symbol for asset in assets if asset.tradable]

    day_bars = {}
    symbols_chunked = list(chunks(list(set(symbols)), 200))
    open = datetime.isoformat(pd.Timestamp(market_open_dt))
    for symbol_group in symbols_chunked:
        day_group = api.get_barset(','.join(symbol_group), '1D', until=open, limit=1)
        for symbol in symbol_group:
            day_bars[symbol] = day_group[symbol]

    tickers = []
    for symbol in symbols:
        try:
            prevDay = day_bars[symbol][0]
            prevVolume = prevDay.v
            changePerc = (prevDay.h - prevDay.l) / prevDay.l * 100
            if (
                prevDay.c >= min_share_price and
                prevDay.c <= max_share_price and
                prevVolume * prevDay.c > min_last_dv and
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
    print('finding stop')
    try:
        series = minute_history['low'][-100:] \
                    .dropna().resample('5min').min()
        series = series[now.floor('1D'):]
        diff = np.diff(series.values)
        low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
        if (low_index) > 0:
            return series[low_index[-1]] - 0.01
        return current_value * default_stop
    except Exception as ex:
        print(ex)
    return current_value * default_stop

def run(market_open_dt, market_close_dt):
    tickers = get_tickers(market_open_dt)
    
    # Update initial state with info from tickers
    volume_today = {}
    prev_closes = {}
    for ticker in tickers:
        symbol = ticker['ticker']
        prev_closes[symbol] = ticker['prevClose']
        volume_today[symbol] = ticker['volume']
    
    symbols = [ticker['ticker'] for ticker in tickers]
    minute_history = get_1000m_history_data(symbols, market_open_dt)
    
    # Simulat trading with $10k
    portfolio_value = float(10000)

    # Keep track of what is being bought/sold
    positions = {}
    buy_prices = {}
    stop_prices = {}
    target_prices = {}

    def handle_trade(symbol, side, qty, limit_price):
        print('\n\nTrade update: ', symbol)
        if side == 'sell':
            qty = qty * -1
        positions[symbol] += qty

        action = 'Sold' if side == 'sell' else 'Bought'
        alert = f"{action} {abs(qty)} shares of {symbol} at ${limit_price}"
        if action == 'Sold':
            profit_percent = (
                (float(limit_price) - buy_prices[symbol]) / buy_prices[symbol] * 100
            )
            alert += ' ({}{}%)'.format('+' if profit_percent > 0 else '', '%.2f' % profit_percent)
        print(alert)
    
    def handle_bar(symbol, time, data):
        # print(data)
        close = data['close']
        print('{}: {} - ${}'.format(time, symbol, close))

        time -= timedelta(microseconds=time.microsecond)

        # Aggregate the minute history
        minute_history[symbol].loc[time] = [
            data['open'],
            data['high'],
            data['low'],
            data['close'],
            data['volume']
        ]
        volume_today[symbol] += data['volume']

        # Now check for buy/sell conditions
        since_market_open = time - market_open_dt
        until_market_close = market_close_dt - time
        # print('minutes since market open:', since_market_open.seconds // 60)
        # print('minutes till market close: ', until_market_close.seconds // 60)

        # Already holding shares?
        position = positions.get(symbol, 0)

        # Check after 9:45AM for buy signals
        if (
            since_market_open.seconds // 60 > 15 and
            position == 0
        ):
            # print('close:', close)
            # print('compared to: ', prev_closes[symbol])
            # Get the change percent since yesterday's market close
            daily_pct_change = (close - prev_closes[symbol]) / prev_closes[symbol]
            # print(f'Daily % change: {daily_pct_change}')
            if ( daily_pct_change > .04 and volume_today[symbol] > 30000 ):
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
                    print('MACD is < 0 or is downtrending')
                    return
                hist = ta.trend.macd(
                    minute_history[symbol]['close'].dropna(),
                    window_fast=40,
                    window_slow=60
                )
                if hist[-1] < 0 or np.diff(hist)[-1] < 0:
                    print('MACD < 0 or diff is < 0')
                    return
                stop_price = find_stop(close, minute_history[symbol], time)
                stop_prices[symbol] = stop_price

                target_prices[symbol] = close + (
                    (close - stop_price) * 3
                )
                shares_to_buy = portfolio_value * risk // (
                    close - stop_price
                )
                if shares_to_buy == 0:
                    shares_to_buy = 1
                shares_to_buy -= positions.get(symbol, 0)
                if shares_to_buy <= 0:
                    return
                
                print('Submitting buy for {} shares of {} at {}'.format(
                    shares_to_buy, symbol, close
                ))
                try:
                    handle_trade(
                        symbol=symbol,
                        qty=shares_to_buy,
                        side='buy',
                        limit_price=close
                    )
                    buy_prices[symbol] = close
                except Exception as e:
                    print(e)
                return
        
        # Check for liquidation signals
        elif (
            position > 0 and
            since_market_open.seconds // 60 >= 24 and
            until_market_close.seconds // 60 > 15
        ):
            print('Currently holding')
            # Sell for loss if price is below stop price
            # Sell for loss if price is below purchase and MACD < 0
            # Sell for profit if it's above target price
            hist = ta.trend.macd(
                minute_history[symbol]['close'].dropna(),
                window_fast=13,
                window_slow=21
            )
            if (
                close <= stop_prices[symbol] or
                (close >= target_prices[symbol] and hist[-1] <= 0) or
                (close <= buy_prices[symbol] and hist[-1] <= 0)
            ):
                print('Submitting sell for {} shares of {} at {}'.format(
                    position, symbol, close
                ))
                try:
                    handle_trade(
                        symbol=symbol,
                        side='sell',
                        qty=position,
                        limit_price=close
                    )
                    buy_prices[symbol] = None
                except Exception as e:
                    print(e)
            return
        
        # Check for end of day
        if position > 0 and until_market_close.seconds // 60 <= 15:
            # Liquidate remaining positions
            print('Trading over, liquidating remaining position in {}'.format(symbol))
            handle_trade(
                symbol=symbol,
                side='sell',
                qty=position,
                limit_price=close
            )
            buy_prices[symbol] = None
            symbols.remove(symbol)
            if len(symbols) <= 0:
                print('Stream connection closed.')
            print(f'Deregistered {symbol}.')

        # Deregister watchers at end of the day
        elif until_market_close.seconds // 60 <= 1:
            symbols.remove(symbol)
            if len(symbols) <= 0:
                print('Stream connection closed.')

        print()

    print('Trading {} symbols.'.format(len(symbols)))

    # Simulate trading 15Min bars
    # by retrieving the day's bars
    # and calling handle_minute_bar on each one
    market_data = get_market_bar_data(symbols, market_open_dt, market_close_dt)
    num_traders = 0
    for symbol in symbols:
        symbol_data = market_data[symbol]
        symbol_data = symbol_data[symbol_data['close'] > 0]
        num_bars = len(symbol_data)
        print(f'{symbol}: {num_bars}')
        if num_bars == 26:
            num_traders += 1
            # print(f'Trading {symbol}')
            # for time in symbol_data.index:
                # handle_bar(symbol, time, symbol_data.loc[time])
    print(num_traders)

if __name__ == "__main__":
    # get the market open time
    nyc = timezone('America/New_York')
    today_str = sys.argv[1]
    today = datetime.strptime(today_str, '%Y-%m-%d').astimezone(nyc)
    calendar = api.get_calendar(start=today_str, end=today_str)[0]
    if calendar.date.strftime('%Y-%m-%d') == today_str:
        market_open = today.replace(
            hour=calendar.open.hour,
            minute=calendar.open.minute,
            second=0,
            microsecond=0
        ).astimezone(nyc)
        market_close = today.replace(
            hour=calendar.close.hour,
            minute=calendar.close.minute,
            second=0,
            microsecond=0
        ).astimezone(nyc)
        print(f'The market opened at: {market_open}')
        print(f'The market closed at: {market_close}')
        print()

        run(market_open, market_close)
        # open = datetime.isoformat(pd.Timestamp(market_open))
        # close = datetime.isoformat(pd.Timestamp(market_close))
        # bars = api.get_barset('AAPL', '15Min', start=open, end=close, limit=1000).df
        # print(len(bars))
    else:
        print(f'Market was not open on {today_str}')
