"""
NASDAQ-100 Stock Screener
Computes RSI, MACD, Moving Averages, Bollinger Bands & Volume signals
for all NASDAQ-100 components. Outputs data.js for the PWA dashboard.

Run: py nasdaq_screener.py
Refresh: run again any time — data.js overwrites with latest data
"""

import sys, io, os, json, datetime, warnings
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "yfinance", "-q"])
    import yfinance as yf

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
PERIOD   = "500d"   # ~2 years — enough for MA200 + indicator warmup
MIN_DAYS = 210      # skip tickers with less data

# ── NASDAQ-100 COMPONENTS ─────────────────────────────────────────────────────
NASDAQ_100 = {
    # Technology
    "AAPL":  ("Apple Inc.",              "Technology"),
    "MSFT":  ("Microsoft Corp.",         "Technology"),
    "NVDA":  ("NVIDIA Corp.",            "Technology"),
    "AVGO":  ("Broadcom Inc.",           "Technology"),
    "ADBE":  ("Adobe Inc.",              "Technology"),
    "CSCO":  ("Cisco Systems",           "Technology"),
    "QCOM":  ("Qualcomm Inc.",           "Technology"),
    "AMD":   ("AMD",                     "Technology"),
    "AMAT":  ("Applied Materials",       "Technology"),
    "MU":    ("Micron Technology",       "Technology"),
    "LRCX":  ("Lam Research",            "Technology"),
    "KLAC":  ("KLA Corp.",               "Technology"),
    "SNPS":  ("Synopsys Inc.",           "Technology"),
    "CDNS":  ("Cadence Design",          "Technology"),
    "ADI":   ("Analog Devices",          "Technology"),
    "NXPI":  ("NXP Semiconductors",      "Technology"),
    "MCHP":  ("Microchip Technology",    "Technology"),
    "MRVL":  ("Marvell Technology",      "Technology"),
    "ON":    ("ON Semiconductor",        "Technology"),
    "INTC":  ("Intel Corp.",             "Technology"),
    "ANSS":  ("ANSYS Inc.",              "Technology"),
    "ARM":   ("Arm Holdings",            "Technology"),
    "EA":    ("Electronic Arts",         "Technology"),
    "CTSH":  ("Cognizant Technology",    "Technology"),
    "NTES":  ("NetEase Inc.",            "Technology"),
    "NTAP":  ("NetApp Inc.",             "Technology"),
    "SMCI":  ("Super Micro Computer",    "Technology"),
    # Communication Services
    "GOOGL": ("Alphabet Inc. (A)",       "Communication"),
    "GOOG":  ("Alphabet Inc. (C)",       "Communication"),
    "META":  ("Meta Platforms",          "Communication"),
    "NFLX":  ("Netflix Inc.",            "Communication"),
    "CMCSA": ("Comcast Corp.",           "Communication"),
    "CHTR":  ("Charter Comms.",          "Communication"),
    "TMUS":  ("T-Mobile US",             "Communication"),
    "WBD":   ("Warner Bros. Discovery",  "Communication"),
    # Consumer Discretionary
    "AMZN":  ("Amazon.com",              "Cons. Discret."),
    "TSLA":  ("Tesla Inc.",              "Cons. Discret."),
    "BKNG":  ("Booking Holdings",        "Cons. Discret."),
    "SBUX":  ("Starbucks Corp.",         "Cons. Discret."),
    "MAR":   ("Marriott Intl.",          "Cons. Discret."),
    "ORLY":  ("O'Reilly Automotive",     "Cons. Discret."),
    "ROST":  ("Ross Stores",             "Cons. Discret."),
    "ABNB":  ("Airbnb Inc.",             "Cons. Discret."),
    "LULU":  ("Lululemon Athletica",     "Cons. Discret."),
    "DASH":  ("DoorDash Inc.",           "Cons. Discret."),
    "PDD":   ("PDD Holdings",            "Cons. Discret."),
    "EBAY":  ("eBay Inc.",               "Cons. Discret."),
    # Consumer Staples
    "COST":  ("Costco Wholesale",        "Cons. Staples"),
    "PEP":   ("PepsiCo Inc.",            "Cons. Staples"),
    "KDP":   ("Keurig Dr Pepper",        "Cons. Staples"),
    "KHC":   ("Kraft Heinz Co.",         "Cons. Staples"),
    "MDLZ":  ("Mondelez Intl.",          "Cons. Staples"),
    "MNST":  ("Monster Beverage",        "Cons. Staples"),
    # Healthcare
    "ISRG":  ("Intuitive Surgical",      "Healthcare"),
    "AMGN":  ("Amgen Inc.",              "Healthcare"),
    "REGN":  ("Regeneron Pharma.",       "Healthcare"),
    "GILD":  ("Gilead Sciences",         "Healthcare"),
    "DXCM":  ("DexCom Inc.",             "Healthcare"),
    "IDXX":  ("IDEXX Laboratories",      "Healthcare"),
    "MRNA":  ("Moderna Inc.",            "Healthcare"),
    "ILMN":  ("Illumina Inc.",           "Healthcare"),
    "BIIB":  ("Biogen Inc.",             "Healthcare"),
    "GEHC":  ("GE HealthCare",           "Healthcare"),
    "AZN":   ("AstraZeneca PLC",         "Healthcare"),
    # Financials
    "PYPL":  ("PayPal Holdings",         "Financials"),
    "MELI":  ("MercadoLibre",            "Financials"),
    "PAYX":  ("Paychex Inc.",            "Financials"),
    # Industrials
    "HON":   ("Honeywell Intl.",         "Industrials"),
    "CTAS":  ("Cintas Corp.",            "Industrials"),
    "VRSK":  ("Verisk Analytics",        "Industrials"),
    "FAST":  ("Fastenal Co.",            "Industrials"),
    "ODFL":  ("Old Dominion Freight",    "Industrials"),
    "PCAR":  ("PACCAR Inc.",             "Industrials"),
    "CPRT":  ("Copart Inc.",             "Industrials"),
    "CDW":   ("CDW Corp.",               "Industrials"),
    "ROP":   ("Roper Technologies",      "Industrials"),
    # Energy / Utilities
    "CEG":   ("Constellation Energy",    "Energy"),
    "EXC":   ("Exelon Corp.",            "Utilities"),
    "XEL":   ("Xcel Energy",             "Utilities"),
    "AEP":   ("American Elec. Power",    "Utilities"),
    "ENPH":  ("Enphase Energy",          "Energy"),
    "FSLR":  ("First Solar",             "Energy"),
    "FANG":  ("Diamondback Energy",      "Energy"),
    # Software / Cloud
    "INTU":  ("Intuit Inc.",             "Software"),
    "PANW":  ("Palo Alto Networks",      "Software"),
    "CRWD":  ("CrowdStrike Holdings",    "Software"),
    "FTNT":  ("Fortinet Inc.",           "Software"),
    "ZS":    ("Zscaler Inc.",            "Software"),
    "DDOG":  ("Datadog Inc.",            "Software"),
    "WDAY":  ("Workday Inc.",            "Software"),
    "TTD":   ("The Trade Desk",          "Software"),
    "TEAM":  ("Atlassian Corp.",         "Software"),
    "APP":   ("AppLovin Corp.",          "Software"),
    "MDB":   ("MongoDB Inc.",            "Software"),
    "GFS":   ("GlobalFoundries",         "Software"),
}

