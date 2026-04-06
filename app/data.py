import pandas as pd

# ── Tenta usar curl_cffi (mais resistente a bloqueios) ────────────────────────
try:
    from curl_cffi import requests as curl_requests
    _CURL_SESSION = curl_requests.Session(impersonate="chrome110")
    import yfinance as yf
    _USE_CURL = True
except Exception:
    _USE_CURL = False
    import yfinance as yf

def _ticker(symbol):
    if _USE_CURL:
        return yf.Ticker(symbol, session=_CURL_SESSION)
    return yf.Ticker(symbol)

# ─────────────────────────────────────────────────────────────────────────────

def _safe(df, *keys):
    if df is None or df.empty:
        return None
    for k in keys:
        if k in df.index:
            return df.loc[k]
    return None

def _v(series, date):
    if series is None:
        return 0.0
    try:
        v = series.get(date, 0.0)
        return float(v) if pd.notna(v) else 0.0
    except Exception:
        return 0.0

def _ttm(df, date, dates, *keys):
    series = _safe(df, *keys)
    if series is None:
        return 0.0
    idx = list(dates).index(date)
    window = list(dates)[max(0, idx-3): idx+1]
    total = 0.0
    for d in window:
        try:
            v = series.get(d, 0.0)
            if pd.notna(v):
                total += float(v)
        except Exception:
            pass
    return total


def fetch_company_profile(ticker):
    try:
        t    = _ticker(ticker)
        info = t.info or {}

        price = (info.get("currentPrice")
              or info.get("regularMarketPrice")
              or info.get("previousClose")
              or 0)

        if not price:
            hist = t.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        return {
            "companyName":      info.get("longName") or info.get("shortName", ticker),
            "price":            float(price),
            "sector":           info.get("sector", ""),
            "industry":         info.get("industry", ""),
            "currency":         info.get("currency", "USD"),
            "exchangeShortName":info.get("exchange", ""),
            "description":      (info.get("longBusinessSummary") or "")[:300],
            "sharesOutstanding":info.get("sharesOutstanding") or 0,
        }
    except Exception:
        return {"companyName": ticker, "price": 0, "sector": "", "industry": "",
                "currency": "USD", "exchangeShortName": "", "description": "", "sharesOutstanding": 0}


