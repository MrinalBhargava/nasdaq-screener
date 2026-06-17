'use strict';

// ── Service worker registration ──────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js').catch(() => {});
}

// ── State ────────────────────────────────────────────────────────
const state = {
  view:        'screener',
  sigFilter:   'ALL',
  sector:      '',
  sort:        'score',
  watchlist:   JSON.parse(localStorage.getItem('watchlist') || '[]'),
  detail:      null,
};

// ── Helpers ──────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function sigClass(sig) {
  return 'sig-' + sig.replace(' ', '-');
}

function sigShort(sig) {
  const MAP = {
    'STRONG BUY':  'STR BUY',
    'BUY':         'BUY',
    'HOLD':        'HOLD',
    'SELL':        'SELL',
    'STRONG SELL': 'STR SELL',
  };
  return MAP[sig] || sig;
}

function scoreColor(score) {
  if (score >= 75) return '#22c55e';
  if (score >= 55) return '#86efac';
  if (score >= 35) return '#fbbf24';
  if (score >= 15) return '#f97316';
  return '#ef4444';
}

function scoreRingClass(score) {
  if (score >= 75) return 'high';
  if (score >= 55) return 'good';
  if (score >= 35) return 'mid';
  if (score >= 15) return 'low';
  return 'poor';
}

function rsiLabel(rsi) {
  if (rsi < 30) return 'Oversold';
  if (rsi > 70) return 'Overbought';
  return 'Neutral';
}

function maLabel(cross) {
  const MAP = {golden:'Golden X', death:'Death X', above:'Above 200d', below:'Below 200d'};
  return MAP[cross] || cross;
}

function bbLabel(pct) {
  if (pct < 0.10) return 'Near Low';
  if (pct < 0.30) return 'Lower Half';
  if (pct < 0.70) return 'Mid Range';
  if (pct < 0.90) return 'Upper Half';
  return 'Near High';
}

function volLabel(ratio) {
  if (ratio > 2) return ratio.toFixed(1) + 'x Surge';
  if (ratio > 1.3) return ratio.toFixed(1) + 'x Avg';
  return ratio.toFixed(1) + 'x Avg';
}

function fmtChange(chg) {
  const arrow = chg >= 0 ? '▲' : '▼';
  return `${arrow}${Math.abs(chg).toFixed(1)}%`;
}

function fmtPrice(p) {
  return p >= 100 ? '$' + p.toFixed(0) : '$' + p.toFixed(2);
}

function toast(msg, ms = 1800) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), ms);
}

// ── Data access ──────────────────────────────────────────────────
function getData() {
  if (typeof SCREENER_DATA === 'undefined') return null;
  return SCREENER_DATA;
}

function filteredStocks() {
  const data = getData();
  if (!data) return [];

  let stocks = [...data.stocks];

  // Signal filter
  if (state.sigFilter === 'BUY') {
    stocks = stocks.filter(s => s.signal === 'BUY' || s.signal === 'STRONG BUY');
  } else if (state.sigFilter === 'HOLD') {
    stocks = stocks.filter(s => s.signal === 'HOLD');
  } else if (state.sigFilter === 'SELL') {
    stocks = stocks.filter(s => s.signal === 'SELL' || s.signal === 'STRONG SELL');
  }

  // Sector filter
  if (state.sector) {
    stocks = stocks.filter(s => s.sector === state.sector);
  }

  // Sort
  if (state.sort === 'rsi_asc')   stocks.sort((a, b) => a.rsi - b.rsi);
  else if (state.sort === 'rsi_desc') stocks.sort((a, b) => b.rsi - a.rsi);
  else if (state.sort === 'change')   stocks.sort((a, b) => b.change_pct - a.change_pct);
  else if (state.sort === 'alpha')    stocks.sort((a, b) => a.ticker.localeCompare(b.ticker));
  // default: score (already sorted)

  return stocks;
}

