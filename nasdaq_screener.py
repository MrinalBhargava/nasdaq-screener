"""
NASDAQ-100 Stock Screener  — v2
Improvements over v1:
  1. Fundamental overlay  (P/E, forward P/E, EPS growth, revenue growth)
  2. Relative (percentile-rank) scoring  — always produces Strong Buy + Strong Sell
  3. Signal trend arrows   (vs previous run)
  4. Sector heatmap data   (pre-aggregated for PWA)

Outputs:
  data_prev.js  — copy of previous run (for trend comparison)
  data.js       — current screener results consumed by PWA

Run:  py nasdaq_screener.py
Auto: GitHub Actions fires at 4:30 pm ET every weekday
"""

import sys, io, os, json, shutil, warnings, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ── CONFIGURATION ─────────────────────────────────────────────────
OUT_DIR  = os.path.dirname(os.path.abspath(__file__))
JS_PATH  = os.path.join(OUT_DIR, "data.js")
PREV_PATH= os.path.join(OUT_DIR, "data_prev.js")
PERIOD   = "500d"
MIN_DAYS = 210
SIG_RANK = {"STRONG SELL": 0, "SELL": 1, "HOLD": 2, "BUY": 3, "STRONG BUY": 4}

# ── NASDAQ-100 COMPONENTS ─────────────────────────────────────────
NASDAQ_100 = {
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
    "ARM":   ("Arm Holdings",            "Technology"),
    "EA":    ("Electronic Arts",         "Technology"),
    "CTSH":  ("Cognizant Technology",    "Technology"),
    "NTES":  ("NetEase Inc.",            "Technology"),
    "NTAP":  ("NetApp Inc.",             "Technology"),
    "SMCI":  ("Super Micro Computer",    "Technology"),
    "GOOGL": ("Alphabet Inc. (A)",       "Communication"),
    "GOOG":  ("Alphabet Inc. (C)",       "Communication"),
    "META":  ("Meta Platforms",          "Communication"),
    "NFLX":  ("Netflix Inc.",            "Communication"),
    "CMCSA": ("Comcast Corp.",           "Communication"),
    "CHTR":  ("Charter Comms.",          "Communication"),
    "TMUS":  ("T-Mobile US",             "Communication"),
    "WBD":   ("Warner Bros. Discovery",  "Communication"),
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
    "COST":  ("Costco Wholesale",        "Cons. Staples"),
    "PEP":   ("PepsiCo Inc.",            "Cons. Staples"),
    "KDP":   ("Keurig Dr Pepper",        "Cons. Staples"),
    "KHC":   ("Kraft Heinz Co.",         "Cons. Staples"),
    "MDLZ":  ("Mondelez Intl.",          "Cons. Staples"),
    "MNST":  ("Monster Beverage",        "Cons. Staples"),
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
    "PYPL":  ("PayPal Holdings",         "Financials"),
    "MELI":  ("MercadoLibre",            "Financials"),
    "PAYX":  ("Paychex Inc.",            "Financials"),
    "HON":   ("Honeywell Intl.",         "Industrials"),
    "CTAS":  ("Cintas Corp.",            "Industrials"),
    "VRSK":  ("Verisk Analytics",        "Industrials"),
    "FAST":  ("Fastenal Co.",            "Industrials"),
    "ODFL":  ("Old Dominion Freight",    "Industrials"),
    "PCAR":  ("PACCAR Inc.",             "Industrials"),
    "CPRT":  ("Copart Inc.",             "Industrials"),
    "CDW":   ("CDW Corp.",               "Industrials"),
    "ROP":   ("Roper Technologies",      "Industrials"),
    "CEG":   ("Constellation Energy",    "Energy"),
    "EXC":   ("Exelon Corp.",            "Utilities"),
    "XEL":   ("Xcel Energy",             "Utilities"),
    "AEP":   ("American Elec. Power",    "Utilities"),
    "ENPH":  ("Enphase Energy",          "Energy"),
    "FSLR":  ("First Solar",             "Energy"),
    "FANG":  ("Diamondback Energy",      "Energy"),
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

# ── TECHNICAL INDICATORS ──────────────────────────────────────────
def calc_rsi(prices, period=14):
    d  = prices.diff()
    ag = d.clip(lower=0).ewm(com=period-1, min_periods=period).mean()
    al = (-d).clip(lower=0).ewm(com=period-1, min_periods=period).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)