def fetch_quarterly_financials(ticker, quarters=45):
    t = _ticker(ticker)

    try:
        inc = t.get_income_stmt(freq="quarterly", trailing=False)
    except Exception:
        inc = t.quarterly_income_stmt

    try:
        bs = t.get_balance_sheet(freq="quarterly", trailing=False)
    except Exception:
        bs = t.quarterly_balance_sheet

    try:
        cf = t.get_cash_flow(freq="quarterly", trailing=False)
    except Exception:
        cf = t.quarterly_cashflow

    if inc is None or inc.empty:
        return []

    dates = sorted(inc.columns.tolist())
    if len(dates) > quarters:
        dates = dates[-quarters:]

    info       = t.info or {}
    shares_ref = info.get("sharesOutstanding") or 1

    rows = []
    for date in dates:
        sh_series = _safe(bs, "Ordinary Shares Number", "Share Issued", "Common Stock")
        shares    = _v(sh_series, date) or shares_ref

        revenue    = _ttm(inc, date, dates, "Total Revenue", "Revenue")
        ebit       = _ttm(inc, date, dates, "Operating Income", "EBIT", "Ebit")
        net_income = _ttm(inc, date, dates, "Net Income", "Net Income Common Stockholders")
        sbc        = _ttm(inc, date, dates, "Stock Based Compensation")
        da         = _ttm(inc, date, dates, "Reconciled Depreciation",
                          "Depreciation And Amortization", "Depreciation Amortization Depletion")
        interest   = _ttm(inc, date, dates, "Interest Expense",
                          "Interest Expense Non Operating", "Net Interest Income")
        tax_exp    = _ttm(inc, date, dates, "Tax Provision", "Income Tax Expense")
        ebt        = _ttm(inc, date, dates, "Pretax Income", "Income Before Tax") or 1

        ocf        = _ttm(cf, date, dates, "Operating Cash Flow", "Cash Flow From Operations")
        capex      = _ttm(cf, date, dates, "Capital Expenditure", "Purchase Of PPE", "Capital Expenditures")
        dividends  = _ttm(cf, date, dates, "Common Stock Dividend Paid",
                          "Cash Dividends Paid", "Payment Of Dividends")
        repurchase = _ttm(cf, date, dates, "Repurchase Of Capital Stock",
                          "Common Stock Repurchase", "Purchase Of Business")

        cash_eq    = _v(_safe(bs, "Cash And Cash Equivalents", "Cash"), date)
        cash_st    = _v(_safe(bs, "Cash Cash Equivalents And Short Term Investments",
                               "Other Short Term Investments",
                               "Available For Sale Securities"), date)
        cash_total = max(cash_eq, cash_st)
        total_debt = _v(_safe(bs, "Total Debt", "Long Term Debt And Capital Lease Obligation",
                               "Long Term Debt"), date)
        goodwill   = _v(_safe(bs, "Goodwill"), date)
        intang_raw = _v(_safe(bs, "Goodwill And Other Intangible Assets",
                               "Other Intangible Assets"), date)
        intang     = max(intang_raw - goodwill, 0)
        equity     = _v(_safe(bs, "Stockholders Equity", "Total Equity Gross Minority Interest",
                               "Common Stock Equity"), date) or 1
        cur_assets = _v(_safe(bs, "Current Assets", "Total Current Assets"), date)
        cur_liab   = _v(_safe(bs, "Current Liabilities", "Total Current Liabilities"), date)
        ppe        = _v(_safe(bs, "Net PPE", "Net Property Plant And Equipment"), date)
        tot_assets = _v(_safe(bs, "Total Assets"), date) or 1

        nwc             = (cur_assets - cash_total) - (cur_liab - total_debt)
        invested_cap    = nwc + ppe + goodwill + intang
        invested_cap_ex = max(invested_cap - goodwill, 1)

        eff_tax     = max(0.0, min(tax_exp / ebt if ebt else 0.21, 0.5))
        nopat       = ebit * (1 - eff_tax)
        debt_r      = total_debt / (total_debt + abs(equity)) if (total_debt + abs(equity)) else 0
        eq_r        = 1 - debt_r
        kd          = abs(interest) / total_debt if total_debt else 0
        wacc        = eq_r * 0.10 + debt_r * kd * (1 - eff_tax)
        roic        = nopat / invested_cap    if invested_cap    else 0
        roic_ex_gw  = nopat / invested_cap_ex if invested_cap_ex else 0
        econ_profit = nopat - wacc * invested_cap
        fcf_sbc     = ocf - abs(capex) - sbc
        ocf_sbc     = ocf - sbc
        divs_paid   = abs(dividends)
        repurch_abs = abs(repurchase)
        cash_ret    = divs_paid + repurch_abs

        def ps(v):
            return v / shares if shares else 0

        row = {
            "date":  str(date)[:10],
            "shares": shares,
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
            "revenue_abs":      revenue,
            "ebit_abs":         ebit,
            "nopat_abs":        nopat,
            "ocf_sbc_abs":      ocf_sbc,
            "fcf_sbc_abs":      fcf_sbc,
            "econ_profit_abs":  econ_profit,
            "invested_cap_abs": invested_cap,
            "invested_cap_ex_gw_abs": invested_cap_ex,
            "cash_abs":         cash_total,
            "total_debt_abs":   total_debt,
            "equity_abs":       equity,
            "goodwill_abs":     goodwill,
            "total_assets_abs": tot_assets,
            "net_debt":         total_debt - cash_total,
            "roic":             roic,
            "roic_ex_gw":       roic_ex_gw,
            "wacc":             wacc,
            "eff_tax":          eff_tax,
            "ebitda":           ebit + da,
            "capex_rev":        abs(capex) / revenue if revenue else 0,
            "opex_rev":         (revenue - ebit - da) / revenue if revenue else 0,
            "debt_cap":         debt_r,
            "equity_cap":       eq_r,
            "net_debt_fcf":     (total_debt - cash_total) / fcf_sbc if fcf_sbc else 0,
            "roiic_1y":         None,
            "_ebit_cagr": None, "_fcf_cagr": None,
            "_ep_cagr":   None, "_div_cagr": None, "_rev_cagr": None,
        }
        rows.append(row)

    for i in range(len(rows)):
        if i >= 4:
            dn = rows[i]["nopat_abs"] - rows[i-4]["nopat_abs"]
            di = rows[i]["invested_cap_abs"] - rows[i-4]["invested_cap_abs"]
            rows[i]["roiic_1y"] = dn / di if di else None

    for field, out in [
        ("ebit_ps","_ebit_cagr"), ("fcf_sbc_ps","_fcf_cagr"),
        ("econ_profit_ps","_ep_cagr"), ("dividend_ps","_div_cagr"),
        ("revenue_ps","_rev_cagr"),
    ]:
        for i in range(len(rows)):
            for yrs in [10, 5, 3]:
                lb = yrs * 4
                if i >= lb:
                    v0 = rows[i-lb][field]
                    v1 = rows[i][field]
                    if v0 and v1 and v0 > 0 and v1 > 0:
                        rows[i][out] = (v1/v0)**(1/yrs) - 1
                        break

    return rows


