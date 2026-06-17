'use strict';

if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => {});

// ── State ──────────────────────────────────────────────────────────
const state = {
  view:      'screener',
  sigFilter: 'ALL',
  sector:    '',
  sort:      'score',
  watchlist: JSON.parse(localStorage.getItem('watchlist') || '[]'),
};

// ── Helpers ────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function sigClass(sig) { return 'sig-' + sig.replace(' ', '-'); }

function sigShort(sig) {
  return {'STRONG BUY':'STR BUY','BUY':'BUY','HOLD':'HOLD','SELL':'SELL','STRONG SELL':'STR SELL'}[sig] || sig;
}

function scoreColor(s) {
  if (s >= 85) return '#22c55e';
  if (s >= 65) return '#86efac';
  if (s >= 35) return '#fbbf24';
  if (s >= 15) return '#f97316';
  return '#ef4444';
}

function fmtChange(c) {
  return (c >= 0 ? '▲' : '▼') + Math.abs(c).toFixed(1) + '%';
}
function fmtPrice(p) { return p >= 100 ? '$' + p.toFixed(0) : '$' + p.toFixed(2); }

function rsiLabel(v)  { return v < 30 ? 'Oversold' : v > 70 ? 'Overbought' : 'Neutral'; }
function maLabel(c)   { return {golden:'Golden X',death:'Death X',above:'Above 200d',below:'Below 200d'}[c]||c; }
function bbLabel(v)   { return v<0.1?'Near Low':v<0.3?'Lower Half':v<0.7?'Mid Range':v<0.9?'Upper Half':'Near High'; }
function volLabel(v)  { return v > 1.5 ? v.toFixed(1) + 'x Surge' : v.toFixed(1) + 'x Avg'; }

function trendHTML(s) {
  if (s.trend === 'up')   return `<span class="trend-up"  title="Upgraded from ${s.prev_signal}">↑</span>`;
  if (s.trend === 'down') return `<span class="trend-down" title="Downgraded from ${s.prev_signal}">↓</span>`;
  if (s.trend === 'new')  return `<span class="trend-new">NEW</span>`;
  return '';
}

function toast(msg, ms = 1800) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), ms);
}

function getData() { return typeof SCREENER_DATA !== 'undefined' ? SCREENER_DATA : null; }

// ── Filtering & sorting ────────────────────────────────────────────
function filteredStocks() {
  const data = getData();
  if (!data) return [];
  let stocks = [...data.stocks];
  if (state.sigFilter === 'BUY')  stocks = stocks.filter(s => s.signal==='BUY'||s.signal==='STRONG BUY');
  if (state.sigFilter === 'HOLD') stocks = stocks.filter(s => s.signal==='HOLD');
  if (state.sigFilter === 'SELL') stocks = stocks.filter(s => s.signal==='SELL'||s.signal==='STRONG SELL');
  if (state.sector) stocks = stocks.filter(s => s.sector === state.sector);
  if (state.sort === 'rsi_asc')   stocks.sort((a,b) => a.rsi - b.rsi);
  else if (state.sort === 'rsi_desc') stocks.sort((a,b) => b.rsi - a.rsi);
  else if (state.sort === 'change')   stocks.sort((a,b) => b.change_pct - a.change_pct);
  else if (state.sort === 'alpha')    stocks.sort((a,b) => a.ticker.localeCompare(b.ticker));
  return stocks;
}

