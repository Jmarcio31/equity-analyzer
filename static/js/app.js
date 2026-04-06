// ─── State ───────────────────────────────────────────────────────────────────
let allResults = [];
const COLORS = ['#4f7cff','#22c55e','#f59e0b'];
const chartInstances = {};

// ─── Helpers ─────────────────────────────────────────────────────────────────
const fmt = {
  pct:  v => v == null ? '—' : (v * 100).toFixed(1) + '%',
  pct1: v => v == null ? '—' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%',
  x:    v => v == null ? '—' : v.toFixed(1) + 'x',
  $:    v => v == null ? '—' : '$' + v.toFixed(2),
  $2:   v => v == null ? '—' : '$' + v.toFixed(2),
  bn:   v => v == null ? '—' : '$' + (v / 1e9).toFixed(1) + 'B',
  round: v => v == null ? '—' : v.toFixed(2),
};

function colorClass(v, reverse=false) {
  if (v == null) return '';
  const good = reverse ? v < 0 : v > 0;
  return good ? 'pos' : (v === 0 ? 'neu' : 'neg');
}

function setTickers(t1, t2, t3) {
  document.getElementById('t1').value = t1 || '';
  document.getElementById('t2').value = t2 || '';
  document.getElementById('t3').value = t3 || '';
  runAnalysis();
}

// ─── Analysis trigger ─────────────────────────────────────────────────────────
async function runAnalysis() {
  const tickers = ['t1','t2','t3']
    .map(id => document.getElementById(id).value.trim().toUpperCase())
    .filter(Boolean);

  if (!tickers.length) return;

  document.getElementById('landing').classList.add('hidden');
  document.getElementById('results').classList.add('hidden');
  document.getElementById('error-box').classList.add('hidden');
  document.getElementById('loading').classList.remove('hidden');

  const btn = document.getElementById('btn-analyze');
  btn.disabled = true;
  document.getElementById('btn-text').textContent = 'Buscando…';

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tickers})
    });
    const data = await res.json();

    if (data.errors && data.errors.length) {
      const eb = document.getElementById('error-box');
      eb.innerHTML = data.errors.map(e =>
        `<b>${e.ticker}</b>: ${e.error}`
      ).join('<br>');
      eb.classList.remove('hidden');
    }

    if (data.results && data.results.length) {
      allResults = data.results;
      renderResults(data.results);
    }
  } catch(e) {
    const eb = document.getElementById('error-box');
    eb.textContent = 'Erro de conexão: ' + e.message;
    eb.classList.remove('hidden');
  } finally {
    document.getElementById('loading').classList.add('hidden');
    btn.disabled = false;
    document.getElementById('btn-text').textContent = 'Analisar';
  }
}

// Enter key support
['t1','t2','t3'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') runAnalysis();
  });
});

// ─── Render ───────────────────────────────────────────────────────────────────
function renderResults(results) {
  const container = document.getElementById('results');
  container.innerHTML = '';

  // Comparison section (if multiple tickers)
  if (results.length > 1) {
    container.appendChild(buildComparisonPanel(results));
  }

  // Individual company cards
  results.forEach((r, idx) => {
    container.appendChild(buildCompanyCard(r, idx));
  });

  container.classList.remove('hidden');
}

// ─── Comparison Panel ─────────────────────────────────────────────────────────
function buildComparisonPanel(results) {
  const metrics = [
    { label: 'Preço', fn: r => fmt.$(r.price), raw: r => r.price },
    { label: 'Margem de Segurança (Média)', fn: r => fmt.pct1(r.valuation.avg_ms), raw: r => r.valuation.avg_ms },
    { label: 'EV / EBIT', fn: r => fmt.x(r.valuation.ev_ebit), raw: r => r.valuation.ev_ebit },
    { label: 'ROIC (último)', fn: r => fmt.pct(r.valuation.roic_last), raw: r => r.valuation.roic_last },
    { label: 'WACC (último)', fn: r => fmt.pct(r.valuation.wacc_last), raw: r => r.valuation.wacc_last },
    { label: 'Spread ROIC-WACC', fn: r => fmt.pct1(r.valuation.econ_spread), raw: r => r.valuation.econ_spread },
    { label: 'FCF Yield', fn: r => fmt.pct(r.valuation.fcf_yield), raw: r => r.valuation.fcf_yield },
    { label: 'Div Yield', fn: r => fmt.pct(r.valuation.div_yield), raw: r => r.valuation.div_yield },
    { label: 'Market Cap', fn: r => fmt.bn(r.valuation.mktcap), raw: r => r.valuation.mktcap },
  ];

  const cards = metrics.map(m => {
    const rows = results.map(r => {
      const raw = m.raw(r);
      return `<div class="comp-row">
        <span class="comp-ticker">${r.ticker}</span>
        <span class="comp-val ${colorClass(raw)}">${m.fn(r)}</span>
      </div>`;
    }).join('');
    return `<div class="comp-metric-card">
      <div class="comp-metric-title">${m.label}</div>
      ${rows}
    </div>`;
  }).join('');

  const div = document.createElement('div');
  div.innerHTML = `
    <div class="company-card">
      <div class="company-header">
        <div class="company-title">
          <span style="font-size:18px;font-weight:700">Comparação</span>
          <span style="color:var(--text3);font-size:13px">${results.map(r=>r.ticker).join(' · ')}</span>
        </div>
      </div>
      <div style="padding:24px">
        <div class="comparison-grid">${cards}</div>
      </div>
    </div>`;
  return div.firstElementChild;
}

