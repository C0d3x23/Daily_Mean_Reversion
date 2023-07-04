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

warnings.filterwarnings('ignore')

leverage = 5
marginMode = 'cross'
in_position = False

exchange = ccxt.binanceusdm({
    'enableRateLimit': True,
    'apiKey': credentials.api_key,
    'secret': credentials.api_secret,
    'defaultType': 'future'
})

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

    # Fetch new data
    daily = fetch_data('ETH/USDT', '1d', 201)

    # Calculate SMA
    s_SMA(daily)
    f_SMA(daily)

    # Calculate daily trend
    daily['trend'] = daily.Close > daily.slow_SMA
    daily['f_trend'] = daily.Close < daily.fast_SMA

    # Calculate RSI
    RSI(daily)

    daily['oversold'] = daily.RSI < 10
    daily['Buy'] = daily.trend & daily.f_trend & daily.oversold 
    daily['Sell_1'] = (daily.Close.iloc[-1] > daily.fast_SMA.iloc[-1]) or (daily.Close.iloc[-1] < (daily.fast_sma.iloc[-1] * 1.10))
    daily['Sell_2'] = (daily.Close.iloc[-1] > daily.Close.iloc[-2]) or (daily.Close.iloc[-1] < daily.trend.iloc[-1])
    daily['Buy'] = daily.Buy.shift().fillna(False)
    daily['Sell_1'] = daily['Sell_1'].shift().fillna(False)
    daily['Sell_2'] = daily['Sell_2'].shift().fillna(False)
    print(daily)
    if daily.trend.iloc[-1] and daily.f_trend.iloc[-1]:
        print(f'ETH/USDT {daily.Timestamp.iloc[-1]} - {daily.RSI.iloc[-1]}')

def buy_sell():
    global in_position

    if not in_position and daily.Buy.iloc[-1]:
        exchange.setLeverage(leverage=leverage, symbol='ETH/USDT')
        exchange.setMarginMode(marginMode=marginMode, symbol='ETH/USDT')
        ticker = exchange.fetchTicker('ETH/USDT')
        ask_price = float(ticker['info']['lastPrice'])
        balance = exchange.fetchBalance()['total']['USDT']
        buy_quantity = (balance * leverage) / ask_price
        buy = exchange.createMarketOrder('ETH/USDT', side='BUY', amount=buy_quantity)
        print(buy)
        in_position = True

    if in_position and (daily.Sell_1.iloc[-1] or daily.Sell_2.iloc[-1]):
        pos = exchange.fetchPositions(symbols=['ETH/USDT'])
        sell_qty = float(pos[-1]['info']['positionAmt'])
        sell = exchange.createMarketOrder('ETH/USDT', side='SELL', amount=sell_qty)
        print(sell)
        in_position = False

def scanPositions():
    
    posi = pd.DataFrame(exchange.fetchPositions(symbols=['ETH/USDT']))
    posi['Active'] = posi['entryPrice'] > 0
    if posi.Active.iloc[-1]:
        return
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
