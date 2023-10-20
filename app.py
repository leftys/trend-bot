from datetime import datetime
import ccxt
import requests
import schedule
import pandas as pd
import time

from supertrend import supertrend
import config


exchange: ccxt.Exchange = ccxt.binance({
    "apiKey": config.API_KEY,
    "secret": config.API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
    },
})

# To run binance paper trading (https://testnet.binancefuture.com/)
exchange.set_sandbox_mode(config.SANDBOX_MODE)

def table(values):
    '''currently not used'''
    first = values[0]
    keys = list(first.keys()) if isinstance(first, dict) else range(0, len(first))
    widths = [max([len(str(v[k])) for v in values]) for k in keys]
    string = ' | '.join(['{:<' + str(w) + '}' for w in widths])
    return "\n".join([string.format(*[str(v[k]) for k in keys]) for v in values])

def create_stop_order(side, stop_price, quantity, max_slip):
    print(f"Opening stop order {side} {quantity} at {stop_price}")
    autocancel_time = int(time.time()) + 60 * 60 * 8 # 8 hours
    order = exchange.create_order(
        config.SYMBOL, 'limit', side, amount = quantity, price = stop_price + max_slip * (1 if side == 'buy' else -1),
        params={'type': 'TAKE_PROFIT_LIMIT', 'stopPrice': stop_price, 'timeInForce': 'GTD', 'newClientOrderId': f'btc-{side}-stop-limit', 'goodTillDate': autocancel_time * 1000}
    )
    print(order)
    return order

previous_position = None

def check_buy_sell_signals(df):
    global previous_position
    position = get_position(config.SYMBOL)
    if previous_position is None:
        previous_position = position
    print('Position', position)

    print("Checking for buy and sell signals...")
    print(df.tail(config.LOGS_DISPLAYED + 1))
    last_row_index = len(df.index) - 1
    # previous_row_index = last_row_index - 1
    atr = df['atr'][last_row_index]
    max_slip = atr / 2.
    price_upper = df['upperband'][last_row_index]
    price_lower = df['lowerband'][last_row_index]

    cancel_orders()

    if position == 0:
        # print(f"Possible change to uptrend. updating buy stop limit at {price_upper} -> {price_upper + max_slip}")
        create_stop_order('buy', price_upper, config.QUANTITY, max_slip)
        create_stop_order('sell', price_lower, config.QUANTITY, max_slip)
    elif position < 0:
        # Reverse
        create_stop_order('buy', price_upper, config.QUANTITY + min(-position, config.QUANTITY), max_slip)
    elif position > 0:
        # Reverse
        create_stop_order('sell', price_lower, config.QUANTITY + min(position, config.QUANTITY), max_slip)

    # df['in_downtrend'][last_row_index]
    if position >= 0:
        # print(f"Possible change to downtrend. updating buy stop limit at {price_lower} -> {price_lower - max_slip}")

    # If last fill is neede for one of the following conditions, fetch it
    if previous_position != position or abs(position) > 1e-6:
        last_fill = exchange.fetch_my_trades(symbol=config.SYMBOL, limit=1)[0]
        open_fill_time = last_fill['timestamp']
        open_fill_side = last_fill['side']
        open_fill_sign = 1 if open_fill_side == 'buy' else -1
        open_fill_price = last_fill['price']

    if previous_position != position:
        send_telegram_message(f'Position changed from {previous_position} to {position} for {open_fill_price}.')

    # If we have position, close it after x hours
    if abs(position) > 1e-6:
        since_fill = time.time() - open_fill_time / 1000
        if since_fill > 60 * 60 * config.CLOSE_AFTER_HOURS:
            print(last_fill)
            order = exchange.create_market_order(config.SYMBOL, opposite(open_fill_side), abs(position))
            close_average_price = order['average']
            print(f"Closed {open_fill_side} position filled at {open_fill_price} with return {open_fill_sign * (close_average_price - open_fill_price)}")
            print(order)

    previous_position = position

def opposite(side):
    return 'buy' if side == 'sell' else 'sell'

def get_position(symbol):
    response = exchange.fetch_positions(symbols = [symbol])
    # print(response)
    position = float(response[0]['info']['positionAmt'])
    return position

def cancel_orders():
    try:
        exchange.cancelOrder(None, 'BTC/USDT', {'clientOrderId': 'btc-buy-stop-limit'})
    except ccxt.OrderNotFound:
        pass
    try:
        exchange.cancelOrder(None, 'BTC/USDT', {'clientOrderId': 'btc-sell-stop-limit'})
    except ccxt.OrderNotFound:
        pass

def run_supertrend():
    print('TrendBot is working...')

    print(f"Fetching new bars for: {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv(config.SYMBOL, timeframe=config.TIMEFRAME, limit=config.LOOKBACK)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    supertrend_data = supertrend(df, config.PERIOD, config.ATR_FACTOR)
    check_buy_sell_signals(supertrend_data)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message.replace('\n', '%0A')}
    response = requests.post(url, data=data)
    return response.json()


pd.set_option('display.max_rows', None)
schedule.every(1).minutes.at(":05").do(run_supertrend)
try:
    run_supertrend()
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    print('Exitting & closing orders')
    cancel_orders()

# TODO sentry, influx, logging, telegram, refactor, unit tests

# TODO backtest volume influence
