import requests
import logging

import sentry_sdk
import sentry_sdk.integrations.logging

import config

if config.SENTRY_URL:
    sentry_logging = sentry_sdk.integrations.logging.LoggingIntegration(
        level = logging.INFO,  # Capture info and above as breadcrumbs
        event_level = logging.ERROR  # Send errors as events
    )
    sentry_sdk.init(
        config.SENTRY_URL,
        traces_sample_rate = 0,
        propagate_traces = False,
        integrations = [sentry_logging],
    )

def send_telegram_message(message: str) -> dict:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message.replace('\n', '%0A')}
    response = requests.post(url, data=data)
    return response.json()

