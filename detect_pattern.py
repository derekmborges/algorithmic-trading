from pandas.core.frame import DataFrame
from candle import Candle

def detect_bullish_patterns(df: DataFrame):
    """
    Finds all bullish candlestick patterns in a DataFrame with 3 daily candlesticks.

    :param df: DataFrame with 3 days of candlestick data
    """
    assert type(df) == DataFrame
    assert len(df) == 3

    candle1 = Candle(df.iloc[0])
    candle2 = Candle(df.iloc[1])
    candle3 = Candle(df.iloc[2])

    if is_bullish_engulfing(candle1, candle2, candle3):
        return 'bullish_engulfing'
    elif is_three_white_knights(candle1, candle2, candle3):
        return 'three_white_knights'
    elif is_morning_star(candle1, candle2, candle3):
        return 'morning_star'

    return ''


def is_bullish_engulfing(
    first_candle: Candle,
    second_candle: Candle,
    third_candle: Candle
):
    """
    Determines if the candles match a Bullish Engulfing candlestick pattern.
    Also checks for the long position entry requirement.
    """

    # Check for a red then green candle
    if first_candle.is_bearish and second_candle.is_bullish:
        
        # Check if green candle body engulfs the red candle
        if second_candle.close > first_candle.open \
            and second_candle.open < first_candle.close:
            
            # Check if the 3rd candle went higher than the green candle
            if third_candle.high > second_candle.high:
                return True
    
    return False


def is_three_white_knights(
    first_candle: Candle,
    second_candle: Candle,
    third_candle: Candle
):
    """
    Determines if the candles match a Three White Knights bullish candlestick pattern.
    """

    # First check for all green candles
    if first_candle.is_bullish and second_candle.is_bullish and third_candle.is_bullish:

        # Check that all open and closing prices increase every day
        if third_candle.open > second_candle.open > first_candle.open \
            and third_candle.close > second_candle.close > first_candle.close:
                return True
    
    return False

def is_morning_star(
    first_candle: Candle,
    second_candle: Candle,
    third_candle: Candle
):
    """
    Determines if the candles match a Morning Star bullish candlestick pattern.
    """

    # First check if the first is red and the third is green
    if first_candle.is_bearish and third_candle.is_bullish:

        # Make sure the second candle's body does not overlap the first or third
        if second_candle.close < first_candle.close and second_candle.open < first_candle.close \
            and second_candle.close < third_candle.open and second_candle.open < third_candle.open:

            # Then check if the second candle's body is much smaller than the first
            if (second_candle.get_body() / first_candle.get_body()) < 0.3:

                # Check if the third's body is also long (at least 60% of its size)
                if (third_candle.get_body() / first_candle.get_body()) >= 0.6:

                    # Finally check that the third candle overlaps the first
                    third_center = third_candle.get_body_center()
                    if third_center > (first_candle.close * 1.05) and third_center < (first_candle.open * 0.95):
                        return True
        
    return False
