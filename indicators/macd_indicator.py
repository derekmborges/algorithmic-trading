
def macd_check(macd, prev_macd, signal, prev_signal, position):
    if macd and prev_macd and signal and prev_signal:
        # if not position and macd > 0 and macd > signal:
        if not position and macd > signal and prev_macd <= prev_signal:
            return 'Buy'

        # If bot is holding shares and is waiting for a trigger to sell
        elif position and macd < signal:
            return 'Sell'
    return None
