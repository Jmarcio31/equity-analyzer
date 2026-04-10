// ─── State ────────────────────────────────────────────────────────────────────
let allResults = [];
let selectedTickers = []; // [{symbol, name, color}]
const chartInstances = {};

// ─── Ticker Card Selection ────────────────────────────────────────────────────
function toggleTicker(symbol, name, color) {
  const idx = selectedTickers.findIndex(t => t.symbol === symbol);
  const card = document.getElementById(`card-${symbol}`);

  if (idx >= 0) {
    // Deseleciona
    selectedTickers.splice(idx, 1);
    card.classList.remove('selected');
    card.style.borderColor = '';
  } else {
    if (selectedTickers.length >= 3) {
      // Remove o mais antigo
      const removed = selectedTickers.shift();
      const oldCard = document.getElementById(`card-${removed.symbol}`);
      if (oldCard) { oldCard.classList.remove('selected'); oldCard.style.borderColor = ''; }
    }
    selectedTickers.push({symbol, name, color});
    card.classList.add('selected');
    card.style.borderColor = color;
    card.querySelector('.ticker-card-check').style.color = color;
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  const preview      = document.getElementById('selected-preview');
  const headerSelected = document.getElementById('header-selected');
  const headerChips  = document.getElementById('header-chips');
  const btnMain      = document.getElementById('btn-analyze-main');

  if (selectedTickers.length === 0) {
    preview.innerHTML = '<div class="sidebar-hint">Clique nas ações<br>para selecionar</div>';
    if (btnMain) btnMain.disabled = true;
    return;
  }

  preview.innerHTML = selectedTickers.map(t =>
    `<div class="preview-chip" style="background:${t.color}">${t.symbol} — ${t.name}</div>`
  ).join('');

  if (btnMain) btnMain.disabled = false;

  if (headerChips) {
    headerChips.innerHTML = selectedTickers.map(t =>
      `<div class="header-chip" style="background:${t.color}">${t.symbol}</div>`
    ).join('');
  }
}

function clearSelection() {
  selectedTickers.forEach(t => {
    const card = document.getElementById(`card-${t.symbol}`);
    if (card) { card.classList.remove('selected'); card.style.borderColor = ''; }
  });
  selectedTickers = [];
  updateSelectionUI();
  goHome();
}

// ─── Format helpers ───────────────────────────────────────────────────────────
const fmt = {
  pct:  v => v == null ? '—' : (v * 100).toFixed(1) + '%',
  pct1: v => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%',
  x:    v => v == null ? '—' : v.toFixed(1) + 'x',
  $:    v => v == null ? '—' : '$' + v.toFixed(2),
  bn:   v => v == null ? '—' : '$' + (v / 1e9).toFixed(1) + 'B',
};
function colorClass(v) { return v == null ? '' : v > 0 ? 'pos' : v < 0 ? 'neg' : ''; }

// ─── Suggestions ──────────────────────────────────────────────────────────────
function filterSuggestions(idx) {
  const input = document.getElementById(`main-t${idx}`);
  const box   = document.getElementById(`sug-${idx}`);
  const q = (input.value || '').toUpperCase().trim();
  if (!q) { box.classList.remove('open'); return; }
  const matches = POPULAR.filter(p => p.s.startsWith(q) || p.n.toUpperCase().includes(q)).slice(0, 6);
  if (!matches.length) { box.classList.remove('open'); return; }
  box.innerHTML = matches.map(p =>
    `<div class="sug-item" onclick="selectTicker(${idx},'${p.s}')">
      <span class="sug-ticker">${p.s}</span>
      <span class="sug-name">${p.n}</span>
    </div>`
  ).join('');
  box.classList.add('open');
}

function selectTicker(idx, ticker) {
  const input = document.getElementById(`main-t${idx}`);
  input.value = ticker;
  document.getElementById(`sug-${idx}`).classList.remove('open');
  // Sync header input if exists
  const hi = document.getElementById(`h-t${idx}`);
  if (hi) hi.value = ticker;
}

function handleKey(e, idx) {
  if (e.key === 'Enter') { closeSuggestions(); runAnalysis(); }
  if (e.key === 'Escape') closeSuggestions();
}

function closeSuggestions() {
  document.querySelectorAll('.suggestions').forEach(s => s.classList.remove('open'));
}
document.addEventListener('click', e => {
  if (!e.target.closest('.ticker-slot') && !e.target.closest('.header-ticker-wrapper')) closeSuggestions();
});

// ─── Navigation ───────────────────────────────────────────────────────────────
function goHome() {
  document.getElementById('results').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  document.getElementById('landing').classList.remove('hidden');
  document.getElementById('header-selected').style.display = 'none';
  allResults = [];
}

function setTickers(t0, t1, t2) {
  document.getElementById('main-t0').value = t0 || '';
  document.getElementById('main-t1').value = t1 || '';
  document.getElementById('main-t2').value = t2 || '';
  runAnalysis();
}

// ─── Header search sync ───────────────────────────────────────────────────────
function showHeaderSelection() {
  const el = document.getElementById('header-selected');
  if (el) el.style.display = 'flex';
}

// ─── Status visual dos cards (carregado = vibrante, pendente = pálido) ───────
async function applyCardStatus() {
  try {
    const r = await fetch('/api/quota-check');
    const d = await r.json();
    d.tickers.forEach(t => {
      const card = document.getElementById(`card-${t.symbol}`);
      if (!card) return;
      if (t.has_data) {
        card.classList.remove('ticker-card--pending');
        card.classList.add('ticker-card--loaded');
      } else {
        card.classList.remove('ticker-card--loaded');
        card.classList.add('ticker-card--pending');
      }
    });
  } catch(e) { console.log('Erro ao verificar status:', e); }
}

// Aplica visual de carregado/pendente nos cards
document.addEventListener('DOMContentLoaded', () => applyCardStatus());

// ─── Main analysis ────────────────────────────────────────────────────────────
async function runAnalysis() {
  const tickers = selectedTickers.map(t => t.symbol);
  if (!tickers.length) return;
  document.getElementById('landing').classList.add('hidden');
  document.getElementById('results').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  document.getElementById('loading').classList.remove('hidden');

  const btnMain   = document.getElementById('btn-text-main');
  const btnHeader = document.getElementById('btn-text-header');
  if (btnMain)   btnMain.textContent   = 'Buscando…';
  if (btnHeader) btnHeader.textContent = 'Buscando…';

  try {
    const res  = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tickers})
    });
    const data = await res.json();

    if (data.errors?.length) {
      const eb = document.getElementById('error-box');
      eb.innerHTML = data.errors.map(e => `<b>${e.ticker}</b>: ${e.error}`).join('<br>');
      eb.classList.remove('hidden');
    }
    if (data.results?.length) {
      allResults = data.results;
      showHeaderSelection();
      renderResults(data.results);
    }
  } catch(e) {
    const eb = document.getElementById('error-box');
    eb.textContent = 'Erro de conexão: ' + e.message;
    eb.classList.remove('hidden');
    document.getElementById('landing').classList.remove('hidden');
    document.getElementById('header-search').style.display = 'none';
  } finally {
    document.getElementById('loading').classList.add('hidden');
    if (btnMain)   btnMain.textContent   = 'Analisar';
    if (btnHeader) btnHeader.textContent = 'Analisar';
  }
}

