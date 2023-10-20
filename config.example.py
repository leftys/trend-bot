# Our Binance credentials.
API_KEY = ''
API_SECRET = ''
SANDBOX_MODE = True

# Provide pair.
SYMBOL = "BTC/USDT"

# Tokens per trade.
QUANTITY = 0.1

# Provide timeframe to trade.
TIMEFRAME = '1h'

# Supertrend parameters.
ATR_FACTOR = 3
PERIOD = 50

# Initialize the bot by setting a lookback period. ( In a 1-min strategy, LOOKBACK = 90 --> Last 90 minutes )
LOOKBACK = PERIOD + 1

# How many logs would you like to display on cmd screen (changes visual only).
LOGS_DISPLAYED = 10

CLOSE_AFTER_HOURS = 3

TELEGRAM_BOT_TOKEN = ''
# You can get it on https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates
TELEGRAM_CHAT_ID = ''

SENTRY_URL = ''