// ─── Company Card ─────────────────────────────────────────────────────────────
function buildCompanyCard(r, idx) {
  const color = COLORS[idx % COLORS.length];
  const v = r.valuation;

  const card = document.createElement('div');
  card.className = 'company-card';
  card.innerHTML = `
    <div class="company-header">
      <div class="company-title">
        <span class="ticker-badge" style="background:${color}">${r.ticker}</span>
        <div>
          <div class="company-name">${r.name}</div>
          <div class="company-meta">${r.sector} · ${r.exchange} · ${r.currency}</div>
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
      <button class="tab-btn" onclick="switchTab('${r.ticker}','table',this)">🗂 45 Trimestres</button>
    </div>

    <div id="panel-${r.ticker}-valuation" class="tab-panel active">
      ${buildValuationPanel(r, v, color)}
    </div>
    <div id="panel-${r.ticker}-charts" class="tab-panel">
      ${buildChartsPanel(r, color)}
    </div>
    <div id="panel-${r.ticker}-table" class="tab-panel">
      ${buildTablePanel(r)}
    </div>`;

  // Delay chart rendering until visible
  card._r = r;
  card._color = color;
  return card;
}

function switchTab(ticker, tab, btnEl) {
  document.querySelectorAll(`#tabs-${ticker} .tab-btn`).forEach(b => b.classList.remove('active'));
  document.querySelectorAll(`[id^="panel-${ticker}-"]`).forEach(p => p.classList.remove('active'));
  btnEl.classList.add('active');
  const panel = document.getElementById(`panel-${ticker}-${tab}`);
  panel.classList.add('active');
  if (tab === 'charts') renderCharts(ticker);
}

