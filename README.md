# NASDAQ-100 Stock Screener

A technical analysis screener for all NASDAQ-100 stocks. Computes RSI, MACD, Moving Average crossovers, Bollinger Bands and Volume signals for each stock, producing a ranked Buy/Hold/Sell signal table.

**Live dashboard:** https://mrinalbhargava.github.io/nasdaq-screener/

## How to refresh data
```
py nasdaq_screener.py
```
Then commit and push — GitHub Pages auto-updates.

## Tech stack
- Python: yfinance, numpy, pandas
- PWA: vanilla JS, CSS, service worker (installable to phone home screen)

