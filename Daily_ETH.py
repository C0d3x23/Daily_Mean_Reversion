"""
Overview:

This bot is a Daily Mean Reversion Strategy Trading Bot version 1.1
Start Date : July 5, 2023

Base on backtest from 7 pairs from 2019 - 2023, 3 coins can be traded

"""
import ccxt
import pandas as pd
import credentials
import talib as ta
import numpy as np
import datetime
import schedule
import time
import warnings
import testnet

warnings.filterwarnings('ignore')

leverage = 5
marginMode = 'cross'
in_position = False

# exchange = ccxt.binanceusdm({
#     'enableRateLimit': True,
#     'apiKey': credentials.api_key,
#     'secret': credentials.api_secret,
#     'defaultType': 'future'
# })

exchange = ccxt.binanceusdm({
    'enableRateLimit': True,
    'apiKey': testnet.api_key,
    'secret': testnet.api_secret,
    'defaultType': 'future'
})

exchange.set_sandbox_mode(True)

def fetch_data(symbol, tf, limit):

    frame = pd.DataFrame(exchange.fetchOHLCV(symbol=symbol, timeframe=tf, limit=limit))
    frame = frame.iloc[:, :5]
    frame.columns = ['Timestamp', 'Open', 'High', 'Low', 'Close']
    frame['Timestamp'] = pd.to_datetime(frame.Timestamp, unit='ms')
    return frame

def s_SMA(df, window=200):
    df['slow_SMA'] = df.Close.rolling(window).mean()
    return df

def f_SMA(df, window=5):
    df['fast_SMA'] = df.Close.rolling(window).mean()
    return df

def RSI(df, window=2):
    df['RSI'] = ta.RSI(np.array(df.Close), window)
    return df
    
def update_data():
    global daily

    pairs = ['ETH/USDT', 'ADA/USDT', 'BNB/USDT']

    for pair in pairs:

        daily = fetch_data(pair, '1d', 201)

        s_SMA(daily)
        f_SMA(daily)

        daily['trend'] = daily.Close > daily.slow_SMA
        daily['f_trend'] = daily.Close < daily.fast_SMA

        RSI(daily)

        # Entry - if price is > 200SMA and < 5SMA and RSI2 < 10
        # Exit  - if price > Entry[-2] or price < 200SMA or > 5SMA or price < (5SMA * 10%)
   
        daily['oversold'] = daily.RSI < 10
        daily['Buy'] = daily.trend & daily.f_trend & daily.oversold 
        daily['Sell'] = (daily.Close.iloc[-1] > daily.fast_SMA.iloc[-1]) or \
                          (daily.Close.iloc[-1] < (daily.fast_SMA.iloc[-1] * 1.10)) or \
                          (daily.Close.iloc[-1] > daily.Close.iloc[-2]) or \
                          (daily.Close.iloc[-1] < daily.trend.iloc[-1])
        daily['Buy'] = daily.Buy.shift().fillna(False)
        daily['Sell'] = daily.Sell.shift().fillna(False)
        if daily.trend.iloc[-1] and daily.f_trend.iloc[-1]:
            print(f'{pair} {daily.Timestamp.iloc[-1]} - {daily.RSI.iloc[-1]}')
        # else:
        #     print(".", end="", flush=True)
            # print(f'{pair} - {daily.Timestamp.iloc[-1]}')

def buy_sell():
    global in_position

    pairs = ['ETH/USDT', 'ADA/USDT', 'BNB/USDT']

    for pair in pairs:

        if not in_position and daily.Buy.iloc[-1]:
            exchange.setLeverage(leverage=leverage, symbol=pair)
            exchange.setMarginMode(marginMode=marginMode, symbol=pair)
            ticker = exchange.fetchTicker(pair)
            ask_price = float(ticker['info']['lastPrice'])
            balance = exchange.fetchBalance()['total']['USDT']
            buy_quantity = (balance * leverage) / ask_price
            buy = exchange.createMarketOrder(pair, side='BUY', amount=buy_quantity)
            print(buy)
            in_position = True

        if in_position and daily.Sell.iloc[-1]:
            pos = exchange.fetchPositions(symbols=[pair])
            sell_qty = float(pos[-1]['info']['positionAmt'])
            sell = exchange.createMarketOrder(pair, side='SELL', amount=sell_qty)
            print(sell)
            in_position = False

def scanPositions():

    pairs = ['ETH/USDT', 'ADA/USDT', 'BNB/USDT']

    for pair in pairs:
    
        posi = pd.DataFrame(exchange.fetchPositions(symbols=[pair]))
        posi['Active'] = posi['entryPrice'] > 0
        active_count = (posi['Active'] == True).sum()
        open_positions = active_count == 1
        if open_positions:
            in_position = True
        else:
            pass

def MRB():
    scanPositions()
    update_data()
    buy_sell()

# Schedule the strategy to run every 10 seconds
schedule.every(10).seconds.do(MRB)

while True:
    schedule.run_pending()
    time.sleep(1)
