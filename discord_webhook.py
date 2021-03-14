from discord import Webhook, RequestsWebhookAdapter

def notify_intro(num_symbols):
    summary = """
**Today's trading plan**

Screening criteria:
- Price between $5 - $13
- previous day change > 3.5%
- previous dollar volume > 500,000

Buying criteria:
- Today's change is > 4%
- Today's volume is > 30,000
- MACD is positive and increasing

Selling criteria:
- Price is below stop price
- Price is below purchase and MACD < 0
- Sell for profit if price is above target

Today I will be watching {} symbols at 1 minute intervals.
""".format(num_symbols)
    _send_messsage(summary)


def notify_trade(action):
    _send_messsage('TRADE: ' + action)

def _send_messsage(message):
    webhook_url = 'https://discord.com/api/webhooks/820019542327558144/uQDd4qJw6Ho03ZYPgEG_A3x6mjwQBBze0uwefxp8Kd79OI_-9_DUTL9CvMdB5DsfEr3E'
    webhook = Webhook.from_url(webhook_url, adapter=RequestsWebhookAdapter())
    webhook.send(message)
