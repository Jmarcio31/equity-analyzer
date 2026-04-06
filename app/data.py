import yfinance as yf

def fetch_company_profile(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "companyName":      info.get("longName") or info.get("shortName", ticker),
            "price":            info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "sector":           info.get("sector", ""),
            "industry":         info.get("industry", ""),
            "currency":         info.get("currency", "USD"),
            "exchangeShortName":info.get("exchange", ""),
            "description":      (info.get("longBusinessSummary") or "")[:300],
        }
    except Exception:
        return {"companyName": ticker, "price": 0, "sector": "", "industry": "",
                "currency": "USD", "exchangeShortName": "", "description": ""}


def fetch_quarterly_financials(ticker, quarters=45):
    t = yf.Ticker(ticker)

    inc = t.quarterly_income_stmt
    bs  = t.quarterly_balance_sheet
    cf  = t.quarterly_cashflow

    # yfinance: colunas = datas (mais recente à esquerda), linhas = métricas
    def col(df, col_date):
        if df is None or col_date not in df.columns:
            return {}
        return df[col_date].to_dict()

    def val(d, *keys):
        for k in keys:
            v = d.get(k)
            if v is not None and v == v:  # not NaN
                return float(v)
        return 0.0

    # Pega datas disponíveis (mais antiga → mais recente)
    if inc is None or inc.empty:
        return []
    dates = sorted(inc.columns.tolist())[-quarters:]

    # Shares — usa info para shares atuais
    info = t.info
    shares_now = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 1

    rows = []
    for date in dates:
        i = col(inc, date)
        b = col(bs,  date)
        c = col(cf,  date)

        # Shares — tenta do balanço, senão usa info atual
        shares = val(b, "Ordinary Shares Number", "Share Issued") or shares_now

        # TTM: soma os 4 trimestres até esta data
        def ttm(df, *keys):
            if df is None: return 0.0
            idx = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            total = 0.0
            for k in keys:
                if k in df.index:
                    for d in window:
                        if d in df.columns:
                            v = df.loc[k, d]
                            if v == v:  # not NaN
                                total += float(v)
                    return total
            return 0.0

        revenue    = ttm(inc, "Total Revenue")
        ebit       = ttm(inc, "Operating Income", "EBIT")
        net_income = ttm(inc, "Net Income")
        sbc        = ttm(inc, "Stock Based Compensation")
        da         = ttm(inc, "Reconciled Depreciation", "Depreciation And Amortization")
        interest   = ttm(inc, "Interest Expense")
        tax_exp    = ttm(inc, "Tax Provision", "Income Tax Expense")
        ebt        = ttm(inc, "Pretax Income") or 1
        ocf        = ttm(cf,  "Operating Cash Flow")
        capex      = ttm(cf,  "Capital Expenditure")          # negativo
        dividends  = ttm(cf,  "Common Stock Dividend Paid", "Cash Dividends Paid")
        repurchase = ttm(cf,  "Repurchase Of Capital Stock", "Common Stock Repurchase")

        # Balanço (ponto)
        cash       = val(b, "Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
        cash_st    = val(b, "Other Short Term Investments", "Available For Sale Securities") 
        cash_total = cash + cash_st
        total_debt = val(b, "Total Debt", "Long Term Debt And Capital Lease Obligation")
        goodwill   = val(b, "Goodwill")
        intang     = val(b, "Other Intangible Assets", "Goodwill And Other Intangible Assets") - goodwill
        intang     = max(intang, 0)
        equity     = val(b, "Stockholders Equity", "Total Equity Gross Minority Interest") or 1
        cur_assets = val(b, "Current Assets")
        cur_liab   = val(b, "Current Liabilities")
        ppe        = val(b, "Net PPE")
        total_assets = val(b, "Total Assets") or 1

        # Capital investido
        nwc             = (cur_assets - cash_total) - (cur_liab - total_debt)
        invested_cap    = nwc + ppe + goodwill + intang
        invested_cap_ex = invested_cap - goodwill

        # Tax rate efetivo
        eff_tax = max(0.0, min((tax_exp / ebt) if ebt else 0.21, 0.5))

        # NOPAT
        nopat = ebit * (1 - eff_tax)

        # WACC
        debt_r = total_debt / (total_debt + equity) if (total_debt + equity) else 0
        eq_r   = 1 - debt_r
        kd     = (abs(interest) / total_debt) if total_debt else 0
        wacc   = eq_r * 0.10 + debt_r * kd * (1 - eff_tax)

        # ROIC
        roic       = nopat / invested_cap    if invested_cap    else 0
        roic_ex_gw = nopat / invested_cap_ex if invested_cap_ex else 0

        # Economic Profit (EVA)
        econ_profit = nopat - wacc * invested_cap

        # FCF e OCF ajustados por SBC
        fcf_sbc = ocf - abs(capex) - sbc
        ocf_sbc = ocf - sbc

        # Cash retornado
        divs_paid   = abs(dividends)
        repurch_abs = abs(repurchase)
        cash_ret    = divs_paid + repurch_abs

        def ps(v):
            return v / shares if shares else 0

        # Formata data como string YYYY-MM-DD
        date_str = str(date)[:10]

        row = {
            "date":   date_str,
            "shares": shares,

            # Per share
            "cash_ps":          ps(cash_total),
            "debt_lease_ps":    ps(total_debt),
            "revenue_ps":       ps(revenue),
            "ebit_ps":          ps(ebit),
            "nopat_ps":         ps(nopat),
            "net_income_ps":    ps(net_income),
            "ocf_sbc_ps":       ps(ocf_sbc),
            "fcf_sbc_ps":       ps(fcf_sbc),
            "dividend_ps":      ps(divs_paid),
            "repurchase_ps":    ps(repurch_abs),
            "cash_returned_ps": ps(cash_ret),
            "econ_profit_ps":   ps(econ_profit),
            "invested_cap_ps":  ps(invested_cap_ex),

            # Absolutos
            "revenue_abs":           revenue,
            "ebit_abs":              ebit,
            "nopat_abs":             nopat,
            "ocf_sbc_abs":           ocf_sbc,
            "fcf_sbc_abs":           fcf_sbc,
            "econ_profit_abs":       econ_profit,
            "invested_cap_abs":      invested_cap,
            "invested_cap_ex_gw_abs":invested_cap_ex,
            "cash_abs":              cash_total,
            "total_debt_abs":        total_debt,
            "equity_abs":            equity,
            "goodwill_abs":          goodwill,
            "total_assets_abs":      total_assets,
            "net_debt":              total_debt - cash_total,

            # Ratios
            "roic":       roic,
            "roic_ex_gw": roic_ex_gw,
            "wacc":       wacc,
            "eff_tax":    eff_tax,
            "ebitda":     ebit + da,
            "capex_rev":  abs(capex) / revenue if revenue else 0,
            "opex_rev":   (revenue - ebit - da) / revenue if revenue else 0,
            "debt_cap":   debt_r,
            "equity_cap": eq_r,
            "net_debt_fcf": ((total_debt - cash_total) / fcf_sbc) if fcf_sbc else 0,
            "roiic_1y":   None,

            # CAGRs (calculados depois)
            "_ebit_cagr": None, "_fcf_cagr":  None,
            "_ep_cagr":   None, "_div_cagr":  None, "_rev_cagr": None,
        }
        rows.append(row)

    # ROIIC (1 ano = 4 trimestres)
    for idx in range(len(rows)):
        if idx >= 4:
            d_nopat = rows[idx]["nopat_abs"] - rows[idx-4]["nopat_abs"]
            d_ic    = rows[idx]["invested_cap_abs"] - rows[idx-4]["invested_cap_abs"]
            rows[idx]["roiic_1y"] = d_nopat / d_ic if d_ic else None

    # CAGRs por métrica
    for field, out in [
        ("ebit_ps", "_ebit_cagr"), ("fcf_sbc_ps", "_fcf_cagr"),
        ("econ_profit_ps", "_ep_cagr"), ("dividend_ps", "_div_cagr"),
        ("revenue_ps", "_rev_cagr"),
    ]:
        for idx in range(len(rows)):
            for yrs in [10, 5, 3]:
                lb = yrs * 4
                if idx >= lb:
                    v0 = rows[idx - lb][field]
                    v1 = rows[idx][field]
                    if v0 and v1 and v0 > 0 and v1 > 0:
                        rows[idx][out] = (v1 / v0) ** (1 / yrs) - 1
                        break

    return rows


def compute_valuation(rows, price, treasury_yield=0.0428):
    if not rows:
        return {}
    last  = rows[-1]
    y_pct = treasury_yield * 100

    def pct(v):  return (v or 0) * 100
    def graham(eps, g_pct):
        if not eps or eps <= 0 or y_pct <= 0: return None
        return eps * (8.5 + 2 * g_pct) * (4.4 / y_pct)
    def ms(iv, px):
        if not iv or iv <= 0: return None
        return (iv - px) / iv

    g_ebit = graham(last["ebit_ps"],        pct(last.get("_ebit_cagr")))
    g_fcf  = graham(last["fcf_sbc_ps"],     pct(last.get("_fcf_cagr")))
    g_ep   = graham(last["econ_profit_ps"], pct(last.get("_ep_cagr")))
    g_div  = graham(last["dividend_ps"],    pct(last.get("_div_cagr")))

    ms_ebit = ms(g_ebit, price)
    ms_fcf  = ms(g_fcf,  price)
    ms_ep   = ms(g_ep,   price)
    ms_div  = ms(g_div,  price)

    valid  = [v for v in [ms_fcf, ms_ep, ms_div] if v is not None]
    avg_ms = sum(valid) / len(valid) if valid else None
    mktcap = price * last["shares"]
    ev     = mktcap + last["total_debt_abs"] - last["cash_abs"]

    return {
        "price": price, "treasury_yield": treasury_yield,
        "cash_ps": last["cash_ps"], "debt_ps": last["debt_lease_ps"],
        "cash_excess_ps": max(last["cash_ps"] - last["debt_lease_ps"], 0),

        "ebit_ps": last["ebit_ps"],         "ebit_cagr":  last.get("_ebit_cagr"),
        "graham_ebit": g_ebit,              "ms_ebit":    ms_ebit,
        "fcf_ps":  last["fcf_sbc_ps"],      "fcf_cagr":   last.get("_fcf_cagr"),
        "graham_fcf": g_fcf,                "ms_fcf":     ms_fcf,
        "ep_ps":   last["econ_profit_ps"],  "ep_cagr":    last.get("_ep_cagr"),
        "graham_ep": g_ep,                  "ms_ep":      ms_ep,
        "div_ps":  last["dividend_ps"],     "div_cagr":   last.get("_div_cagr"),
        "graham_div": g_div,                "ms_div":     ms_div,

        "avg_ms":  avg_ms,
        "ev_ebit": ev / last["ebit_abs"] if last["ebit_abs"] else None,
        "ev": ev, "mktcap": mktcap,
        "ebit_yield": last["ebit_abs"] / ev        if ev      else None,
        "fcf_yield":  last["fcf_sbc_abs"] / mktcap if mktcap  else None,
        "ep_yield":   last["econ_profit_abs"] / mktcap if mktcap else None,
        "div_yield":  last["dividend_ps"] / price  if price   else None,
        "tir":        last["ebit_abs"] / ev        if ev      else None,
        "roic_last":   last["roic"],
        "wacc_last":   last["wacc"],
        "econ_spread": last["roic"] - last["wacc"],
    }


def fetch_treasury_yield():
    try:
        import yfinance as yf
        t = yf.Ticker("^TNX")
        hist = t.history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1]) / 100
    except Exception:
        pass
    return 0.0428


def analyze_ticker(ticker):
    ticker   = ticker.upper().strip()
    profile  = fetch_company_profile(ticker)
    rows     = fetch_quarterly_financials(ticker, quarters=45)
    price    = profile.get("price") or 0
    treasury = fetch_treasury_yield()
    val      = compute_valuation(rows, price, treasury)
    return {
        "ticker":      ticker,
        "name":        profile.get("companyName", ticker),
        "sector":      profile.get("sector", ""),
        "industry":    profile.get("industry", ""),
        "price":       price,
        "currency":    profile.get("currency", "USD"),
        "exchange":    profile.get("exchangeShortName", ""),
        "description": profile.get("description", ""),
        "rows":        rows,
        "valuation":   val,
        "quarters":    [r["date"] for r in rows],
    }
