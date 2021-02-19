import sys
import time as t
from datetime import datetime as dt, timedelta
import pandas as pd
from pandas.plotting import register_matplotlib_converters
import numpy as np
from indicators.cci_indicator import cci_check
from indicators.macd_indicator import macd_check
from indicators.rsi_indicator import rsi_check
from indicators.stoch_indicator import stoch_check
from helpers import is_market_open, portfolio_input
from stock_finder import get_10_best_active_stocks
import finnhub
import matplotlib.pyplot as plot
plot.style.use('fivethirtyeight')
register_matplotlib_converters()

def main(args):
    # Retrieve API Key
    from secrets import FINNHUB_TOKEN
    finnhub_client = finnhub.Client(FINNHUB_TOKEN)

    # If no symbols were passed in
    # Retrieve 
    try:
        symbols = [args[1]]
    except IndexError:
        print('No symbol provided. Retrieving top 10 from Yahoo Finance...')
        symbols = get_10_best_active_stocks()

    print(symbols)
    confirmation = input('Are these the stocks you want to test? (Y/n): ')
    if confirmation.lower() != 'y':
        return

    interval = '1min'
    trading_day = dt.strftime((dt.now() - timedelta(1)), '%Y-%m-%d')
    results = {}

    for symbol in symbols:
        pass
        # TODO


main(sys.argv)
