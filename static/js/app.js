// ─── Estado global ────────────────────────────────────────────────────────────
let allResults       = [];
let selectedTickers  = [];
const chartInstances = {};

// ─── Formatadores ─────────────────────────────────────────────────────────────
const fmt = {
  pct:  v => v == null ? '—' : (v * 100).toFixed(1) + '%',
  pct1: v => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%',
  x:    v => v == null ? '—' : v.toFixed(1) + 'x',
  $:    v => v == null ? '—' : '$' + v.toFixed(2),
  bn:   v => v == null ? '—' : '$' + (Math.abs(v) >= 1e12 ? (v/1e12).toFixed(1)+'T' : Math.abs(v) >= 1e9 ? (v/1e9).toFixed(1)+'B' : (v/1e6).toFixed(0)+'M'),
};

function colorClass(v) { return v == null ? '' : v > 0 ? 'green' : v < 0 ? 'red' : ''; }
function fmtDate(d) {
  if (!d) return '';
  const [y, m, day] = d.split('-');
  return `${day}/${m}/${y}`;
}

// ─── Definições de tooltip ────────────────────────────────────────────────────
window.TOOLTIPS = {
  'ROIC':             'Return on Invested Capital.\n\nFórmula: NOPAT ÷ Capital Investido ex-Goodwill\nNOPAT = EBIT × (1 − Tax Rate efetivo, cap 30%)\n\nExclui goodwill para refletir retorno sobre ativos tangíveis.',
  'WACC':             'Weighted Average Cost of Capital.\n\nFórmula: Ke × We + Kd × (1−t) × Wd\nKe (custo do equity) = 10% fixo\nKd = Despesa Financeira ÷ Dívida Total',
  'Spread ROIC−WACC': 'ROIC − WACC. Spread positivo = empresa criando valor econômico acima do custo de capital.',
  'EP / Ação':        'Economic Profit por ação (TTM).\n\nFórmula: NOPAT − (WACC × Capital Investido ex-Goodwill)',
  'FCF Yield':        'FCF−SBC ÷ Market Cap.\n\nFCF−SBC = OCF − Capex − Stock-Based Compensation',
  'EBIT Yield':       'EBIT (TTM) ÷ Enterprise Value. Rendimento operacional implícito.',
  'EV / EBIT':        'Enterprise Value ÷ EBIT (TTM).\nEV = Market Cap + Dívida − Caixa.\n<15x = barato; >30x = caro (varia por setor).',
  'FCF/Ação':         'Free Cash Flow − SBC por ação (TTM). OCF − Capex − SBC ÷ Ações.',
  'EBIT/Ação':        'EBIT por ação nos últimos 12 meses (TTM).',
  'Receita/Ação':     'Receita total por ação (TTM).',
  'Div/Ação':         'Dividendos pagos por ação nos últimos 12 meses (TTM).',
  'Market Cap':       'Preço × Ações em circulação do último trimestre.',
  'Enterprise Value': 'Market Cap + Dívida Total − Caixa Completo (ST + LT investments).',
  'Cash Excess/Ação': 'max(Caixa Completo − Dívida Total, 0) ÷ Ações.',
  'Div Yield':        'Dividendos pagos por ação (TTM) ÷ Preço atual.',
  'Treasury 10Y':     'Yield do Treasury americano de 10 anos. Taxa livre de risco na Fórmula de Graham.',
  'ROE':              'Return on Equity — Lucro Líquido TTM ÷ Patrimônio Líquido.',
  'P/E':              'Preço ÷ Lucro Líquido por ação (TTM).',
  'P/TBV':            'Preço ÷ Tangible Book Value por ação. TBV = PL − Goodwill.',
  'EBIT':             'Earnings Before Interest and Taxes — lucro operacional (TTM).',
  'FCF − SBC':        'Free Cash Flow ajustado por Stock-Based Compensation.\nFórmula: OCF − |Capex| − SBC.',
  'Economic Profit':  'Lucro Econômico (EVA®).\nFórmula: NOPAT − (WACC × Capital Investido ex-Goodwill).',
  'Dividendos':       'Dividendos pagos por ação (TTM).',
  'Margem de Segurança': 'Fórmula de Graham (1974):\nV = EPS × (8,5 + 2×g%) × (4,4÷Y%)\nMS = (V − Preço) ÷ V',
};

