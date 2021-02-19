
def cci_check(cci, prev_cci, position):
    # Checking < -100 or > 100
    if cci and prev_cci:
        if not position and cci < -100 and prev_cci < -100:
            return 'Buy'
        elif position and cci > 100 and prev_cci > 100:
            return 'Sell'
    return None

    # if cci and prev_cci:
    #     if (cci < 0 and prev_cci > 0) or (cci > 0 and prev_cci < 0):
    #         return True
    # return False

        # elif cci < 0:
        #     if position is None:
        #         print("Buying shares at $%.2f" % (data['Close'][i]))
        #         Buy.append(data['Close'][i])
        #         Sell.append(np.NaN)
        #         position = 1
        #     elif prev_cci >= 0:
        #         print("Selling shares at $%.2f\n" % (data['Close'][i]))
        #         Buy.append(np.NaN)
        #         Sell.append(data['Close'][i])
        #         position = None
        #     else:
        #         Buy.append(np.NaN)
        #         Sell.append(np.NaN)
        # elif cci > 0 and prev_cci <= 0 and position is not None:
        #     print("Selling shares at $%.2f\n" % (data['Close'][i]))
        #     Buy.append(np.NaN)
        #     Sell.append(data['Close'][i])
        #     position = None
        # else:
        #     Buy.append(np.NaN)
        #     Sell.append(np.NaN)
