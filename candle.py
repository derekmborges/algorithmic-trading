import statistics as stats
import pandas as pd
from pandas.core.series import Series

class Candle:
    def __init__(self, series: Series):
        self.open = float(series['open'])
        self.high = float(series['high'])
        self.low = float(series['low'])
        self.close = float(series['close'])
        self.is_bearish = self.close < self.open
        self.is_bullish = self.close > self.open

    def get_body(self):
        return self.close - self.open if self.is_bullish \
                else self.open - self.close

    def get_body_center(self):
        return stats.median([self.open, self.close])
    