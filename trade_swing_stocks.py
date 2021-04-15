import time
from pytz import timezone
from datetime import datetime
from google.cloud import storage
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
from select_swing_stocks import select_swing_stocks
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

    # Select the swing stocks to buy, sell, and hold
    df_buy, df_sell, df_hold = select_swing_stocks()
    
    alert = f'**Daily Swing Trade Alert**\n'

    # Sell all stocks in DataFrame
    if not df_sell.empty:
        df_sell = df_sell.set_index('symbol', drop=True)
        print('\nSELLING:')
        alert += '\n**SELL (Estimated gains)**'
        for symbol in df_sell.index:
            qty = df_sell['qty'][symbol]
            alert += f'\n{symbol}: {qty}'
            print(f'{symbol}: {qty}')
            latest_price = df_sell['latest_price'][symbol]
            purchase_price = df_sell['purchase_price'][symbol]
            gain = (latest_price - purchase_price) / purchase_price * 100
            alert += ' ({}{}%)'.format(
                '+' if gain > 0 else '',
                '%.1f' % gain
            )

            # Submit limit sell order
            api.submit_order(
                symbol=symbol, qty=str(qty), side='sell',
                type='limit', limit_price=str(latest_price), time_in_force='day'
            )
    
    # Buy stocks in DataFrame
    if not df_buy.empty:
        df_buy = df_buy.set_index('symbol', drop=True)
        print('\nBUYING:')
        alert += '\n\n**BUY**'
        for symbol in df_buy.index:
            qty = df_buy['qty'][symbol]
            price = df_buy['close'][symbol]
            print(f'{symbol}: {qty}')
            alert += f'\n{symbol}: {qty}'

            # Submit limit sell order
            api.submit_order(
                symbol=symbol, qty=str(qty), side='buy',
                type='limit', limit_price=str(price), time_in_force='day'
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
                side = order.side
                try:
                    print(f'Cancelling {side} order for {qty} shares of {symbol}')
                    api.cancel_order(order.id)
                    # submit new market order
                    print(f'Resubmitting {side} order for {qty} shares of {symbol}')

                    api.get_last_trade(symbol)
                    api.submit_order(
                        symbol=symbol, qty=str(qty), side=side,
                        type='market', time_in_force='day'
                    )
                except Exception as e:
                    print(f'Error with {symbol} order:', e)
                    discord_webhook.send_error(f'Error trying to fill {symbol}:', e)
        else:
            complete = True
    
    # Send trade alert
    discord_webhook._send_messsage(alert)

else:
    discord_webhook.notify_info('Arg! The market is not open today.')