# ── INDICATOR FUNCTIONS ───────────────────────────────────────────────────────
def rsi(prices, period=14):
    delta = prices.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    ag    = gain.ewm(com=period - 1, min_periods=period).mean()
    al    = loss.ewm(com=period - 1, min_periods=period).mean()
    rs    = ag / al.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)

def macd(prices, fast=12, slow=26, sig=9):
    ef = prices.ewm(span=fast, adjust=False).mean()
    es = prices.ewm(span=slow, adjust=False).mean()
    m  = ef - es
    s  = m.ewm(span=sig, adjust=False).mean()
    return m, s, m - s

def bb_pct(prices, period=20, nstd=2):
    ma    = prices.rolling(period).mean()
    std   = prices.rolling(period).std()
    upper = ma + nstd * std
    lower = ma - nstd * std
    pct   = (prices - lower) / (upper - lower).replace(0, np.nan)
    return pct.clip(0, 1).fillna(0.5)

# ── SCORING ───────────────────────────────────────────────────────────────────
def score_rsi(v):
    if v < 25:  return 25
    if v < 30:  return 22
    if v < 40:  return 17
    if v < 50:  return 13
    if v < 60:  return 10
    if v < 70:  return 5
    return 0

def score_macd(m, s):
    above = m > s
    pos   = m > 0
    if above and pos:    return 25
    if above:            return 18
    if pos:              return 10
    return 3

