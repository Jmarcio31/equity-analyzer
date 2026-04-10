// ─── Definições de tooltip por métrica ───────────────────────────────────────// ─── Painel de valuation para financeiras ────────────────────────────────────
function buildValuationPanelFinancial(r, v) {
  const fmt2 = {
    pct:  x => x == null ? '—' : (x*100).toFixed(1)+'%',
    x:    x => x == null ? '—' : x.toFixed(1)+'x',
    $:    x => x == null ? '—' : '$'+x.toFixed(2),
    bn:   x => x == null ? '—' : (Math.abs(x)>=1e12 ? (x/1e12).toFixed(1)+'T' : Math.abs(x)>=1e9 ? (x/1e9).toFixed(1)+'B' : (x/1e6).toFixed(0)+'M'),
    pct1: x => x == null ? '—' : (x>=0?'+':'')+(x*100).toFixed(1)+'%',
  };

  const FIN_TOOLTIPS = {
    'ROE': 'Return on Equity — Lucro Líquido TTM ÷ Patrimônio Líquido.

Principal métrica de rentabilidade para bancos, substitui o ROIC.

ROE > custo do equity (≈10-12%) = criação de valor para o acionista.',
    'P/TBV': 'Preço ÷ Tangible Book Value por ação.

TBV = Patrimônio Líquido − Goodwill

Múltiplo fundamental para bancos. P/TBV < 1 pode indicar desconto; > 2 pode indicar prêmio elevado.

Bancos que destroem valor tendem a negociar abaixo de 1x TBV.',
    'P/E': 'Preço ÷ Lucro Líquido por ação (TTM).

Para financeiras, é mais útil que EV/EBIT porque a estrutura de capital é parte do negócio.',
    'NIM (proxy)': 'Net Interest Margin — Receita Total ÷ Total de Ativos.

Proxy aproximado: a API não separa receita de juros líquida com precisão suficiente.

NIM real = (Juros Recebidos − Juros Pagos) ÷ Ativos Rentáveis.',
    'Eficiência': 'Despesas Operacionais ÷ Receita Total.

Quanto menor, mais eficiente. Bancos bem geridos ficam abaixo de 50%.

Bancos brasileiros tipicamente ficam entre 40-55%.',
    'Payout': 'Dividendos Pagos ÷ Lucro Líquido TTM.

Bancos maduros (JPM, ITUB) tendem a ter payouts de 30-50%.

Bancos de crescimento (NU) tendem a reter mais capital.',
    'TBV / Ação': 'Tangible Book Value por ação = (Patrimônio Líquido − Goodwill) ÷ Ações.

Representa o valor contábil tangível por ação, base para o P/TBV.',
    'Total de Ativos': 'Total de ativos do último trimestre. Para bancos, o crescimento de ativos é proxy do crescimento da carteira de crédito.',
  };

  function tip2(key) {
    const txt = FIN_TOOLTIPS[key];
    if (!txt) return '';
    const escaped = txt.replace(/"/g, '&quot;').replace(/\n/g, '&#10;');
    return `<span class="info-icon" data-tip="${escaped}" onclick="showTooltipModal(this)">ⓘ</span>`;
  }

  const cc = x => x == null ? '' : x > 0 ? 'green' : x < 0 ? 'red' : '';

  const kpis = [
    {label:'Cotação',          value: fmt2.$(v.price)},
    {label:'P/E',              value: fmt2.x(v.p_e),         cls: ''},
    {label:'P/TBV',            value: fmt2.x(v.p_tbv),       cls: ''},
    {label:'ROE',              value: fmt2.pct(v.roe),        cls: cc(v.roe - 0.10)},
    {label:'NIM (proxy)',      value: fmt2.pct(v.nim_proxy)},
    {label:'Eficiência',       value: fmt2.pct(v.efficiency), cls: v.efficiency ? (v.efficiency < 0.50 ? 'green' : 'red') : ''},
    {label:'Payout',           value: fmt2.pct(v.payout)},
    {label:'Div Yield',        value: fmt2.pct(v.div_yield),  cls: cc(v.div_yield)},
    {label:'TBV / Ação',       value: fmt2.$(v.tbv_ps)},
    {label:'BV / Ação',        value: fmt2.$(v.bv_ps)},
    {label:'Total de Ativos',  value: fmt2.bn(v.total_assets)},
    {label:'Patrimônio Líq.',  value: fmt2.bn(v.equity_abs)},
  ];

  const kpiHtml = kpis.map(k => `<div class="val-card">
    <div class="val-label">${k.label}${tip2(k.label)}</div>
    <div class="val-value ${k.cls||''}">${k.value}</div>
  </div>`).join('');

  // Tabela Graham adaptada (EPS e Dividendos)
  const msRows = [
    {metric:'EPS (Lucro Líq./Ação)', tip:'P/E', eps: fmt2.$(v.eps_ps),  cagr: fmt2.pct(v.eps_cagr), graham: fmt2.$(v.graham_eps), ms: v.ms_eps},
    {metric:'Dividendos/Ação',       tip:'Payout', eps: fmt2.$(v.div_ps), cagr: fmt2.pct(v.div_cagr), graham: fmt2.$(v.graham_div), ms: v.ms_div},
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
      <td class="${cc(ms)}" style="font-weight:600">${ms==null?'—':fmt2.pct1(ms)}</td>
      <td><div class="ms-bar-bg" style="position:relative">
        <div class="ms-bar-fill" style="${barStyle};background:${barColor};position:absolute;top:0;height:100%"></div>
        <div style="position:absolute;top:0;left:50%;width:1px;height:100%;background:var(--border)"></div>
      </div></td>
    </tr>`;
  }).join('');

  return `
    <div class="fin-notice">
      ⚠️ <b>Instituição Financeira</b> — framework adaptado (Damodaran). ROIC/EVA/FCF não aplicáveis.
      Métricas: ROE · P/TBV · NIM · Eficiência · Payout.
    </div>
    <div class="valuation-grid">${kpiHtml}</div>
    <h3 style="margin-bottom:8px;font-size:13px;color:var(--text2)">Margem de Segurança — Fórmula de Graham (adaptada)</h3>
    <p style="font-size:11px;color:var(--text3);margin-bottom:12px">
      V = EPS × (8,5 + 2 × CAGR%) × 4,4 / Y &nbsp;·&nbsp; EPS = Lucro Líquido/Ação &nbsp;·&nbsp; CAGR = crescimento de receita (proxy)
    </p>
    <div class="ms-table-wrap"><table class="ms-table">
      <thead><tr><th>Métrica</th><th>Valor/Ação TTM</th><th>CAGR</th><th>Graham (V)</th><th>Margem de Segurança</th><th></th></tr></thead>
      <tbody>${msRows}</tbody>
      <tfoot><tr style="font-weight:700;border-top:2px solid var(--border)">
        <td colspan="4" style="text-align:right;padding-right:14px">Média (EPS + Div)</td>
        <td class="${cc(v.avg_ms)}" style="font-size:15px">${v.avg_ms==null?'—':((v.avg_ms>=0?'+':'')+(v.avg_ms*100).toFixed(1)+'%')}</td><td></td>
      </tr></tfoot>
    </table></div>`;
}


const TOOLTIPS = {
  'Cotação': 'Última cotação disponível no banco de dados. Atualizada diariamente pelo script de carga.',
  'EV / EBIT': 'Enterprise Value dividido pelo EBIT (TTM). Mede quanto o mercado paga pelo lucro operacional. <15x = barato; >30x = caro (regra geral, varia por setor).',
  'Market Cap': 'Preço × Ações em circulação do último trimestre disponível.',
  'Enterprise Value': 'Market Cap + Dívida Total − Caixa Completo (ST + LT investments). Representa o valor total da empresa para um comprador.',
  'ROIC (último trim.)': 'Return on Invested Capital.

Fórmula: NOPAT ÷ Capital Investido ex-Goodwill

NOPAT = EBIT × (1 − Tax Rate efetivo, cap 30%)
Capital Investido ex-GW = NWC + PP&E + Intangíveis
NWC = (Ativo Circ. − Caixa Completo) − (Passivo Circ. − Dívida CP)

Exclui goodwill do denominador para refletir o retorno sobre ativos tangíveis, sem distorção de aquisições a prêmio.

Horizonte: último trimestre (anualizado via TTM).',
  'WACC (último trim.)': 'Weighted Average Cost of Capital.

Fórmula: Ke × We + Kd × (1−t) × Wd

Ke (custo do equity) = 10% fixo
Kd (custo da dívida) = Despesa Financeira ÷ Dívida Total
Ponderação: estrutura de capital do último trimestre

O Ke de 10% é uma proxy do custo de equity para mercado americano. Empresas brasileiras têm custo de capital maior — limitação do modelo atual.',
  'Spread ROIC−WACC': 'ROIC − WACC. Spread positivo = empresa criando valor econômico; negativo = destruindo valor mesmo com lucro contábil positivo.

É o principal indicador de qualidade do negócio neste framework.',
  'Treasury Yield (10Y)': 'Taxa do Treasury americano de 10 anos, usada como:
1. Taxa livre de risco na Fórmula de Graham (denominador Y%)
2. Referência para o WACC

Fonte: Alpha Vantage, atualizada periodicamente.',
  'Cash Excess / Ação': 'Caixa excedente por ação.

Fórmula: max(Caixa Completo − Dívida Total, 0) ÷ Ações

Caixa Completo = Cash & ST Investments + LT Investments

Representa o caixa líquido disponível acima da dívida.',
  'FCF Yield': 'FCF−SBC ÷ Market Cap.

FCF−SBC = Fluxo de Caixa Operacional − Capex − Stock-Based Compensation

É o "free cash flow to equity" ajustado pelo SBC, que é uma despesa real mas não-caixa.',
  'EBIT Yield (TIR)': 'EBIT (TTM) ÷ Enterprise Value. Equivale ao inverso do EV/EBIT.

Interpretação: se você comprasse a empresa inteira, qual seria o rendimento anual sobre o preço pago.',
  'Div Yield': 'Dividendos pagos por ação (TTM) ÷ Preço atual.',
  'EBIT': 'Earnings Before Interest and Taxes — lucro operacional.

Fonte: operatingIncome da API (TTM = soma dos últimos 4 trimestres).

Usado na Fórmula de Graham como proxy do poder de lucro operacional.',
  'FCF − SBC': 'Free Cash Flow ajustado por Stock-Based Compensation.

Fórmula: OCF − |Capex| − SBC

É o FCFE implícito (equity free cash flow), pois parte do OCF já reflete pagamentos de dívida.

Não é FCFF (firm). O SBC é deduzido porque dilui o acionista.',
  'Economic Profit': 'Lucro Econômico (equivalente ao EVA®).

Fórmula: NOPAT − (WACC × Capital Investido ex-Goodwill)

Diferente do EVA clássico: usamos capital ex-goodwill para evitar distorção de aquisições.

EP > 0 = empresa gerando retorno acima do custo de capital.',
  'Dividendos': 'Dividendos pagos por ação nos últimos 12 meses (TTM).

Fonte: dividendsPaid do Cash Flow Statement.

Como o CAGR de dividendos exige histórico longo, a Margem de Segurança por dividendos tem menor peso analítico para empresas de crescimento.',
  'Margem de Segurança': 'Fórmula de Graham (revisão 1974):

V = EPS × (8,5 + 2 × g%) × (4,4 ÷ Y%)

Onde:
• EPS = métrica por ação (EBIT, FCF, EP ou Div)
• 8,5 = múltiplo base para crescimento zero
• g% = CAGR histórico de 5 anos (ou 3 se indisponível)
• 4,4 = yield do AAA bond na época de Graham (~1962)
• Y% = Treasury 10Y atual

MS = (V − Preço) ÷ V

MS > 0 = ação abaixo do valor intrínseco calculado',
};

function tooltip(key) {
  const txt = TOOLTIPS[key];
  if (!txt) return '';
  const escaped = txt.replace(/"/g, '&quot;').replace(/\n/g, '&#10;');
  return `<span class="info-icon" data-tip="${escaped}" onclick="showTooltipModal(this)">ⓘ</span>`;
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
    <div class="val-label">${k.label}${tooltip(k.label)}</div>
    <div class="val-value ${k.cls||''}">${k.value}</div>
  </div>`).join('');

  const msRows = [
    {metric:'EBIT',           tip:'EBIT',            eps: fmt.$(v.ebit_ps), cagr: fmt.pct(v.ebit_cagr), graham: fmt.$(v.graham_ebit), ms: v.ms_ebit},
    {metric:'FCF − SBC',      tip:'FCF − SBC',        eps: fmt.$(v.fcf_ps),  cagr: fmt.pct(v.fcf_cagr),  graham: fmt.$(v.graham_fcf),  ms: v.ms_fcf},
    {metric:'Economic Profit',tip:'Economic Profit',  eps: fmt.$(v.ep_ps),   cagr: fmt.pct(v.ep_cagr),   graham: fmt.$(v.graham_ep),   ms: v.ms_ep},
    {metric:'Dividendos',     tip:'Dividendos',       eps: fmt.$(v.div_ps),  cagr: fmt.pct(v.div_cagr),  graham: fmt.$(v.graham_div),  ms: v.ms_div},
  ].map(row => {
    const ms = row.ms;
    const barPct = ms == null ? 0 : Math.min(Math.abs(ms) * 100, 100);
    const barColor = ms == null ? '#64748b' : (ms >= 0 ? '#22c55e' : '#ef4444');
    const barStyle = ms != null && ms < 0
      ? `right:50%;width:${barPct/2}%`
      : `left:50%;width:${barPct/2}%`;
    return `<tr>
      <td><b>${row.metric}</b>${tooltip(row.tip||row.metric)}</td>
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
      <thead><tr><th>Métrica</th><th>EPS/Ação TTM${tooltip('EBIT')}</th><th>CAGR</th><th>Graham (V)${tooltip('Margem de Segurança')}</th><th>Margem de Segurança</th><th></th></tr></thead>
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
