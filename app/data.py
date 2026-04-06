import os
import requests
import math
from functools import lru_cache

FMP_BASE = "https://financialmodelingprep.com/api/v3"
API_KEY = os.environ.get("FMP_API_KEY", "")


def _get(endpoint, params=None):
    if params is None:
        params = {}
    params["apikey"] = API_KEY
    r = requests.get(f"{FMP_BASE}/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_company_profile(ticker):
    data = _get(f"profile/{ticker}")
    return data[0] if data else {}


def fetch_quarterly_financials(ticker, quarters=45):
    """Fetch income statement, balance sheet, cash flow — quarterly, TTM-style."""
    inc = _get(f"income-statement/{ticker}", {"period": "quarter", "limit": quarters})
    bs  = _get(f"balance-sheet-statement/{ticker}", {"period": "quarter", "limit": quarters})
    cf  = _get(f"cash-flow-statement/{ticker}", {"period": "quarter", "limit": quarters})
    km  = _get(f"key-metrics/{ticker}", {"period": "quarter", "limit": quarters})
    rat = _get(f"ratios/{ticker}", {"period": "quarter", "limit": quarters})

    # Align all by date
    def to_dict(lst):
        return {item["date"]: item for item in lst} if lst else {}

    inc_d = to_dict(inc)
    bs_d  = to_dict(bs)
    cf_d  = to_dict(cf)
    km_d  = to_dict(km)
    rat_d = to_dict(rat)

    dates = sorted(inc_d.keys())[-quarters:]

    rows = []
    for date in dates:
        i = inc_d.get(date, {})
        b = bs_d.get(date, {})
        c = cf_d.get(date, {})
        k = km_d.get(date, {})
        r = rat_d.get(date, {})

        shares = i.get("weightedAverageShsOut", 1) or 1
        price  = k.get("stockPrice") or r.get("priceToBookRatio", 0)

        # --- Raw financials (absolute) ---
        revenue    = _ttm(inc_d, dates, date, "revenue")
        ebit       = _ttm(inc_d, dates, date, "operatingIncome")
        net_income = _ttm(inc_d, dates, date, "netIncome")
        sbc        = _ttm(inc_d, dates, date, "stockBasedCompensation") or 0
        ocf        = _ttm(cf_d,  dates, date, "operatingCashFlow")
        capex      = _ttm(cf_d,  dates, date, "capitalExpenditure")  # negative
        dividends  = _ttm(cf_d,  dates, date, "dividendsPaid") or 0  # negative
        repurchase = _ttm(cf_d,  dates, date, "commonStockRepurchased") or 0
        da         = _ttm(inc_d, dates, date, "depreciationAndAmortization") or 0
        interest   = _ttm(inc_d, dates, date, "interestExpense") or 0
        tax_exp    = _ttm(inc_d, dates, date, "incomeTaxExpense") or 0
        ebt        = _ttm(inc_d, dates, date, "incomeBeforeTax") or 1

        cash       = b.get("cashAndShortTermInvestments") or b.get("cash") or 0
        total_debt = b.get("totalDebt") or 0
        lease      = b.get("totalLiabilitiesAndStockholdersEquity", 0) - b.get("totalLiabilities", 0) - b.get("totalStockholdersEquity", 0)
        goodwill   = b.get("goodwill") or 0
        equity     = b.get("totalStockholdersEquity") or 1
        total_assets = b.get("totalAssets") or 1

        # Invested Capital
        nwc = (b.get("totalCurrentAssets", 0) - cash) - (b.get("totalCurrentLiabilities", 0) - total_debt)
        pp_e = b.get("propertyPlantEquipmentNet") or 0
        intangibles = b.get("intangibleAssets") or 0
        invested_capital = nwc + pp_e + goodwill + intangibles
        invested_capital_ex_gw = invested_capital - goodwill

        # Tax rate
        eff_tax = tax_exp / ebt if ebt else 0.21
        eff_tax = max(0, min(eff_tax, 0.5))

        # NOPAT
        nopat = ebit * (1 - eff_tax)

        # WACC components
        debt_ratio   = total_debt / (total_debt + equity) if (total_debt + equity) else 0
        equity_ratio = 1 - debt_ratio
        interest_rate = interest / total_debt if total_debt else 0
        cost_of_equity = 0.10  # assumed
        wacc = equity_ratio * cost_of_equity + debt_ratio * interest_rate * (1 - eff_tax)

        # ROIC
        roic = nopat / invested_capital if invested_capital else 0
        roic_ex_gw = nopat / invested_capital_ex_gw if invested_capital_ex_gw else 0

        # Economic Profit
        econ_profit = nopat - wacc * invested_capital

        # FCF - SBC
        fcf_sbc = ocf - abs(capex) - sbc if ocf else 0

        # OCF - SBC
        ocf_sbc = ocf - sbc if ocf else 0

        # Cash returned
        divs_paid   = abs(dividends)
        repurch_paid = abs(repurchase)
        cash_returned = divs_paid + repurch_paid

        # Per-share metrics
        def ps(val): return val / shares if shares else 0

        row = {
            "date": date,
            "period": i.get("period", ""),
            "shares": shares,
            "price": price,

            # Per share
            "cash_ps":         ps(cash),
            "debt_lease_ps":   ps(total_debt),
            "revenue_ps":      ps(revenue),
            "ebit_ps":         ps(ebit),
            "nopat_ps":        ps(nopat),
            "net_income_ps":   ps(net_income),
            "ocf_sbc_ps":      ps(ocf_sbc),
            "fcf_sbc_ps":      ps(fcf_sbc),
            "dividend_ps":     ps(divs_paid),
            "repurchase_ps":   ps(repurch_paid),
            "cash_returned_ps":ps(cash_returned),
            "econ_profit_ps":  ps(econ_profit),
            "invested_cap_ps": ps(invested_capital_ex_gw),

            # Absolute
            "revenue_abs":     revenue,
            "ebit_abs":        ebit,
            "nopat_abs":       nopat,
            "ocf_sbc_abs":     ocf_sbc,
            "fcf_sbc_abs":     fcf_sbc,
            "net_debt":        total_debt - cash,
            "econ_profit_abs": econ_profit,
            "invested_cap_abs":invested_capital,
            "invested_cap_ex_gw_abs": invested_capital_ex_gw,

            # Balance sheet
            "cash_abs":        cash,
            "total_debt_abs":  total_debt,
            "equity_abs":      equity,
            "goodwill_abs":    goodwill,
            "total_assets_abs":total_assets,

            # Ratios
            "roic":        roic,
            "roic_ex_gw":  roic_ex_gw,
            "wacc":        wacc,
            "eff_tax":     eff_tax,
            "capex_rev":   abs(capex) / revenue if revenue else 0,
            "opex_rev":    (revenue - ebit - da) / revenue if revenue else 0,
            "ebitda":      ebit + da,
            "debt_cap":    debt_ratio,
            "equity_cap":  equity_ratio,
            "net_debt_fcf":((total_debt - cash) / fcf_sbc) if fcf_sbc else 0,

            # For growth calc
            "_ebit_raw":        ebit,
            "_fcf_raw":         fcf_sbc,
            "_econ_profit_raw": econ_profit,
            "_dividend_raw":    divs_paid,
            "_revenue_raw":     revenue,
        }
        rows.append(row)

    # Compute growth rates (CAGR per-share over available window)
    _add_growth_rates(rows, "ebit_ps",       "_ebit_cagr")
    _add_growth_rates(rows, "fcf_sbc_ps",    "_fcf_cagr")
    _add_growth_rates(rows, "econ_profit_ps","_ep_cagr")
    _add_growth_rates(rows, "dividend_ps",   "_div_cagr")
    _add_growth_rates(rows, "revenue_ps",    "_rev_cagr")

    # ROIIC
    _add_roiic(rows)

    return rows


def _ttm(data_dict, all_dates, current_date, field):
    """Sum last 4 quarters of a field as of current_date (TTM)."""
    idx = all_dates.index(current_date) if current_date in all_dates else -1
    if idx < 3:
        # Not enough quarters yet — use what we have
        window = all_dates[max(0, idx-3): idx+1]
    else:
        window = all_dates[idx-3: idx+1]
    total = 0
    for d in window:
        total += data_dict.get(d, {}).get(field) or 0
    return total


def _cagr(v_start, v_end, years):
    if not v_start or not v_end or years <= 0:
        return None
    if v_start < 0 or v_end < 0:
        return None
    try:
        return (v_end / v_start) ** (1 / years) - 1
    except Exception:
        return None


def _add_growth_rates(rows, field, out_field):
    """Annualised CAGR from 10 years back (40 quarters) to current."""
    n = len(rows)
    for i, row in enumerate(rows):
        # Try 10yr, 5yr, 3yr windows
        for yrs in [10, 5, 3]:
            lookback = yrs * 4
            if i >= lookback:
                v0 = rows[i - lookback][field]
                v1 = row[field]
                rate = _cagr(v0, v1, yrs)
                if rate is not None:
                    row[out_field] = rate
                    break
        else:
            row[out_field] = None


def _add_roiic(rows):
    """Incremental ROIC: ΔNOPAT / ΔInvested Capital over 1-year window."""
    for i, row in enumerate(rows):
        if i >= 4:
            prev = rows[i - 4]
            d_nopat = row["nopat_abs"] - prev["nopat_abs"]
            d_ic    = row["invested_cap_abs"] - prev["invested_cap_abs"]
            row["roiic_1y"] = d_nopat / d_ic if d_ic else None
        else:
            row["roiic_1y"] = None


def compute_valuation(rows, price, treasury_yield=0.0428):
    """
    Graham-based valuation using the last available quarter's TTM metrics.
    MS = (Graham - Price) / Graham
    """
    if not rows:
        return {}

    last = rows[-1]

    # 10-year CAGRs (as percentages for Graham formula)
    def pct(v): return (v or 0) * 100

    ebit_cagr_pct  = pct(last.get("_ebit_cagr"))
    fcf_cagr_pct   = pct(last.get("_fcf_cagr"))
    ep_cagr_pct    = pct(last.get("_ep_cagr"))
    div_cagr_pct   = pct(last.get("_div_cagr"))

    ebit_ps  = last["ebit_ps"]
    fcf_ps   = last["fcf_sbc_ps"]
    ep_ps    = last["econ_profit_ps"]
    div_ps   = last["dividend_ps"]

    cash_ps  = last["cash_ps"]
    debt_ps  = last["debt_lease_ps"]
    cash_excess_ps = max(cash_ps - debt_ps, 0)
    price_ex_cash  = max(price - cash_excess_ps, price * 0.01)

    y_pct = treasury_yield * 100  # e.g. 4.28

    def graham(eps, g_pct):
        """Benjamin Graham formula: V = EPS × (8.5 + 2g) × 4.4 / Y"""
        if not eps or eps <= 0:
            return None
        return eps * (8.5 + 2 * g_pct) * (4.4 / y_pct)

    def ms(intrinsic, px):
        """Margin of Safety = (Intrinsic - Price) / Intrinsic"""
        if not intrinsic or intrinsic <= 0:
            return None
        return (intrinsic - px) / intrinsic

    g_ebit  = graham(ebit_ps, ebit_cagr_pct)
    g_fcf   = graham(fcf_ps,  fcf_cagr_pct)
    g_ep    = graham(ep_ps,   ep_cagr_pct)
    g_div   = graham(div_ps,  div_cagr_pct)

    ms_ebit = ms(g_ebit, price)
    ms_fcf  = ms(g_fcf,  price)
    ms_ep   = ms(g_ep,   price)
    ms_div  = ms(g_div,  price)

    # Combined: average of non-None margins + cash excess bonus
    valid_ms = [v for v in [ms_fcf, ms_ep, ms_div] if v is not None]
    avg_ms = sum(valid_ms) / len(valid_ms) if valid_ms else None

    # EV / EBIT multiple
    mktcap   = price * last["shares"]
    ev       = mktcap + last["total_debt_abs"] - last["cash_abs"]
    ev_ebit  = ev / last["ebit_abs"] if last["ebit_abs"] else None

    # Yield metrics
    ebit_yield      = last["ebit_abs"] / ev if ev else None
    fcf_yield       = last["fcf_sbc_abs"] / mktcap if mktcap else None
    ep_yield        = last["econ_profit_abs"] / mktcap if mktcap else None
    div_yield       = last["dividend_ps"] / price if price else None

    # TIR proxy (EBIT yield on EV)
    tir = ebit_yield

    return {
        "price": price,
        "treasury_yield": treasury_yield,
        "cash_ps": cash_ps,
        "debt_ps": debt_ps,
        "cash_excess_ps": cash_excess_ps,
        "price_ex_cash": price_ex_cash,

        "ebit_ps": ebit_ps,
        "ebit_cagr": last.get("_ebit_cagr"),
        "graham_ebit": g_ebit,
        "ms_ebit": ms_ebit,

        "fcf_ps": fcf_ps,
        "fcf_cagr": last.get("_fcf_cagr"),
        "graham_fcf": g_fcf,
        "ms_fcf": ms_fcf,

        "ep_ps": ep_ps,
        "ep_cagr": last.get("_ep_cagr"),
        "graham_ep": g_ep,
        "ms_ep": ms_ep,

        "div_ps": div_ps,
        "div_cagr": last.get("_div_cagr"),
        "graham_div": g_div,
        "ms_div": ms_div,

        "avg_ms": avg_ms,
        "ev_ebit": ev_ebit,
        "ev": ev,
        "mktcap": mktcap,
        "ebit_yield": ebit_yield,
        "fcf_yield": fcf_yield,
        "ep_yield": ep_yield,
        "div_yield": div_yield,
        "tir": tir,

        "roic_last": last["roic"],
        "wacc_last": last["wacc"],
        "econ_spread": last["roic"] - last["wacc"],
    }


def fetch_treasury_yield():
    """Fetch 10-year US Treasury yield from FMP."""
    try:
        data = _get("treasury", {"from": "2025-01-01"})
        if data:
            latest = data[0]
            return latest.get("year10", 0.0428) / 100
    except Exception:
        pass
    return 0.0428  # fallback


def analyze_ticker(ticker):
    ticker = ticker.upper().strip()
    profile = fetch_company_profile(ticker)
    rows = fetch_quarterly_financials(ticker, quarters=45)

    price = profile.get("price") or (rows[-1]["price"] if rows else 0)
    treasury = fetch_treasury_yield()
    valuation = compute_valuation(rows, price, treasury)

    return {
        "ticker": ticker,
        "name": profile.get("companyName", ticker),
        "sector": profile.get("sector", ""),
        "industry": profile.get("industry", ""),
        "price": price,
        "currency": profile.get("currency", "USD"),
        "exchange": profile.get("exchangeShortName", ""),
        "description": profile.get("description", "")[:300],
        "rows": rows,
        "valuation": valuation,
        "quarters": [r["date"] for r in rows],
    }