// ─── Render ───────────────────────────────────────────────────────────────────
function renderResults(results) {
  const container = document.getElementById('results');
  container.innerHTML = '';
  if (results.length > 1) container.appendChild(buildComparisonPanel(results));
  results.forEach((r, idx) => container.appendChild(buildCompanyCard(r, idx)));
  container.classList.remove('hidden');
}

// ─── Comparison ───────────────────────────────────────────────────────────────
function buildComparisonPanel(results) {
  const metrics = [
    {label:'Preço',              fn: r => fmt.$(r.price),                raw: r => r.price},
    {label:'Margem de Segurança (Média)', fn: r => fmt.pct1(r.valuation.avg_ms), raw: r => r.valuation.avg_ms},
    {label:'EV / EBIT',          fn: r => fmt.x(r.valuation.ev_ebit),   raw: r => r.valuation.ev_ebit},
    {label:'ROIC (último)',      fn: r => fmt.pct(r.valuation.roic_last),raw: r => r.valuation.roic_last},
    {label:'WACC (último)',      fn: r => fmt.pct(r.valuation.wacc_last),raw: r => r.valuation.wacc_last},
    {label:'Spread ROIC−WACC',  fn: r => fmt.pct1(r.valuation.econ_spread), raw: r => r.valuation.econ_spread},
    {label:'FCF Yield',          fn: r => fmt.pct(r.valuation.fcf_yield),raw: r => r.valuation.fcf_yield},
    {label:'Div Yield',          fn: r => fmt.pct(r.valuation.div_yield),raw: r => r.valuation.div_yield},
    {label:'Market Cap',         fn: r => fmt.bn(r.valuation.mktcap),   raw: r => r.valuation.mktcap},
  ];
  const cards = metrics.map(m => {
    const rows = results.map(r => `<div class="comp-row">
      <span class="comp-ticker">${r.ticker}</span>
      <span class="comp-val ${colorClass(m.raw(r))}">${m.fn(r)}</span></div>`).join('');
    return `<div class="comp-metric-card"><div class="comp-metric-title">${m.label}</div>${rows}</div>`;
  }).join('');
  const div = document.createElement('div');
  div.innerHTML = `<div class="company-card">
    <div class="company-header">
      <div class="company-title">
        <span style="font-size:17px;font-weight:700">Comparação</span>
        <span style="color:var(--text3);font-size:12px">${results.map(r=>r.ticker).join(' · ')}</span>
      </div>
    </div>
    <div style="padding:20px"><div class="comparison-grid">${cards}</div></div>
  </div>`;
  return div.firstElementChild;
}