// ── Render: stock card ───────────────────────────────────────────
function renderCard(s) {
  const isWatched = state.watchlist.includes(s.ticker);
  const chgPos    = s.change_pct >= 0;
  const rsiCls    = s.rsi < 30 ? 'rsi-low' : s.rsi > 70 ? 'rsi-high' : '';
  const macdCls   = s.macd_bull ? 'macd-bull' : 'macd-bear';
  const maCls     = s.ma_cross === 'golden' ? 'ma-golden' : s.ma_cross === 'death' ? 'ma-death' : '';
  const macdDir   = s.macd_bull ? '▲' : '▼';
  const maIcon    = {golden: '★', death: '✕', above: '↑', below: '↓'}[s.ma_cross] || '—';
  const color     = scoreColor(s.score);

  const el = document.createElement('article');
  el.className = 'stock-card' + (isWatched ? ' watched' : '');
  el.dataset.ticker = s.ticker;
  el.innerHTML = `
    <div class="sc-row1">
      <div class="sc-rank">#${s.rank}</div>
      <div class="sc-info">
        <div class="sc-ticker-line">
          <span class="sc-ticker">${s.ticker}</span>
          <span class="sc-name">${s.name}</span>
        </div>
        <div class="sc-sector">${s.sector}</div>
      </div>
      <div class="sc-right">
        <span class="sig-badge ${sigClass(s.signal)}">${sigShort(s.signal)}</span>
        <span class="sc-change ${chgPos ? 'pos' : 'neg'}">${fmtChange(s.change_pct)}</span>
        <span class="sc-price">${fmtPrice(s.price)}</span>
      </div>
    </div>
    <div class="sc-row2">
      <div class="sc-metric">Score <b style="color:${color}">${s.score}</b></div>
      <div class="sc-metric ${rsiCls}">RSI <b>${s.rsi}</b></div>
      <div class="sc-metric ${macdCls}">MACD <b>${macdDir}</b></div>
      <div class="sc-metric ${maCls}">MA <b>${maIcon}</b></div>
      <div class="sc-metric" style="flex:1">
        <div class="score-bar-wrap">
          <div class="score-bar-fill" style="width:${s.score}%;background:${color}"></div>
        </div>
      </div>
    </div>`;

  el.addEventListener('click', () => openDetail(s));
  return el;
}

// ── Render: screener list ────────────────────────────────────────
function renderScreener() {
  const list   = $('stock-list');
  const stocks = filteredStocks();
  list.innerHTML = '';

  if (!getData()) {
    list.innerHTML = `<div class="empty-state">
      <h3>No data loaded</h3>
      <p>Run <b>nasdaq_screener.py</b> to generate data.js,<br>then refresh this page.</p>
    </div>`;
    return;
  }

  if (stocks.length === 0) {
    list.innerHTML = `<div class="empty-state">
      <h3>No stocks match</h3>
      <p>Try changing the filter.</p>
    </div>`;
    return;
  }

  const frag = document.createDocumentFragment();
  stocks.forEach(s => frag.appendChild(renderCard(s)));
  list.appendChild(frag);
}

// ── Render: watchlist ────────────────────────────────────────────
function renderWatchlist() {
  const list = $('watchlist-list');
  list.innerHTML = '';

  const data = getData();
  if (!data || state.watchlist.length === 0) {
    list.innerHTML = `<div class="wl-empty">
      <div class="star">☆</div>
      <p>Tap any stock to open it,<br>then hit <b>Watch</b> to pin it here.</p>
    </div>`;
    return;
  }

  const watched = data.stocks.filter(s => state.watchlist.includes(s.ticker));
  const frag    = document.createDocumentFragment();
  watched.forEach(s => frag.appendChild(renderCard(s)));
  list.appendChild(frag);
}

// ── Render: summary bar ──────────────────────────────────────────
function renderSummary() {
  const data = getData();
  const bar  = $('summary-bar');
  if (!data) { bar.innerHTML = ''; return; }

  const S = data.summary;
  bar.innerHTML = `
    <span class="sum-chip sb">▲▲ ${S['STRONG BUY']} Str Buy</span>
    <span class="sum-chip b">▲ ${S['BUY']} Buy</span>
    <span class="sum-chip h">— ${S['HOLD']} Hold</span>
    <span class="sum-chip s">▼ ${S['SELL']} Sell</span>
    <span class="sum-chip ss">▼▼ ${S['STRONG SELL']} Str Sell</span>`;
}