def fetch_price_history(ticker, start_date, end_date=None):
    try:
        t    = _ticker(ticker)
        hist = t.history(start=start_date, end=end_date, interval="1d", auto_adjust=True)
        if hist.empty:
            return []
        return [{"date": str(d)[:10], "close": float(r["Close"])}
                for d, r in hist.iterrows()]
    except Exception:
        return []


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

    g_ebit = graham(last["ebit_ps"],        pct(last.get("_ebit_cagr")))
    g_fcf  = graham(last["fcf_sbc_ps"],     pct(last.get("_fcf_cagr")))
    g_ep   = graham(last["econ_profit_ps"], pct(last.get("_ep_cagr")))
    g_div  = graham(last["dividend_ps"],    pct(last.get("_div_cagr")))

    ms_ebit = ms(g_ebit, price)
    ms_fcf  = ms(g_fcf,  price)
    ms_ep   = ms(g_ep,   price)
    ms_div  = ms(g_div,  price)

    valid  = [v for v in [ms_fcf, ms_ep, ms_div] if v is not None]
    avg_ms = sum(valid)/len(valid) if valid else None
    mktcap = price * last["shares"]
    ev     = mktcap + last["total_debt_abs"] - last["cash_abs"]

    return {
        "price": price, "treasury_yield": treasury_yield,
        "cash_ps": last["cash_ps"], "debt_ps": last["debt_lease_ps"],
        "cash_excess_ps": max(last["cash_ps"] - last["debt_lease_ps"], 0),
        "ebit_ps":   last["ebit_ps"],        "ebit_cagr":  last.get("_ebit_cagr"),
        "graham_ebit": g_ebit,               "ms_ebit":    ms_ebit,
        "fcf_ps":    last["fcf_sbc_ps"],     "fcf_cagr":   last.get("_fcf_cagr"),
        "graham_fcf": g_fcf,                 "ms_fcf":     ms_fcf,
        "ep_ps":     last["econ_profit_ps"], "ep_cagr":    last.get("_ep_cagr"),
        "graham_ep": g_ep,                   "ms_ep":      ms_ep,
        "div_ps":    last["dividend_ps"],    "div_cagr":   last.get("_div_cagr"),
        "graham_div": g_div,                 "ms_div":     ms_div,
        "avg_ms": avg_ms,
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
        t    = _ticker("^TNX")
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
        "ticker":   ticker,
        "name":     profile.get("companyName", ticker),
        "sector":   profile.get("sector", ""),
        "industry": profile.get("industry", ""),
        "price":    price,
        "currency": profile.get("currency", "USD"),
        "exchange": profile.get("exchangeShortName", ""),
        "description": profile.get("description", ""),
        "rows":     rows,
        "valuation":val,
        "quarters": [r["date"] for r in rows],
    }