// ─── Company Card ─────────────────────────────────────────────────────────────
function buildCompanyCard(r, idx) {
  const color = r.color || ['#4f7cff','#22c55e','#f59e0b'][idx % 3];
  const v = r.valuation;
  const card = document.createElement('div');
  card.className = 'company-card';
  card.innerHTML = `
    <div class="company-header">
      <div class="company-title">
        <span class="ticker-badge" style="background:${color}">${r.ticker}</span>
        <div>
          <div class="company-name">${r.name}</div>
          <div class="company-meta">${r.sector}${r.industry ? ' · ' + r.industry : ''} · ${r.exchange} · ${r.currency}</div>
        </div>
      </div>
      <div class="company-price">
        <div class="price-value">${fmt.$(r.price)}</div>
        <div class="price-label">Cotação atual</div>
      </div>
    </div>
    <div class="tabs" id="tabs-${r.ticker}">
      <button class="tab-btn active" onclick="switchTab('${r.ticker}','valuation',this)">📊 Valuation</button>
      <button class="tab-btn" onclick="switchTab('${r.ticker}','charts',this)">📈 Gráficos</button>
      <button class="tab-btn" onclick="switchTab('${r.ticker}','table',this)">🗂 Trimestres (${r.rows.length})</button>
      <button class="tab-btn" onclick="switchTab('${r.ticker}','glossary',this)">📖 Glossário</button>
    </div>
    <div id="panel-${r.ticker}-valuation" class="tab-panel active">${buildValuationPanel(r, v)}</div>
    <div id="panel-${r.ticker}-charts"    class="tab-panel">${buildChartsPanel(r)}</div>
    <div id="panel-${r.ticker}-table"     class="tab-panel">${buildTablePanel(r)}</div>
    <div id="panel-${r.ticker}-glossary"  class="tab-panel">${buildGlossaryPanel()}</div>`;
  return card;
}

function switchTab(ticker, tab, btnEl) {
  document.querySelectorAll(`#tabs-${ticker} .tab-btn`).forEach(b => b.classList.remove('active'));
  document.querySelectorAll(`[id^="panel-${ticker}-"]`).forEach(p => p.classList.remove('active'));
  btnEl.classList.add('active');
  document.getElementById(`panel-${ticker}-${tab}`).classList.add('active');
  if (tab === 'charts') renderCharts(ticker);
}

