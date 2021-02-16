from dateutil.parser import parse

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def portfolio_input():
    global portfolio_size
    # Retrieve the user's portfolio value ($$$)
    portfolio_size = input('Enter the value of your portfolio: ')
    try:
        float(portfolio_size)
        return portfolio_size
    except ValueError:
        print('Value must be a number.\n')
        portfolio_size = input('Enter the value of your portfolio: ')
        float(portfolio_size)
        return portfolio_size

def is_market_open(datetime_string):
    dt = parse(str(datetime_string))
    return dt.time().hour >= 9 and dt.time().minute >= 30 and dt.time().hour < 16
