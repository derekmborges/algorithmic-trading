import alpaca_trade_api as tradeapi
import pandas as pd
import statistics
import sys
import time
from datetime import datetime, timedelta
from pytz import timezone
from dotenv import load_dotenv
load_dotenv()

def chunks(l, n):
    n = max(1, n)
    return (l[i:i+n] for i in range(0, len(l), n))

stocks_to_hold = 75 # Max 200

# Only stocks with prices in this range will be considered.
# Currently $5 - $20 works the best
min_stock_price = 5
max_stock_price = 20

# API datetimes will match this format. (-04:00 represents the market's TZ.)
api_time_format = '%Y-%m-%dT%H:%M:%S.%f-04:00'

# Rate stocks based on the volume's deviation from the previous 5 days and
# momentum. Returns a dataframe mapping stock symbols to ratings and prices.
# Note: If algo_time is None, the API's default behavior of the current time
# as `end` will be used. We use this for live trading.
def get_ratings(symbols, algo_time = None):
    ratings = pd.DataFrame(columns=['symbol', 'rating', 'price'])
    batch_size = 200 # The maximum number of stocks to request data for
    window_size = 5 # The number of days of data to consider
    
    # For backtesting
    if algo_time is not None:
        distance = window_size + 1
        market_days = 0
        # Determine the start date that contains `window_size` market days
        while market_days != window_size:
            start_date = algo_time.date() - timedelta(days=distance)
            calendars = api.get_calendar(start_date.strftime("%Y-%m-%d"), algo_time.strftime("%Y-%m-%d"))
            market_days = len(calendars)
            distance += 1
    else:
        start_date = None
    # print(start_date.strftime("%Y-%m-%d"))
    # print(algo_time.strftime("%Y-%m-%d"))
    symbols_batched = list(chunks(list(set(symbols)), batch_size))
    for symbol_batch in symbols_batched:
        # Retrieve data for this batch of symbols.
        bars_batch = api.get_barset(','.join(symbol_batch),
                            '1D',
                            window_size,
                            api_format(start_date) if start_date else None,
                            api_format(algo_time) if algo_time else None)
        for symbol in symbol_batch:
            bars = bars_batch[symbol]
            # print(f'{symbol}: {len(bars)}')

            if len(bars) == window_size:
                # Make sure we aren't missing the most recent data.
                latest_bar = bars[-1].t.to_pydatetime().astimezone(
                    timezone('EST')
                )
                if algo_time and (algo_time - latest_bar).days > 1:
                    # print(f'The latest bar is too far away: {(algo_time - latest_bar).days} days')
                    continue

                # Now, if the stock is within our target range, rate it.
                price = bars[-1].c
                # print(price)
                if price <= max_stock_price and price >= min_stock_price:
                    price_change = price - bars[0].c
                    # Calculate standard deviation of previous volumes
                    past_volumes = [bar.v for bar in bars[:-1]]
                    volume_stdev = statistics.stdev(past_volumes)
                    if volume_stdev == 0:
                        # The data for the stock might be low quality.
                        continue
                    # Then, compare it to the change in volume since yesterday.
                    volume_change = bars[-1].v - bars[-2].v
                    volume_factor = volume_change / volume_stdev
                    # Rating = momentum * Number of volume standard deviations.
                    rating = price_change/bars[0].c * volume_factor
                    # print(f'{symbol}: {rating}')
                    if rating > 0 and rating < 2:
                        ratings = ratings.append({
                            'symbol': symbol,
                            'rating': rating,
                            'price': price
                        }, ignore_index=True)
                # print()

    ratings = ratings.sort_values('rating', ascending=False)
    ratings = ratings.reset_index(drop=True)
    return ratings[:stocks_to_hold]


def get_shares_to_buy(ratings_df, portfolio):
    total_rating = ratings_df['rating'].sum()
    shares = {}
    for _, row in ratings_df.iterrows():
        shares[row['symbol']] = int(
            row['rating'] / total_rating * portfolio / row['price']
        )
    return shares


