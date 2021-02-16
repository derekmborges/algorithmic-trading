
def cci_check(cci, prev_cci):
    if cci and prev_cci:
        if (cci < 0 and prev_cci > 0) or (cci > 0 and prev_cci < 0):
              return True  
    return False

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


        # Checking < -100 or > 100
        # if cci is None:
        #     Buy.append(np.NaN)
        #     Sell.append(np.NaN)
        # elif not position:
        #     if cci < -100 and not waitingBuy:
        #         waitingBuy = True
        #         Buy.append(np.NaN)
        #         Sell.append(np.NaN)
        #     elif cci > -100 and waitingBuy:
        #         print("Buying shares at $%.2f" % (data['Close'][i]))
        #         Buy.append(data['Close'][i])
        #         Sell.append(np.NaN)
        #         position = 1
        #         waitingBuy = False
        #     else:
        #         Buy.append(np.NaN)
        #         Sell.append(np.NaN)
        # else:
        #     if cci > 100 and not waitingSell:
        #         waitingSell = True
        #         Buy.append(np.NaN)
        #         Sell.append(np.NaN)
        #     elif cci < 100 and waitingSell:
        #         print("Selling shares at $%.2f\n" % (data['Close'][i]))
        #         Buy.append(np.NaN)
        #         Sell.append(data['Close'][i])
        #         position = None
        #         waitingSell = False
        #     else:
        #         Buy.append(np.NaN)
        #         Sell.append(np.NaN)