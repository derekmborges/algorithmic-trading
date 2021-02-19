
def rsi_check(rsi, prev_rsi, position):
    if rsi:
        if not position and rsi < 30:
            return 'Buy'
        if position and rsi > 70:
            return 'Sell'
    return None
