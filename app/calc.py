"""
Cálculos de valuation — separados do acesso a dados.
Recebe rows do banco e retorna valuation calculado.
"""

def compute_valuation(rows, price, treasury_yield=0.0428):
    if not rows:
        return {}
    last  = rows[-1]
    y_pct = treasury_yield * 100

    def pct(v): return (v or 0) * 100
    def graham(eps, g_pct):
        if not eps or eps <= 0 or y_pct <= 0: return None
        return eps * (8.5 + 2 * g_pct) * (4.4 / y_pct)
    def ms(iv, px):
        if not iv or iv <= 0: return None
        return (iv - px) / iv
    def safe(v):
        """Converte None para 0 — evita NoneType em operações aritméticas."""
        return v if v is not None else 0

    g_ebit = graham(last.get("ebit_ps", 0),        pct(last.get("_ebit_cagr")))
    g_fcf  = graham(last.get("fcf_sbc_ps", 0),     pct(last.get("_fcf_cagr")))
    g_ep   = graham(last.get("econ_profit_ps", 0), pct(last.get("_ep_cagr")))
    g_div  = graham(last.get("dividend_ps", 0),    pct(last.get("_div_cagr")))

    ms_ebit = ms(g_ebit, price)
    ms_fcf  = ms(g_fcf,  price)
    ms_ep   = ms(g_ep,   price)
    ms_div  = ms(g_div,  price)

    # avg_ms: usa FCF e Div (mais estáveis que EP)
    # Dividendo só entra se ticker tiver ≥8 trimestres de histórico
    div_quarters_with_data = sum(1 for r in rows if (r.get("dividend_ps") or 0) > 0)
    div_history_sufficient = div_quarters_with_data >= 8

    valid_ms = []
    if g_fcf and g_fcf > 0 and ms_fcf is not None:
        valid_ms.append(ms_fcf)
    if div_history_sufficient and g_div and g_div > 0 and ms_div is not None:
        valid_ms.append(ms_div)
    avg_ms = sum(valid_ms) / len(valid_ms) if valid_ms else None

    shares = last.get("shares", 1)
    mktcap = price * shares
    ev     = mktcap + safe(last.get("total_debt_abs")) - safe(last.get("cash_abs"))

    # Campos absolutos — podem ser None quando IC negativo (P3)
    ebit_abs        = last.get("ebit_abs")
    fcf_sbc_abs     = last.get("fcf_sbc_abs")
    econ_profit_abs = last.get("econ_profit_abs")

    return {
        "price": price, "treasury_yield": treasury_yield,
        "cash_ps":       last.get("cash_ps", 0),
        "debt_ps":       last.get("debt_lease_ps", 0),
        "cash_excess_ps": max(last.get("cash_ps", 0) - last.get("debt_lease_ps", 0), 0),

        "ebit_ps":     last.get("ebit_ps", 0),    "ebit_cagr":  last.get("_ebit_cagr"),
        "graham_ebit": g_ebit,                     "ms_ebit":    ms_ebit,
        "fcf_ps":      last.get("fcf_sbc_ps", 0), "fcf_cagr":   last.get("_fcf_cagr"),
        "graham_fcf":  g_fcf,                      "ms_fcf":     ms_fcf,
        "ep_ps":       last.get("econ_profit_ps", 0), "ep_cagr": last.get("_ep_cagr"),
        "graham_ep":   g_ep,                       "ms_ep":      ms_ep,
        "div_ps":      last.get("dividend_ps", 0), "div_cagr":   last.get("_div_cagr"),
        "graham_div":  g_div,                      "ms_div":     ms_div,
        "avg_ms": avg_ms,

        "ev_ebit":  ev / ebit_abs        if ev and ebit_abs        else None,
        "ev":       ev,
        "mktcap":   mktcap,
        "ebit_yield":  ebit_abs        / ev     if ev     and ebit_abs        is not None else None,
        "fcf_yield":   fcf_sbc_abs     / mktcap if mktcap and fcf_sbc_abs     is not None else None,
        "ep_yield":    econ_profit_abs / mktcap if mktcap and econ_profit_abs is not None else None,
        "div_yield":   last.get("dividend_ps", 0) / price if price else None,
        "tir":         ebit_abs        / ev     if ev     and ebit_abs        is not None else None,

        # P2: usa roic_ex_gw (ex-Goodwill) — cap abs<5 filtra dados legados com max(...,1)
        "roic_last": last.get("roic_ex_gw")
                     if (last.get("roic_ex_gw") is not None
                         and abs(last.get("roic_ex_gw", 0)) < 5)
                     else last.get("roic", 0),
        "wacc_last":   last.get("wacc", 0),
        # P2: spread usa roic_ex_gw; suprime quando off-scale
        "econ_spread": ((last.get("roic_ex_gw") or last.get("roic", 0)) - last.get("wacc", 0))
                       if (last.get("roic_ex_gw") is not None
                           and abs(last.get("roic_ex_gw", 0)) < 5)
                       else None,
    }


