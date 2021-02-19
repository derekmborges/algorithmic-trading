
def stoch_check(stoch, position):
    if not position and stoch < 20:
        return 'Buy'
    if position and stoch > 80:
        return 'Sell'
    return False