// ─── Valuation Panel ──────────────────────────────────────────────────────────
function buildValuationPanel(r, v, color) {
  const kpis = [
    { label: 'Cotação', value: fmt.$(r.price) },
    { label: 'EV / EBIT', value: fmt.x(v.ev_ebit) },
    { label: 'Market Cap', value: fmt.bn(v.mktcap) },
    { label: 'Enterprise Value', value: fmt.bn(v.ev) },
    { label: 'ROIC (último trim.)', value: fmt.pct(v.roic_last), cls: colorClass(v.roic_last - v.wacc_last) },
    { label: 'WACC (último trim.)', value: fmt.pct(v.wacc_last) },
    { label: 'Spread ROIC−WACC', value: fmt.pct1(v.econ_spread), cls: colorClass(v.econ_spread) },
    { label: 'Treasury Yield (10Y)', value: fmt.pct(v.treasury_yield) },
    { label: 'Cash Excess / Ação', value: fmt.$(v.cash_excess_ps) },
    { label: 'FCF Yield', value: fmt.pct(v.fcf_yield), cls: colorClass(v.fcf_yield) },
    { label: 'EBIT Yield (TIR)', value: fmt.pct(v.tir), cls: colorClass(v.tir) },
    { label: 'Div Yield', value: fmt.pct(v.div_yield) },
  ];

  const kpiHtml = kpis.map(k => `
    <div class="val-card">
      <div class="val-label">${k.label}</div>
      <div class="val-value ${k.cls||''}">${k.value}</div>
    </div>`).join('');

  // MS Table
  const msRows = [
    { metric: 'EBIT', eps: fmt.$(v.ebit_ps), cagr: fmt.pct(v.ebit_cagr), graham: fmt.$(v.graham_ebit), ms: v.ms_ebit },
    { metric: 'FCF − SBC', eps: fmt.$(v.fcf_ps), cagr: fmt.pct(v.fcf_cagr), graham: fmt.$(v.graham_fcf), ms: v.ms_fcf },
    { metric: 'Economic Profit', eps: fmt.$(v.ep_ps), cagr: fmt.pct(v.ep_cagr), graham: fmt.$(v.graham_ep), ms: v.ms_ep },
    { metric: 'Dividendos', eps: fmt.$(v.div_ps), cagr: fmt.pct(v.div_cagr), graham: fmt.$(v.graham_div), ms: v.ms_div },
  ];

  const msTableHtml = msRows.map(row => {
    const ms = row.ms;
    const msText = ms == null ? '—' : fmt.pct1(ms);
    const barPct = ms == null ? 0 : Math.min(Math.abs(ms) * 100, 100);
    const barColor = ms == null ? '#64748b' : (ms >= 0 ? '#22c55e' : '#ef4444');
    const barLeft = ms != null && ms < 0 ? `margin-left:${50 - barPct/2}%;width:${barPct/2}%` : `margin-left:50%;width:${barPct/2}%`;
    return `<tr>
      <td><b>${row.metric}</b></td>
      <td>${row.eps}</td>
      <td>${row.cagr}</td>
      <td>${row.graham}</td>
      <td class="${ms==null?'':colorClass(ms)}" style="font-weight:600">${msText}</td>
      <td class="ms-bar-cell">
        <div class="ms-bar-wrap">
          <div class="ms-bar-bg" style="position:relative">
            <div class="ms-bar-fill" style="position:absolute;top:0;height:100%;background:${barColor};${barLeft}"></div>
            <div style="position:absolute;top:0;left:50%;width:1px;height:100%;background:var(--border)"></div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('');

  const avgMs = v.avg_ms;
  const avgMsClass = colorClass(avgMs);

  return `
    <div class="valuation-grid">${kpiHtml}</div>

    <h3 style="margin-bottom:12px;font-size:14px;color:var(--text2)">Margem de Segurança — Fórmula de Graham</h3>
    <p style="font-size:11px;color:var(--text3);margin-bottom:14px">
      V = EPS × (8,5 + 2 × CAGR%) × 4,4 / Y&nbsp;&nbsp;·&nbsp;&nbsp;MS = (V − Preço) / V
    </p>
    <div class="ms-table-wrap">
      <table class="ms-table">
        <thead>
          <tr>
            <th>Métrica</th>
            <th>EPS/Ação TTM</th>
            <th>CAGR (10A)</th>
            <th>Graham (V)</th>
            <th>Margem de Segurança</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${msTableHtml}</tbody>
        <tfoot>
          <tr style="font-weight:700;border-top:2px solid var(--border)">
            <td colspan="4" style="text-align:right;padding-right:14px">Média (FCF + EP + Div)</td>
            <td class="${avgMsClass}" style="font-size:16px">${fmt.pct1(avgMs)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>`;
}

// ─── Charts Panel ─────────────────────────────────────────────────────────────
function buildChartsPanel(r, color) {
  const id = r.ticker;
  return `
    <div class="charts-grid">
      <div class="chart-card"><div class="chart-title">EBIT por Ação (TTM) — 45 trimestres</div><canvas class="chart-canvas" id="ch-ebit-${id}"></canvas></div>
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
  const idx = allResults.indexOf(r);
  const color = COLORS[idx % COLORS.length];
  const rows = r.rows;
  const labels = rows.map(rw => rw.date.slice(0,7));

  function makeChart(canvasId, datasets, opts={}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (chartInstances[canvasId]) chartInstances[canvasId].destroy();
    chartInstances[canvasId] = new Chart(canvas, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: datasets.length > 1, labels: { color: '#94a3b8', font: { size: 11 } } },
          tooltip: { mode: 'index', intersect: false }
        },
        scales: {
          x: { ticks: { color: '#64748b', maxTicksLimit: 8, font: { size: 10 } }, grid: { color: '#2d3150' } },
          y: { ticks: { color: '#64748b', font: { size: 10 }, callback: v => opts.pct ? (v*100).toFixed(0)+'%' : '$'+v.toFixed(opts.dec ?? 2) }, grid: { color: '#2d3150' } }
        },
        ...opts.extra
      }
    });
  }

  const ds = (label, data, col, fill=false) => ({
    label, data,
    borderColor: col,
    backgroundColor: fill ? col + '22' : 'transparent',
    borderWidth: 2,
    pointRadius: 0,
    tension: 0.3,
    fill
  });

  makeChart(`ch-ebit-${ticker}`, [ds('EBIT/ação', rows.map(r=>r.ebit_ps), color, true)]);
  makeChart(`ch-fcf-${ticker}`,  [ds('FCF-SBC/ação', rows.map(r=>r.fcf_sbc_ps), '#22c55e', true)]);
  makeChart(`ch-ep-${ticker}`,   [ds('Eco. Profit/ação', rows.map(r=>r.econ_profit_ps), '#a78bfa', true)]);
  makeChart(`ch-roic-${ticker}`, [
    ds('ROIC', rows.map(r=>r.roic), color),
    ds('WACC', rows.map(r=>r.wacc), '#ef4444')
  ], {pct:true});
  makeChart(`ch-rev-${ticker}`,  [ds('Receita/ação', rows.map(r=>r.revenue_ps), '#f59e0b', true)]);
  makeChart(`ch-lev-${ticker}`,  [ds('Net Debt/FCF', rows.map(r=>r.net_debt_fcf), '#f87171')], {dec:1});
}

