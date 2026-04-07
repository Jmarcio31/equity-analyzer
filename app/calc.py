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

    g_ebit = graham(last.get("ebit_ps",0),        pct(last.get("_ebit_cagr")))
    g_fcf  = graham(last.get("fcf_sbc_ps",0),     pct(last.get("_fcf_cagr")))
    g_ep   = graham(last.get("econ_profit_ps",0), pct(last.get("_ep_cagr")))
    g_div  = graham(last.get("dividend_ps",0),    pct(last.get("_div_cagr")))

    ms_ebit = ms(g_ebit, price)
    ms_fcf  = ms(g_fcf,  price)
    ms_ep   = ms(g_ep,   price)
    ms_div  = ms(g_div,  price)

    valid  = [v for v in [ms_fcf, ms_ep, ms_div] if v is not None]
    avg_ms = sum(valid)/len(valid) if valid else None
    shares = last.get("shares", 1)
    mktcap = price * shares
    ev     = mktcap + last.get("total_debt_abs",0) - last.get("cash_abs",0)

    return {
        "price": price, "treasury_yield": treasury_yield,
        "cash_ps": last.get("cash_ps",0),
        "debt_ps": last.get("debt_lease_ps",0),
        "cash_excess_ps": max(last.get("cash_ps",0) - last.get("debt_lease_ps",0), 0),
        "ebit_ps":    last.get("ebit_ps",0),        "ebit_cagr":  last.get("_ebit_cagr"),
        "graham_ebit": g_ebit,                       "ms_ebit":    ms_ebit,
        "fcf_ps":     last.get("fcf_sbc_ps",0),     "fcf_cagr":   last.get("_fcf_cagr"),
        "graham_fcf":  g_fcf,                        "ms_fcf":     ms_fcf,
        "ep_ps":      last.get("econ_profit_ps",0), "ep_cagr":    last.get("_ep_cagr"),
        "graham_ep":   g_ep,                         "ms_ep":      ms_ep,
        "div_ps":     last.get("dividend_ps",0),    "div_cagr":   last.get("_div_cagr"),
        "graham_div":  g_div,                        "ms_div":     ms_div,
        "avg_ms": avg_ms,
        "ev_ebit": ev / last.get("ebit_abs",1) if last.get("ebit_abs") else None,
        "ev": ev, "mktcap": mktcap,
        "ebit_yield": last.get("ebit_abs",0) / ev          if ev      else None,
        "fcf_yield":  last.get("fcf_sbc_abs",0) / mktcap   if mktcap  else None,
        "ep_yield":   last.get("econ_profit_abs",0) / mktcap if mktcap else None,
        "div_yield":  last.get("dividend_ps",0) / price    if price   else None,
        "tir":        last.get("ebit_abs",0) / ev          if ev      else None,
        "roic_last":   last.get("roic",0),
        "wacc_last":   last.get("wacc",0),
        "econ_spread": last.get("roic",0) - last.get("wacc",0),
    }