// ─── Valuation Panel ──────────────────────────────────────────────────────────
function buildValuationPanel(r, v) {
  const kpis = [
    {label:'Cotação',           value: fmt.$(r.price)},
    {label:'EV / EBIT',         value: fmt.x(v.ev_ebit)},
    {label:'Market Cap',        value: fmt.bn(v.mktcap)},
    {label:'Enterprise Value',  value: fmt.bn(v.ev)},
    {label:'ROIC (último trim.)',value: fmt.pct(v.roic_last),  cls: colorClass(v.roic_last - v.wacc_last)},
    {label:'WACC (último trim.)',value: fmt.pct(v.wacc_last)},
    {label:'Spread ROIC−WACC',  value: fmt.pct1(v.econ_spread), cls: colorClass(v.econ_spread)},
    {label:'Treasury Yield (10Y)',value: fmt.pct(v.treasury_yield)},
    {label:'Cash Excess / Ação', value: fmt.$(v.cash_excess_ps)},
    {label:'FCF Yield',          value: fmt.pct(v.fcf_yield), cls: colorClass(v.fcf_yield)},
    {label:'EBIT Yield (TIR)',   value: fmt.pct(v.tir),       cls: colorClass(v.tir)},
    {label:'Div Yield',          value: fmt.pct(v.div_yield)},
  ];
  const kpiHtml = kpis.map(k => `<div class="val-card">
    <div class="val-label">${k.label}</div>
    <div class="val-value ${k.cls||''}">${k.value}</div>
  </div>`).join('');

  const msRows = [
    {metric:'EBIT',           eps: fmt.$(v.ebit_ps), cagr: fmt.pct(v.ebit_cagr), graham: fmt.$(v.graham_ebit), ms: v.ms_ebit},
    {metric:'FCF − SBC',      eps: fmt.$(v.fcf_ps),  cagr: fmt.pct(v.fcf_cagr),  graham: fmt.$(v.graham_fcf),  ms: v.ms_fcf},
    {metric:'Economic Profit',eps: fmt.$(v.ep_ps),   cagr: fmt.pct(v.ep_cagr),   graham: fmt.$(v.graham_ep),   ms: v.ms_ep},
    {metric:'Dividendos',     eps: fmt.$(v.div_ps),  cagr: fmt.pct(v.div_cagr),  graham: fmt.$(v.graham_div),  ms: v.ms_div},
  ].map(row => {
    const ms = row.ms;
    const barPct = ms == null ? 0 : Math.min(Math.abs(ms) * 100, 100);
    const barColor = ms == null ? '#64748b' : (ms >= 0 ? '#22c55e' : '#ef4444');
    const barStyle = ms != null && ms < 0
      ? `right:50%;width:${barPct/2}%`
      : `left:50%;width:${barPct/2}%`;
    return `<tr>
      <td><b>${row.metric}</b></td>
      <td>${row.eps}</td><td>${row.cagr}</td><td>${row.graham}</td>
      <td class="${colorClass(ms)}" style="font-weight:600">${ms==null?'—':fmt.pct1(ms)}</td>
      <td><div class="ms-bar-bg" style="position:relative">
        <div class="ms-bar-fill" style="${barStyle};background:${barColor};position:absolute;top:0;height:100%"></div>
        <div style="position:absolute;top:0;left:50%;width:1px;height:100%;background:var(--border)"></div>
      </div></td>
    </tr>`;
  }).join('');

  return `
    <div class="valuation-grid">${kpiHtml}</div>
    <h3 style="margin-bottom:8px;font-size:13px;color:var(--text2)">Margem de Segurança — Fórmula de Graham</h3>
    <p style="font-size:11px;color:var(--text3);margin-bottom:12px">V = EPS × (8,5 + 2 × CAGR%) × 4,4 / Y &nbsp;·&nbsp; MS = (V − Preço) / V</p>
    <div class="ms-table-wrap"><table class="ms-table">
      <thead><tr><th>Métrica</th><th>EPS/Ação TTM</th><th>CAGR</th><th>Graham (V)</th><th>Margem de Segurança</th><th></th></tr></thead>
      <tbody>${msRows}</tbody>
      <tfoot><tr style="font-weight:700;border-top:2px solid var(--border)">
        <td colspan="4" style="text-align:right;padding-right:14px">Média (FCF + EP + Div)</td>
        <td class="${colorClass(v.avg_ms)}" style="font-size:15px">${fmt.pct1(v.avg_ms)}</td><td></td>
      </tr></tfoot>
    </table></div>`;
}

// ─── Charts Panel ─────────────────────────────────────────────────────────────
function buildChartsPanel(r) {
  const id = r.ticker;
  return `
    <div class="chart-card chart-card-wide">
      <div class="chart-header">
        <div class="chart-title">📈 Preço × Métricas Fundamentalistas</div>
        <div class="chart-toggles" id="tog-${id}">
          <label class="tog-btn tog-active" data-metric="ebit"><span class="tog-dot" style="background:#4f7cff"></span>EBIT/ação</label>
          <label class="tog-btn tog-active" data-metric="ep"><span class="tog-dot" style="background:#a78bfa"></span>Eco. Profit/ação</label>
          <label class="tog-btn tog-active" data-metric="fcf"><span class="tog-dot" style="background:#22c55e"></span>FCF-SBC/ação</label>
          <label class="tog-btn" data-metric="graham_ebit"><span class="tog-dot" style="background:#f59e0b"></span>Graham EBIT</label>
          <label class="tog-btn" data-metric="graham_ep"><span class="tog-dot" style="background:#fb923c"></span>Graham EP</label>
        </div>
      </div>
      <canvas style="max-height:320px" id="ch-price-${id}"></canvas>
    </div>
    <div class="charts-grid">
      <div class="chart-card"><div class="chart-title">EBIT por Ação (TTM)</div><canvas class="chart-canvas" id="ch-ebit-${id}"></canvas></div>
      <div class="chart-card"><div class="chart-title">FCF − SBC por Ação (TTM)</div><canvas class="chart-canvas" id="ch-fcf-${id}"></canvas></div>
      <div class="chart-card"><div class="chart-title">Economic Profit por Ação (TTM)</div><canvas class="chart-canvas" id="ch-ep-${id}"></canvas></div>
      <div class="chart-card"><div class="chart-title">ROIC vs WACC</div><canvas class="chart-canvas" id="ch-roic-${id}"></canvas></div>
      <div class="chart-card"><div class="chart-title">Receita por Ação (TTM)</div><canvas class="chart-canvas" id="ch-rev-${id}"></canvas></div>
      <div class="chart-card"><div class="chart-title">Dívida Líquida / FCF (anos)</div><canvas class="chart-canvas" id="ch-lev-${id}"></canvas></div>
    </div>`;
}

