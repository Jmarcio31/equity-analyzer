import os
import time
import requests
import pandas as pd

AV_BASE      = "https://www.alphavantage.co/query"
AV_KEY       = os.environ.get("AV_API_KEY", "")
_LAST_CALL   = 0.0      # timestamp da última chamada
_CACHE       = {}       # cache em memória: (function, symbol) -> data
_CACHE_TTL   = 3600     # 1 hora

def _get(function, symbol, **kwargs):
    global _LAST_CALL, _CACHE
    cache_key = (function, symbol)

    # Retorna do cache se disponível e fresco
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if time.time() - ts < _CACHE_TTL:
            return data

    # Respeita 1 req/segundo do plano gratuito
    elapsed = time.time() - _LAST_CALL
    if elapsed < 1.2:
        time.sleep(1.2 - elapsed)
    _LAST_CALL = time.time()

    params = {"function": function, "symbol": symbol, "apikey": AV_KEY}
    params.update(kwargs)
    r = requests.get(AV_BASE, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "Information" in data or "Note" in data:
        raise ValueError(data.get("Information") or data.get("Note"))

    _CACHE[cache_key] = (time.time(), data)
    return data

def _f(d, *keys):
    """Pega valor float de um dict por múltiplas chaves alternativas."""
    for k in keys:
        v = d.get(k)
        if v and v != "None":
            try:
                return float(v)
            except Exception:
                pass
    return 0.0


def fetch_company_profile(ticker):
    try:
        data  = _get("GLOBAL_QUOTE", ticker)
        quote = data.get("Global Quote", {})
        price = _f(quote, "05. price")

        info  = _get("OVERVIEW", ticker)
        return {
            "companyName": info.get("Name", ticker),
            "price":       price,
            "sector":      info.get("Sector", ""),
            "industry":    info.get("Industry", ""),
            "currency":    "USD",
            "exchangeShortName": info.get("Exchange", ""),
            "description": (info.get("Description") or "")[:300],
            "sharesOutstanding": _f(info, "SharesOutstanding"),
        }
    except Exception:
        return {"companyName": ticker, "price": 0, "sector": "", "industry": "",
                "currency": "USD", "exchangeShortName": "", "description": "", "sharesOutstanding": 0}


def fetch_quarterly_financials(ticker, quarters=20):
    quarters = min(quarters, 20)
    inc_data = _get("INCOME_STATEMENT",  ticker)
    bs_data  = _get("BALANCE_SHEET",     ticker)
    cf_data  = _get("CASH_FLOW",         ticker)

    inc_q = inc_data.get("quarterlyReports", [])
    bs_q  = bs_data.get("quarterlyReports",  [])
    cf_q  = cf_data.get("quarterlyReports",  [])

    # Indexar por data
    def to_dict(lst):
        return {item["fiscalDateEnding"]: item for item in lst}

    inc_d = to_dict(inc_q)
    bs_d  = to_dict(bs_q)
    cf_d  = to_dict(cf_q)

    # Datas comuns ordenadas do mais antigo ao mais recente
    dates = sorted(set(inc_d.keys()) & set(bs_d.keys()) & set(cf_d.keys()))
    dates = dates[-quarters:]

    # Shares fallback — tenta do primeiro balanço disponível
    shares_ref = 1
    if bs_q:
        shares_ref = _f(bs_q[0], "commonStockSharesOutstanding") or 1

    rows = []
    for date in dates:
        i = inc_d[date]
        b = bs_d[date]
        c = cf_d[date]

        shares = _f(b, "commonStockSharesOutstanding") or shares_ref

        # TTM — soma os 4 trimestres disponíveis até esta data
        def ttm(*keys):
            idx    = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            total  = 0.0
            for d in window:
                src = inc_d.get(d) or cf_d.get(d) or {}
                for k in keys:
                    v = src.get(k)
                    if v and v != "None":
                        try:
                            total += float(v)
                            break
                        except Exception:
                            pass
            return total

        def ttm_cf(*keys):
            idx    = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            total  = 0.0
            for d in window:
                src = cf_d.get(d, {})
                for k in keys:
                    v = src.get(k)
                    if v and v != "None":
                        try:
                            total += float(v)
                            break
                        except Exception:
                            pass
            return total

        def ttm_inc(*keys):
            idx    = dates.index(date)
            window = dates[max(0, idx-3): idx+1]
            total  = 0.0
            for d in window:
                src = inc_d.get(d, {})
                for k in keys:
                    v = src.get(k)
                    if v and v != "None":
                        try:
                            total += float(v)
                            break
                        except Exception:
                            pass
            return total

        revenue    = ttm_inc("totalRevenue")
        ebit       = ttm_inc("operatingIncome", "ebit")
        net_income = ttm_inc("netIncome")
        sbc        = ttm_inc("stockBasedCompensation") or 0
        da         = ttm_inc("depreciationAndAmortization") or 0
        interest   = ttm_inc("interestExpense") or 0
        tax_exp    = ttm_inc("incomeTaxExpense") or 0
        ebt        = ttm_inc("incomeBeforeIncomeTaxes", "ebitBeforeInterestAndTaxes") or 1

        ocf        = ttm_cf("operatingCashflow")
        capex      = ttm_cf("capitalExpenditures")
        dividends  = ttm_cf("dividendPayout", "dividendPayoutCommonStock") or 0
        repurchase = ttm_cf("paymentsForRepurchaseOfCommonStock") or 0

        # Balanço (ponto)
        cash_total = _f(b, "cashAndShortTermInvestments", "cashAndCashEquivalentsAtCarryingValue")
        total_debt = _f(b, "shortLongTermDebtTotal", "longTermDebt")
        goodwill   = _f(b, "goodwill")
        intang     = max(_f(b, "intangibleAssetsExcludingGoodwill", "intangibleAssets") - goodwill, 0)
        equity     = _f(b, "totalShareholderEquity") or 1
        cur_assets = _f(b, "totalCurrentAssets")
        cur_liab   = _f(b, "totalCurrentLiabilities")
        ppe        = _f(b, "propertyPlantEquipment")
        tot_assets = _f(b, "totalAssets") or 1

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
            "date":  date,
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

    # ROIIC
    for i in range(len(rows)):
        if i >= 4:
            dn = rows[i]["nopat_abs"] - rows[i-4]["nopat_abs"]
            di = rows[i]["invested_cap_abs"] - rows[i-4]["invested_cap_abs"]
            rows[i]["roiic_1y"] = dn / di if di else None

    # CAGRs
    for field, out in [
        ("ebit_ps","_ebit_cagr"), ("fcf_sbc_ps","_fcf_cagr"),
        ("econ_profit_ps","_ep_cagr"), ("dividend_ps","_div_cagr"),
        ("revenue_ps","_rev_cagr"),
    ]:
        for i in range(len(rows)):
            for yrs in [5, 3]:
                lb = yrs * 4
                if i >= lb:
                    v0 = rows[i-lb][field]
                    v1 = rows[i][field]
                    if v0 and v1 and v0 > 0 and v1 > 0:
                        rows[i][out] = (v1/v0)**(1/yrs) - 1
                        break

    return rows


def fetch_price_history(ticker, start_date):
    """Busca preço histórico diário via Alpha Vantage."""
    try:
        data   = _get("TIME_SERIES_DAILY_ADJUSTED", ticker, outputsize="full")
        series = data.get("Time Series (Daily)", {})
        result = []
        for date, vals in sorted(series.items()):
            if date >= start_date:
                result.append({
                    "date":  date,
                    "close": float(vals.get("5. adjusted close", vals.get("4. close", 0)))
                })
        return result
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
        data = _get("TREASURY_YIELD", "", interval="monthly", maturity="10year")
        pts  = data.get("data", [])
        if pts:
            return float(pts[0]["value"]) / 100
    except Exception:
        pass
    return 0.0428


def analyze_ticker(ticker):
    ticker   = ticker.upper().strip()
    profile  = fetch_company_profile(ticker)
    rows     = fetch_quarterly_financials(ticker, quarters=20)
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
