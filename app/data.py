import os
import time
import requests

AV_BASE = "https://www.alphavantage.co/query"
AV_KEY  = os.environ.get("AV_API_KEY", "")

_LAST_CALL = 0.0

def _get(function, symbol, **kwargs):
    global _LAST_CALL
    elapsed = time.time() - _LAST_CALL
    if elapsed < 1.5:
        time.sleep(1.5 - elapsed)
    _LAST_CALL = time.time()
    params = {"function": function, "symbol": symbol, "apikey": AV_KEY}
    params.update(kwargs)
    r = requests.get(AV_BASE, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "Information" in data or "Note" in data:
        raise ValueError(data.get("Information") or data.get("Note"))
    return data

def _f(d, *keys):
    for k in keys:
        v = d.get(k)
        if v and v != "None":
            try:
                return float(v)
            except Exception:
                pass
    return 0.0

def fetch_current_price(symbol):
    data  = _get("GLOBAL_QUOTE", symbol)
    quote = data.get("Global Quote", {})
    return _f(quote, "05. price")

def fetch_overview(symbol):
    return _get("OVERVIEW", symbol)

def fetch_income_statement(symbol):
    return _get("INCOME_STATEMENT", symbol)

def fetch_balance_sheet(symbol):
    return _get("BALANCE_SHEET", symbol)

def fetch_cash_flow(symbol):
    return _get("CASH_FLOW", symbol)

def fetch_price_history(symbol):
    data   = _get("TIME_SERIES_MONTHLY_ADJUSTED", symbol)
    series = data.get("Monthly Adjusted Time Series", {})
    return [
        {"date": d, "close": float(v.get("5. adjusted close", 0))}
        for d, v in sorted(series.items())
    ]


def build_rows_from_statements(inc_data, bs_data, cf_data, quarters=20):
    """
    Monta rows trimestrais a partir dos statements.

    Correcoes (sincronizadas com load_av.py):
    - P3: sem max(invested_cap_ex, 1) — IC negativo retorna None
    - P5: intang nao subtrai goodwill duas vezes
    - P6: calcula _eps_cagr explicitamente
    - BUG2: try/except nos CAGRs
    - ROIIC: protegido contra nopat_abs None
    """
    inc_q = inc_data.get("quarterlyReports", [])
    bs_q  = bs_data.get("quarterlyReports",  [])
    cf_q  = cf_data.get("quarterlyReports",  [])

    def to_dict(lst):
        return {item["fiscalDateEnding"]: item for item in lst}

    inc_d = to_dict(inc_q)
    bs_d  = to_dict(bs_q)
    cf_d  = to_dict(cf_q)

    dates = sorted(set(inc_d.keys()) & set(bs_d.keys()) & set(cf_d.keys()))
    dates = dates[-quarters:]
    shares_ref = _f(bs_q[0], "commonStockSharesOutstanding") if bs_q else 1

    rows = []
    for date in dates:
        b = bs_d[date]
        shares = _f(b, "commonStockSharesOutstanding") or shares_ref

        def ttm_inc(*keys):
            idx = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            total = 0.0
            for d in window:
                src = inc_d.get(d, {})
                for k in keys:
                    v = src.get(k)
                    if v and v != "None":
                        try: total += float(v); break
                        except: pass
            return total

        def ttm_cf(*keys):
            idx = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            total = 0.0
            for d in window:
                src = cf_d.get(d, {})
                for k in keys:
                    v = src.get(k)
                    if v and v != "None":
                        try: total += float(v); break
                        except: pass
            return total

        revenue    = ttm_inc("totalRevenue")
        ebit       = ttm_inc("operatingIncome", "ebit")
        net_income = ttm_inc("netIncome")
        sbc        = ttm_inc("stockBasedCompensation") or 0
        da         = ttm_inc("depreciationAndAmortization") or 0
        interest   = ttm_inc("interestExpense") or 0
        tax_exp    = ttm_inc("incomeTaxExpense") or 0
        ebt_val    = ttm_inc("incomeBeforeIncomeTaxes") or 1

        ocf        = ttm_cf("operatingCashflow")
        capex      = ttm_cf("capitalExpenditures")
        dividends  = ttm_cf("dividendPayout", "dividendPayoutCommonStock") or 0
        repurchase = ttm_cf("paymentsForRepurchaseOfCommonStock") or 0

        cash_st    = _f(b, "cashAndShortTermInvestments", "cashAndCashEquivalentsAtCarryingValue")
        cash_lt    = _f(b, "longTermInvestments")
        cash_total = cash_st + cash_lt
        total_debt = _f(b, "shortLongTermDebtTotal", "longTermDebt")
        goodwill   = _f(b, "goodwill")
        # P5: campo ja exclui goodwill — nao subtrair novamente
        intang     = _f(b, "intangibleAssetsExcludingGoodwill")
        equity     = _f(b, "totalShareholderEquity") or 1
        cur_assets = _f(b, "totalCurrentAssets")
        cur_liab   = _f(b, "totalCurrentLiabilities")
        ppe        = _f(b, "propertyPlantEquipment")
        tot_assets = _f(b, "totalAssets") or 1

        nwc          = (cur_assets - cash_total) - (cur_liab - total_debt)
        invested_cap = nwc + ppe + goodwill + intang
        icx          = invested_cap - goodwill   # ex-goodwill

        raw_tax = tax_exp / ebt_val if (ebt_val and ebt_val > 0) else 0.21
        eff_tax = max(0.05, min(raw_tax, 0.30))
        nopat   = ebit * (1 - eff_tax)
        debt_r  = total_debt / (total_debt + abs(equity)) if (total_debt + abs(equity)) else 0
        eq_r    = 1 - debt_r
        kd      = abs(interest) / total_debt if total_debt else 0
        wacc    = eq_r * 0.10 + debt_r * kd * (1 - eff_tax)

        # P3: sem max(...,1) — None quando IC insignificante
        roic       = nopat / invested_cap if invested_cap and abs(invested_cap) > 1e6 else 0
        roic_ex_gw = nopat / icx          if icx and icx > 1e6 else None
        econ_profit= nopat - wacc * icx   if icx and icx > 1e6 else None

        fcf_sbc    = ocf - abs(capex) - sbc
        ocf_sbc    = ocf - sbc
        divs_paid  = abs(dividends)
        repurch_abs= abs(repurchase)
        cash_ret   = divs_paid + repurch_abs

        def ps(v):
            return (v / shares if shares else 0) if v is not None else None

        row = {
            "date": date, "shares": shares,
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
            "invested_cap_ps":  ps(icx) if icx and icx > 1e6 else None,
            "revenue_abs":             revenue,
            "ebit_abs":                ebit,
            "nopat_abs":               nopat,
            "ocf_sbc_abs":             ocf_sbc,
            "fcf_sbc_abs":             fcf_sbc,
            "econ_profit_abs":         econ_profit,
            "invested_cap_abs":        invested_cap if invested_cap and abs(invested_cap) > 1e6 else None,
            "invested_cap_ex_gw_abs":  icx if icx and icx > 1e6 else None,
            "cash_abs":                cash_total,
            "total_debt_abs":          total_debt,
            "equity_abs":              equity,
            "goodwill_abs":            goodwill,
            "total_assets_abs":        tot_assets,
            "net_debt":                total_debt - cash_total,
            "roic":         roic,
            "roic_ex_gw":   roic_ex_gw,
            "wacc":         wacc,
            "eff_tax":      eff_tax,
            "ebitda":       ebit + da,
            "capex_rev":    abs(capex) / revenue if revenue else 0,
            "opex_rev":     (revenue - ebit - da) / revenue if revenue else 0,
            "debt_cap":     debt_r,
            "equity_cap":   eq_r,
            "net_debt_fcf": (total_debt - cash_total) / fcf_sbc if fcf_sbc else 0,
            "roiic_1y":  None,
            "_ebit_cagr": None, "_fcf_cagr": None, "_ep_cagr": None,
            "_div_cagr":  None, "_rev_cagr": None, "_eps_cagr": None,
        }
        rows.append(row)

    # ROIIC
    for idx in range(len(rows)):
        if idx >= 4:
            na = rows[idx]["nopat_abs"]
            nb = rows[idx-4]["nopat_abs"]
            ia = rows[idx]["invested_cap_abs"]
            ib = rows[idx-4]["invested_cap_abs"]
            if all(v is not None for v in [na, nb, ia, ib]):
                dn = na - nb
                di = ia - ib
                rows[idx]["roiic_1y"] = dn / di if di else None

    # CAGRs — P6 inclui _eps_cagr; BUG2 protegido com try/except
    cagr_metrics = [
        ("ebit_ps",       "_ebit_cagr"),
        ("fcf_sbc_ps",    "_fcf_cagr"),
        ("econ_profit_ps","_ep_cagr"),
        ("dividend_ps",   "_div_cagr"),
        ("revenue_ps",    "_rev_cagr"),
        ("net_income_ps", "_eps_cagr"),
    ]
    for field, out_key in cagr_metrics:
        for idx in range(len(rows)):
            for yrs in [5, 3]:
                lb = yrs * 4
                if idx < lb:
                    continue
                try:
                    v0 = rows[idx - lb][field]
                    v1 = rows[idx][field]
                    if v0 and v1 and float(v0) > 0 and float(v1) > 0:
                        rows[idx][out_key] = (float(v1) / float(v0)) ** (1 / yrs) - 1
                        break
                except (TypeError, ValueError, ZeroDivisionError):
                    pass

    return rows


def fetch_treasury_yield():
    try:
        data = _get("TREASURY_YIELD", "", interval="monthly", maturity="10year")
        pts  = data.get("data", [])
        if pts:
            return float(pts[0]["value"]) / 100
    except Exception:
        pass
    return 0.0428
