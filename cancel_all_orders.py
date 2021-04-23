
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
load_dotenv()

api = tradeapi.REST()
api.cancel_all_orders()