function renderCharts(ticker) {
  const r = allResults.find(x => x.ticker === ticker);
  if (!r) return;
  const color = r.color || ['#4f7cff','#22c55e','#f59e0b'][allResults.indexOf(r) % 3];
  const rows   = r.rows;
  const labels = rows.map(rw => rw.date.slice(0,7));

  function makeChart(id, datasets, pct=false) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (chartInstances[id]) chartInstances[id].destroy();
    chartInstances[id] = new Chart(canvas, {
      type: 'line',
      data: {labels, datasets},
      options: {
        responsive: true, maintainAspectRatio: true,
        plugins: {legend: {display: datasets.length > 1, labels: {color:'#94a3b8',font:{size:10}}}, tooltip: {mode:'index',intersect:false}},
        scales: {
          x: {ticks: {color:'#64748b',maxTicksLimit:8,font:{size:9}}, grid: {color:'#2d3150'}},
          y: {ticks: {color:'#64748b',font:{size:9}, callback: v => pct ? (v*100).toFixed(0)+'%' : '$'+v.toFixed(1)}, grid: {color:'#2d3150'}}
        }
      }
    });
  }
  const ds = (label, data, col, fill=false) => ({label, data, borderColor: col, backgroundColor: fill ? col+'22':'transparent', borderWidth:2, pointRadius:0, tension:0.3, fill});

  makeChart(`ch-ebit-${ticker}`, [ds('EBIT/ação', rows.map(r=>r.ebit_ps), color, true)]);
  makeChart(`ch-fcf-${ticker}`,  [ds('FCF-SBC/ação', rows.map(r=>r.fcf_sbc_ps), '#22c55e', true)]);
  makeChart(`ch-ep-${ticker}`,   [ds('Eco.Profit/ação', rows.map(r=>r.econ_profit_ps), '#a78bfa', true)]);
  makeChart(`ch-roic-${ticker}`, [ds('ROIC', rows.map(r=>r.roic), color), ds('WACC', rows.map(r=>r.wacc), '#ef4444')], true);
  makeChart(`ch-rev-${ticker}`,  [ds('Receita/ação', rows.map(r=>r.revenue_ps), '#f59e0b', true)]);
  makeChart(`ch-lev-${ticker}`,  [ds('Net Debt/FCF', rows.map(r=>r.net_debt_fcf), '#f87171')]);

  // ── Gráfico combinado: Preço × Métricas ──────────────────────────────
  renderPriceChart(ticker, r, color);

  // Toggle handlers
  const togArea = document.getElementById(`tog-${ticker}`);
  if (togArea) {
    togArea.querySelectorAll('.tog-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        btn.classList.toggle('tog-active');
        renderPriceChart(ticker, r, color);
      });
    });
  }
}