# ─── Motor analítico para financeiras ────────────────────────────────────────
# FINANCIAL_TICKERS definido em config.py (fonte única da verdade)

def compute_valuation_financial(rows, price, treasury_yield=0.0428):
    """
    Motor analítico para instituições financeiras.
    Baseado em ROE, P/TBV, NIM, Eficiência e Payout.
    Não usa ROIC/EVA/FCF operacional (inadequados para bancos).
    """
    if not rows:
        return {}

    last  = rows[-1]
    y_pct = treasury_yield * 100

    def fv(v): return v if v is not None else 0.0
    def pct(v): return (v or 0) * 100

    # ── Patrimônio Líquido ────────────────────────────────────────────────────
    equity   = fv(last.get("equity_abs"))
    goodwill = fv(last.get("goodwill_abs"))

    # P10: TBV = PL − goodwill; pode não excluir todos os intangíveis (dados AV)
    tbv             = max(equity - goodwill, 1)
    tbv_approximate = True

    shares   = fv(last.get("shares")) or 1
    tbv_ps   = tbv / shares
    bv_ps    = equity / shares

    # P5: mktcap e ev calculados aqui (evita fallback no comparativo)
    mktcap_fin = price * shares
    ev_fin     = mktcap_fin + fv(last.get("total_debt_abs")) - fv(last.get("cash_abs"))

    # ── ROE (TTM) ─────────────────────────────────────────────────────────────
    ni_ps          = fv(last.get("net_income_ps"))
    net_income_ttm = ni_ps * shares if ni_ps else 0.0
    roe            = net_income_ttm / equity if equity else 0

    # ── Yield de Ativos (proxy NIM) ───────────────────────────────────────────
    total_assets       = fv(last.get("total_assets_abs"))
    revenue_ttm        = fv(last.get("revenue_abs"))
    yield_assets_proxy = revenue_ttm / total_assets if total_assets else 0

    # ── Eficiência ────────────────────────────────────────────────────────────
    efficiency = fv(last.get("opex_rev"))

    # ── P/TBV e P/BV ─────────────────────────────────────────────────────────
    p_tbv = price / tbv_ps if tbv_ps else None
    p_bv  = price / bv_ps  if bv_ps  else None

    # ── Payout ────────────────────────────────────────────────────────────────
    div_ps        = fv(last.get("dividend_ps"))
    div_ttm       = div_ps * shares
    payout        = div_ttm / net_income_ttm if net_income_ttm else None
    div_yield_fin = div_ps / price if price else None

    # ── EPS e crescimento ─────────────────────────────────────────────────────
    eps_ps   = ni_ps
    eps_cagr = last.get("_eps_cagr") or last.get("_ebit_cagr")   # P6
    div_cagr = last.get("_div_cagr")

    # ── Graham adaptado para financeiras ──────────────────────────────────────
    def graham_fin(eps, g_pct):
        if not eps or eps <= 0 or y_pct <= 0:
            return None
        return eps * (8.5 + 2 * g_pct) * (4.4 / y_pct)

    def ms(iv, px):
        if not iv or iv <= 0: return None
        return (iv - px) / iv

    g_cagr     = pct(last.get("_eps_cagr") or last.get("_ebit_cagr"))
    g_div_cagr = pct(last.get("_div_cagr"))

    graham_eps = graham_fin(eps_ps, g_cagr)
    graham_div = graham_fin(div_ps, g_div_cagr)
    ms_eps     = ms(graham_eps, price)
    ms_div     = ms(graham_div, price)

    valid_fin = [v for v in [ms_eps, ms_div] if v is not None and -5 < v < 5]
    avg_ms    = sum(valid_fin) / len(valid_fin) if valid_fin else None

    # ── P/E ───────────────────────────────────────────────────────────────────
    pe = price / eps_ps if eps_ps and eps_ps > 0 else None

    return {
        "is_financial": True,
        "price":        price,
        "treasury_yield": treasury_yield,

        "roe":    roe,
        "p_tbv":  p_tbv,
        "p_bv":   p_bv,
        "p_e":    pe,
        "tbv_ps": tbv_ps,
        "bv_ps":  bv_ps,
        "eps_ps": eps_ps,

        "nim_proxy":   yield_assets_proxy,
        "efficiency":  efficiency,
        "payout":      payout,
        "div_yield":   div_yield_fin,
        "div_ps":      div_ps,
        "div_cagr":    last.get("_div_cagr"),
        "eps_cagr":    last.get("_eps_cagr") or last.get("_ebit_cagr"),
        "revenue_abs": revenue_ttm,
        "total_assets": total_assets,
        "equity_abs":  equity,
        "tbv_abs":     tbv,
        "tbv_approximate": tbv_approximate,

        "graham_eps": graham_eps,
        "graham_div": graham_div,
        "ms_eps":     ms_eps,
        "ms_div":     ms_div,
        "avg_ms":     avg_ms,

        "mktcap": mktcap_fin,
        "ev":     ev_fin,
    }