def score_ma(price, ma50, ma200):
    if np.isnan(ma200):
        return 18 if price > ma50 else 8
    if price > ma50 > ma200:   return 25
    if price > ma200 >= ma50:  return 15
    if ma50 > price > ma200:   return 12
    return 3

def score_bb(v):
    if v < 0.05:  return 15
    if v < 0.20:  return 12
    if v < 0.40:  return 9
    if v < 0.60:  return 7
    if v < 0.80:  return 4
    if v < 0.95:  return 1
    return 0

def score_vol(ratio, chg):
    if ratio > 2.0 and chg > 0:  return 10
    if ratio > 1.5 and chg > 0:  return 8
    if ratio > 1.0 and chg > 0:  return 6
    if ratio < 1.0:               return 4
    if ratio > 1.5:               return 1
    return 0

def signal(score):
    if score >= 75: return "STRONG BUY"
    if score >= 55: return "BUY"
    if score >= 35: return "HOLD"
    if score >= 15: return "SELL"
    return "STRONG SELL"

def ma_cross_label(price_s, ma50_s, ma200_s):
    if ma200_s.isna().all():
        return "above" if price_s.iloc[-1] > ma50_s.iloc[-1] else "below"
    valid = ma200_s.dropna()
    if len(valid) < 5:
        return "above" if ma50_s.iloc[-1] > ma200_s.iloc[-1] else "below"
    w = min(5, len(valid))
    was_above = ma50_s.iloc[-w] > ma200_s.iloc[-w]
    now_above = ma50_s.iloc[-1] > ma200_s.iloc[-1]
    if not was_above and now_above:  return "golden"
    if was_above and not now_above:  return "death"
    return "above" if now_above else "below"

# ── MAIN ──────────────────────────────────────────────────────────────────────
tickers = list(NASDAQ_100.keys())

print("=" * 60)
print("  NASDAQ-100 STOCK SCREENER")
print(f"  {len(tickers)} tickers  |  {PERIOD} price history")
print("=" * 60)
print(f"\n[1] Downloading batch price data...")
raw = yf.download(tickers, period=PERIOD, auto_adjust=True,
                  progress=True, group_by="ticker")

print("\n[2] Computing indicators for each ticker...")
results = []
skipped = []

