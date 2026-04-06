import os
import requests

FMP_BASE = "https://financialmodelingprep.com/api/v3"
API_KEY = os.environ.get("FMP_API_KEY", "")


def _get(endpoint, params=None):
    if params is None:
        params = {}
    params["apikey"] = API_KEY
    r = requests.get(f"{FMP_BASE}/{endpoint}", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "Error Message" in data:
        raise ValueError(data["Error Message"])
    return data


def fetch_company_profile(ticker):
    """Usa quote endpoint (free tier) em vez de profile."""
    try:
        data = _get(f"quote/{ticker}")
        if data and isinstance(data, list):
            q = data[0]
            return {
                "companyName":      q.get("name", ticker),
                "price":            q.get("price", 0),
                "sector":           q.get("exchange", ""),
                "industry":         "",
                "currency":         "USD",
                "exchangeShortName":q.get("exchange", ""),
                "description":      "",
            }
    except Exception:
        pass
    return {"companyName": ticker, "price": 0, "sector": "", "industry": "",
            "currency": "USD", "exchangeShortName": "", "description": ""}


def fetch_quarterly_financials(ticker, quarters=45):
    inc = _get(f"income-statement/{ticker}",       {"period": "quarter", "limit": quarters})
    bs  = _get(f"balance-sheet-statement/{ticker}", {"period": "quarter", "limit": quarters})
    cf  = _get(f"cash-flow-statement/{ticker}",    {"period": "quarter", "limit": quarters})

    def to_dict(lst):
        return {item["date"]: item for item in lst} if lst else {}

    inc_d = to_dict(inc)
    bs_d  = to_dict(bs)
    cf_d  = to_dict(cf)
    dates = sorted(inc_d.keys())[-quarters:]

    rows = []
    for date in dates:
        i = inc_d.get(date, {})
        b = bs_d.get(date, {})
        c = cf_d.get(date, {})

        shares = i.get("weightedAverageShsOut") or i.get("weightedAverageShsDil") or 1

        def ttm(d_dict, field):
            idx = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            return sum((d_dict.get(d, {}).get(field) or 0) for d in window)

        revenue    = ttm(inc_d, "revenue")
        ebit       = ttm(inc_d, "operatingIncome")
        net_income = ttm(inc_d, "netIncome")
        sbc        = ttm(inc_d, "stockBasedCompensation")
        da         = ttm(inc_d, "depreciationAndAmortization")
        interest   = ttm(inc_d, "interestExpense")
        tax_exp    = ttm(inc_d, "incomeTaxExpense")
        ebt        = ttm(inc_d, "incomeBeforeTax") or 1
        ocf        = ttm(cf_d,  "operatingCashFlow")
        capex      = ttm(cf_d,  "capitalExpenditure")
        dividends  = ttm(cf_d,  "dividendsPaid") or 0
        repurchase = ttm(cf_d,  "commonStockRepurchased") or 0

        cash       = b.get("cashAndShortTermInvestments") or b.get("cash") or 0
        total_debt = b.get("totalDebt") or 0
        goodwill   = b.get("goodwill") or 0
        intang     = b.get("intangibleAssets") or 0
        equity     = b.get("totalStockholdersEquity") or 1
        cur_assets = b.get("totalCurrentAssets") or 0
        cur_liab   = b.get("totalCurrentLiabilities") or 0
        ppe        = b.get("propertyPlantEquipmentNet") or 0
        total_assets = b.get("totalAssets") or 1

        nwc             = (cur_assets - cash) - (cur_liab - total_debt)
        invested_cap    = nwc + ppe + goodwill + intang
        invested_cap_ex = invested_cap - goodwill

        eff_tax     = max(0, min((tax_exp / ebt) if ebt else 0.21, 0.5))
        nopat       = ebit * (1 - eff_tax)
        debt_r      = total_debt / (total_debt + equity) if (total_debt + equity) else 0
        eq_r        = 1 - debt_r
        kd          = (interest / total_debt) if total_debt else 0
        wacc        = eq_r * 0.10 + debt_r * kd * (1 - eff_tax)
        roic        = nopat / invested_cap    if invested_cap    else 0
        roic_ex_gw  = nopat / invested_cap_ex if invested_cap_ex else 0
        econ_profit = nopat - wacc * invested_cap
        fcf_sbc     = ocf - abs(capex) - sbc
        ocf_sbc     = ocf - sbc
        divs_paid   = abs(dividends)
        repurch_abs = abs(repurchase)
        cash_ret    = divs_paid + repurch_abs

        def ps(val):
            return val / shares if shares else 0

        row = {
            "date": date, "shares": shares,
            "cash_ps":          ps(cash),
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
            "cash_abs":         cash,
            "total_debt_abs":   total_debt,
            "equity_abs":       equity,
            "goodwill_abs":     goodwill,
            "total_assets_abs": total_assets,
            "net_debt":         total_debt - cash,
            "roic":       roic,
            "roic_ex_gw": roic_ex_gw,
            "wacc":       wacc,
            "eff_tax":    eff_tax,
            "ebitda":     ebit + da,
            "capex_rev":  abs(capex) / revenue if revenue else 0,
            "opex_rev":   (revenue - ebit - da) / revenue if revenue else 0,
            "debt_cap":   debt_r,
            "equity_cap": eq_r,
            "net_debt_fcf": ((total_debt - cash) / fcf_sbc) if fcf_sbc else 0,
            "roiic_1y":   None,
            "_ebit_cagr": None, "_fcf_cagr": None,
            "_ep_cagr":   None, "_div_cagr": None, "_rev_cagr": None,
        }
        rows.append(row)

    # ROIIC
    for idx in range(len(rows)):
        if idx >= 4:
            d_nopat = rows[idx]["nopat_abs"] - rows[idx-4]["nopat_abs"]
            d_ic    = rows[idx]["invested_cap_abs"] - rows[idx-4]["invested_cap_abs"]
            rows[idx]["roiic_1y"] = d_nopat / d_ic if d_ic else None

    # CAGRs
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

    valid   = [v for v in [ms_fcf, ms_ep, ms_div] if v is not None]
    avg_ms  = sum(valid) / len(valid) if valid else None
    mktcap  = price * last["shares"]
    ev      = mktcap + last["total_debt_abs"] - last["cash_abs"]

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
        "avg_ms": avg_ms, "ev_ebit": ev / last["ebit_abs"] if last["ebit_abs"] else None,
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
        data = _get("treasury", {"from": "2025-01-01"})
        if data and isinstance(data, list):
            return (data[0].get("year10") or 4.28) / 100
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
        "description": "",
        "rows":     rows,
        "valuation":val,
        "quarters": [r["date"] for r in rows],
    }