def calc_macd(prices, fast=12, slow=26, sig=9):
    m = prices.ewm(span=fast,adjust=False).mean() - prices.ewm(span=slow,adjust=False).mean()
    s = m.ewm(span=sig, adjust=False).mean()
    return m, s

def calc_bb_pct(prices, period=20, nstd=2):
    ma  = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    pct = (prices - (ma - nstd*std)) / (2*nstd*std).replace(0, np.nan)
    return pct.clip(0,1).fillna(0.5)

def ma_cross(price_s, ma50_s, ma200_s):
    if ma200_s.isna().all(): return "above" if price_s.iloc[-1]>ma50_s.iloc[-1] else "below"
    if ma200_s.dropna().__len__() < 5: return "above" if ma50_s.iloc[-1]>ma200_s.iloc[-1] else "below"
    was = ma50_s.iloc[-5] > ma200_s.iloc[-5]
    now = ma50_s.iloc[-1] > ma200_s.iloc[-1]
    if not was and now:  return "golden"
    if was and not now: return "death"
    return "above" if now else "below"

# ── TECHNICAL SCORING (0-100) ─────────────────────────────────────
def t_rsi(v):
    if v<25: return 25
    if v<30: return 22
    if v<40: return 17
    if v<50: return 13
    if v<60: return 10
    if v<70: return 5
    return 0

def t_macd(m,s): return 25 if m>s and m>0 else 18 if m>s else 10 if m>0 else 3

def t_ma(price, ma50, ma200):
    if np.isnan(ma200): return 18 if price>ma50 else 8
    if price>ma50>ma200:  return 25
    if price>ma200>=ma50: return 15
    if ma50>price>ma200:  return 12
    return 3

def t_bb(v):
    if v<0.05: return 15
    if v<0.20: return 12
    if v<0.40: return 9
    if v<0.60: return 7
    if v<0.80: return 4
    if v<0.95: return 1
    return 0

def t_vol(ratio, chg):
    if ratio>2.0 and chg>0: return 10
    if ratio>1.5 and chg>0: return 8
    if ratio>1.0 and chg>0: return 6
    if ratio<1.0: return 4
    if ratio>1.5: return 1
    return 0

# ── FUNDAMENTAL SCORING (0-30) ────────────────────────────────────
def f_score(pe, fpe, eg, rg):
    s = 0
    if pe and pe > 0:
        s += 8 if pe<15 else 5 if pe<25 else 2 if pe<40 else 0
    if pe and fpe and pe>0 and fpe>0:
        s += 5 if fpe<pe else 2 if fpe<pe*1.1 else 0
    if eg is not None:
        s += 10 if eg>0.30 else 7 if eg>0.15 else 4 if eg>0.05 else 2 if eg>0 else 0
    if rg is not None:
        s += 7 if rg>0.20 else 4 if rg>0.10 else 2 if rg>0.02 else 0
    return s

# ── SIGNAL MAPPING (applied to normalised 0-100 score) ───────────
def signal(score):
    if score>=85: return "STRONG BUY"
    if score>=65: return "BUY"
    if score>=35: return "HOLD"
    if score>=15: return "SELL"
    return "STRONG SELL"

# ── LOAD PREVIOUS SIGNALS ─────────────────────────────────────────
def load_prev():
    if not os.path.exists(PREV_PATH): return {}
    try:
        with open(PREV_PATH, "r", encoding="utf-8") as f:
            raw = f.read().split("const SCREENER_DATA = ", 1)[1].rstrip(";\n")
        data = json.loads(raw)
        return {s["ticker"]: s["signal"] for s in data.get("stocks", [])}
    except Exception:
        return {}

# ── FETCH FUNDAMENTALS (threaded) ─────────────────────────────────
def fetch_one(ticker):
    try:
        info = yf.Ticker(ticker).info
        return ticker, {
            "pe":  info.get("trailingPE"),
            "fpe": info.get("forwardPE"),
            "eg":  info.get("earningsGrowth"),
            "rg":  info.get("revenueGrowth"),
        }
    except Exception:
        return ticker, {}

# ═══════════════════════════════════════════════════════════════════
print("=" * 62)
print("  NASDAQ-100 SCREENER  v2  — Technical + Fundamental")
print("=" * 62)

