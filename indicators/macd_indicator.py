
def macd_check(macd, signal, position):
    if macd and signal:
        if not position and macd > 0 and macd > signal:
            return True
        elif position and macd < signal:
            return True
    return False
