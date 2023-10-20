'''
Enter BTC-USDT perp positions on supertrend upper/lower bound breakout.

Close after preset time or when other bound is hit.

Integrated with Telegram for notifications and Sentry for errors.
'''

from typing import Literal
from datetime import datetime
import logging
import ccxt
import schedule
import pandas as pd
import time

from supertrend import supertrend
from integrations import send_telegram_message
import config


logging.basicConfig(
    # format = '[%(asctime)s,%(msecs)03d] %(name)-22s %(levelname)7s: %(message)s',
    format = '[%(asctime)s,%(msecs)03d] %(levelname)7s: %(message)s',
    datefmt = '%y%m%d %H:%M:%S',
    level = logging.INFO,
)

# Globals
logger = logging.getLogger('app')
exchange: ccxt.Exchange
previous_position = None

def create_stop_order(side: Literal['buy', 'sell'], stop_price: float, quantity: float, max_slip: float) -> dict:
    logger.info(f"Opening stop order {side} {quantity} at {stop_price}")
    autocancel_time = int(time.time()) + 60 * 60 * 8 # 8 hours
    order = exchange.create_order(
        config.SYMBOL, 'limit', side, amount = quantity, price = stop_price + max_slip * (1 if side == 'buy' else -1),
        params={'type': 'TAKE_PROFIT_LIMIT', 'stopPrice': stop_price, 'timeInForce': 'GTD', 'newClientOrderId': f'btc-{side}-stop-limit', 'goodTillDate': autocancel_time * 1000}
    )
    logger.info(order)
    return order

def check_buy_sell_signals(df):
    global previous_position
    position = get_position(config.SYMBOL)
    if previous_position is None:
        previous_position = position
    logger.info('Position %f', position)

    logger.info("Checking for buy and sell signals...")
    logger.info(df.tail(config.LOGS_DISPLAYED + 1))
    last_row_index = len(df.index) - 1
    # previous_row_index = last_row_index - 1
    atr = df['atr'][last_row_index]
    max_slip = atr / 2.
    price_upper = df['upperband'][last_row_index]
    price_lower = df['lowerband'][last_row_index]

    cancel_orders()

    if position == 0:
        # logger.info(f"Possible change to uptrend. updating buy stop limit at {price_upper} -> {price_upper + max_slip}")
        create_stop_order('buy', price_upper, config.QUANTITY, max_slip)
        create_stop_order('sell', price_lower, config.QUANTITY, max_slip)
    elif position < 0:
        # Reverse
        create_stop_order('buy', price_upper, config.QUANTITY + min(-position, config.QUANTITY), max_slip)
    elif position > 0:
        # Reverse
        create_stop_order('sell', price_lower, config.QUANTITY + min(position, config.QUANTITY), max_slip)

    # df['in_downtrend'][last_row_index]

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
            logger.info(last_fill)
            order = exchange.create_market_order(config.SYMBOL, opposite(open_fill_side), abs(position))
            close_average_price = order['average']
            logger.info(f"Closed {open_fill_side} position filled at {open_fill_price} with return {open_fill_sign * (close_average_price - open_fill_price)}")
            logger.info(order)

    previous_position = position

def opposite(side: Literal['buy', 'sell']) -> Literal['buy', 'sell']:
    return 'buy' if side == 'sell' else 'sell'

def get_position(symbol: str) -> float:
    response = exchange.fetch_positions(symbols = [symbol])
    # logger.info(response)
    position = float(response[0]['info']['positionAmt'])
    return position

def cancel_orders() -> None:
    try:
        exchange.cancelOrder(None, 'BTC/USDT', {'clientOrderId': 'btc-buy-stop-limit'})
    except ccxt.OrderNotFound:
        pass
    try:
        exchange.cancelOrder(None, 'BTC/USDT', {'clientOrderId': 'btc-sell-stop-limit'})
    except ccxt.OrderNotFound:
        pass

def run_supertrend():
    logger.info('TrendBot is working...')

    logger.info(f"Fetching new bars for: {datetime.now().isoformat()}")
    bars = exchange.fetch_ohlcv(config.SYMBOL, timeframe=config.TIMEFRAME, limit=config.LOOKBACK)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    supertrend_df = supertrend(df, config.PERIOD, config.ATR_FACTOR)
    check_buy_sell_signals(supertrend_df)

def table(values):
    '''convert list of dicts/lists into a simple table-string for printing'''
    first = values[0]
    keys = list(first.keys()) if isinstance(first, dict) else range(0, len(first))
    widths = [max([len(str(v[k])) for v in values]) for k in keys]
    string = ' | '.join(['{:<' + str(w) + '}' for w in widths])
    return "\n".join([string.format(*[str(v[k]) for k in keys]) for v in values])


if __name__ == '__main__':
    pd.set_option('display.max_rows', None)
    schedule.every(1).minutes.at(":05").do(run_supertrend)
    try:
        exchange= ccxt.binance({
            "apiKey": config.API_KEY,
            "secret": config.API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            },
        })

        # To run binance paper trading (https://testnet.binancefuture.com/)
        exchange.set_sandbox_mode(config.SANDBOX_MODE)

        run_supertrend()
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Exitting & closing orders')
        cancel_orders()

# TODO influx, unit tests
# TODO close my current hedging btc short position
# TODO backtest volume influence