// ─── Fallback seguro para tooltip (evita ReferenceError) ─────────────────────
function tooltip(key) {
  const txt = (window.TOOLTIPS || {})[key];
  if (!txt) return '';
  const esc = txt.replace(/"/g, '&quot;').replace(/\n/g, '&#10;');
  return `<span class="info-icon" data-tip="${esc}" onclick="showTooltipModal(this)">ⓘ</span>`;
}

function showTooltipModal(el) {
  document.getElementById('tooltip-modal')?.remove();
  const txt = el.getAttribute('data-tip').replace(/&#10;/g, '\n');
  const modal = document.createElement('div');
  modal.id = 'tooltip-modal';
  modal.className = 'tooltip-modal';
  modal.innerHTML = `
    <div class="tooltip-modal-inner">
      <button class="tooltip-modal-close" onclick="document.getElementById('tooltip-modal').remove()">✕</button>
      <div class="tooltip-modal-body">${txt.replace(/\n/g,'<br>')}</div>
    </div>`;
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  document.body.appendChild(modal);
}

// ─── Gauge SVG ────────────────────────────────────────────────────────────────
function gaugeArc(cx, cy, r, startDeg, endDeg) {
  const rad = d => (d - 90) * Math.PI / 180;
  const sx = cx + r * Math.cos(rad(startDeg)), sy = cy + r * Math.sin(rad(startDeg));
  const ex = cx + r * Math.cos(rad(endDeg)),   ey = cy + r * Math.sin(rad(endDeg));
  const large = (endDeg - startDeg) > 180 ? 1 : 0;
  return `M ${sx} ${sy} A ${r} ${r} 0 ${large} 1 ${ex} ${ey}`;
}

// makeGaugeCard: gauge + valor atual + média histórica + seta % — tudo integrado
function makeGaugeCard(title, tooltipKey, value, histValues, min, max, unit, note, thresholds, invertColor=false) {
  if (value == null || isNaN(value)) {
    return `<div class="gauge-card">
      <div class="gauge-title">${title} ${tooltip(tooltipKey||title)}</div>
      <div style="text-align:center;color:var(--text3);padding:32px 0">—</div>
      <div class="gauge-note">${note}</div>
    </div>`;
  }

  const pct = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const cx = 70, cy = 68, r = 52;
  const th = thresholds || [{pct:0.33,color:'#ef4444'},{pct:0.66,color:'#f59e0b'},{pct:1,color:'#22c55e'}];

  let arcs = '', prev = 0;
  th.forEach(t => {
    arcs += `<path d="${gaugeArc(cx,cy,r,-135+prev*270,-135+t.pct*270)}" stroke="${t.color}" stroke-width="10" fill="none" stroke-linecap="butt" opacity="0.9"/>`;
    prev = t.pct;
  });

  const angle = -135 + pct * 270;
  const needleRad = (angle - 90) * Math.PI / 180;
  const nx = cx + 42 * Math.cos(needleRad), ny = cy + 42 * Math.sin(needleRad);

  let valColor = '#22c55e';
  if (pct < 0.33) valColor = '#ef4444';
  else if (pct < 0.66) valColor = '#f59e0b';

  const fmtVal = v => {
    if (v == null) return '—';
    return unit==='%' ? (v*100).toFixed(1)+'%' : unit==='x' ? v.toFixed(1)+'x' : unit==='$' ? '$'+v.toFixed(2) : v.toFixed(2);
  };

  const dispVal = fmtVal(value);
  const minLbl = unit==='%' ? (min*100).toFixed(0)+'%' : min;
  const maxLbl = unit==='%' ? (max*100).toFixed(0)+'%' : max;

  // Histórico
  const vals = (histValues||[]).filter(v => v != null && !isNaN(v));
  const avg  = vals.length ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
  const pctDiff = (avg != null && avg !== 0) ? (value - avg) / Math.abs(avg) : null;
  const isGood  = invertColor ? pctDiff != null && pctDiff < 0 : pctDiff != null && pctDiff > 0;
  const isBad   = invertColor ? pctDiff != null && pctDiff > 0 : pctDiff != null && pctDiff < 0;
  const dColor  = isGood ? '#22c55e' : isBad ? '#ef4444' : '#94a3b8';
  const arrow   = isGood ? '▲' : isBad ? '▼' : '●';
  const pctStr  = pctDiff != null ? (pctDiff>=0?'+':'')+(pctDiff*100).toFixed(1)+'%' : '';

  return `<div class="gauge-card">
    <div class="gauge-title">${title} ${tooltip(tooltipKey||title)}</div>
    <svg viewBox="0 0 140 100" class="gauge-svg">
      <path d="${gaugeArc(cx,cy,r,-135,135)}" stroke="var(--border)" stroke-width="10" fill="none" stroke-linecap="butt"/>
      ${arcs}
      <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="4" fill="white"/>
      <text x="16" y="94" text-anchor="middle" font-size="7" fill="var(--text3)">${minLbl}</text>
      <text x="124" y="94" text-anchor="middle" font-size="7" fill="var(--text3)">${maxLbl}</text>
    </svg>
    <div class="gauge-bottom">
      <div class="gauge-current">${dispVal}</div>
      ${avg != null ? `<div class="gauge-hist-row">
        <span class="gauge-hist-label">Média histórica: ${fmtVal(avg)}</span>
        <span class="gauge-hist-delta" style="color:${dColor}">${arrow} ${pctStr}</span>
      </div>` : ''}
    </div>
    <div class="gauge-note">${note}</div>
  </div>`;
}

// Compatibilidade: makeGauge retorna apenas o SVG (para uso legado)
function makeGauge(value, min, max, label, unit, thresholds) {
  return makeGaugeCard(label, label, value, [], min, max, unit||'%', '', thresholds).replace(/<div class="gauge-card">.*?<svg/s,'<svg').split('</svg>')[0]+'</svg>';
}

// ─── Seleção de cards na landing ──────────────────────────────────────────────
function toggleTicker(symbol, name, color) {
  const idx  = selectedTickers.findIndex(t => t.symbol === symbol);
  const card = document.getElementById('card-' + symbol);
  if (idx >= 0) {
    selectedTickers.splice(idx, 1);
    card.classList.remove('selected');
    card.style.borderColor = '';
  } else {
    if (selectedTickers.length >= 3) {
      const removed = selectedTickers.shift();
      const old = document.getElementById('card-' + removed.symbol);
      if (old) { old.classList.remove('selected'); old.style.borderColor = ''; }
    }
    selectedTickers.push({symbol, name, color});
    card.classList.add('selected');
    card.style.borderColor = color;
    const chk = card.querySelector('.ticker-card-check');
    if (chk) chk.style.color = color;
  }
  updateSelectionUI();
}

function updateSelectionUI() {
  const preview = document.getElementById('selected-preview');
  const btn     = document.getElementById('btn-analyze-main');
  const hChips  = document.getElementById('header-chips');

  if (selectedTickers.length === 0) {
    if (preview) preview.innerHTML = '<div class="sidebar-hint">Clique nas ações<br>para selecionar</div>';
    if (btn) btn.disabled = true;
    return;
  }
  if (preview) {
    preview.innerHTML = selectedTickers.map(t =>
      `<div class="preview-chip" style="background:${t.color}">${t.symbol} — ${t.name}</div>`
    ).join('');
  }
  if (btn) btn.disabled = false;
  if (hChips) hChips.innerHTML = selectedTickers.map(t =>
    `<div class="header-chip" style="background:${t.color}">${t.symbol}</div>`
  ).join('');
}

function clearSelection() {
  selectedTickers.forEach(t => {
    const c = document.getElementById('card-' + t.symbol);
    if (c) { c.classList.remove('selected'); c.style.borderColor = ''; }
  });
  selectedTickers = [];
  updateSelectionUI();
  goHome();
}

// ─── Análise ──────────────────────────────────────────────────────────────────
async function runAnalysis() {
  const tickers = selectedTickers.map(t => t.symbol);
  if (!tickers.length) return;

  document.getElementById('landing').classList.add('hidden');
  document.getElementById('results').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  document.getElementById('loading').classList.remove('hidden');

  const btnTxt = document.getElementById('btn-text-main');
  if (btnTxt) btnTxt.textContent = 'Buscando…';

  try {
    const res  = await fetch('/api/analyze', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tickers})
    });
    const data = await res.json();
    if (data.error) { showError(data.error); return; }
    if (data.errors && data.errors.length) {
      const eb = document.getElementById('error-box');
      eb.innerHTML = data.errors.map(e => `<b>${e.ticker}</b>: ${e.error}`).join('<br>');
      eb.classList.remove('hidden');
    }
    if (data.results && data.results.length) {
      allResults = data.results;
      const hSel = document.getElementById('header-selected');
      if (hSel) hSel.style.display = 'flex';
      renderResults(data.results);
    }
  } catch(e) { showError('Erro de conexão: ' + e.message); }
  finally {
    document.getElementById('loading').classList.add('hidden');
    if (btnTxt) btnTxt.textContent = 'Analisar';
  }
}

function showError(msg) {
  const eb = document.getElementById('error-box');
  eb.textContent = msg; eb.classList.remove('hidden');
  document.getElementById('landing').classList.remove('hidden');
}

function goHome() {
  document.getElementById('results').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  document.getElementById('landing').classList.remove('hidden');
  const hSel = document.getElementById('header-selected');
  if (hSel) hSel.style.display = 'none';
  allResults = [];
}