for ticker in tickers:
    name, sector = NASDAQ_100[ticker]
    try:
        # Handle yfinance MultiIndex structure
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker not in raw.columns.get_level_values(0):
                skipped.append(ticker); continue
            t_data = raw[ticker]
        else:
            t_data = raw

        price  = t_data["Close"].dropna()
        volume = t_data["Volume"].dropna()

        if len(price) < MIN_DAYS:
            skipped.append(ticker); continue

        last  = float(price.iloc[-1])
        prev  = float(price.iloc[-2])
        chg   = (last - prev) / prev * 100

        r     = float(rsi(price).iloc[-1])
        m, s, h = macd(price)
        mv, sv  = float(m.iloc[-1]), float(s.iloc[-1])

        ma50_s  = price.rolling(50).mean()
        ma200_s = price.rolling(200).mean()
        ma50v   = float(ma50_s.iloc[-1])
        ma200v  = float(ma200_s.iloc[-1]) if not np.isnan(ma200_s.iloc[-1]) else float("nan")

        cross   = ma_cross_label(price, ma50_s, ma200_s)

        bbv     = float(bb_pct(price).iloc[-1])
        vol_l   = float(volume.iloc[-1]) if not np.isnan(volume.iloc[-1]) else 0
        vol_a   = float(volume.rolling(20).mean().iloc[-1])
        vol_r   = vol_l / vol_a if vol_a > 0 else 1.0

        sr  = score_rsi(r)
        sm  = score_macd(mv, sv)
        sma = score_ma(last, ma50v, ma200v)
        sb  = score_bb(bbv)
        sv2 = score_vol(vol_r, chg)
        tot = sr + sm + sma + sb + sv2

        pct200 = round((last - ma200v) / ma200v * 100, 1) if not np.isnan(ma200v) else None

        results.append({
            "rank":       0,
            "ticker":     ticker,
            "name":       name,
            "sector":     sector,
            "price":      round(last, 2),
            "change_pct": round(chg, 2),
            "score":      tot,
            "signal":     signal(tot),
            "rsi":        round(r, 1),
            "macd_bull":  bool(mv > sv),
            "macd_val":   round(mv, 4),
            "ma_cross":   cross,
            "pct_ma50":   round((last - ma50v) / ma50v * 100, 1),
            "pct_ma200":  pct200,
            "bb_pct":     round(bbv, 3),
            "vol_ratio":  round(vol_r, 2),
            "scores":     {"rsi": sr, "macd": sm, "ma": sma, "bb": sb, "vol": sv2},
        })
    except Exception as e:
        skipped.append(ticker)

# Sort and rank
results.sort(key=lambda x: x["score"], reverse=True)
for i, r in enumerate(results):
    r["rank"] = i + 1

# Summary
sig_counts = {"STRONG BUY": 0, "BUY": 0, "HOLD": 0, "SELL": 0, "STRONG SELL": 0}
for r in results:
    sig_counts[r["signal"]] += 1

# ── WRITE data.js ──────────────────────────────────────────────────────────────
now = datetime.datetime.now().strftime("%d %b %Y %H:%M")
payload = {
    "updated": now,
    "count":   len(results),
    "summary": sig_counts,
    "stocks":  results,
}
js_path = os.path.join(OUT_DIR, "data.js")
with open(js_path, "w", encoding="utf-8") as f:
    f.write(f"// NASDAQ-100 Screener data — generated {now}\n")
    f.write("const SCREENER_DATA = ")
    f.write(json.dumps(payload, ensure_ascii=False))
    f.write(";\n")
print(f"\n[3] data.js written: {len(results)} stocks  ({len(skipped)} skipped: {', '.join(skipped[:5])}{'...' if len(skipped)>5 else ''})")

# ── PRINT RESULTS ─────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  TOP 15 BUY SIGNALS")
print("=" * 68)
print(f"  {'#':<4} {'Tkr':<6} {'Name':<24} {'Signal':<12} {'Score':>5} {'RSI':>6} {'Chg%':>7}")
print("  " + "-" * 62)
for r in results[:15]:
    chg_s = f"+{r['change_pct']:.1f}%" if r['change_pct'] >= 0 else f"{r['change_pct']:.1f}%"
    print(f"  {r['rank']:<4} {r['ticker']:<6} {r['name']:<24} {r['signal']:<12} {r['score']:>5} {r['rsi']:>6.1f} {chg_s:>7}")

print("\n" + "=" * 40)
print("  MARKET SUMMARY")
print("=" * 40)
for sig, count in sig_counts.items():
    bar = "■" * min(count, 40)
    print(f"  {sig:<15} {count:>3}  {bar}")

print(f"\nDone. Run again to refresh. Open index.html to view dashboard.")
