
def stoch_check(stoch, position):
    if not position and stoch < 20:
        return True
    if position and stoch > 80:
        return True
    return False
