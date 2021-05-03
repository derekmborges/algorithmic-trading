from datetime import datetime, timedelta
import pandas as pd
pd.set_option('mode.chained_assignment', None)
from alpaca_trade_api import REST
import discord_webhook
import statistics as stats

api = REST()

# Retrieve all trade activities for the week
today = datetime.today()
monday = today - timedelta(days=4)
today_str = f'{today.date()}T23:59:59Z'
monday_str = f'{monday.date()}T00:00:00Z'
print(f'Results from {monday_str} to {today_str}')
activities = api.get_activities(activity_types='FILL', after=monday_str, until=today_str)

# Retrieve all currently owned symbols
positions = api.list_positions()
owned_symbols = [position.symbol for position in positions]

# Need to store the symbols that were sold out
# and the entry/exit prices
sold_symbols = []
buy_prices = {}
sell_prices = {}

# Loop through all the trades and pair up the buy/sell activities
for activity in activities:
    symbol = activity.symbol
    if activity.side == 'sell' \
        and symbol not in owned_symbols \
            and symbol not in sold_symbols:
        sold_symbols.append(symbol)
        sell_prices[symbol] = activity.price
    elif activity.side == 'buy' and symbol in sold_symbols:
        buy_prices[symbol] = activity.price

# Calculate the profit and build the alert
alert = '**This Week\'s Results**\n'
profits = []
for symbol in sold_symbols:
    if symbol in buy_prices.keys():
        percent = (float(sell_prices[symbol]) - float(buy_prices[symbol])) / float(buy_prices[symbol]) * 100
        profits.append(percent)
        print('{}: {}%'.format(symbol, '%.2f' % percent))
        alert += '{}: {}%\n'.format(symbol, '%.2f' % percent)

# Calculate stats
max_profit = max(profits)
worst_loss = min(profits)
average_profit = stats.mean(profits)
total_profit = sum(profits)

print('\nBEST:  {}%'.format('%.2f' % max_profit))
print('WORST: {}%'.format('%.2f' % worst_loss))
print('AVG:   {}%'.format('%.2f' % average_profit))
print('TOTAL: {}%'.format('%.2f' % total_profit))
# Notify Discord
alert += '\n*Summary*'
alert += '\nBest:  {}%'.format('%.2f' % max_profit)
alert += '\nWorst: {}%'.format('%.2f' % worst_loss)
alert += '\nAvg:   {}%'.format('%.2f' % average_profit)
alert += '\nTotal: {}%'.format('%.2f' % total_profit)
discord_webhook._send_messsage(alert)