// ─── 45Q Table Panel ──────────────────────────────────────────────────────────
function buildTablePanel(r) {
  const rows = r.rows;
  const metrics = [
    { label: 'Cash / Ação',           fn: rw => fmt.$(rw.cash_ps) },
    { label: 'Dívida + Lease / Ação', fn: rw => fmt.$(rw.debt_lease_ps) },
    { label: 'Receita / Ação TTM',    fn: rw => fmt.$(rw.revenue_ps) },
    { label: 'EBIT / Ação TTM',       fn: rw => fmt.$(rw.ebit_ps) },
    { label: 'NOPAT / Ação TTM',      fn: rw => fmt.$(rw.nopat_ps) },
    { label: 'Net Income / Ação TTM', fn: rw => fmt.$(rw.net_income_ps) },
    { label: 'OCF−SBC / Ação TTM',    fn: rw => fmt.$(rw.ocf_sbc_ps) },
    { label: 'FCF−SBC / Ação TTM',    fn: rw => fmt.$(rw.fcf_sbc_ps) },
    { label: 'Dividendos / Ação TTM', fn: rw => fmt.$(rw.dividend_ps) },
    { label: 'Recompra / Ação TTM',   fn: rw => fmt.$(rw.repurchase_ps) },
    { label: 'Cash Retornado / Ação', fn: rw => fmt.$(rw.cash_returned_ps) },
    { label: 'Eco. Profit / Ação TTM',fn: rw => fmt.$(rw.econ_profit_ps) },
    { label: 'Cap. Investido / Ação', fn: rw => fmt.$(rw.invested_cap_ps) },
    { label: 'ROIC',                  fn: rw => fmt.pct(rw.roic) },
    { label: 'ROIC ex-Goodwill',      fn: rw => fmt.pct(rw.roic_ex_gw) },
    { label: 'ROIIC (1 ano)',         fn: rw => rw.roiic_1y == null ? '—' : fmt.pct(rw.roiic_1y) },
    { label: 'WACC',                  fn: rw => fmt.pct(rw.wacc) },
    { label: 'Tax Rate Efetivo',      fn: rw => fmt.pct(rw.eff_tax) },
    { label: 'Capex / Receita',       fn: rw => fmt.pct(rw.capex_rev) },
    { label: 'Opex / Receita',        fn: rw => fmt.pct(rw.opex_rev) },
    { label: 'Net Debt / FCF (anos)', fn: rw => rw.net_debt_fcf ? rw.net_debt_fcf.toFixed(1) + 'x' : '—' },
    { label: 'Ações Diluídas',        fn: rw => (rw.shares / 1e9).toFixed(3) + 'B' },
  ];

  const dates = rows.map(rw => rw.date.slice(0,7));
  const thHtml = dates.map(d => `<th>${d}</th>`).join('');
  const tbodyHtml = metrics.map(m => {
    const cells = rows.map(rw => `<td>${m.fn(rw)}</td>`).join('');
    return `<tr><td>${m.label}</td>${cells}</tr>`;
  }).join('');

  const exportFn = `exportCSV_${r.ticker.replace('-','_')}`;
  window[exportFn] = () => exportCSV(r);

  return `
    <div style="display:flex;justify-content:flex-end;margin-bottom:10px">
      <button class="export-btn" onclick="${exportFn}()">⬇ Exportar CSV</button>
    </div>
    <div class="data-table-wrap">
      <table class="data-table">
        <thead><tr><th>Métrica</th>${thHtml}</tr></thead>
        <tbody>${tbodyHtml}</tbody>
      </table>
    </div>`;
}

// ─── CSV Export ───────────────────────────────────────────────────────────────
function exportCSV(r) {
  const rows = r.rows;
  const fields = Object.keys(rows[0]).filter(k => !k.startsWith('_'));
  const header = ['metric', ...rows.map(rw => rw.date)].join(',');
  const body = fields.map(f => [f, ...rows.map(rw => rw[f] ?? '')].join(',')).join('\n');
  const blob = new Blob([header + '\n' + body], {type: 'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${r.ticker}_45Q_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
}
