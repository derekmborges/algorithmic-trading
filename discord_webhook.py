from discord import Webhook, RequestsWebhookAdapter

def notify_intro(num_symbols):
    summary = """
**New bot trading plan**

Screening criteria:
- 10 highest momentum stocks based on closing prices over 125 days.

Buying criteria:
- N/A

Selling criteria:
- Stock not in the 10 highest momentum stocks of the last 125 days.

Today I will be watching {} symbols at 1 minute intervals.
""".format(num_symbols)
    _send_messsage(summary)


def notify_trade(action):
    _send_messsage('TRADE: ' + action)

def _send_messsage(message):
    webhook_url = 'https://discord.com/api/webhooks/820019542327558144/uQDd4qJw6Ho03ZYPgEG_A3x6mjwQBBze0uwefxp8Kd79OI_-9_DUTL9CvMdB5DsfEr3E'
    webhook = Webhook.from_url(webhook_url, adapter=RequestsWebhookAdapter())
    webhook.send(message)

def send_error(error):
    webhook_url = 'https://discord.com/api/webhooks/821144490130538526/Wyvu3uOiuqpZhEA7ljjTlQ178OTfujof318DlU-2fXAcMCdFReLcecs7mAaZNM_BE179'
    webhook = Webhook.from_url(webhook_url, adapter=RequestsWebhookAdapter())
    webhook.send(error)