async function applyCardStatus() {
  try {
    const r = await fetch('/api/quota-check');
    const d = await r.json();
    d.tickers.forEach(t => {
      const card = document.getElementById('card-' + t.symbol);
      if (!card) return;
      card.classList.toggle('ticker-card--pending', !t.has_data);
      card.classList.toggle('ticker-card--loaded', t.has_data);
    });
  } catch(e) {}
}
document.addEventListener('DOMContentLoaded', () => applyCardStatus());

// ─── Render ───────────────────────────────────────────────────────────────────
function renderResults(results) {
  const container = document.getElementById('results');
  container.innerHTML = '';
  if (results.length > 1) container.appendChild(buildComparisonPanel(results));
  results.forEach((r, idx) => container.appendChild(buildCompanyCard(r, idx)));
  container.classList.remove('hidden');
}

// ─── Painel de comparação ─────────────────────────────────────────────────────
function buildComparisonPanel(results) {
  const metrics = [
    {label:'Preço',              fn: r => fmt.$(r.price),                  raw: r => r.price},
    {label:'MS Média',           fn: r => fmt.pct1(r.valuation.avg_ms),    raw: r => r.valuation.avg_ms},
    {label:'EV / EBIT',          fn: r => fmt.x(r.valuation.ev_ebit),      raw: r => r.valuation.ev_ebit, inv: true},
    {label:'ROIC',               fn: r => fmt.pct(r.valuation.roic_last),   raw: r => r.valuation.roic_last},
    {label:'Spread ROIC−WACC',   fn: r => fmt.pct1(r.valuation.econ_spread),raw: r => r.valuation.econ_spread},
    {label:'FCF Yield',          fn: r => fmt.pct(r.valuation.fcf_yield),   raw: r => r.valuation.fcf_yield},
    {label:'EBIT Yield',         fn: r => fmt.pct(r.valuation.tir),         raw: r => r.valuation.tir},
    {label:'Market Cap',         fn: r => fmt.bn(r.valuation.mktcap),       raw: r => r.valuation.mktcap},
  ];

  const cols = results.map(r => `<th style="color:${r.color||'#4f7cff'};font-size:15px">${r.ticker}</th>`).join('');
  const rows = metrics.map(m => {
    const vals = results.map(r => m.raw(r));
    const best = m.inv ? Math.min(...vals.filter(v => v != null)) : Math.max(...vals.filter(v => v != null));
    const cells = results.map(r => {
      const v = m.raw(r);
      const isBest = v === best;
      const cls = colorClass(m.inv ? -v : v);
      return `<td class="${cls}${isBest ? ' comp-best' : ''}">${m.fn(r)}</td>`;
    }).join('');
    return `<tr><td class="comp-label">${m.label}</td>${cells}</tr>`;
  }).join('');

  const div = document.createElement('div');
  div.innerHTML = `<div class="company-card">
    <div class="section-header">⚖️ Comparação — ${results.map(r=>r.ticker).join(' · ')}</div>
    <div style="padding:0 24px 24px">
      <table class="comp-table">
        <thead><tr><th></th>${cols}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
  return div.firstElementChild;
}

// ─── Card de empresa ──────────────────────────────────────────────────────────
function buildCompanyCard(r, idx) {
  const color = r.color || ['#4f7cff','#22c55e','#f59e0b'][idx % 3];
  const v     = r.valuation;
  const card  = document.createElement('div');
  card.className = 'company-card';
  const priceDate = r.price_date ? `<span class="price-date">em ${fmtDate(r.price_date)}</span>` : '';
  card.innerHTML = `
    <div class="company-header">
      <div class="company-title">
        <span class="ticker-badge" style="background:${color}">${r.ticker}</span>
        <div>
          <div class="company-name">${r.name}</div>
          <div class="company-meta">${r.sector} · USD</div>
        </div>
      </div>
      <div class="company-price">
        <div class="price-value">${fmt.$(r.price)}</div>
        <div class="price-label">Cotação atual ${priceDate}</div>
      </div>
    </div>
    <div class="tabs" id="tabs-${r.ticker}">
      <button class="tab-btn active" onclick="switchTab('${r.ticker}','valuation',this)">📊 Valuation</button>
      <button class="tab-btn" onclick="switchTab('${r.ticker}','charts',this)">📈 Gráficos</button>
      <button class="tab-btn" onclick="switchTab('${r.ticker}','table',this)">🗂 Trimestres (${r.rows.length})</button>
      <button class="tab-btn" onclick="switchTab('${r.ticker}','glossary',this)">📖 Glossário</button>
    </div>
    <div id="panel-${r.ticker}-valuation" class="tab-panel active">${v.is_financial ? buildValuationFinancial(r,v) : buildValuation(r,v,color)}</div>
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

// ─── Card Histórico vs Atual ──────────────────────────────────────────────────
function histCard(label, current, histValues, unit='%', invertColor=false) {
  const vals = histValues.filter(v => v != null && !isNaN(v));
  const avg  = vals.length ? vals.reduce((a,b) => a+b, 0) / vals.length : null;
  const pctDiff = (current != null && avg != null && avg !== 0) ? (current - avg) / Math.abs(avg) : null;
  const isGood = invertColor ? (pctDiff != null && pctDiff < 0) : (pctDiff != null && pctDiff > 0);
  const isBad  = invertColor ? (pctDiff != null && pctDiff > 0) : (pctDiff != null && pctDiff < 0);

  const fmt2 = v => {
    if (v == null) return '—';
    if (unit === '%') return (v * 100).toFixed(1) + '%';
    if (unit === 'x') return v.toFixed(1) + 'x';
    if (unit === '$') return '$' + v.toFixed(2);
    return v.toFixed(2);
  };

  const pctStr = pctDiff != null ? (pctDiff >= 0 ? '+' : '') + (pctDiff * 100).toFixed(1) + '%' : '';
  const arrow  = isGood ? '▲' : isBad ? '▼' : '●';
  const clr    = isGood ? '#22c55e' : isBad ? '#ef4444' : '#94a3b8';

  return `<div class="hist-card">
    <div class="hist-label">${label}${tooltip(label)}</div>
    <div class="hist-main-row">
      <div class="hist-center">
        <div class="hist-val-current">${fmt2(current)}</div>
        <div class="hist-sub-row">
          <span class="hist-avg-label">Média histórica:</span>
          <span class="hist-avg-val">${fmt2(avg)}</span>
        </div>
      </div>
      <div class="hist-delta" style="color:${clr}">
        <span class="hist-arrow">${arrow}</span>
        <span class="hist-pct">${pctStr}</span>
      </div>
    </div>
  </div>`;
}

// ─── Aba Valuation (não-financeiras) ─────────────────────────────────────────
function buildValuation(r, v, color) {
  const rows = r.rows;

  // Séries históricas para cada métrica
  const roicSeries  = rows.map(rw => rw.roic);
  const waccSeries  = rows.map(rw => rw.wacc);
  const spreadSeries= rows.map(rw => rw.roic - rw.wacc);
  const fcfSeries   = rows.map(rw => rw.fcf_sbc_ps);
  const ebitSeries  = rows.map(rw => rw.ebit_ps);
  const epSeries    = rows.map(rw => rw.econ_profit_ps);
  const divSeries   = rows.map(rw => rw.dividend_ps);
  const revSeries   = rows.map(rw => rw.revenue_ps);

  // Gauges integrados com histórico
  const roicGauge   = makeGaugeCard('ROIC',           'ROIC',           v.roic_last,   roicSeries,   0,    0.5,  '%', 'Return on Invested Capital');
  const waccGauge   = makeGaugeCard('WACC',           'WACC',           v.wacc_last,   waccSeries,   0,    0.2,  '%', 'Custo médio de capital',
    [{pct:0.33,color:'#22c55e'},{pct:0.66,color:'#f59e0b'},{pct:1,color:'#ef4444'}], true);
  const spreadGauge = makeGaugeCard('Spread ROIC−WACC','Spread ROIC−WACC',v.econ_spread,spreadSeries,-0.1, 0.5,  '%', 'Criação de valor econômico',
    [{pct:0.17,color:'#ef4444'},{pct:0.33,color:'#f59e0b'},{pct:1,color:'#22c55e'}]);
  const fcfGauge    = makeGaugeCard('FCF Yield',       'FCF Yield',      v.fcf_yield,   rows.map(r=>r.fcf_sbc_ps&&v.price?r.fcf_sbc_ps*rows[rows.length-1].shares/v.mktcap:null), 0, 0.06, '%', 'FCF−SBC ÷ Market Cap');
  const ebitGauge   = makeGaugeCard('EBIT Yield',      'EBIT Yield',     v.tir,         null,          0,    0.08, '%', 'EBIT ÷ Enterprise Value');
  const evGauge     = makeGaugeCard('EV / EBIT',       'EV / EBIT',      Math.min(v.ev_ebit||50,50), null, 0, 50, 'x', 'Múltiplo de valuation',
    [{pct:0.3,color:'#22c55e'},{pct:0.6,color:'#f59e0b'},{pct:1,color:'#ef4444'}]);

  // Graham table
  const msRows = [
    {metric:'EBIT',           tip:'EBIT',            eps: fmt.$(v.ebit_ps), cagr: fmt.pct(v.ebit_cagr), graham: fmt.$(v.graham_ebit), ms: v.ms_ebit},
    {metric:'FCF − SBC',      tip:'FCF − SBC',        eps: fmt.$(v.fcf_ps),  cagr: fmt.pct(v.fcf_cagr),  graham: fmt.$(v.graham_fcf),  ms: v.ms_fcf},
    {metric:'Economic Profit',tip:'Economic Profit',  eps: fmt.$(v.ep_ps),   cagr: fmt.pct(v.ep_cagr),   graham: fmt.$(v.graham_ep),   ms: v.ms_ep},
    {metric:'Dividendos',     tip:'Dividendos',       eps: fmt.$(v.div_ps),  cagr: fmt.pct(v.div_cagr),  graham: fmt.$(v.graham_div),  ms: v.ms_div},
  ].map(row => {
    const ms = row.ms;
    const barPct = ms == null ? 0 : Math.min(Math.abs(ms) * 100, 100);
    const barColor = ms == null ? '#64748b' : ms >= 0 ? '#22c55e' : '#ef4444';
    const barStyle = ms != null && ms < 0 ? `right:50%;width:${barPct/2}%` : `left:50%;width:${barPct/2}%`;
    return `<tr>
      <td><b>${row.metric}</b></td>
      <td>${row.eps}</td><td>${row.cagr}</td><td>${row.graham}</td>
      <td class="${colorClass(ms)}" style="font-weight:600">${ms==null?'—':fmt.pct1(ms)}</td>
      <td><div class="ms-bar-bg" style="position:relative">
        <div class="ms-bar-fill" style="${barStyle};background:${barColor};position:absolute;top:0;height:100%"></div>
        <div style="position:absolute;top:0;left:50%;width:1px;height:100%;background:var(--border)"></div>
      </div></td></tr>`;
  }).join('');

  return `
  <!-- SEÇÃO 1: Qualidade do Negócio -->
  <div class="section-header">🏆 Qualidade do Negócio</div>
  <div class="section-body">
    <div class="gauge-row">
      ${roicGauge}
      ${waccGauge}
      ${spreadGauge}
    </div>

  </div>

  <!-- SEÇÃO 2: Geração de Caixa e Valuation -->
  <div class="section-header">💰 Geração de Caixa & Valuation</div>
  <div class="section-body">
    <div class="gauge-row">
      ${fcfGauge}
      ${ebitGauge}
      ${evGauge}
    </div>
    <div class="kpi-strip">
      <div class="kpi-pill">
        <span class="kpi-pill-label">Market Cap ${tooltip('Market Cap')}</span>
        <span class="kpi-pill-val">${fmt.bn(v.mktcap)}</span>
      </div>
      <div class="kpi-pill">
        <span class="kpi-pill-label">Enterprise Value ${tooltip('Enterprise Value')}</span>
        <span class="kpi-pill-val">${fmt.bn(v.ev)}</span>
      </div>
      <div class="kpi-pill">
        <span class="kpi-pill-label">Cash Excess/Ação ${tooltip('Cash Excess/Ação')}</span>
        <span class="kpi-pill-val ${colorClass(v.cash_excess_ps)}">${fmt.$(v.cash_excess_ps)}</span>
      </div>
      <div class="kpi-pill">
        <span class="kpi-pill-label">Div Yield ${tooltip('Div Yield')}</span>
        <span class="kpi-pill-val">${fmt.pct(v.div_yield)}</span>
      </div>
      <div class="kpi-pill">
        <span class="kpi-pill-label">Treasury 10Y ${tooltip('Treasury 10Y')}</span>
        <span class="kpi-pill-val">${fmt.pct(v.treasury_yield)}</span>
      </div>
    </div>

  </div>

  <!-- SEÇÃO 3: Margem de Segurança -->
  <div class="section-header">🎯 Margem de Segurança — Fórmula de Graham</div>
  <div class="section-body">
    <p style="font-size:13px;color:var(--text2);margin-bottom:14px">
      V = EPS × (8,5 + 2 × CAGR%) × 4,4 / Y &nbsp;·&nbsp; MS = (V − Preço) / V
      &nbsp;·&nbsp; Treasury 10Y: ${fmt.pct(v.treasury_yield)} &nbsp;·&nbsp; Preço: ${fmt.$(v.price)}
    </p>
    <div class="ms-table-wrap"><table class="ms-table">
      <thead><tr>
        <th>Métrica</th><th>EPS/Ação TTM</th><th>CAGR</th>
        <th>Graham (V)</th><th>Margem de Segurança</th><th></th>
      </tr></thead>
      <tbody>${msRows}</tbody>
      <tfoot><tr style="font-weight:700;border-top:2px solid var(--border)">
        <td colspan="4" style="text-align:right;padding-right:14px">Média (FCF + EP + Div)</td>
        <td class="${colorClass(v.avg_ms)}" style="font-size:16px">${fmt.pct1(v.avg_ms)}</td><td></td>
      </tr></tfoot>
    </table></div>
  </div>`;
}

// ─── Aba Valuation Financeiras ─────────────────────────────────────────────
function buildValuationFinancial(r, v) {
  const rows = r.rows;

  const roeSeries  = rows.map(rw => rw.net_income_ps && rw.equity_abs && rw.shares ? (rw.net_income_ps*rw.shares)/rw.equity_abs : null);
  const roeGauge   = makeGaugeCard('ROE',  'ROE',  v.roe||0, roeSeries, 0, 0.35, '%', 'Return on Equity');
  const peGauge    = makeGaugeCard('P/E',  'P/E',  Math.min(v.p_e||30,40), null, 0, 40, 'x', 'Preço ÷ Lucro/Ação',
    [{pct:0.375,color:'#22c55e'},{pct:0.625,color:'#f59e0b'},{pct:1,color:'#ef4444'}]);
  const ptbvGauge  = makeGaugeCard('P/TBV','P/TBV',Math.min(v.p_tbv||2,4), null, 0, 4, 'x', 'Preço ÷ Tangible BV',
    [{pct:0.25,color:'#22c55e'},{pct:0.5,color:'#f59e0b'},{pct:1,color:'#ef4444'}]);

  return `
  <div class="fin-notice">⚠️ <b>Instituição Financeira</b> — framework adaptado (Damodaran). ROIC/EVA/FCF não aplicáveis.</div>

  <div class="section-header">🏦 Rentabilidade</div>
  <div class="section-body">
    <div class="gauge-row">
      ${roeGauge}
      ${peGauge}
      ${ptbvGauge}
    </div>
    <div class="kpi-strip">
      <div class="kpi-pill"><span class="kpi-pill-label">TBV/Ação</span><span class="kpi-pill-val">${fmt.$(v.tbv_ps)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">BV/Ação</span><span class="kpi-pill-val">${fmt.$(v.bv_ps)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">Eficiência</span><span class="kpi-pill-val ${v.efficiency < 0.5 ? 'green' : 'red'}">${fmt.pct(v.efficiency)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">NIM (proxy)</span><span class="kpi-pill-val">${fmt.pct(v.nim_proxy)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">Payout</span><span class="kpi-pill-val">${fmt.pct(v.payout)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">Div Yield ${tooltip('Div Yield')}</span><span class="kpi-pill-val">${fmt.pct(v.div_yield)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">Total Ativos</span><span class="kpi-pill-val">${fmt.bn(v.total_assets)}</span></div>
      <div class="kpi-pill"><span class="kpi-pill-label">PL</span><span class="kpi-pill-val">${fmt.bn(v.equity_abs)}</span></div>
    </div>
  </div>

  <div class="section-header">🎯 Graham (adaptado)</div>
  <div class="section-body">
    <p style="font-size:13px;color:var(--text2);margin-bottom:14px">EPS = Lucro Líquido/Ação · CAGR = crescimento de receita (proxy)</p>
    <div class="ms-table-wrap"><table class="ms-table">
      <thead><tr><th>Métrica</th><th>Valor/Ação TTM</th><th>CAGR</th><th>Graham (V)</th><th>Margem de Segurança</th><th></th></tr></thead>
      <tbody>
        ${[{m:'EPS', eps:fmt.$(v.eps_ps), cagr:fmt.pct(v.eps_cagr), graham:fmt.$(v.graham_eps), ms:v.ms_eps},
           {m:'Dividendos', eps:fmt.$(v.div_ps), cagr:fmt.pct(v.div_cagr), graham:fmt.$(v.graham_div), ms:v.ms_div}
          ].map(row => {
            const ms = row.ms;
            const barPct = ms == null ? 0 : Math.min(Math.abs(ms)*100, 100);
            const barColor = ms == null ? '#64748b' : ms >= 0 ? '#22c55e' : '#ef4444';
            const barStyle = ms != null && ms < 0 ? `right:50%;width:${barPct/2}%` : `left:50%;width:${barPct/2}%`;
            return `<tr><td><b>${row.m}</b></td><td>${row.eps}</td><td>${row.cagr}</td><td>${row.graham}</td>
              <td class="${colorClass(ms)}" style="font-weight:600">${ms==null?'—':fmt.pct1(ms)}</td>
              <td><div class="ms-bar-bg" style="position:relative">
                <div class="ms-bar-fill" style="${barStyle};background:${barColor};position:absolute;top:0;height:100%"></div>
                <div style="position:absolute;top:0;left:50%;width:1px;height:100%;background:var(--border)"></div>
              </div></td></tr>`;
          }).join('')}
      </tbody>
    </table></div>
  </div>`;
}

// ─── Aba Gráficos ─────────────────────────────────────────────────────────────
function buildChartsPanel(r) {
  const id  = r.ticker;
  const fin = r.valuation?.is_financial;

  if (fin) {
    // Gráficos específicos para instituições financeiras
    return `
      <div class="chart-card chart-card-wide">
        <div class="chart-header">
          <div class="chart-title">📈 Preço × Book Value por Ação</div>
          <div class="chart-toggles" id="tog-${id}">
            <label class="tog-btn tog-active" data-metric="bv"><span class="tog-dot" style="background:#4f7cff"></span>Book Value/ação</label>
            <label class="tog-btn tog-active" data-metric="tbv"><span class="tog-dot" style="background:#22c55e"></span>Tang. Book Value/ação</label>
            <label class="tog-btn" data-metric="ni"><span class="tog-dot" style="background:#f59e0b"></span>Lucro Líq./ação</label>
          </div>
        </div>
        <canvas style="max-height:320px" id="ch-price-${id}"></canvas>
      </div>
      <div class="charts-grid">
        <div class="chart-card"><div class="chart-title">ROE — Retorno sobre Patrimônio</div><canvas class="chart-canvas" id="ch-roe-${id}"></canvas></div>
        <div class="chart-card"><div class="chart-title">Eficiência Operacional</div><canvas class="chart-canvas" id="ch-eff-${id}"></canvas></div>
        <div class="chart-card"><div class="chart-title">P/TBV Histórico</div><canvas class="chart-canvas" id="ch-ptbv-${id}"></canvas></div>
        <div class="chart-card"><div class="chart-title">P/E Histórico</div><canvas class="chart-canvas" id="ch-pe-${id}"></canvas></div>
        <div class="chart-card"><div class="chart-title">Book Value & TBV por Ação</div><canvas class="chart-canvas" id="ch-bv-${id}"></canvas></div>
        <div class="chart-card"><div class="chart-title">Dividendos & Cash Retornado / Ação</div><canvas class="chart-canvas" id="ch-div-${id}"></canvas></div>
      </div>`;
  }

  // Gráficos padrão (não-financeiras)
  return `
    <div class="chart-card chart-card-wide">
      <div class="chart-header">
        <div class="chart-title">📈 Preço × Métricas Fundamentalistas</div>
        <div class="chart-toggles" id="tog-${id}">
          <label class="tog-btn tog-active" data-metric="ebit"><span class="tog-dot" style="background:#4f7cff"></span>EBIT/ação</label>
          <label class="tog-btn tog-active" data-metric="ep"><span class="tog-dot" style="background:#a78bfa"></span>Eco.Profit/ação</label>
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
  const rows  = r.rows;
  const val   = r.valuation;
  const labels = rows.map(rw => rw.date.slice(0,7));

  function makeChart(id, datasets, opts={}) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (chartInstances[id]) chartInstances[id].destroy();
    const isPct = opts.pct;
    const isX   = opts.x;
    chartInstances[id] = new Chart(canvas, {
      type: 'line', data: {labels, datasets},
      options: {
        responsive: true, maintainAspectRatio: true,
        plugins: {
          legend: {display: datasets.length > 1, labels: {color:'#94a3b8', font:{size:10}}},
          tooltip: {mode:'index', intersect:false}
        },
        scales: {
          x: {ticks: {color:'#64748b', maxTicksLimit:8, font:{size:9}}, grid: {color:'#2d3150'}},
          y: {ticks: {color:'#64748b', font:{size:9},
            callback: v => isPct ? (v*100).toFixed(0)+'%' : isX ? v.toFixed(1)+'x' : '$'+v.toFixed(1)
          }, grid: {color:'#2d3150'}}
        }
      }
    });
  }
  const ds = (label, data, col, fill=false) => ({
    label, data, borderColor: col, backgroundColor: fill ? col+'22':'transparent',
    borderWidth:2, pointRadius:0, tension:0.3, fill
  });

  if (val?.is_financial) {
    // ── Gráficos para financeiras ──────────────────────────────────────────
    // ROE series calculado por trimestre
    const roeSeries = rows.map(rw => {
      const ni = rw.net_income_ps; const eq = rw.equity_abs; const sh = rw.shares;
      return (ni != null && eq && sh) ? (ni * sh) / eq : null;
    });
    // Book Value e TBV por ação
    const bvSeries  = rows.map(rw => rw.shares ? rw.equity_abs / rw.shares : null);
    const tbvSeries = rows.map(rw => rw.shares ? (rw.equity_abs - (rw.goodwill_abs||0)) / rw.shares : null);
    // P/TBV e P/E histórico (usando preço atual — limitação: não temos preço histórico trimestral)
    const price = val.price || r.price;
    const ptbvSeries = tbvSeries.map(v => v && v > 0 ? price/v : null);
    const peSeries   = rows.map(rw => rw.net_income_ps && rw.net_income_ps > 0 ? price/rw.net_income_ps : null);
    // Eficiência
    const effSeries  = rows.map(rw => rw.opex_rev);
    // Payout
    const payoutSeries = rows.map(rw => rw.net_income_ps && rw.net_income_ps > 0 ? rw.dividend_ps / rw.net_income_ps : null);

    makeChart(`ch-roe-${ticker}`,  [ds('ROE', roeSeries, color, true)], {pct:true});
    makeChart(`ch-eff-${ticker}`,  [ds('Eficiência', effSeries, '#f59e0b', true)], {pct:true});
    makeChart(`ch-ptbv-${ticker}`, [ds('P/TBV', ptbvSeries, '#a78bfa')], {x:true});
    makeChart(`ch-pe-${ticker}`,   [ds('P/E', peSeries, '#fb923c')], {x:true});
    makeChart(`ch-bv-${ticker}`,   [ds('Book Value/ação', bvSeries, '#4f7cff', true), ds('TBV/ação', tbvSeries, '#22c55e')]);
    makeChart(`ch-div-${ticker}`,  [ds('Dividendos/ação', rows.map(rw=>rw.dividend_ps), '#22c55e', true),
                                    ds('Cash Retornado/ação', rows.map(rw=>rw.cash_returned_ps), '#f59e0b')]);
    renderPriceChartFin(ticker, r, color, bvSeries, tbvSeries);
    const togArea = document.getElementById(`tog-${ticker}`);
    if (togArea) {
      togArea.querySelectorAll('.tog-btn').forEach(btn => {
        btn.addEventListener('click', () => { btn.classList.toggle('tog-active'); renderPriceChartFin(ticker,r,color,bvSeries,tbvSeries); });
      });
    }
  } else {
    // ── Gráficos padrão (não-financeiras) ─────────────────────────────────
    makeChart(`ch-ebit-${ticker}`,  [ds('EBIT/ação', rows.map(r=>r.ebit_ps), color, true)]);
    makeChart(`ch-fcf-${ticker}`,   [ds('FCF-SBC/ação', rows.map(r=>r.fcf_sbc_ps), '#22c55e', true)]);
    makeChart(`ch-ep-${ticker}`,    [ds('Eco.Profit/ação', rows.map(r=>r.econ_profit_ps), '#a78bfa', true)]);
    makeChart(`ch-roic-${ticker}`,  [ds('ROIC', rows.map(r=>r.roic), color), ds('WACC', rows.map(r=>r.wacc), '#ef4444')], {pct:true});
    makeChart(`ch-rev-${ticker}`,   [ds('Receita/ação', rows.map(r=>r.revenue_ps), '#f59e0b', true)]);
    makeChart(`ch-lev-${ticker}`,   [ds('Net Debt/FCF', rows.map(r=>r.net_debt_fcf), '#f87171')]);
    renderPriceChart(ticker, r, color);
    const togArea = document.getElementById(`tog-${ticker}`);
    if (togArea) {
      togArea.querySelectorAll('.tog-btn').forEach(btn => {
        btn.addEventListener('click', () => { btn.classList.toggle('tog-active'); renderPriceChart(ticker,r,color); });
      });
    }
  }
}

// ── Gráfico de preço para financeiras (BV + TBV como métricas) ───────────────
function renderPriceChartFin(ticker, r, color, bvSeries, tbvSeries) {
  const canvas = document.getElementById(`ch-price-${ticker}`);
  if (!canvas) return;
  const priceHist = r.price_history || [];
  const rows = r.rows;
  const qDates = rows.map(rw => rw.date);

  const togArea = document.getElementById(`tog-${ticker}`);
  const active  = new Set();
  if (togArea) togArea.querySelectorAll('.tog-btn.tog-active').forEach(b => active.add(b.dataset.metric));

  const priceDataXY = priceHist.map(p => ({x: p.date, y: p.close}));
  const datasets = [{
    label:'Preço', data: priceDataXY,
    borderColor: color, backgroundColor: color+'18',
    borderWidth:2, pointRadius:0, tension:0.2, fill:true, yAxisID:'yPrice', order:0
  }];

  const metricMap = {
    bv:  {label:'Book Value/ação', color:'#4f7cff',  data: bvSeries},
    tbv: {label:'TBV/ação',        color:'#22c55e',  data: tbvSeries},
    ni:  {label:'Lucro Líq./ação', color:'#f59e0b',  data: rows.map(rw=>rw.net_income_ps)},
  };
  for (const [key, m] of Object.entries(metricMap)) {
    if (!active.has(key)) continue;
    datasets.push({
      label: m.label, data: m.data.map((v,i) => ({x: qDates[i], y: v})),
      borderColor: m.color, backgroundColor:'transparent',
      borderWidth:1.5, borderDash:[5,3], pointRadius:3, pointBackgroundColor:m.color,
      tension:0.3, fill:false, yAxisID:'yMetric', order:1
    });
  }

  if (chartInstances[`ch-price-${ticker}`]) chartInstances[`ch-price-${ticker}`].destroy();
  chartInstances[`ch-price-${ticker}`] = new Chart(canvas, {
    type:'line', data:{datasets},
    options:{
      responsive:true, maintainAspectRatio:true,
      interaction:{mode:'index', intersect:false},
      plugins:{
        legend:{display:true, labels:{color:'#94a3b8', font:{size:11}, usePointStyle:true}},
        tooltip:{callbacks:{label: ctx => {
          const v = ctx.parsed.y;
          return v == null ? null : `${ctx.dataset.label}: $${v.toFixed(2)}`;
        }}}
      },
      scales:{
        x:{type:'time', time:{unit:'month', displayFormats:{month:'MMM yy'}},
           ticks:{color:'#64748b', maxTicksLimit:10, font:{size:9}}, grid:{color:'#2d3150'}},
        yPrice:{type:'linear', position:'left',
                ticks:{color:'#94a3b8', font:{size:9}, callback:v=>'$'+v.toFixed(0)},
                grid:{color:'#2d3150'},
                title:{display:true, text:'Preço ($)', color:'#64748b', font:{size:10}}},
        yMetric:{type:'linear', position:'right',
                 ticks:{color:'#64748b', font:{size:9}, callback:v=>'$'+v.toFixed(1)},
                 grid:{drawOnChartArea:false},
                 title:{display:true, text:'Valor/Ação ($)', color:'#64748b', font:{size:10}}}
      }
    }
  });
}

function renderPriceChart(ticker, r, color) {
  const canvas = document.getElementById(`ch-price-${ticker}`);
  if (!canvas) return;
  const priceHist = r.price_history || [];
  const rows = r.rows;
  const val  = r.valuation;

  const metricMap = {
    ebit:        {label:'EBIT/ação',       color:'#4f7cff', data: rows.map(r=>r.ebit_ps)},
    ep:          {label:'Eco.Profit/ação', color:'#a78bfa', data: rows.map(r=>r.econ_profit_ps)},
    fcf:         {label:'FCF-SBC/ação',    color:'#22c55e', data: rows.map(r=>r.fcf_sbc_ps)},
    graham_ebit: {label:'Graham(EBIT)',    color:'#f59e0b', data: rows.map(r => {
      const cagr = (val.ebit_cagr||0)*100;
      const y = val.treasury_yield*100||4.28;
      return r.ebit_ps > 0 ? r.ebit_ps*(8.5+2*cagr)*4.4/y : null;
    })},
    graham_ep: {label:'Graham(EP)', color:'#fb923c', data: rows.map(r => {
      const cagr = (val.ep_cagr||0)*100;
      const y = val.treasury_yield*100||4.28;
      return r.econ_profit_ps > 0 ? r.econ_profit_ps*(8.5+2*cagr)*4.4/y : null;
    })},
  };

  const togArea = document.getElementById(`tog-${ticker}`);
  const active  = new Set();
  if (togArea) togArea.querySelectorAll('.tog-btn.tog-active').forEach(b => active.add(b.dataset.metric));

  const priceDataXY = priceHist.map(p => ({x: p.date, y: p.close}));
  const qDates = rows.map(rw => rw.date);

  const datasets = [{
    label:'Preço', data: priceDataXY,
    borderColor: color, backgroundColor: color+'18',
    borderWidth:2, pointRadius:0, tension:0.2, fill:true, yAxisID:'yPrice', order:0
  }];

  for (const [key, m] of Object.entries(metricMap)) {
    if (!active.has(key)) continue;
    datasets.push({
      label: m.label, data: m.data.map((v,i) => ({x: qDates[i], y: v})),
      borderColor: m.color, backgroundColor:'transparent',
      borderWidth:1.5, borderDash:[5,3], pointRadius:3, pointBackgroundColor:m.color,
      tension:0.3, fill:false, yAxisID:'yMetric', order:1
    });
  }

  if (chartInstances[`ch-price-${ticker}`]) chartInstances[`ch-price-${ticker}`].destroy();
  chartInstances[`ch-price-${ticker}`] = new Chart(canvas, {
    type:'line', data:{datasets},
    options:{
      responsive:true, maintainAspectRatio:true,
      interaction:{mode:'index', intersect:false},
      plugins:{
        legend:{display:true, labels:{color:'#94a3b8', font:{size:11}, usePointStyle:true}},
        tooltip:{callbacks:{label: ctx => {
          const v = ctx.parsed.y;
          return v == null ? null : `${ctx.dataset.label}: $${v.toFixed(2)}`;
        }}}
      },
      scales:{
        x:{type:'time', time:{unit:'month', displayFormats:{month:'MMM yy'}},
           ticks:{color:'#64748b', maxTicksLimit:10, font:{size:9}}, grid:{color:'#2d3150'}},
        yPrice:{type:'linear', position:'left',
                ticks:{color:'#94a3b8', font:{size:9}, callback:v=>'$'+v.toFixed(0)},
                grid:{color:'#2d3150'},
                title:{display:true, text:'Preço ($)', color:'#64748b', font:{size:10}}},
        yMetric:{type:'linear', position:'right',
                 ticks:{color:'#64748b', font:{size:9}, callback:v=>'$'+v.toFixed(1)},
                 grid:{drawOnChartArea:false},
                 title:{display:true, text:'Métricas/Ação ($)', color:'#64748b', font:{size:10}}}
      }
    }
  });
}

// ─── Aba Trimestres ───────────────────────────────────────────────────────────
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
    {label:'ROIC',                   fn: rw => rw.roic, pct:true},
    {label:'ROIC ex-Goodwill',       fn: rw => rw.roic_ex_gw != null && Math.abs(rw.roic_ex_gw) < 100 ? rw.roic_ex_gw : null, pct:true},
    {label:'ROIIC (1 ano)',          fn: rw => rw.roiic_1y, pct:true},
    {label:'WACC',                   fn: rw => rw.wacc, pct:true},
    {label:'Tax Rate Efetivo',       fn: rw => rw.eff_tax, pct:true},
    {label:'Capex / Receita',        fn: rw => rw.capex_rev, pct:true},
    {label:'Opex / Receita',         fn: rw => rw.opex_rev, pct:true},
    {label:'Net Debt / FCF (anos)',  fn: rw => rw.net_debt_fcf, raw:true},
    {label:'Ações Diluídas',         fn: rw => rw.shares, shares:true},
  ];

  const dates   = rows.map(rw => rw.date.slice(0,7));
  const thHtml  = dates.map(d => `<th class="qtr-header">${d}</th>`).join('');
  const tbodyHtml = metrics.map(m => {
    const cells = rows.map((rw, i) => {
      const v = m.fn(rw);
      let display;
      if (v == null || isNaN(v)) display = '—';
      else if (m.shares) display = (v/1e9).toFixed(3)+'B';
      else if (m.pct)    display = (v*100).toFixed(1)+'%';
      else if (m.raw)    display = v.toFixed(1)+'x';
      else               display = '$'+v.toFixed(2);

      let pctChange = null;
      if (i > 0 && v != null && !isNaN(v)) {
        const prev = m.fn(rows[i-1]);
        if (prev != null && prev !== 0 && !isNaN(prev)) pctChange = (v - prev) / Math.abs(prev);
      }
      const pctHtml = pctChange != null
        ? `<span class="${pctChange >= 0 ? 'pct-pos':'pct-neg'}">${pctChange>=0?'▲':'▼'} ${Math.abs(pctChange*100).toFixed(1)}%</span>`
        : '';
      return `<td><div class="pct-cell"><span>${display}</span>${pctHtml}</div></td>`;
    }).join('');
    return `<tr><td>${m.label}</td>${cells}</tr>`;
  }).join('');

  const fnName = `exportCSV_${r.ticker.replace(/[^a-zA-Z0-9]/g,'_')}`;
  window[fnName] = () => exportCSV(r);

  return `
    <div class="table-toolbar">
      <span style="font-size:12px;color:var(--text3)">${rows.length} trimestres · Arraste horizontalmente</span>
      <button class="export-btn" onclick="${fnName}()">⬇ Exportar CSV</button>
    </div>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr><th>Métrica</th>${thHtml}</tr></thead>
        <tbody>${tbodyHtml}</tbody>
      </table>
    </div>`;
}

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

// ─── Aba Glossário ────────────────────────────────────────────────────────────
function buildGlossaryPanel() {
  const cats = [
    { title: '📊 Métricas de Retorno', items: [
      {term:'NOPAT', def:'Net Operating Profit After Tax — EBIT × (1 − alíquota efetiva). Lucro operacional após impostos, base para ROIC e EVA.'},
      {term:'ROIC', def:'Return on Invested Capital — NOPAT ÷ Capital Investido ex-Goodwill. Mede quanto a empresa gera por real investido. ROIC > WACC = criação de valor.'},
      {term:'ROIC ex-Goodwill', def:'ROIC calculado excluindo goodwill do capital investido. Mostra o retorno sobre ativos tangíveis, sem distorção de aquisições a prêmio.'},
      {term:'ROIIC', def:'Return on Incremental Invested Capital — variação do NOPAT ÷ variação do Capital Investido (1 ano). Mede a qualidade do crescimento recente.'},
    ]},
    { title: '⚖️ Custo de Capital', items: [
      {term:'WACC', def:'Weighted Average Cost of Capital — Ke×We + Kd×(1−t)×Wd. Ke = 10% fixo (proxy mercado americano). Kd = despesa financeira ÷ dívida.'},
      {term:'Economic Profit (EVA)', def:'NOPAT − (WACC × Capital Investido ex-Goodwill). Valor criado acima do custo de capital. EVA > 0 = criação de valor real.'},
      {term:'Spread ROIC−WACC', def:'ROIC menos WACC. Principal indicador de qualidade. Spread positivo e crescente = empresa mais valiosa ao longo do tempo.'},
    ]},
    { title: '💵 Fluxo de Caixa', items: [
      {term:'FCF−SBC', def:'Free Cash Flow ajustado por Stock-Based Compensation. Fórmula: OCF − |Capex| − SBC. O SBC é deduzido porque dilui o acionista (despesa real não-caixa).'},
      {term:'OCF−SBC', def:'Fluxo de Caixa Operacional menos Stock-Based Compensation. Versão do FCF antes do desconto do Capex.'},
      {term:'Cash Retornado', def:'Dividendos pagos + Recompra de ações. Total devolvido ao acionista no período (TTM).'},
    ]},
    { title: '📐 Capital Investido', items: [
      {term:'Capital Investido', def:'NWC + PP&E + Goodwill + Intangíveis. Total de recursos investidos nas operações. Base para o cálculo do ROIC.'},
      {term:'NWC', def:'Net Working Capital — (Ativo Circulante − Caixa) − (Passivo Circulante − Dívida CP). Capital de giro operacional líquido.'},
      {term:'Cash Excess', def:'max(Caixa Completo − Dívida Total, 0). Caixa líquido positivo disponível. Caixa Completo = ST Investments + LT Investments.'},
    ]},
    { title: '🎯 Valuation', items: [
      {term:'Fórmula de Graham', def:'V = EPS × (8,5 + 2×g%) × (4,4÷Y%). 8,5 = múltiplo base; g% = CAGR histórico 5 anos; 4,4 = AAA bond 1962; Y% = Treasury 10Y atual.'},
      {term:'Margem de Segurança', def:'(V − Preço) ÷ V. MS > 0 = ação abaixo do valor intrínseco calculado. MS < 0 = ação cara pelo critério de Graham.'},
      {term:'EV/EBIT', def:'Enterprise Value ÷ EBIT (TTM). Múltiplo de valuation. EV = Market Cap + Dívida − Caixa Completo.'},
      {term:'EBIT Yield (TIR)', def:'EBIT ÷ Enterprise Value. Inverso do EV/EBIT. Rendimento operacional implícito para quem comprasse a empresa toda.'},
    ]},
    { title: '🏦 Financeiras', items: [
      {term:'ROE', def:'Return on Equity — Lucro Líquido ÷ Patrimônio Líquido. Principal métrica de rentabilidade para bancos, substitui o ROIC.'},
      {term:'P/TBV', def:'Preço ÷ Tangible Book Value/ação. TBV = PL − Goodwill. Múltiplo fundamental para bancos. < 1x pode indicar desconto relevante.'},
      {term:'NIM', def:'Net Interest Margin — Receita Líquida de Juros ÷ Ativos Rentáveis. Aqui calculado como proxy (receita total ÷ total de ativos).'},
      {term:'Eficiência', def:'Despesas Operacionais ÷ Receita Total. Quanto menor, mais eficiente. Bancos bem geridos: abaixo de 50%.'},
    ]},
  ];

  const html = cats.map(cat => `
    <div class="glossary-cat">
      <div class="glossary-cat-title">${cat.title}</div>
      <div class="glossary-items">
        ${cat.items.map(item => `
          <div class="glossary-item">
            <div class="glossary-term">${item.term}</div>
            <div class="glossary-def">${item.def}</div>
          </div>`).join('')}
      </div>
    </div>`).join('');

  return `<div class="glossary-wrap">${html}</div>`;
}