// ── Render: header ───────────────────────────────────────────────
function renderHeader() {
  const data = getData();
  if (!data) return;
  $('header-count').textContent = data.count + ' stocks';
  $('header-updated').textContent = 'Updated ' + data.updated;
}

// ── Detail sheet ─────────────────────────────────────────────────
function openDetail(s) {
  state.detail = s;
  const isWatched = state.watchlist.includes(s.ticker);
  const chgPos    = s.change_pct >= 0;
  const color     = scoreColor(s.score);
  const ringCls   = scoreRingClass(s.score);

  const scores    = s.scores;
  const maxScores = {rsi: 25, macd: 25, ma: 25, bb: 15, vol: 10};

  function indRow(name, val, max, fill, fillColor, valStr, labelStr) {
    return `<div class="ind-row">
      <div class="ind-name">${name}</div>
      <div class="ind-bar-wrap"><div class="ind-bar-fill" style="width:${Math.round(fill*100)}%;background:${fillColor}"></div></div>
      <div class="ind-val" style="color:${fillColor}">${valStr}</div>
      <div class="ind-label">${labelStr}</div>
    </div>`;
  }

  function bdRow(name, pts, max) {
    return `<div class="breakdown-row">
      <div class="bd-name">${name}</div>
      <div class="bd-bar-wrap"><div class="bd-bar-fill" style="width:${Math.round(pts/max*100)}%"></div></div>
      <div class="bd-pts">${pts}/${max}</div>
    </div>`;
  }

  const rsiColor  = s.rsi < 30 ? '#22c55e' : s.rsi > 70 ? '#ef4444' : '#94a3b8';
  const macdColor = s.macd_bull ? '#22c55e' : '#ef4444';
  const maColor   = s.ma_cross === 'golden' ? '#d4a017' : s.ma_cross === 'death' ? '#ef4444' : '#94a3b8';
  const bbColor   = s.bb_pct < 0.3 ? '#22c55e' : s.bb_pct > 0.8 ? '#ef4444' : '#94a3b8';
  const volColor  = s.vol_ratio > 1.5 && chgPos ? '#22c55e' : '#94a3b8';

  const macdStr   = s.macd_bull ? 'Bullish' : 'Bearish';
  const pct200Str = s.pct_ma200 != null ? (s.pct_ma200 >= 0 ? '+' : '') + s.pct_ma200 + '%' : 'N/A';

  $('sheet-content').innerHTML = `
    <div class="sheet-header">
      <div class="sheet-left">
        <div class="sheet-ticker">${s.ticker}</div>
        <div class="sheet-name">${s.name}</div>
        <div class="sheet-sector">${s.sector}</div>
      </div>
      <div class="sheet-right">
        <div class="sheet-price ${chgPos ? 'pos' : 'neg'}" style="color:${chgPos?'#22c55e':'#ef4444'}">
          ${fmtPrice(s.price)}&nbsp;${fmtChange(s.change_pct)}
        </div>
        <button class="watch-btn ${isWatched ? 'watching' : ''}" id="watch-btn">
          ${isWatched ? '★ Watching' : '☆ Watch'}
        </button>
      </div>
    </div>

    <div class="score-section">
      <div class="score-ring ${ringCls}" style="border-color:${color};color:${color}">${s.score}</div>
      <div class="score-info">
        <div class="score-label">Overall Score / 100</div>
        <div class="score-signal-large" style="color:${color}">${s.signal}</div>
      </div>
    </div>

    <div class="section-title">Technical Indicators</div>
    ${indRow('RSI (14-day)', s.rsi, 100, s.rsi/100, rsiColor, s.rsi.toFixed(1), rsiLabel(s.rsi))}
    ${indRow('MACD', null, 1, s.macd_bull ? 0.75 : 0.25, macdColor, macdStr, s.macd_bull ? 'Bullish' : 'Bearish')}
    ${indRow('50d / 200d MA', null, 1, s.pct_ma200 != null ? Math.min(Math.max((s.pct_ma200+30)/60, 0), 1) : 0.5, maColor, pct200Str, maLabel(s.ma_cross))}
    ${indRow('Bollinger %B', s.bb_pct, 1, 1 - s.bb_pct, bbColor, (s.bb_pct*100).toFixed(0)+'%', bbLabel(s.bb_pct))}
    ${indRow('Volume Ratio', s.vol_ratio, 3, Math.min(s.vol_ratio/3, 1), volColor, s.vol_ratio.toFixed(1)+'x', volLabel(s.vol_ratio))}

    <div class="section-title">Score Breakdown</div>
    ${bdRow('RSI',  scores.rsi,  maxScores.rsi)}
    ${bdRow('MACD', scores.macd, maxScores.macd)}
    ${bdRow('MA',   scores.ma,   maxScores.ma)}
    ${bdRow('Boll', scores.bb,   maxScores.bb)}
    ${bdRow('Vol',  scores.vol,  maxScores.vol)}`;

  $('watch-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    toggleWatch(s.ticker);
  });

  const backdrop = $('sheet-backdrop');
  const sheet    = $('detail-sheet');
  backdrop.classList.remove('hidden');
  sheet.classList.remove('hidden');
  requestAnimationFrame(() => sheet.classList.add('open'));
}