# Returns a string version of a timestamp compatible with the Alpaca API.
def api_format(dt):
    return dt.strftime(api_time_format)

def backtest(api, days_to_test, portfolio_amount):
    # This is the collection of stocks that will be used for backtesting.
    # Note: for longer testing windows, this should be replaced with a list
    # of symbols that were active during the time period you are testing.
    assets = api.list_assets('active')
    symbols = [asset.symbol for asset in assets if asset.tradable]
    # symbols = ['AAPL','MSFT','KO','WMT','TSLA']
    print(f'Total symbols: {len(symbols)}')

    now = datetime.now(timezone('EST'))
    beginning = now - timedelta(days=days_to_test)

    # The calendars API will let us skip over market holidays and handle early
    # market closures during our backtesting window.
    calendars = api.get_calendar(
        start=beginning.strftime("%Y-%m-%d"),
        end=now.strftime("%Y-%m-%d")
    )
    shares = {}
    entry_prices = {}

    # Build results dictionary
    results = {}
    num_ranges = 5
    range_width = int((max_stock_price - min_stock_price) / num_ranges)
    while range_width == 0:
        num_ranges -= 1
        range_width = int((max_stock_price - min_stock_price) / num_ranges)

    for price in range(min_stock_price, max_stock_price, range_width):
        lower_range = int(price)
        upper_range = int(price + range_width)
        if upper_range > max_stock_price:
            upper_range = max_stock_price
        r = f'{lower_range}-{upper_range}'
        results[r] = []

    cal_index = 0
    for calendar in calendars:
        # See how much we got back by holding the last day's picks overnight
        new_amount, profits = get_value_of_assets(api, shares, entry_prices, calendar.date)
        portfolio_amount += new_amount
        print('Portfolio value on {}: ${:0.2f}'.format(calendar.date.strftime(
            '%Y-%m-%d'), portfolio_amount)
        )

        # Update the price range's results
        for symbol in profits:
            price = entry_prices[symbol]
            for range_str in results:
                range_arr = str(range_str).split('-')
                lower = float(range_arr[0])
                upper = float(range_arr[1])
                if price >= lower and price <= upper:
                    results[range_str].append(profits[symbol])
                    break

        if cal_index == len(calendars) - 1:
            # We've reached the end of the backtesting window.
            break

        # Reset the entry prices
        entry_prices = {}

        # Get the ratings for a particular day
        ratings = get_ratings(symbols, timezone('EST').localize(calendar.date))
        shares = get_shares_to_buy(ratings, portfolio_amount)
        for _, row in ratings.iterrows():
            # "Buy" our shares on that day and subtract the cost.
            shares_to_buy = shares[row['symbol']]
            entry_prices[row['symbol']] = row['price']
            cost = row['price'] * shares_to_buy
            portfolio_amount -= cost
        cal_index += 1

    # Print market (S&P500) return for the time period
    sp500_bars = api.get_barset('SPY',
                                    '1D',
                                    start=api_format(calendars[0].date),
                                    end=api_format(calendars[-1].date))['SPY']
    sp500_change = (sp500_bars[-1].c - sp500_bars[0].c) / sp500_bars[0].c
    print('S&P 500 change during backtesting window: {:.4f}%'.format(
        sp500_change*100)
    )

    print('\nAverage results per price:')
    for price_range in results:
        print('{}: {:.4f}%'.format(
            price_range,
            statistics.mean(results[price_range]) if results[price_range] else 0
        ))
    print('\nBest results per price:')
    for price_range in results:
        print('{}: {:.4f}%'.format(
            price_range,
            max(results[price_range]) if results[price_range] else 0
        ))
    print('\nWorst results per price:')
    for price_range in results:
        print('{}: {:.4f}%'.format(
            price_range,
            min(results[price_range]) if results[price_range] else 0
        ))
    print('\nTotal results per price:')
    for price_range in results:
        print('{}: {:.4f}%'.format(
            price_range,
            sum(results[price_range]) if results[price_range] else 0
        ))
    print()
    return portfolio_amount