function renderPriceChart(ticker, r, color) {
  const canvas = document.getElementById(`ch-price-${ticker}`);
  if (!canvas) return;

  const priceHist = r.price_history || [];
  const rows      = r.rows;
  const val       = r.valuation;

  // Preço diário
  const priceDates  = priceHist.map(p => p.date);
  const priceValues = priceHist.map(p => p.close);

  // Métricas trimestrais — alinhadas à data do trimestre
  const qDates = rows.map(rw => rw.date);
  const metricMap = {
    ebit:        { label: 'EBIT/ação',       color: '#4f7cff', data: rows.map(r=>r.ebit_ps) },
    ep:          { label: 'Eco.Profit/ação', color: '#a78bfa', data: rows.map(r=>r.econ_profit_ps) },
    fcf:         { label: 'FCF-SBC/ação',    color: '#22c55e', data: rows.map(r=>r.fcf_sbc_ps) },
    graham_ebit: { label: 'Graham (EBIT)',   color: '#f59e0b', data: rows.map(r => {
      const cagr = r._ebit_cagr != null ? r._ebit_cagr * 100 : (val.ebit_cagr||0)*100;
      const y    = val.treasury_yield * 100 || 4.28;
      return r.ebit_ps > 0 ? r.ebit_ps * (8.5 + 2*cagr) * 4.4/y : null;
    })},
    graham_ep:   { label: 'Graham (EP)',     color: '#fb923c', data: rows.map(r => {
      const cagr = (val.ep_cagr||0)*100;
      const y    = val.treasury_yield * 100 || 4.28;
      return r.econ_profit_ps > 0 ? r.econ_profit_ps * (8.5 + 2*cagr) * 4.4/y : null;
    })},
  };

  // Quais métricas estão ativas
  const togArea  = document.getElementById(`tog-${ticker}`);
  const active   = new Set();
  if (togArea) togArea.querySelectorAll('.tog-btn.tog-active').forEach(b => active.add(b.dataset.metric));

  // Dataset do preço (eixo y principal)
  const datasets = [{
    label:           'Preço',
    data:            priceValues,
    borderColor:     color,
    backgroundColor: color + '18',
    borderWidth:     2,
    pointRadius:     0,
    tension:         0.2,
    fill:            true,
    yAxisID:         'yPrice',
    order:           0,
  }];

  // Datasets das métricas (eixo y secundário, escalado)
  for (const [key, m] of Object.entries(metricMap)) {
    if (!active.has(key)) continue;
    datasets.push({
      label:       m.label,
      data:        m.data,
      borderColor: m.color,
      backgroundColor: 'transparent',
      borderWidth: 1.5,
      borderDash:  [5, 3],
      pointRadius: 3,
      pointBackgroundColor: m.color,
      tension:     0.3,
      fill:        false,
      yAxisID:     'yMetric',
      order:       1,
      // Alinha às datas dos trimestres
    });
    // Corrige labels para usar datas dos trimestres para métricas
    datasets[datasets.length-1]._qDates = qDates;
  }

  if (chartInstances[`ch-price-${ticker}`]) chartInstances[`ch-price-${ticker}`].destroy();

  // Usa datas do preço para eixo X, mas plota métricas nas datas dos trimestres
  // Estratégia: dataset de preço usa priceDates, métricas usam qDates
  // Chart.js suporta dados como {x, y} para datasets com datas diferentes

  const priceDataXY  = priceHist.map(p => ({x: p.date, y: p.close}));

  const metricDatasets = datasets.slice(1).map(d => {
    const qd = d._qDates || qDates;
    return {
      ...d,
      data: d.data.map((v, i) => ({x: qd[i], y: v})),
    };
  });

  chartInstances[`ch-price-${ticker}`] = new Chart(canvas, {
    type: 'line',
    data: { datasets: [{ ...datasets[0], data: priceDataXY }, ...metricDatasets] },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: true, labels: { color: '#94a3b8', font: { size: 11 }, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const v = ctx.parsed.y;
              if (v == null) return null;
              return `${ctx.dataset.label}: $${v.toFixed(2)}`;
            }
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'month', displayFormats: { month: 'MMM yy' } },
          ticks: { color: '#64748b', maxTicksLimit: 10, font: { size: 9 } },
          grid:  { color: '#2d3150' },
        },
        yPrice: {
          type: 'linear', position: 'left',
          ticks: { color: '#94a3b8', font: { size: 9 }, callback: v => '$'+v.toFixed(0) },
          grid:  { color: '#2d3150' },
          title: { display: true, text: 'Preço ($)', color: '#64748b', font: { size: 10 } },
        },
        yMetric: {
          type: 'linear', position: 'right',
          ticks: { color: '#64748b', font: { size: 9 }, callback: v => '$'+v.toFixed(1) },
          grid:  { drawOnChartArea: false },
          title: { display: true, text: 'Métricas / Ação ($)', color: '#64748b', font: { size: 10 } },
        },
      }
    }
  });
}