# Step 0: archive previous data.js → data_prev.js
prev_sigs = load_prev()
if os.path.exists(JS_PATH):
    shutil.copy(JS_PATH, PREV_PATH)
    print(f"\n[0] Archived previous run ({len(prev_sigs)} signals loaded)")
else:
    print("\n[0] No previous data (first run)")

# Step 1: download price + volume data
tickers = list(NASDAQ_100.keys())
print(f"[1] Downloading {len(tickers)}-ticker price history ({PERIOD})...")
raw = yf.download(tickers, period=PERIOD, auto_adjust=True, progress=True, group_by="ticker")

# Step 2: compute technical indicators
print("\n[2] Computing technical indicators...")
tech_results = []
skipped = []

for ticker in tickers:
    name, sector = NASDAQ_100[ticker]
    try:
        td     = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
        price  = td["Close"].dropna()
        volume = td["Volume"].dropna()
        if len(price) < MIN_DAYS:
            skipped.append(ticker); continue

        last, prev = float(price.iloc[-1]), float(price.iloc[-2])
        chg = (last - prev) / prev * 100

        rsi_v = float(calc_rsi(price).iloc[-1])
        m, s  = calc_macd(price)
        mv, sv = float(m.iloc[-1]), float(s.iloc[-1])

        ma50_s  = price.rolling(50).mean()
        ma200_s = price.rolling(200).mean()
        ma50v   = float(ma50_s.iloc[-1])
        ma200v  = float(ma200_s.iloc[-1]) if not np.isnan(ma200_s.iloc[-1]) else float("nan")
        cross   = ma_cross(price, ma50_s, ma200_s)

        bbv   = float(calc_bb_pct(price).iloc[-1])
        vol_l = float(volume.iloc[-1]) if not np.isnan(volume.iloc[-1]) else 0
        vol_a = float(volume.rolling(20).mean().iloc[-1])
        vol_r = vol_l / vol_a if vol_a > 0 else 1.0

        pct50  = round((last - ma50v) / ma50v * 100, 1)
        pct200 = round((last - ma200v) / ma200v * 100, 1) if not np.isnan(ma200v) else None

        ts = t_rsi(rsi_v) + t_macd(mv,sv) + t_ma(last,ma50v,ma200v) + t_bb(bbv) + t_vol(vol_r,chg)

        tech_results.append({
            "ticker": ticker, "name": name, "sector": sector,
            "price": round(last, 2), "change_pct": round(chg, 2),
            "rsi": round(rsi_v, 1), "macd_bull": bool(mv > sv),
            "macd_val": round(mv, 4),
            "ma_cross": cross, "pct_ma50": pct50, "pct_ma200": pct200,
            "bb_pct": round(bbv, 3), "vol_ratio": round(vol_r, 2),
            "tech_score": ts,
            "scores": {
                "rsi": t_rsi(rsi_v), "macd": t_macd(mv,sv),
                "ma": t_ma(last,ma50v,ma200v), "bb": t_bb(bbv), "vol": t_vol(vol_r,chg)
            },
        })
    except Exception:
        skipped.append(ticker)

print(f"    {len(tech_results)} processed, {len(skipped)} skipped: {', '.join(skipped)}")

# Step 3: fetch fundamentals (threaded, 6 workers)
print(f"[3] Fetching fundamentals ({len(tech_results)} tickers, threaded)...")
fund_map = {}
done_count = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    futures = {ex.submit(fetch_one, r["ticker"]): r["ticker"] for r in tech_results}
    for fut in as_completed(futures):
        ticker, info = fut.result()
        fund_map[ticker] = info
        done_count += 1
        if done_count % 20 == 0:
            print(f"    {done_count}/{len(tech_results)} done")
print(f"    {done_count}/{len(tech_results)} fundamentals fetched")

# Step 4: combine scores + add fundamental data to each result
for r in tech_results:
    f = fund_map.get(r["ticker"], {})
    fs = f_score(f.get("pe"), f.get("fpe"), f.get("eg"), f.get("rg"))
    r["raw_score"]   = r["tech_score"] + fs
    r["fund_score"]  = fs
    r["scores"]["fund"] = fs
    r["pe"]          = round(f["pe"],  1) if f.get("pe")  else None
    r["fpe"]         = round(f["fpe"], 1) if f.get("fpe") else None
    r["eps_growth"]  = round(f["eg"] * 100, 1) if f.get("eg") else None
    r["rev_growth"]  = round(f["rg"] * 100, 1) if f.get("rg") else None

