"""
load_av.py — Carga de dados via Alpha Vantage
═══════════════════════════════════════════════════════════════════════════════
Limite: 25 req/dia · 4 tickers por execução (5 req cada)

Uso:
  python load_av.py                    # carrega próximos pendentes (até 4)
  python load_av.py --update           # verifica trimestres novos por data
  python load_av.py --prices           # atualiza apenas cotações
  python load_av.py --reload SYMBOL    # recarrega ticker específico
  python load_av.py --reload           # recarrega todos (4 por dia)
"""
import sys, time, json, requests, psycopg2
from datetime import date, datetime

# ─── Configuração ─────────────────────────────────────────────────────────────
# Valores substituídos pelo GitHub Actions via sed antes da execução
AV_KEY       = "DZHRZQ6SWSMUBW4J"
AV_BASE      = "https://www.alphavantage.co/query"
DATABASE_URL = "postgresql://equity_analyzer_db_hx38_user:YUfgSMUWH6OuWEacmiXSwTyPx5ow163n@dpg-d7aghkua2pns73dg3rd0-a.ohio-postgres.render.com/equity_analyzer_db_hx38"
MAX_PER_DAY  = 4   # 4 tickers × 5 req = 20 req (margem de segurança)

# ─── Lista de tickers (sincronizada com config.py) ────────────────────────────
# Remova UNH — já excluído do config.py
TICKERS = [
    {"symbol": "AAPL",  "name": "Apple Inc."},
    {"symbol": "MSFT",  "name": "Microsoft"},
    {"symbol": "NVDA",  "name": "NVIDIA"},
    {"symbol": "GOOGL", "name": "Alphabet Inc."},
    {"symbol": "META",  "name": "Meta Platforms"},
    {"symbol": "ASML",  "name": "ASML Holding"},
    {"symbol": "AMZN",  "name": "Amazon"},
    {"symbol": "TSLA",  "name": "Tesla"},
    {"symbol": "WMT",   "name": "Walmart"},
    {"symbol": "NFLX",  "name": "Netflix"},
    {"symbol": "MELI",  "name": "MercadoLibre"},
    {"symbol": "ABEV",  "name": "Ambev"},
    {"symbol": "JBS",   "name": "JBS S.A."},
    {"symbol": "JPM",   "name": "JPMorgan Chase"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway B"},
    {"symbol": "V",     "name": "Visa"},
    {"symbol": "ITUB",  "name": "Itaú Unibanco"},
    {"symbol": "NU",    "name": "Nubank"},
    {"symbol": "BBD",   "name": "Bradesco"},
    {"symbol": "BDORY", "name": "Banco do Brasil"},
    {"symbol": "JNJ",   "name": "Johnson & Johnson"},
    {"symbol": "LLY",   "name": "Eli Lilly"},
    {"symbol": "XOM",   "name": "Exxon Mobil"},
    {"symbol": "PBR",   "name": "Petrobras"},
    {"symbol": "AXIA",  "name": "Eletrobrás"},
    {"symbol": "VALE",  "name": "Vale S.A."},
    {"symbol": "SUZ",   "name": "Suzano S.A."},
]


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO 1: API Alpha Vantage
# ═══════════════════════════════════════════════════════════════════════════════

_last_req = 0.0
_req_count = 0

def av_get(function, symbol, **kwargs):
    """
    Requisição à API da AV com rate limiting (15s entre chamadas).
    Levanta ValueError se AV retornar mensagem de rate limit.
    """
    global _last_req, _req_count
    elapsed = time.time() - _last_req
    if elapsed < 15:
        time.sleep(15 - elapsed)
    _last_req  = time.time()
    _req_count += 1
    params = {"function": function, "symbol": symbol, "apikey": AV_KEY}
    params.update(kwargs)
    resp = requests.get(AV_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "Information" in data or "Note" in data:
        raise ValueError(data.get("Information") or data.get("Note"))
    return data


def fv(v):
    """Converte valor da AV para float, retornando 0.0 se ausente/inválido."""
    try:
        if v not in (None, "None", ""):
            return float(v)
    except (TypeError, ValueError):
        pass
    return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO 2: Transformação de dados (statements → rows)
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize_income(r):
    return {
        **r,
        "date":                     r["fiscalDateEnding"],
        "revenue":                  r.get("totalRevenue"),
        "operatingIncome":          r.get("operatingIncome"),
        "netIncome":                r.get("netIncome"),
        "stockBasedCompensation":   r.get("stockBasedCompensation"),
        "depreciationAndAmortization": r.get("depreciationAndAmortization"),
        "interestExpense":          r.get("interestExpense"),
        "incomeTaxExpense":         r.get("incomeTaxExpense"),
        "incomeBeforeTax":          r.get("incomeBeforeIncomeTaxes"),
    }

def _normalize_balance(r):
    return {
        **r,
        "date": r["fiscalDateEnding"],
        "cashAndShortTermInvestments": (
            r.get("cashAndShortTermInvestments")
            or r.get("cashAndCashEquivalentsAtCarryingValue")
        ),
        "longTermInvestments":      r.get("longTermInvestments"),
        "totalDebt":                r.get("shortLongTermDebtTotal") or r.get("longTermDebt"),
        "goodwill":                 r.get("goodwill"),
        "intangibleAssets":         r.get("intangibleAssetsExcludingGoodwill"),
        "totalStockholdersEquity":  r.get("totalShareholderEquity"),
        "totalCurrentAssets":       r.get("totalCurrentAssets"),
        "totalCurrentLiabilities":  r.get("totalCurrentLiabilities"),
        "propertyPlantEquipmentNet":r.get("propertyPlantEquipment"),
        "totalAssets":              r.get("totalAssets"),
        "commonStock":              r.get("commonStockSharesOutstanding"),
    }

def _normalize_cashflow(r):
    return {
        **r,
        "date":                  r["fiscalDateEnding"],
        "operatingCashFlow":     r.get("operatingCashflow"),
        "capitalExpenditure":    r.get("capitalExpenditures"),
        "dividendsPaid":         r.get("dividendPayout") or r.get("dividendPayoutCommonStock"),
        "commonStockRepurchased":r.get("paymentsForRepurchaseOfCommonStock"),
    }


def build_rows(inc_raw, bs_raw, cf_raw, quarters=20):
    """
    Constrói lista de trimestres com métricas por ação a partir dos
    demonstrativos brutos da AV (income, balance sheet, cash flow).

    Retorna lista de dicts com todos os campos necessários para calc.py.
    """
    inc = [_normalize_income(r)  for r in inc_raw]
    bs  = [_normalize_balance(r) for r in bs_raw]
    cf  = [_normalize_cashflow(r) for r in cf_raw]

    by_date = lambda lst: {x["date"]: x for x in lst}
    id2, bd, cd = by_date(inc), by_date(bs), by_date(cf)

    # Apenas trimestres presentes nos 3 demonstrativos
    dates = sorted(set(id2) & set(bd) & set(cd))[-quarters:]
    if not dates:
        return []

    # Fallback para ações quando commonStock está ausente no primeiro período
    shares_fallback = fv(bs[0].get("commonStock")) if bs else 1

    rows = []
    for ds in dates:
        b  = bd[ds]
        sh = fv(b.get("commonStock")) or shares_fallback

        def ttm_inc(*keys):
            """Soma TTM de campo do income statement (4 trimestres)."""
            window = dates[max(0, dates.index(ds) - 3): dates.index(ds) + 1]
            total  = 0.0
            for d in window:
                stmt = id2.get(d, {})
                for k in keys:
                    v = stmt.get(k)
                    if v not in (None, "None", ""):
                        try:
                            total += float(v)
                            break
                        except (TypeError, ValueError):
                            pass
            return total

        def ttm_cf(*keys):
            """Soma TTM de campo do cash flow statement (4 trimestres)."""
            window = dates[max(0, dates.index(ds) - 3): dates.index(ds) + 1]
            total  = 0.0
            for d in window:
                stmt = cd.get(d, {})
                for k in keys:
                    v = stmt.get(k)
                    if v not in (None, "None", ""):
                        try:
                            total += float(v)
                            break
                        except (TypeError, ValueError):
                            pass
            return total

        def ps(v):
            """Valor por ação. Retorna None se v for None."""
            return (v / sh if sh else 0) if v is not None else None

        # ── Income Statement (TTM) ────────────────────────────────────────────
        rev  = ttm_inc("revenue")
        ebit = ttm_inc("operatingIncome")
        ni   = ttm_inc("netIncome")
        sbc  = ttm_inc("stockBasedCompensation") or 0
        da   = ttm_inc("depreciationAndAmortization") or 0
        intr = ttm_inc("interestExpense") or 0
        tax  = ttm_inc("incomeTaxExpense") or 0
        ebt  = ttm_inc("incomeBeforeTax") or 1

        # ── Cash Flow (TTM) ───────────────────────────────────────────────────
        ocf  = ttm_cf("operatingCashFlow")
        cap  = ttm_cf("capitalExpenditure")
        div  = ttm_cf("dividendsPaid") or 0
        rep  = ttm_cf("commonStockRepurchased") or 0

        # ── Balance Sheet (ponto único — último trimestre) ────────────────────
        cst   = fv(b.get("cashAndShortTermInvestments"))
        clt   = fv(b.get("longTermInvestments"))
        cash  = cst + clt
        debt  = fv(b.get("totalDebt"))
        gw    = fv(b.get("goodwill"))
        ia    = max(fv(b.get("intangibleAssets")) - gw, 0)
        eq    = fv(b.get("totalStockholdersEquity")) or 1
        ca    = fv(b.get("totalCurrentAssets"))
        cl    = fv(b.get("totalCurrentLiabilities"))
        ppe   = fv(b.get("propertyPlantEquipmentNet"))
        ta    = fv(b.get("totalAssets")) or 1

        # ── Capital Investido ─────────────────────────────────────────────────
        nwc   = (ca - cash) - (cl - debt)
        ic    = nwc + ppe + gw + ia          # com goodwill
        icx   = ic - gw                      # ex-goodwill

        # ── Retornos e WACC ───────────────────────────────────────────────────
        rt    = max(0.05, min(tax / ebt if ebt > 0 else 0.21, 0.30))
        np2   = ebit * (1 - rt)              # NOPAT
        dr    = debt / (debt + abs(eq)) if (debt + abs(eq)) else 0
        er    = 1 - dr
        kd    = abs(intr) / debt if debt else 0
        wacc  = er * 0.10 + dr * kd * (1 - rt)

        # ROIC / ROIC ex-GW — None quando IC insignificante (evita valores absurdos)
        roic  = np2 / ic  if ic  and abs(ic)  > 1e6 else 0
        rx    = np2 / icx if icx and icx      > 1e6 else None
        ep    = np2 - wacc * icx if icx and icx > 1e6 else None

        # ── Fluxo de Caixa ────────────────────────────────────────────────────
        fcf   = ocf - abs(cap) - sbc         # FCF - SBC
        ocf_s = ocf - sbc                    # OCF - SBC
        dp    = abs(div)
        ra    = abs(rep)

        row = {
            "date":   ds,
            "shares": sh,

            # Por ação
            "cash_ps":            ps(cash),
            "debt_lease_ps":      ps(debt),
            "revenue_ps":         ps(rev),
            "ebit_ps":            ps(ebit),
            "nopat_ps":           ps(np2),
            "net_income_ps":      ps(ni),
            "ocf_sbc_ps":         ps(ocf_s),
            "fcf_sbc_ps":         ps(fcf),
            "dividend_ps":        ps(dp),
            "repurchase_ps":      ps(ra),
            "cash_returned_ps":   ps(dp + ra),
            "econ_profit_ps":     ps(ep),
            "invested_cap_ps":    ps(icx) if icx and icx > 1e6 else None,

            # Absolutos
            "revenue_abs":              rev,
            "ebit_abs":                 ebit,
            "nopat_abs":                np2,
            "ocf_sbc_abs":              ocf_s,
            "fcf_sbc_abs":              fcf,
            "econ_profit_abs":          ep,
            "invested_cap_abs":         ic  if (ic  is not None and abs(ic)  > 1e6) else None,
            "invested_cap_ex_gw_abs":   icx if (icx is not None and icx      > 1e6) else None,
            "cash_abs":                 cash,
            "total_debt_abs":           debt,
            "equity_abs":               eq,
            "goodwill_abs":             gw,
            "total_assets_abs":         ta,
            "net_debt":                 debt - cash,

            # Métricas derivadas
            "roic":         roic,
            "roic_ex_gw":   rx,
            "wacc":         wacc,
            "eff_tax":      rt,
            "ebitda":       ebit + da,
            "capex_rev":    abs(cap) / rev if rev else 0,
            "opex_rev":     (rev - ebit - da) / rev if rev else 0,
            "debt_cap":     dr,
            "equity_cap":   er,
            "net_debt_fcf": (debt - cash) / fcf if fcf else 0,

            # Preenchidos em pós-processamento
            "roiic_1y":   None,
            "_ebit_cagr": None,
            "_fcf_cagr":  None,
            "_ep_cagr":   None,
            "_div_cagr":  None,
            "_rev_cagr":  None,
        }
        rows.append(row)

    # ── Pós-processamento: ROIIC e CAGRs ──────────────────────────────────────
    _compute_roiic(rows)
    _compute_cagrs(rows)
    return rows


def _compute_roiic(rows):
    """ROIIC = ΔNopat / ΔIC — variação anual (4 trimestres)."""
    for i in range(len(rows)):
        if i < 4:
            continue
        na  = rows[i]["nopat_abs"]
        nb  = rows[i - 4]["nopat_abs"]
        ia  = rows[i]["invested_cap_abs"]
        ib  = rows[i - 4]["invested_cap_abs"]
        if all(v is not None for v in [na, nb, ia, ib]):
            dn = na - nb
            di = ia - ib
            rows[i]["roiic_1y"] = dn / di if di else None


def _compute_cagrs(rows):
    """
    CAGR por métrica — tenta 5 anos primeiro, fallback para 3 anos.
    Apenas para valores positivos (evita CAGR com sinal trocado).
    """
    metrics = [
        ("ebit_ps",    "_ebit_cagr"),
        ("fcf_sbc_ps", "_fcf_cagr"),
        ("econ_profit_ps", "_ep_cagr"),
        ("dividend_ps",    "_div_cagr"),
        ("revenue_ps",     "_rev_cagr"),
    ]
    for field, cagr_key in metrics:
        for i in range(len(rows)):
            for years in [5, 3]:
                lb = years * 4
                if i < lb:
                    continue
                v0 = rows[i - lb][field]
                v1 = rows[i][field]
                if v0 and v1 and v0 > 0 and v1 > 0:
                    rows[i][cagr_key] = (v1 / v0) ** (1 / years) - 1
                    break


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO 3: Banco de dados
# ═══════════════════════════════════════════════════════════════════════════════

def _conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def _init(c):
    with c.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS financials(
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10),
                period_date DATE,
                data JSONB,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(symbol, period_date)
            );
            CREATE TABLE IF NOT EXISTS prices(
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10),
                price_date DATE,
                close NUMERIC(12,4),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(symbol, price_date)
            );
            CREATE TABLE IF NOT EXISTS price_history(
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10),
                price_date DATE,
                close NUMERIC(12,4),
                UNIQUE(symbol, price_date)
            );
            CREATE TABLE IF NOT EXISTS update_log(
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10),
                update_type VARCHAR(20),
                updated_at TIMESTAMP DEFAULT NOW(),
                status VARCHAR(20) DEFAULT 'ok',
                message TEXT,
                UNIQUE(symbol, update_type)
            );
        """)
    c.commit()

def _log(c, symbol, update_type, status="ok", message=None):
    with c.cursor() as cur:
        cur.execute(
            "INSERT INTO update_log(symbol, update_type, status, message) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT(symbol, update_type) "
            "DO UPDATE SET updated_at=NOW(), status=EXCLUDED.status, message=EXCLUDED.message",
            (symbol, update_type, status, message)
        )
    c.commit()

def _save_price(c, symbol, price):
    if not price:
        return
    with c.cursor() as cur:
        cur.execute(
            "INSERT INTO prices(symbol, price_date, close) VALUES(%s,%s,%s) "
            "ON CONFLICT(symbol, price_date) DO UPDATE SET close=EXCLUDED.close, updated_at=NOW()",
            (symbol, date.today(), price)
        )
    c.commit()

def _save_financials(c, symbol, rows):
    with c.cursor() as cur:
        for r in rows:
            cur.execute(
                "INSERT INTO financials(symbol, period_date, data) VALUES(%s,%s,%s) "
                "ON CONFLICT(symbol, period_date) DO UPDATE SET data=EXCLUDED.data, updated_at=NOW()",
                (symbol, r["date"], json.dumps(r))
            )
    c.commit()

def _save_price_history(c, symbol, history):
    with c.cursor() as cur:
        for x in history:
            cur.execute(
                "INSERT INTO price_history(symbol, price_date, close) VALUES(%s,%s,%s) "
                "ON CONFLICT(symbol, price_date) DO NOTHING",
                (symbol, x["date"], x["close"])
            )
    c.commit()

def _clear(c, symbol):
    """Remove todos os dados de um ticker (usado no --reload)."""
    with c.cursor() as cur:
        for table in ["financials", "prices", "price_history", "update_log"]:
            cur.execute(f"DELETE FROM {table} WHERE symbol=%s", (symbol,))
    c.commit()

def _is_loaded(c, symbol):
    with c.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM financials WHERE symbol=%s", (symbol,)
        )
        return cur.fetchone()[0] > 0

def _latest_quarter(c, symbol):
    """Retorna a data do trimestre mais recente no banco."""
    with c.cursor() as cur:
        cur.execute(
            "SELECT MAX(period_date)::text FROM financials WHERE symbol=%s", (symbol,)
        )
        row = cur.fetchone()
        return row[0] if row else None

def _has_new_quarter(c, symbol, days_threshold=95):
    """True se o último trimestre tem mais de 95 dias (provavelmente há um novo)."""
    latest = _latest_quarter(c, symbol)
    if not latest:
        return True
    try:
        latest_date = datetime.strptime(latest[:10], "%Y-%m-%d").date()
        return (date.today() - latest_date).days >= days_threshold
    except Exception:
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO 4: Operações de carga
# ═══════════════════════════════════════════════════════════════════════════════

def _load_ticker(c, symbol, name, reload=False):
    """
    Carrega todos os dados de um ticker (5 req):
      1. Cotação atual
      2. Income Statement
      3. Balance Sheet
      4. Cash Flow
      5. Histórico de preços mensais
    """
    print(f"\n[{symbol}] {name}")
    try:
        # 1. Cotação
        quote = av_get("GLOBAL_QUOTE", symbol)
        price = fv(quote.get("Global Quote", {}).get("05. price"))
        _save_price(c, symbol, price)
        _log(c, symbol, "price")
        print(f"  cotação ${price:.2f} ✓", end="", flush=True)

        # 2-4. Demonstrativos financeiros
        inc_data = av_get("INCOME_STATEMENT", symbol)
        inc      = inc_data.get("quarterlyReports", [])
        print(f" | DRE {len(inc)}q ✓", end="", flush=True)

        bs_data  = av_get("BALANCE_SHEET", symbol)
        bs       = bs_data.get("quarterlyReports", [])
        print(f" | BS ✓", end="", flush=True)

        cf_data  = av_get("CASH_FLOW", symbol)
        cf       = cf_data.get("quarterlyReports", [])
        print(f" | CF ✓", flush=True)

        rows = build_rows(inc, bs, cf)
        if not rows:
            raise ValueError("0 trimestres calculados")

        # Salva no banco (apaga primeiro se reload)
        if reload:
            _clear(c, symbol)
        _save_financials(c, symbol, rows)
        _log(c, symbol, "quarterly")
        print(f"  → {len(rows)} trimestres salvos ✓")

        # 5. Histórico de preços (opcional — não conta como falha)
        try:
            hist_data = av_get("TIME_SERIES_MONTHLY_ADJUSTED", symbol)
            history   = [
                {"date": d, "close": float(v.get("5. adjusted close", 0))}
                for d, v in sorted(hist_data.get("Monthly Adjusted Time Series", {}).items())
            ]
            if history:
                _save_price_history(c, symbol, history)
                print(f"  → {len(history)} preços históricos ✓")
        except Exception:
            pass  # Histórico é opcional

        return True

    except Exception as e:
        print(f"\n  ❌ {e}")
        _log(c, symbol, "quarterly", "error", str(e))
        return False


def _update_prices(c, batch=None):
    """
    Atualiza cotações em lote (1 req por ticker).

    batch=1  → tickers 1-20 (ter/qui)
    batch=2  → tickers 21-27 (qua/sex)
    batch=None → todos (até 25)
    """
    print("=" * 50)
    print("  ATUALIZAÇÃO DE COTAÇÕES")
    print("=" * 50)

    if batch == 1:
        targets = TICKERS[:20]
        print("  Lote 1/2: tickers 1-20")
    elif batch == 2:
        targets = TICKERS[20:]
        print(f"  Lote 2/2: tickers 21-{len(TICKERS)}")
    else:
        targets = TICKERS[:25]
        print("  Lote único: primeiros 25 tickers")

    ok = fail = 0
    for t in targets:
        symbol = t["symbol"]
        if not _is_loaded(c, symbol):
            print(f"  {symbol}: sem dados fundamentais — pulando")
            continue
        try:
            quote = av_get("GLOBAL_QUOTE", symbol)
            price = fv(quote.get("Global Quote", {}).get("05. price"))
            if price > 0:
                _save_price(c, symbol, price)
                _log(c, symbol, "price")
                print(f"  {symbol}: ${price:.2f} ✓")
                ok += 1
            else:
                print(f"  {symbol}: preço indisponível")
        except Exception as e:
            print(f"  {symbol}: ❌ {e}")
            fail += 1

    print(f"\n  Cotações: {ok} ok | {fail} erros")


# ═══════════════════════════════════════════════════════════════════════════════
# MÓDULO 5: Ponto de entrada (CLI)
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    reload_mode  = "--reload"  in sys.argv
    update_mode  = "--update"  in sys.argv
    prices_mode  = "--prices"  in sys.argv
    single = next((a.upper() for a in sys.argv[1:] if not a.startswith("--")), None)

    print("=" * 50)
    print("  CARGA / ATUALIZAÇÃO AV (25 req/dia)")
    print("=" * 50)
    if prices_mode:  print("  Modo: PRICES (somente cotações)")
    elif update_mode: print("  Modo: UPDATE (verifica trimestres novos)")
    elif reload_mode: print("  Modo: RELOAD (recarrega tudo)")

    c = _conn()
    _init(c)

    # ── Modo prices: só atualiza cotações ────────────────────────────────────
    if prices_mode:
        weekday = date.today().weekday()  # 0=seg … 6=dom
        batch   = 1 if weekday in (1, 3) else 2   # ter/qui → lote1; qua/sex → lote2
        _update_prices(c, batch=batch)
        print(f"\nReqs usadas: {_req_count}")
        c.close()
        return

    # ── Seleciona tickers a carregar ──────────────────────────────────────────
    if single:
        todo = [t for t in TICKERS if t["symbol"] == single]
        if not todo:
            print(f"❌ {single} não encontrado nos tickers configurados")
            c.close()
            return

    elif reload_mode:
        todo = TICKERS

    elif update_mode:
        print("\nVerificando trimestres pendentes (sem req à API)...")
        todo = []
        for t in TICKERS:
            symbol = t["symbol"]
            if not _is_loaded(c, symbol):
                print(f"  {symbol}: sem dados — adicionado")
                todo.append(t)
            elif _has_new_quarter(c, symbol):
                lq   = _latest_quarter(c, symbol)
                days = (date.today() - datetime.strptime(lq[:10], "%Y-%m-%d").date()).days if lq else 0
                print(f"  {symbol}: último trimestre {lq} ({days} dias) — atualizando")
                todo.append(t)
            else:
                lq   = _latest_quarter(c, symbol)
                days = (date.today() - datetime.strptime(lq[:10], "%Y-%m-%d").date()).days if lq else 0
                print(f"  {symbol}: atualizado ({lq}, {days} dias) ✓")

    else:
        todo = [t for t in TICKERS if not _is_loaded(c, t["symbol"])]

    # ── Resumo e confirmação ──────────────────────────────────────────────────
    loaded_count = sum(1 for t in TICKERS if _is_loaded(c, t["symbol"]))
    print(f"\nStatus: {loaded_count}/{len(TICKERS)} carregados | Pendentes: {len(todo)}")

    if not single:
        todo = todo[:MAX_PER_DAY]

    if not todo:
        print("🎉 Todos os tickers estão carregados!")
        c.close()
        return

    print(f"Hoje: {', '.join(t['symbol'] for t in todo)}")
    print(f"Req estimadas: {len(todo) * 5} de 25 disponíveis")
    print("\nIniciando em 3s... (Ctrl+C cancela)")
    time.sleep(3)

    # ── Carga ─────────────────────────────────────────────────────────────────
    ok = fail = 0
    for t in todo:
        if _load_ticker(c, t["symbol"], t["name"], reload=reload_mode):
            ok += 1
        else:
            fail += 1

    loaded_final = sum(1 for t in TICKERS if _is_loaded(c, t["symbol"]))
    print(f"\n{'=' * 50}")
    print(f"  Sucesso: {ok} | Falhas: {fail} | "
          f"Banco: {loaded_final}/{len(TICKERS)} | Reqs: {_req_count}")
    if loaded_final < len(TICKERS):
        print("  Execute novamente amanhã para os restantes")
    print(f"{'=' * 50}")
    c.close()


if __name__ == "__main__":
    main()