// ─── 45Q Table ────────────────────────────────────────────────────────────────
function buildTablePanel(r) {
  const rows = r.rows;
  const metrics = [
    {label:'Cash / Ação',            fn: rw => rw.cash_ps},
    {label:'Dívida + Lease / Ação',  fn: rw => rw.debt_lease_ps},
    {label:'Receita / Ação TTM',     fn: rw => rw.revenue_ps},
    {label:'EBIT / Ação TTM',        fn: rw => rw.ebit_ps},
    {label:'NOPAT / Ação TTM',       fn: rw => rw.nopat_ps},
    {label:'Net Income / Ação TTM',  fn: rw => rw.net_income_ps},
    {label:'OCF−SBC / Ação TTM',     fn: rw => rw.ocf_sbc_ps},
    {label:'FCF−SBC / Ação TTM',     fn: rw => rw.fcf_sbc_ps},
    {label:'Dividendos / Ação TTM',  fn: rw => rw.dividend_ps},
    {label:'Recompra / Ação TTM',    fn: rw => rw.repurchase_ps},
    {label:'Cash Retornado / Ação',  fn: rw => rw.cash_returned_ps},
    {label:'Eco. Profit / Ação TTM', fn: rw => rw.econ_profit_ps},
    {label:'Cap. Investido / Ação',  fn: rw => rw.invested_cap_ps},
    {label:'ROIC',                   fn: rw => rw.roic, pct: true},
    {label:'ROIC ex-Goodwill',       fn: rw => rw.roic_ex_gw, pct: true},
    {label:'ROIIC (1 ano)',          fn: rw => rw.roiic_1y, pct: true},
    {label:'WACC',                   fn: rw => rw.wacc, pct: true},
    {label:'Tax Rate Efetivo',       fn: rw => rw.eff_tax, pct: true},
    {label:'Capex / Receita',        fn: rw => rw.capex_rev, pct: true},
    {label:'Opex / Receita',         fn: rw => rw.opex_rev, pct: true},
    {label:'Net Debt / FCF (anos)',  fn: rw => rw.net_debt_fcf, raw: true},
    {label:'Ações Diluídas',         fn: rw => rw.shares, shares: true},
  ];

  const dates = rows.map(rw => rw.date.slice(0,7));
  const thHtml = dates.map(d => `<th class="qtr-header">${d}</th>`).join('');

  const tbodyHtml = metrics.map(m => {
    const cells = rows.map((rw, i) => {
      const v = m.fn(rw);
      let display, pctChange = null;

      if (v == null || v !== v) { display = '—'; }
      else if (m.shares)        { display = (v/1e9).toFixed(3)+'B'; }
      else if (m.pct)           { display = v != null ? (v*100).toFixed(1)+'%' : '—'; }
      else if (m.raw)           { display = v != null ? v.toFixed(1)+'x' : '—'; }
      else                      { display = v != null ? '$'+v.toFixed(2) : '—'; }

      // QoQ % change
      if (i > 0 && v != null && v === v) {
        const prev = m.fn(rows[i-1]);
        if (prev != null && prev !== 0 && prev === prev) {
          pctChange = (v - prev) / Math.abs(prev);
        }
      }

      const pctHtml = pctChange != null
        ? `<span class="${pctChange >= 0 ? 'pct-pos' : 'pct-neg'}">${pctChange >= 0 ? '▲' : '▼'} ${Math.abs(pctChange*100).toFixed(1)}%</span>`
        : '';

      return `<td><div class="pct-cell"><span>${display}</span>${pctHtml}</div></td>`;
    }).join('');
    return `<tr><td>${m.label}</td>${cells}</tr>`;
  }).join('');

  const fnName = `exportCSV_${r.ticker.replace(/[^a-zA-Z0-9]/g,'_')}`;
  window[fnName] = () => exportCSV(r);

  return `
    <div class="table-toolbar">
      <span style="font-size:12px;color:var(--text3)">${rows.length} trimestres · Fonte: Yahoo Finance · Arraste horizontalmente para ver todos</span>
      <button class="export-btn" onclick="${fnName}()">⬇ Exportar CSV</button>
    </div>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr><th>Métrica</th>${thHtml}</tr></thead>
        <tbody>${tbodyHtml}</tbody>
      </table>
    </div>`;
}