# Used while backtesting to find out how much our portfolio would have been
# worth the day after we bought it.
def get_value_of_assets(api, shares_bought, prices_bought, on_date):
    if len(shares_bought.keys()) == 0:
        return (0, {})

    total_value = 0
    profits = {}
    formatted_date = api_format(on_date)

    symbols_bought = list(shares_bought.keys())
    bars_group = api.get_barset(','.join(symbols_bought),
                            '1D',
                            1,
                            formatted_date,
                            formatted_date)
    for symbol in shares_bought:
        if len(bars_group[symbol]) >= 1:
            # print(f'{symbol}: {bars_group[symbol][0].o}')
            total_value += shares_bought[symbol] * bars_group[symbol][0].o
            profits[symbol] = (bars_group[symbol][0].o - prices_bought[symbol]) / prices_bought[symbol] * 100
        else:
            print(f'{symbol} data not found. Using entry price')
            total_value += shares_bought[symbol] * prices_bought[symbol]
            profits[symbol] = 0.0
    return (total_value, profits)


def run_live(api):
    # See if we've already bought or sold positions today. If so, we don't want to do it again.
    # Useful in case the script is restarted during market hours.
    bought_today = False
    sold_today = False

    positions = api.list_positions()
    if not positions:
        sold_today = True

    try:
        # The max stocks_to_hold is 200, so we shouldn't see more than 400
        # orders on a given day.
        orders = api.list_orders(
            after=api_format(datetime.today()),
            limit=400,
            status='all'
        )
        for order in orders:
            if order.side == 'buy':
                bought_today = True
                break
    except:
        # We don't have any orders, so we've obviously not done anything today.
        pass

    while True:
        # We'll wait until the market's open to do anything.
        clock = api.get_clock()
        if clock.is_open and not bought_today:
            if sold_today:
                # Wait to buy
                time_until_close = clock.next_close - clock.timestamp
                print('Seconds till close: ', time_until_close.seconds)
                # We'll buy our shares a couple minutes before market close.
                if time_until_close.seconds <= 120:
                    print('Buying positions...')
                    portfolio_cash = float(api.get_account().cash)
                    assets = api.list_assets()
                    symbols = [asset.symbol for asset in assets if asset.tradable]
                    ratings = get_ratings(symbols, None)
                    shares_to_buy = get_shares_to_buy(ratings, portfolio_cash)
                    for symbol in shares_to_buy:
                        api.submit_order(
                            symbol=symbol,
                            qty=shares_to_buy[symbol],
                            side='buy',
                            type='market',
                            time_in_force='day'
                        )
                    print('Positions bought.')
                    bought_today = True
            else:
                # We need to sell our old positions before buying new ones.
                time_after_open = clock.next_open - clock.timestamp
                # We'll sell our shares just a minute after the market opens.
                if time_after_open.seconds >= 60:
                    print('Liquidating positions.')
                    api.close_all_positions()
                    sold_today = True
        time.sleep(30)



if __name__ == '__main__':
    api = tradeapi.REST()

    if len(sys.argv) < 2:
        print('Error: please specify a command; either "run" or "backtest <cash balance> <number of days to test>".')
    else:
        if sys.argv[1] == 'backtest':
            # Run a backtesting session using the provided parameters
            start_value = float(sys.argv[2])
            testing_days = int(sys.argv[3])
            portfolio_value = backtest(api, testing_days, start_value)
            portfolio_change = (portfolio_value - start_value) / start_value
            print('Portfolio change over {} days: {:.4f}%'.format(testing_days, portfolio_change*100))
        elif sys.argv[1] == 'run':
            run_live(api)
        else:
            print('Error: Unrecognized command ' + sys.argv[1])