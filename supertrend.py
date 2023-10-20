def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return tr


def atr(data, period: int):
    data['tr'] = tr(data)
    data.drop(columns = ['high-low', 'high-pc', 'low-pc'], inplace=True)
    atr = data['tr'].rolling(period).mean()

    return atr

def supertrend(df, period: int, atr_multiplier: float):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True

    for current in range(1, len(df.index)):
        previous = current - 1

        if (df['close'][current] > df['upperband'][previous]):
            df.at[current, 'in_uptrend'] = True
        elif (df['open'][current] < df['lowerband'][previous]):
            df.at[current, 'in_uptrend'] = False
        else:
            df.at[current, 'in_uptrend'] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df.at[current, 'lowerband'] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df.at[current, 'upperband'] = df['upperband'][previous]

    return df