// ─── Glossário ────────────────────────────────────────────────────────────────
function buildGlossaryPanel() {
  const terms = [
    {
      cat: "Métricas de Lucro Operacional",
      items: [
        { term: "EBIT", def: "Earnings Before Interest and Taxes — lucro operacional antes dos juros e impostos. Mede a geração de caixa operacional pura da empresa, excluindo efeitos financeiros e fiscais." },
        { term: "EBITDA", def: "EBIT + Depreciação e Amortização. Aproximação do fluxo de caixa operacional, muito usada para comparação entre empresas de diferentes países e estruturas de capital." },
        { term: "NOPAT", def: "Net Operating Profit After Tax — EBIT × (1 − alíquota efetiva de imposto). Representa o lucro operacional após impostos, base para o cálculo do ROIC e do Economic Profit." },
      ]
    },
    {
      cat: "Fluxo de Caixa",
      items: [
        { term: "OCF − SBC", def: "Operating Cash Flow menos Stock-Based Compensation. O caixa operacional ajustado pela remuneração em ações, que é uma despesa real diluída ao acionista mas não sai do caixa." },
        { term: "FCF − SBC", def: "Free Cash Flow menos SBC. OCF − Capex − SBC. É o caixa livre real gerado para o acionista após investimentos e remuneração em ações. Métrica mais conservadora que o FCF tradicional." },
        { term: "Capex / Receita", def: "Percentual da receita investido em ativos fixos (Property, Plant & Equipment). Empresas de tecnologia tendem a ter Capex baixo; industriais e utilities, alto." },
        { term: "Opex / Receita", def: "Despesas operacionais (excluindo COGS e D&A) como percentual da receita. Mede a eficiência operacional." },
      ]
    },
    {
      cat: "Retorno sobre Capital",
      items: [
        { term: "ROIC", def: "Return on Invested Capital — NOPAT ÷ Capital Investido. Mede quanto a empresa gera de retorno para cada real investido. ROIC > WACC significa criação de valor." },
        { term: "ROIC ex-Goodwill", def: "ROIC calculado excluindo o Goodwill do capital investido. Mostra o retorno sobre o capital tangível, eliminando o efeito de aquisições a prêmio." },
        { term: "ROIIC", def: "Return on Incremental Invested Capital — variação do NOPAT ÷ variação do Capital Investido (1 ano). Mede o retorno sobre o capital marginal investido recentemente." },
      ]
    },
    {
      cat: "Custo de Capital e Valor Econômico",
      items: [
        { term: "WACC", def: "Weighted Average Cost of Capital — custo médio ponderado de capital. Combina o custo do capital próprio (assumido 10%) com o custo da dívida após impostos, ponderados pela estrutura de capital." },
        { term: "Economic Profit (EVA)", def: "NOPAT − (WACC × Capital Investido). Valor econômico criado acima do custo de capital. EVA positivo = empresa criando valor; EVA negativo = destruindo valor mesmo com lucro contábil." },
        { term: "Spread ROIC−WACC", def: "ROIC menos WACC. Spread positivo indica criação de valor; negativo indica destruição. Empresas com spread alto e crescente são as mais valiosas a longo prazo." },
      ]
    },
    {
      cat: "Valuation",
      items: [
        { term: "EV / EBIT", def: "Enterprise Value dividido pelo EBIT TTM. Múltiplo de valuation que compara o valor total da empresa (incluindo dívida) com sua geração operacional. Mais conservador que P/L." },
        { term: "Fórmula de Graham", def: "Valor Intrínseco = EPS × (8,5 + 2 × CAGR%) × 4,4 / Y, onde Y é o yield do Treasury de 10 anos. Benjamin Graham desenvolveu esta fórmula como estimativa do valor justo de uma ação em crescimento." },
        { term: "Margem de Segurança", def: "MS = (Valor Intrínseco − Preço) / Valor Intrínseco. Percentual pelo qual o preço está abaixo (positivo = desconto) ou acima (negativo = prêmio) do valor intrínseco de Graham. Graham recomendava MS > 33%." },
        { term: "CAGR", def: "Compound Annual Growth Rate — taxa de crescimento anual composta. Calculada com base no histórico de 5 ou 3 anos disponível." },
        { term: "TIR (EBIT Yield)", def: "Taxa Interna de Retorno implícita: EBIT ÷ Enterprise Value. Representa o retorno que um comprador pagando o EV atual obteria se o EBIT se mantivesse constante." },
      ]
    },
    {
      cat: "Estrutura de Capital e Liquidez",
      items: [
        { term: "Cash Excess / Ação", def: "Caixa total menos dívida total, dividido pelo número de ações. Representa o excesso de caixa líquido por ação que pode ser devolvido ao acionista sem afetar as operações." },
        { term: "Net Debt / FCF", def: "Dívida líquida dividida pelo FCF−SBC anual. Indica em quantos anos a empresa quitaria toda a dívida líquida com seu fluxo de caixa livre atual. Negativo = empresa com caixa líquido." },
        { term: "Tax Rate Efetivo", def: "Imposto de renda pago ÷ Lucro antes do imposto (TTM). A alíquota real paga pela empresa, que pode diferir significativamente da alíquota nominal por incentivos, deduções e estrutura internacional." },
        { term: "Capital Investido", def: "NWC (Capital de Giro Líquido) + PP&E + Goodwill + Intangíveis. Representa o total de recursos investidos nas operações da empresa, base para o cálculo do ROIC." },
        { term: "FCF Yield", def: "FCF−SBC ÷ Market Cap. Rendimento do caixa livre — quanto % do valor de mercado é gerado em caixa livre. Pode ser comparado com o yield de títulos para avaliar atratividade relativa." },
      ]
    },
  ];

  const html = terms.map(cat => `
    <div class="glossary-cat">
      <div class="glossary-cat-title">${cat.cat}</div>
      <div class="glossary-items">
        ${cat.items.map(item => `
          <div class="glossary-item">
            <div class="glossary-term">${item.term}</div>
            <div class="glossary-def">${item.def}</div>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');

  return `<div class="glossary-wrap">${html}</div>`;
}

// ─── CSV Export ───────────────────────────────────────────────────────────────
function exportCSV(r) {
  const rows   = r.rows;
  const fields = Object.keys(rows[0]).filter(k => !k.startsWith('_'));
  const header = ['metric', ...rows.map(rw => rw.date)].join(',');
  const body   = fields.map(f => [f, ...rows.map(rw => rw[f] ?? '')].join(',')).join('\n');
  const blob   = new Blob([header+'\n'+body], {type:'text/csv'});
  const a      = document.createElement('a');
  a.href       = URL.createObjectURL(blob);
  a.download   = `${r.ticker}_${r.rows.length}Q_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
}
