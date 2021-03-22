import time
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

# Select the best momentum stocks right now
df_buy = select_momentum_stocks()
print(df_buy)
buy_symbols = df_buy['symbol'].tolist()
buy_qty = df_buy['qty'].tolist()
close_prices = df_buy['close'].tolist()

# Store what needs to be bought/sold
buy_amounts = {}
buy_prices = {}
sell_amounts = {}

# Store the quantities to buy and prices for each symbol
for i in range(0, len(buy_symbols)):
    symbol = buy_symbols[i]
    qty = buy_qty[i]
    if qty <= 0:
        qty = 1
    buy_amounts[symbol] = qty
    buy_prices[symbol] = close_prices[i]

# Get all current positions
existing_positions = api.list_positions()

# Determine if need to buy more or liquidate some of its positions
for position in existing_positions:
    if position.symbol in buy_symbols:
        delta = buy_amounts[symbol] - int(position.qty)
        if delta >= 0:
            buy_amounts[symbol] = delta
        else:
            sell_amounts[symbol] = abs(delta)
            buy_amounts[symbol] = 0
    else:
        sell_amounts[position.symbol] = int(position.qty)

# if len(buy_amounts.keys()) > 0: print('BUYING')
# for symbol in buy_amounts.keys():
#     qty = buy_amounts[symbol]
#     print(f'{symbol}: {qty}')

# if len(sell_amounts.keys()) > 0: print('\nSELL')
# for symbol in sell_amounts.keys():
#     qty = sell_amounts[symbol]
#     print(f'{symbol}: {qty}')

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
    open_orders = api.list_orders()
    if open_orders:
        for order in open_orders:
            qty = order.qty
            try:
                api.cancel_order(order.id)
                # submit new market order
                api.submit_order(
                    symbol=symbol, qty=str(qty), side='sell',
                    type='market', time_in_force='day'
                )
            except Exception:
                continue
    else:
        complete = True