function closeDetail() {
  const sheet = $('detail-sheet');
  sheet.classList.remove('open');
  setTimeout(() => {
    sheet.classList.add('hidden');
    $('sheet-backdrop').classList.add('hidden');
    sheet.scrollTop = 0;
  }, 300);
  state.detail = null;
}

$('sheet-backdrop').addEventListener('click', closeDetail);

// ── Watchlist toggle ─────────────────────────────────────────────
function toggleWatch(ticker) {
  const idx = state.watchlist.indexOf(ticker);
  if (idx === -1) {
    state.watchlist.push(ticker);
    toast('Added to watchlist');
  } else {
    state.watchlist.splice(idx, 1);
    toast('Removed from watchlist');
  }
  localStorage.setItem('watchlist', JSON.stringify(state.watchlist));

  // Update watch button in open sheet
  const btn = $('watch-btn');
  if (btn) {
    const watching = state.watchlist.includes(ticker);
    btn.textContent = watching ? '★ Watching' : '☆ Watch';
    btn.classList.toggle('watching', watching);
  }

  // Re-render current view
  if (state.view === 'watchlist') renderWatchlist();
  else renderScreener();
}

// ── Filters ──────────────────────────────────────────────────────
function initFilters() {
  const data = getData();
  if (!data) return;

  // Sector dropdown
  const sectors = [...new Set(data.stocks.map(s => s.sector))].sort();
  const sel = $('sector-filter');
  sectors.forEach(sec => {
    const opt = document.createElement('option');
    opt.value = sec;
    opt.textContent = sec;
    sel.appendChild(opt);
  });

  // Signal tabs
  document.querySelectorAll('.sig-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sig-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.sigFilter = btn.dataset.sig;
      renderScreener();
    });
  });

  // Sector
  sel.addEventListener('change', () => {
    state.sector = sel.value;
    renderScreener();
  });

  // Sort
  $('sort-select').addEventListener('change', (e) => {
    state.sort = e.target.value;
    renderScreener();
  });
}

// ── Nav ──────────────────────────────────────────────────────────
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.view = btn.dataset.view;
    $('screener-view').classList.toggle('hidden',  state.view !== 'screener');
    $('watchlist-view').classList.toggle('hidden', state.view !== 'watchlist');
    if (state.view === 'watchlist') renderWatchlist();
  });
});

// ── Init ─────────────────────────────────────────────────────────
function init() {
  renderHeader();
  renderSummary();
  initFilters();
  renderScreener();

  if ('serviceWorker' in navigator && 'BeforeInstallPromptEvent' in window) {
    let deferredPrompt;
    window.addEventListener('beforeinstallprompt', e => {
      e.preventDefault();
      deferredPrompt = e;
    });
  }
}

init();