# Step 5: percentile-rank normalisation → score 0-100
tech_results.sort(key=lambda x: x["raw_score"], reverse=True)
n = len(tech_results)
for i, r in enumerate(tech_results):
    r["score"]  = round(100 - i / (n - 1) * 100) if n > 1 else 50
    r["signal"] = signal(r["score"])
    r["rank"]   = i + 1

# Step 6: signal trend vs previous run
for r in tech_results:
    t = r["ticker"]
    if t not in prev_sigs:
        r["trend"] = "new";  r["prev_signal"] = None
    elif SIG_RANK[r["signal"]] > SIG_RANK[prev_sigs[t]]:
        r["trend"] = "up";   r["prev_signal"] = prev_sigs[t]
    elif SIG_RANK[r["signal"]] < SIG_RANK[prev_sigs[t]]:
        r["trend"] = "down"; r["prev_signal"] = prev_sigs[t]
    else:
        r["trend"] = "same"; r["prev_signal"] = prev_sigs[t]

# Step 7: sector aggregation for heatmap
sectors = {}
for r in tech_results:
    s = r["sector"]
    if s not in sectors:
        sectors[s] = {"sector": s, "stocks": [], "score_sum": 0,
                      "counts": {"STRONG BUY":0,"BUY":0,"HOLD":0,"SELL":0,"STRONG SELL":0}}
    sectors[s]["stocks"].append(r["ticker"])
    sectors[s]["score_sum"] += r["score"]
    sectors[s]["counts"][r["signal"]] += 1
sector_list = []
for s, d in sectors.items():
    avg = round(d["score_sum"] / len(d["stocks"]))
    sector_list.append({
        "sector": s, "avg_score": avg, "signal": signal(avg),
        "count": len(d["stocks"]), "counts": d["counts"],
        "top": d["stocks"][:4]
    })
sector_list.sort(key=lambda x: x["avg_score"], reverse=True)

# Step 8: market summary
sig_counts = {"STRONG BUY":0,"BUY":0,"HOLD":0,"SELL":0,"STRONG SELL":0}
for r in tech_results: sig_counts[r["signal"]] += 1
up_count   = sum(1 for r in tech_results if r["trend"] == "up")
down_count = sum(1 for r in tech_results if r["trend"] == "down")

# Step 9: write data.js
now = datetime.datetime.now().strftime("%d %b %Y %H:%M")
payload = {
    "updated": now, "count": len(tech_results),
    "summary": sig_counts,
    "trend_summary": {"up": up_count, "down": down_count, "same": n - up_count - down_count},
    "sectors": sector_list,
    "stocks": tech_results,
}
with open(JS_PATH, "w", encoding="utf-8") as f:
    f.write(f"// NASDAQ-100 Screener v2 — {now}\n")
    f.write("const SCREENER_DATA = ")
    f.write(json.dumps(payload, ensure_ascii=False))
    f.write(";\n")

# ── PRINT SUMMARY ─────────────────────────────────────────────────
print(f"\n[Done] data.js written — {len(tech_results)} stocks")
print("\n" + "="*68)
print("  TOP 15 BUY SIGNALS")
print("="*68)
print(f"  {'#':<4}{'Tkr':<6}{'Name':<24}{'Signal':<13}{'Score':>5}{'RSI':>6}{'Fund':>6}{'Chg%':>7}")
print("  "+"-"*64)
for r in tech_results[:15]:
    chg = f"+{r['change_pct']:.1f}%" if r["change_pct"]>=0 else f"{r['change_pct']:.1f}%"
    trend = {"up":"↑","down":"↓","same":"","new":"*"}.get(r["trend"],"")
    print(f"  {r['rank']:<4}{r['ticker']:<6}{r['name']:<24}{r['signal']:<13}{r['score']:>5}"
          f"{r['rsi']:>6.1f}{r['fund_score']:>6}{chg:>7}  {trend}")

print("\n"+"="*45)
print("  MARKET SUMMARY           TREND")
print("="*45)
for sig, cnt in sig_counts.items():
    bar = "■" * min(cnt, 30)
    print(f"  {sig:<15} {cnt:>3}  {bar}")
print(f"\n  Improving signals: {up_count}  |  Deteriorating: {down_count}")
print(f"\nRefresh: run again. Auto-refresh: GitHub Actions (4:30pm ET weekdays)")
