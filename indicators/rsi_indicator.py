
def rsi_check(rsi, prev_rsi, position):
    if rsi:
        if not position and rsi < 30:
            return True
        if position and rsi > 70:
            return True
    # alternative
    # if rsi and prev_rsi:
        # if not position and rsi < 50 and prev_rsi >= 50:
        #     return True
        # if position and rsi > 50 and prev_rsi <= 50:
        #     return True
        
    return False
