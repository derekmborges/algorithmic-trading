import time
from pytz import timezone
from datetime import datetime
from google.cloud import storage
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from select_momentum_stocks import select_momentum_stocks
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

# Check if the market is open today
nyc = timezone('America/New_York')
today = datetime.today().astimezone(nyc)
today_str = today.strftime('%Y-%m-%d')
today = datetime.isoformat(pd.Timestamp(
    datetime.today().astimezone(nyc)
))
try:
    calendar = api.get_calendar(start=today, end=today)[0]
except Exception as e:
    print(e)
    print('Market must not be open')
    calendar = None
if calendar and calendar.date.strftime('%Y-%m-%d') == today_str:

    # Select the best momentum stocks right now
    df_buy = select_momentum_stocks()
    print(df_buy)

    # Store today's optimized portfolio
    buy_symbols = df_buy['symbol'].tolist()
    buy_qty = df_buy['qty'].tolist()
    close_prices = df_buy['close'].tolist()

    # # Store what needs to be bought/sold
    buy_amounts = {}
    buy_prices = {}
    sell_amounts = {}

    # Store the desired quantities and close prices for each symbol
    for i in range(0, len(buy_symbols)):
        symbol = buy_symbols[i]
        qty = buy_qty[i]
        if qty <= 0:
            qty = 1
        buy_amounts[symbol] = qty
        buy_prices[symbol] = close_prices[i]

    print('\nTODAY\'S ALGORITHM CALLS FOR:')
    for symbol in buy_amounts.keys():
        qty = buy_amounts[symbol]
        print(f'{symbol}: {qty}')

    # Get all current positions
    existing_positions = api.list_positions()
    print('\nCURRENT POSITIONS:')
    for position in existing_positions:
        print(f'{position.symbol}: {position.qty}')

    # Re-organization logic
    for position in existing_positions:
        # If the symbol is in our updated portfolio
        # then we still need to hold some shares
        if position.symbol in buy_symbols:
            symbol = position.symbol

            # Determine how many shares (if any)
            # need to be bought or sold to match up with
            # today's optimized portfolio
            delta = buy_amounts[symbol] - int(position.qty)

            # Need to buy more
            if delta > 0:
                buy_amounts[symbol] = delta
            
            # Need to sell some
            elif delta < 0:
                sell_amounts[symbol] = abs(delta)
                del buy_amounts[symbol]
            
            # No action needed
            else:
                del buy_amounts[symbol]

        # The stock has dropped off the list
        # so we need to sell all shares
        else:
            sell_amounts[position.symbol] = int(position.qty)

    if len(buy_amounts.keys()) > 0: print('\nBUYING:')
    for symbol in buy_amounts.keys():
        qty = buy_amounts[symbol]
        print(f'{symbol}: {qty}')

    if len(sell_amounts.keys()) > 0: print('\nSELLING:')
    for symbol in sell_amounts.keys():
        qty = sell_amounts[symbol]
        print(f'{symbol}: {qty}')

    # Generate buy orders
    for symbol in buy_amounts.keys():
        qty = buy_amounts[symbol]
        price = buy_prices[symbol]
        print(f'Submitting buy order for {qty} shares of {symbol}')
        discord_webhook.notify_trade(f'Submitting buy order for {qty} shares of {symbol}')
        api.submit_order(
            symbol=symbol, qty=str(qty), side='buy',
            type='limit', limit_price=str(price), time_in_force='day'
        )

    # Generate sell orders
    for symbol in sell_amounts.keys():
        qty = sell_amounts[symbol]
        print(f'Submitting sell order for {qty} shares of {symbol}')
        discord_webhook.notify_trade(f'Submitting sell order for {qty} shares of {symbol}')
        api.submit_order(
            symbol=symbol, qty=str(qty), side='sell',
            type='market', time_in_force='day'
        )

    # Wait 1 minute and see if any orders were not fulfilled
    # If the limit price was not fulfilled, replace with market order
    complete = False
    while not complete:
        time.sleep(60)
        open_orders = api.list_orders(status='open')
        if open_orders:
            for order in open_orders:
                qty = order.qty
                symbol = order.symbol
                try:
                    print(f'Cancelling order for {qty} shares of {symbol}')
                    api.cancel_order(order.id)
                    # submit new market order
                    print(f'Resubmitting order for {qty} shares of {symbol}')
                    api.submit_order(
                        symbol=symbol, qty=str(qty), side='buy',
                        type='market', time_in_force='day'
                    )
                except Exception as e:
                    print('Error with order:', e)
        else:
            complete = True
else:
    discord_webhook.notify_trade('Arg! The market is not open today.')
