
def vwap_check(vwap, price, position):
    if vwap and price:
        if not position and price > (vwap * 1.005):
            return 'Buy'
        if position and price < (vwap * 0.995):
            return 'Sell'
    return None