// ── Stock card ─────────────────────────────────────────────────────
function renderCard(s) {
  const color   = scoreColor(s.score);
  const rsiCls  = s.rsi < 30 ? 'rsi-low' : s.rsi > 70 ? 'rsi-high' : '';
  const macdCls = s.macd_bull ? 'macd-bull' : 'macd-bear';
  const maCls   = s.ma_cross==='golden' ? 'ma-golden' : s.ma_cross==='death' ? 'ma-death' : '';
  const maIcon  = {golden:'★',death:'✕',above:'↑',below:'↓'}[s.ma_cross] || '—';

  const el = document.createElement('article');
  el.className = 'stock-card' + (state.watchlist.includes(s.ticker) ? ' watched' : '');
  el.dataset.ticker = s.ticker;
  el.innerHTML = `
    <div class="sc-row1">
      <div class="sc-rank">#${s.rank}</div>
      <div class="sc-info">
        <div class="sc-ticker-line">
          <span class="sc-ticker">${s.ticker}</span>
          ${trendHTML(s)}
          <span class="sc-name">${s.name}</span>
        </div>
        <div class="sc-sector">${s.sector}</div>
      </div>
      <div class="sc-right">
        <span class="sig-badge ${sigClass(s.signal)}">${sigShort(s.signal)}</span>
        <span class="sc-change ${s.change_pct>=0?'pos':'neg'}">${fmtChange(s.change_pct)}</span>
        <span class="sc-price">${fmtPrice(s.price)}</span>
      </div>
    </div>
    <div class="sc-row2">
      <div class="sc-metric">Score <b style="color:${color}">${s.score}</b></div>
      <div class="sc-metric ${rsiCls}">RSI <b>${s.rsi}</b></div>
      <div class="sc-metric ${macdCls}">MACD <b>${s.macd_bull?'▲':'▼'}</b></div>
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

// ── Screener view ──────────────────────────────────────────────────
function renderScreener() {
  const list = $('stock-list');
  const stocks = filteredStocks();
  list.innerHTML = '';
  if (!getData()) {
    list.innerHTML = `<div class="empty-state"><h3>No data</h3>
      <p>Run <b>nasdaq_screener.py</b> then refresh.</p></div>`;
    return;
  }
  if (!stocks.length) {
    list.innerHTML = `<div class="empty-state"><h3>No matches</h3><p>Try a different filter.</p></div>`;
    return;
  }
  const frag = document.createDocumentFragment();
  stocks.forEach(s => frag.appendChild(renderCard(s)));
  list.appendChild(frag);
}

// ── Sector heatmap ─────────────────────────────────────────────────
function renderHeatmap() {
  const grid = $('heatmap-grid');
  const data = getData();
  if (!data || !data.sectors) { grid.innerHTML = '<div class="empty-state"><h3>No data</h3></div>'; return; }

  grid.innerHTML = data.sectors.map(sec => {
    const color  = scoreColor(sec.avg_score);
    const buyTot = sec.counts['STRONG BUY'] + sec.counts['BUY'];
    const sellTot= sec.counts['SELL'] + sec.counts['STRONG SELL'];
    const topStr = sec.top.join(' · ');
    const buyPct = Math.round(buyTot / sec.count * 100);

    return `<div class="hm-card" data-sector="${sec.sector}" onclick="goToSector('${sec.sector}')">
      <div class="hm-sector">${sec.sector}</div>
      <div class="hm-score" style="color:${color}">${sec.avg_score}</div>
      <div class="hm-badge-wrap">
        <span class="sig-badge ${sigClass(sec.signal)}">${sigShort(sec.signal)}</span>
      </div>
      <div class="hm-dist">
        <span class="hm-buy">${buyTot} Buy</span>
        <span class="hm-hold">${sec.counts['HOLD']} Hold</span>
        <span class="hm-sell">${sellTot} Sell</span>
      </div>
      <div class="hm-top">${topStr}</div>
      <div class="hm-trend-bar">
        <div class="hm-trend-fill" style="width:${buyPct}%;background:${color}"></div>
      </div>
    </div>`;
  }).join('');
}

function goToSector(sector) {
  // Switch to screener, apply sector filter
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.nav-btn[data-view="screener"]').classList.add('active');
  $('screener-view').classList.remove('hidden');
  $('heatmap-view').classList.add('hidden');
  $('watchlist-view').classList.add('hidden');
  state.view   = 'screener';
  state.sector = sector;
  $('sector-filter').value = sector;
  renderScreener();
}

// ── Watchlist ──────────────────────────────────────────────────────
function renderWatchlist() {
  const list = $('watchlist-list');
  const data = getData();
  list.innerHTML = '';
  if (!data || !state.watchlist.length) {
    list.innerHTML = `<div class="wl-empty"><div class="star">☆</div>
      <p>Tap any stock, then <b>Watch</b> to pin it here.</p></div>`;
    return;
  }
  const watched = data.stocks.filter(s => state.watchlist.includes(s.ticker));
  const frag = document.createDocumentFragment();
  watched.forEach(s => frag.appendChild(renderCard(s)));
  list.appendChild(frag);
}

// ── Summary bar ────────────────────────────────────────────────────
function renderSummary() {
  const data = getData();
  if (!data) return;
  const S = data.summary;
  const T = data.trend_summary || {};
  $('summary-bar').innerHTML = `
    <span class="sum-chip sb">▲▲ ${S['STRONG BUY']}</span>
    <span class="sum-chip b">▲ ${S['BUY']}</span>
    <span class="sum-chip h">— ${S['HOLD']}</span>
    <span class="sum-chip s">▼ ${S['SELL']}</span>
    <span class="sum-chip ss">▼▼ ${S['STRONG SELL']}</span>
    ${T.up||T.down ? `<span class="sum-chip tr">↑${T.up||0} ↓${T.down||0} signals</span>` : ''}`;
}

function renderHeader() {
  const data = getData();
  if (!data) return;
  $('header-count').textContent = data.count + ' stocks';
  $('header-updated').textContent = 'Updated ' + data.updated;
}

// ── Detail sheet ───────────────────────────────────────────────────
function indRow(name, fillPct, color, valStr, labelStr) {
  return `<div class="ind-row">
    <div class="ind-name">${name}</div>
    <div class="ind-bar-wrap"><div class="ind-bar-fill" style="width:${Math.round(fillPct*100)}%;background:${color}"></div></div>
    <div class="ind-val" style="color:${color}">${valStr}</div>
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

function fundItem(val, label, good) {
  const cls = val == null ? 'na' : (good ? 'good' : 'bad');
  const display = val == null ? 'N/A' : val;
  return `<div class="fund-item">
    <div class="fund-val ${cls}">${display}</div>
    <div class="fund-label">${label}</div>
  </div>`;
}

function openDetail(s) {
  const color   = scoreColor(s.score);
  const chgPos  = s.change_pct >= 0;
  const sc      = s.scores || {};
  const maxSc   = {rsi:25, macd:25, ma:25, bb:15, vol:10, fund:30};
  const isWatched = state.watchlist.includes(s.ticker);

  const rsiColor  = s.rsi < 30 ? '#22c55e' : s.rsi > 70 ? '#ef4444' : '#94a3b8';
  const macdColor = s.macd_bull ? '#22c55e' : '#ef4444';
  const maColor   = s.ma_cross==='golden' ? '#d4a017' : s.ma_cross==='death' ? '#ef4444' : '#94a3b8';
  const bbColor   = s.bb_pct < 0.3 ? '#22c55e' : s.bb_pct > 0.8 ? '#ef4444' : '#94a3b8';
  const volColor  = s.vol_ratio > 1.5 && chgPos ? '#22c55e' : '#94a3b8';

  const pct200 = s.pct_ma200 != null ? (s.pct_ma200>=0?'+':'')+s.pct_ma200+'%' : 'N/A';
  const ma200Fill = s.pct_ma200 != null ? Math.min(Math.max((s.pct_ma200+30)/60,0),1) : 0.5;

  const trendLine = s.trend === 'up'   ? `↑ Upgraded from ${s.prev_signal}` :
                    s.trend === 'down' ? `↓ Downgraded from ${s.prev_signal}` : '';

  // Fundamentals display
  const peDisplay  = s.pe  ? s.pe.toFixed(1) + 'x'  : null;
  const fpeDisplay = s.fpe ? s.fpe.toFixed(1) + 'x' : null;
  const egDisplay  = s.eps_growth != null ? (s.eps_growth>0?'+':'')+s.eps_growth+'%' : null;
  const rgDisplay  = s.rev_growth != null ? (s.rev_growth>0?'+':'')+s.rev_growth+'%' : null;

  $('sheet-content').innerHTML = `
    <div class="sheet-header">
      <div class="sheet-left">
        <div class="sheet-ticker">${s.ticker}</div>
        <div class="sheet-name">${s.name}</div>
        <div class="sheet-sector">${s.sector}</div>
      </div>
      <div class="sheet-right">
        <div style="font-size:16px;font-weight:700;color:${chgPos?'#22c55e':'#ef4444'}">
          ${fmtPrice(s.price)} ${fmtChange(s.change_pct)}
        </div>
        <button class="watch-btn ${isWatched?'watching':''}" id="watch-btn">
          ${isWatched ? '★ Watching' : '☆ Watch'}
        </button>
      </div>
    </div>

    <div class="score-section">
      <div class="score-ring" style="border-color:${color};color:${color}">${s.score}</div>
      <div>
        <div class="score-label">Score / 100</div>
        <div class="score-signal-large" style="color:${color}">${s.signal}</div>
        ${trendLine ? `<div class="score-trend">${trendLine}</div>` : ''}
      </div>
    </div>

    <div class="section-title">Technical Indicators</div>
    ${indRow('RSI (14d)', s.rsi/100, rsiColor, s.rsi.toFixed(1), rsiLabel(s.rsi))}
    ${indRow('MACD', s.macd_bull?0.75:0.25, macdColor, s.macd_bull?'Bullish':'Bearish', s.macd_bull?'Bull':'Bear')}
    ${indRow('50d / 200d MA', ma200Fill, maColor, pct200, maLabel(s.ma_cross))}
    ${indRow('Bollinger %B', 1-s.bb_pct, bbColor, (s.bb_pct*100).toFixed(0)+'%', bbLabel(s.bb_pct))}
    ${indRow('Volume', Math.min(s.vol_ratio/3,1), volColor, s.vol_ratio.toFixed(1)+'x', volLabel(s.vol_ratio))}

    <div class="section-title">Fundamentals</div>
    <div class="fund-grid">
      ${fundItem(peDisplay, 'Trailing P/E', s.pe && s.pe < 25)}
      ${fundItem(fpeDisplay, 'Forward P/E', s.fpe && s.pe && s.fpe < s.pe)}
      ${fundItem(egDisplay, 'EPS Growth', s.eps_growth > 0)}
      ${fundItem(rgDisplay, 'Revenue Growth', s.rev_growth > 0)}
    </div>

    <div class="section-title">Score Breakdown</div>
    ${bdRow('RSI',  sc.rsi||0,  maxSc.rsi)}
    ${bdRow('MACD', sc.macd||0, maxSc.macd)}
    ${bdRow('MA',   sc.ma||0,   maxSc.ma)}
    ${bdRow('Boll', sc.bb||0,   maxSc.bb)}
    ${bdRow('Vol',  sc.vol||0,  maxSc.vol)}
    ${bdRow('Fund', sc.fund||0, maxSc.fund)}`;

  $('watch-btn').addEventListener('click', e => { e.stopPropagation(); toggleWatch(s.ticker); });

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
}

$('sheet-backdrop').addEventListener('click', closeDetail);

// ── Watchlist toggle ───────────────────────────────────────────────
function toggleWatch(ticker) {
  const idx = state.watchlist.indexOf(ticker);
  if (idx === -1) { state.watchlist.push(ticker); toast('Added to watchlist'); }
  else            { state.watchlist.splice(idx, 1); toast('Removed from watchlist'); }
  localStorage.setItem('watchlist', JSON.stringify(state.watchlist));
  const btn = $('watch-btn');
  if (btn) {
    const w = state.watchlist.includes(ticker);
    btn.textContent = w ? '★ Watching' : '☆ Watch';
    btn.classList.toggle('watching', w);
  }
  if (state.view === 'watchlist') renderWatchlist();
  else renderScreener();
}

// ── Nav ────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.view = btn.dataset.view;
    $('screener-view').classList.toggle('hidden',  state.view !== 'screener');
    $('heatmap-view').classList.toggle('hidden',   state.view !== 'heatmap');
    $('watchlist-view').classList.toggle('hidden', state.view !== 'watchlist');
    if (state.view === 'heatmap')   renderHeatmap();
    if (state.view === 'watchlist') renderWatchlist();
  });
});

// ── Filters ────────────────────────────────────────────────────────
function initFilters() {
  const data = getData();
  if (!data) return;
  const sectors = [...new Set(data.stocks.map(s => s.sector))].sort();
  const sel = $('sector-filter');
  sectors.forEach(sec => {
    const opt = document.createElement('option');
    opt.value = sec; opt.textContent = sec;
    sel.appendChild(opt);
  });
  document.querySelectorAll('.sig-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.sig-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.sigFilter = btn.dataset.sig;
      renderScreener();
    });
  });
  sel.addEventListener('change', () => { state.sector = sel.value; renderScreener(); });
  $('sort-select').addEventListener('change', e => { state.sort = e.target.value; renderScreener(); });
}

// ── Init ───────────────────────────────────────────────────────────
function init() {
  renderHeader();
  renderSummary();
  initFilters();
  renderScreener();
}
init();
