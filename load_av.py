"""
Carga via Alpha Vantage — 12 tickers (brasileiros + BRK-B).
25 req/dia — carrega 4 tickers por execução.

Uso:
  python load_av.py            # carrega próximos 4 pendentes
  python load_av.py --reload   # recarrega todos (4 por dia)
  python load_av.py MELI       # ticker específico
"""
import sys, time, json, requests, psycopg2
from datetime import date

AV_KEY       = "DZHRZQ6SWSMUBW4J"
AV_BASE      = "https://www.alphavantage.co/query"
DATABASE_URL = "postgresql://equity_analyzer_db_hx38_user:YUfgSMUWH6OuWEacmiXSwTyPx5ow163n@dpg-d7aghkua2pns73dg3rd0-a.ohio-postgres.render.com/equity_analyzer_db_hx38"
MAX_PER_DAY  = 4   # 4 tickers × 5 req = 20 req (margem de segurança)

TICKERS = [
    # Americanos grandes
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
    {"symbol": "JPM",   "name": "JPMorgan Chase"},
    {"symbol": "V",     "name": "Visa"},
    {"symbol": "XOM",   "name": "Exxon Mobil"},
    {"symbol": "UNH",   "name": "UnitedHealth"},
    {"symbol": "JNJ",   "name": "Johnson & Johnson"},
    {"symbol": "LLY",   "name": "Eli Lilly"},
    # Brasileiros e outros
    {"symbol": "MELI",  "name": "MercadoLibre"},
    {"symbol": "ABEV",  "name": "Ambev"},
    {"symbol": "JBS",   "name": "JBS S.A."},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway B"},
    {"symbol": "ITUB",  "name": "Itaú Unibanco"},
    {"symbol": "NU",    "name": "Nubank"},
    {"symbol": "BBD",   "name": "Bradesco"},
    {"symbol": "BDORY", "name": "Banco do Brasil"},
    {"symbol": "AXIA",  "name": "Eletrobrás"},
    {"symbol": "PBR",   "name": "Petrobras"},
    {"symbol": "VALE",  "name": "Vale S.A."},
    {"symbol": "SUZ",   "name": "Suzano S.A."},
]

_last = 0.0
_reqs = 0

def get(fn, sym, **kw):
    global _last, _reqs
    e = time.time()-_last
    if e < 15: time.sleep(15-e)
    _last=time.time(); _reqs+=1
    p={"function":fn,"symbol":sym,"apikey":AV_KEY}; p.update(kw)
    r=requests.get(AV_BASE,params=p,timeout=30); r.raise_for_status()
    d=r.json()
    if "Information" in d or "Note" in d:
        raise ValueError(d.get("Information") or d.get("Note"))
    return d

def fv(v):
    try:
        if v not in (None,"None",""): return float(v)
    except: pass
    return 0.0

def build_rows(inc_raw, bs_raw, cf_raw, quarters=20):
    def conv_inc(r):
        return {**r,"date":r["fiscalDateEnding"],
                "revenue":r.get("totalRevenue"),
                "operatingIncome":r.get("operatingIncome"),
                "netIncome":r.get("netIncome"),
                "stockBasedCompensation":r.get("stockBasedCompensation"),
                "depreciationAndAmortization":r.get("depreciationAndAmortization"),
                "interestExpense":r.get("interestExpense"),
                "incomeTaxExpense":r.get("incomeTaxExpense"),
                "incomeBeforeTax":r.get("incomeBeforeIncomeTaxes")}
    def conv_bs(r):
        return {**r,"date":r["fiscalDateEnding"],
                "cashAndShortTermInvestments":r.get("cashAndShortTermInvestments") or r.get("cashAndCashEquivalentsAtCarryingValue"),
                "longTermInvestments":r.get("longTermInvestments"),
                "totalDebt":r.get("shortLongTermDebtTotal") or r.get("longTermDebt"),
                "goodwill":r.get("goodwill"),
                "intangibleAssets":r.get("intangibleAssetsExcludingGoodwill"),
                "totalStockholdersEquity":r.get("totalShareholderEquity"),
                "totalCurrentAssets":r.get("totalCurrentAssets"),
                "totalCurrentLiabilities":r.get("totalCurrentLiabilities"),
                "propertyPlantEquipmentNet":r.get("propertyPlantEquipment"),
                "totalAssets":r.get("totalAssets"),
                "commonStock":r.get("commonStockSharesOutstanding")}
    def conv_cf(r):
        return {**r,"date":r["fiscalDateEnding"],
                "operatingCashFlow":r.get("operatingCashflow"),
                "capitalExpenditure":r.get("capitalExpenditures"),
                "dividendsPaid":r.get("dividendPayout") or r.get("dividendPayoutCommonStock"),
                "commonStockRepurchased":r.get("paymentsForRepurchaseOfCommonStock")}
    inc=[conv_inc(r) for r in inc_raw]
    bs=[conv_bs(r) for r in bs_raw]
    cf=[conv_cf(r) for r in cf_raw]
    def td(lst): return {x["date"]:x for x in lst}
    id2,bd,cd=td(inc),td(bs),td(cf)
    dates=sorted(set(id2)&set(bd)&set(cd))[-quarters:]
    if not dates: return []
    sr=fv(bs[0].get("commonStock")) if bs else 1
    rows=[]
    for ds in dates:
        b=bd[ds]; sh=fv(b.get("commonStock")) or sr
        def ti(*ks):
            w=dates[max(0,dates.index(ds)-3):dates.index(ds)+1]
            t=0.0
            for d in w:
                s=id2.get(d,{})
                for k in ks:
                    v=s.get(k)
                    if v not in (None,"None",""):
                        try: t+=float(v); break
                        except: pass
            return t
        def tc(*ks):
            w=dates[max(0,dates.index(ds)-3):dates.index(ds)+1]
            t=0.0
            for d in w:
                s=cd.get(d,{})
                for k in ks:
                    v=s.get(k)
                    if v not in (None,"None",""):
                        try: t+=float(v); break
                        except: pass
            return t
        rev=ti("revenue","operatingIncome".replace("operatingIncome","revenue"))
        rev=ti("revenue"); ebit=ti("operatingIncome"); ni=ti("netIncome")
        sbc=ti("stockBasedCompensation") or 0; da=ti("depreciationAndAmortization") or 0
        intr=ti("interestExpense") or 0; tax=ti("incomeTaxExpense") or 0
        ebt=ti("incomeBeforeTax") or 1
        ocf=tc("operatingCashFlow"); cap=tc("capitalExpenditure")
        div=tc("dividendsPaid") or 0; rep=tc("commonStockRepurchased") or 0
        cst=fv(b.get("cashAndShortTermInvestments")); clt=fv(b.get("longTermInvestments"))
        cash=cst+clt; debt=fv(b.get("totalDebt")); gw=fv(b.get("goodwill"))
        ia=max(fv(b.get("intangibleAssets"))-gw,0)
        eq=fv(b.get("totalStockholdersEquity")) or 1
        ca=fv(b.get("totalCurrentAssets")); cl=fv(b.get("totalCurrentLiabilities"))
        ppe=fv(b.get("propertyPlantEquipmentNet")); ta=fv(b.get("totalAssets")) or 1
        nwc=(ca-cash)-(cl-debt); ic=nwc+ppe+gw+ia; icx=ic-gw
        rt=max(0.05,min(tax/ebt if ebt>0 else 0.21,0.30))
        np2=ebit*(1-rt); dr=debt/(debt+abs(eq)) if (debt+abs(eq)) else 0; er=1-dr
        kd=abs(intr)/debt if debt else 0; wacc=er*0.10+dr*kd*(1-rt)
        roic=np2/ic if ic and abs(ic)>1e6 else 0
        rx=np2/icx if icx and icx>1e6 else None
        ep=np2-wacc*icx if icx and icx>1e6 else None
        fcf=ocf-abs(cap)-sbc; os2=ocf-sbc; dp=abs(div); ra=abs(rep)
        def ps(v): return v/sh if sh else 0
        row={"date":ds,"shares":sh,
             "cash_ps":ps(cash),"debt_lease_ps":ps(debt),
             "revenue_ps":ps(rev),"ebit_ps":ps(ebit),
             "nopat_ps":ps(np2),"net_income_ps":ps(ni),
             "ocf_sbc_ps":ps(os2),"fcf_sbc_ps":ps(fcf),
             "dividend_ps":ps(dp),"repurchase_ps":ps(ra),
             "cash_returned_ps":ps(dp+ra),"econ_profit_ps":ps(ep),
             "invested_cap_ps":ps(icx) if icx and icx>1e6 else None,
             "revenue_abs":rev,"ebit_abs":ebit,"nopat_abs":np2,
             "ocf_sbc_abs":os2,"fcf_sbc_abs":fcf,"econ_profit_abs":ep,
             "invested_cap_abs":ic,"invested_cap_ex_gw_abs":icx,
             "cash_abs":cash,"total_debt_abs":debt,"equity_abs":eq,
             "goodwill_abs":gw,"total_assets_abs":ta,"net_debt":debt-cash,
             "roic":roic,"roic_ex_gw":rx,"wacc":wacc,"eff_tax":rt,
             "ebitda":ebit+da,"capex_rev":abs(cap)/rev if rev else 0,
             "opex_rev":(rev-ebit-da)/rev if rev else 0,
             "debt_cap":dr,"equity_cap":er,
             "net_debt_fcf":(debt-cash)/fcf if fcf else 0,
             "roiic_1y":None,
             "_ebit_cagr":None,"_fcf_cagr":None,
             "_ep_cagr":None,"_div_cagr":None,"_rev_cagr":None}
        rows.append(row)
    for i in range(len(rows)):
        if i>=4:
            dn=rows[i]["nopat_abs"]-rows[i-4]["nopat_abs"]
            di=rows[i]["invested_cap_abs"]-rows[i-4]["invested_cap_abs"]
            rows[i]["roiic_1y"]=dn/di if di else None
    for f2,o in [("ebit_ps","_ebit_cagr"),("fcf_sbc_ps","_fcf_cagr"),
                 ("econ_profit_ps","_ep_cagr"),("dividend_ps","_div_cagr"),
                 ("revenue_ps","_rev_cagr")]:
        for i in range(len(rows)):
            for y in [5,3]:
                lb=y*4
                if i>=lb:
                    v0,v1=rows[i-lb][f2],rows[i][f2]
                    if v0 and v1 and v0>0 and v1>0:
                        rows[i][o]=(v1/v0)**(1/y)-1; break
    return rows

def conn(): return psycopg2.connect(DATABASE_URL,sslmode="require")
def init(c):
    with c.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS financials(id SERIAL PRIMARY KEY,symbol VARCHAR(10),
            period_date DATE,data JSONB,updated_at TIMESTAMP DEFAULT NOW(),UNIQUE(symbol,period_date));
            CREATE TABLE IF NOT EXISTS prices(id SERIAL PRIMARY KEY,symbol VARCHAR(10),
            price_date DATE,close NUMERIC(12,4),updated_at TIMESTAMP DEFAULT NOW(),UNIQUE(symbol,price_date));
            CREATE TABLE IF NOT EXISTS price_history(id SERIAL PRIMARY KEY,symbol VARCHAR(10),
            price_date DATE,close NUMERIC(12,4),UNIQUE(symbol,price_date));
            CREATE TABLE IF NOT EXISTS update_log(id SERIAL PRIMARY KEY,symbol VARCHAR(10),
            update_type VARCHAR(20),updated_at TIMESTAMP DEFAULT NOW(),
            status VARCHAR(20) DEFAULT 'ok',message TEXT,UNIQUE(symbol,update_type));
        """)
    c.commit()
def loaded(c,s):
    with c.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM financials WHERE symbol=%s",(s,)); return cur.fetchone()[0]>0

def latest_quarter(c,s):
    """Retorna a data do trimestre mais recente no banco para um ticker."""
    with c.cursor() as cur:
        cur.execute(
            "SELECT MAX(period_date) FROM financials WHERE symbol=%s",(s,))
        row = cur.fetchone()
    return str(row[0]) if row and row[0] else None

def has_new_quarter(c, s, days_threshold=95):
    """
    Verifica se provavelmente há trimestre novo disponível,
    baseado na data do último trimestre no banco.
    NÃO faz requisições à API — zero custo.

    Lógica: trimestres são divulgados ~45-60 dias após o fim do período.
    Se o último trimestre no banco tem mais de 95 dias, provavelmente
    já há um novo disponível.
    """
    from datetime import datetime, date
    latest = latest_quarter(c, s)
    if not latest:
        return True  # sem dados — precisa carregar
    try:
        latest_date = datetime.strptime(latest[:10], "%Y-%m-%d").date()
        days_since = (date.today() - latest_date).days
        return days_since >= days_threshold
    except Exception:
        return True  # em caso de erro, melhor tentar
def clear(c,s):
    with c.cursor() as cur:
        for t in ["financials","prices","price_history","update_log"]:
            cur.execute(f"DELETE FROM {t} WHERE symbol=%s",(s,))
    c.commit()
def save_fin(c,s,rows):
    with c.cursor() as cur:
        for r in rows:
            cur.execute("INSERT INTO financials(symbol,period_date,data) VALUES(%s,%s,%s) "
                       "ON CONFLICT(symbol,period_date) DO UPDATE SET data=EXCLUDED.data,updated_at=NOW()",
                       (s,r["date"],json.dumps(r)))
    c.commit()
def save_px(c,s,p):
    if not p: return
    with c.cursor() as cur:
        cur.execute("INSERT INTO prices(symbol,price_date,close) VALUES(%s,%s,%s) "
                   "ON CONFLICT(symbol,price_date) DO UPDATE SET close=EXCLUDED.close,updated_at=NOW()",
                   (s,date.today(),p)); c.commit()
def save_hist(c,s,h):
    with c.cursor() as cur:
        for x in h:
            cur.execute("INSERT INTO price_history(symbol,price_date,close) VALUES(%s,%s,%s) "
                       "ON CONFLICT(symbol,price_date) DO NOTHING",(s,x["date"],x["close"]))
    c.commit()
def update_prices(c, batch=None):
    """
    Atualiza cotações de todos os tickers em lotes.
    Usa GLOBAL_QUOTE — 1 req por ticker.

    batch=None  → atualiza todos (até 25 por dia)
    batch=1     → tickers 1-20 (seg/qua/sex)
    batch=2     → tickers 21-28 (ter/qui)

    Com 28 tickers e limite de 25 req/dia:
    - Batch 1 (20 tickers): 20 req — seg, qua, sex
    - Batch 2 (8 tickers):  8 req  — ter, qui
    - Total semanal: todos os 28 tickers atualizados 2-3x
    """
    from datetime import date
    print("="*50)
    print("  ATUALIZAÇÃO DE COTAÇÕES")
    print("="*50)

    if batch == 1:
        targets = TICKERS[:20]
        print(f"  Lote 1/2: tickers 1-20")
    elif batch == 2:
        targets = TICKERS[20:]
        print(f"  Lote 2/2: tickers 21-{len(TICKERS)}")
    else:
        targets = TICKERS[:25]
        print(f"  Lote único: primeiros 25 tickers")

    ok = fail = 0
    for t in targets:
        s = t["symbol"]
        if not loaded(c, s):
            print(f"  {s}: sem dados — pulando")
            continue
        try:
            q = get("GLOBAL_QUOTE", s)
            p = fv(q.get("Global Quote", {}).get("05. price"))
            if p > 0:
                save_px(c, s, p)
                log(c, s, "price")
                print(f"  {s}: ${p:.2f} ✓")
                ok += 1
            else:
                print(f"  {s}: preço indisponível")
        except Exception as e:
            print(f"  {s}: ❌ {e}")
            fail += 1

    print(f"\n  Cotações: {ok} ok | {fail} erros")

def log(c,s,t,st="ok",msg=None):
    with c.cursor() as cur:
        cur.execute("INSERT INTO update_log(symbol,update_type,status,message) VALUES(%s,%s,%s,%s) "
                   "ON CONFLICT(symbol,update_type) DO UPDATE SET updated_at=NOW(),"
                   "status=EXCLUDED.status,message=EXCLUDED.message",(s,t,st,msg))
    c.commit()

def load_one(c,sym,name,reload=False):
    print(f"\n[{sym}] {name}")
    try:
        q=get("GLOBAL_QUOTE",sym)
        p=fv(q.get("Global Quote",{}).get("05. price"))
        save_px(c,sym,p); log(c,sym,"price")
        print(f"  cotação ${p:.2f} ✓",end="",flush=True)
        inc_d=get("INCOME_STATEMENT",sym)
        inc=inc_d.get("quarterlyReports",[])
        print(f" | DRE {len(inc)}q ✓",end="",flush=True)
        bs_d=get("BALANCE_SHEET",sym)
        bs=bs_d.get("quarterlyReports",[])
        print(f" | BS ✓",end="",flush=True)
        cf_d=get("CASH_FLOW",sym)
        cf=cf_d.get("quarterlyReports",[])
        print(f" | CF ✓",flush=True)
        rows=build_rows(inc,bs,cf)
        if not rows: raise ValueError("0 trimestres")
        if reload: clear(c,sym)
        save_fin(c,sym,rows); log(c,sym,"quarterly")
        print(f"  → {len(rows)} trimestres salvos ✓")
        try:
            hd=get("TIME_SERIES_MONTHLY_ADJUSTED",sym)
            hist=[{"date":d,"close":float(v.get("5. adjusted close",0))}
                  for d,v in sorted(hd.get("Monthly Adjusted Time Series",{}).items())]
            if hist: save_hist(c,sym,hist); print(f"  → {len(hist)} preços históricos ✓")
        except: pass
        return True
    except Exception as e:
        print(f"\n  ❌ {e}")
        log(c,sym,"quarterly","error",str(e))
        return False

def main():
    reload_mode  = "--reload" in sys.argv
    update_mode  = "--update" in sys.argv
    prices_mode  = "--prices" in sys.argv
    single = next((a.upper() for a in sys.argv[1:] if not a.startswith("--")),None)
    print("="*50)
    print("  CARGA / ATUALIZAÇÃO AV (25 req/dia)")
    print("="*50)
    if prices_mode:  print("  Modo: PRICES (somente cotações)")
    if update_mode:  print("  Modo: UPDATE (verifica trimestres novos)")
    if reload_mode:  print("  Modo: RELOAD (recarrega tudo)")
    c=conn(); init(c)
    if single:
        todo=[t for t in TICKERS if t["symbol"]==single]
        if not todo: print(f"❌ {single} não encontrado"); return
    elif reload_mode:
        todo=TICKERS
    elif update_mode:
        # Verifica quais tickers têm trimestre novo disponível
        # Usa 1 req por ticker para checar — depois 4 req para carregar
        print("\nVerificando trimestres pendentes (por data, sem req à API)...")
        todo=[]
        for t in TICKERS:
            if not loaded(c,t["symbol"]):
                print(f"  {t['symbol']}: sem dados — adicionado")
                todo.append(t)
            elif has_new_quarter(c,t["symbol"]):
                lq = latest_quarter(c,t["symbol"])
                from datetime import date, datetime
                lq_date = datetime.strptime(lq[:10], "%Y-%m-%d").date() if lq else None
                days = (date.today() - lq_date).days if lq_date else 0
                print(f"  {t['symbol']}: último trimestre {lq} ({days} dias) — atualizando")
                todo.append(t)
            else:
                lq = latest_quarter(c,t["symbol"])
                from datetime import date, datetime
                lq_date = datetime.strptime(lq[:10], "%Y-%m-%d").date() if lq else None
                days = (date.today() - lq_date).days if lq_date else 0
                print(f"  {t['symbol']}: atualizado ({lq}, {days} dias) ✓")
    else:
        todo=[t for t in TICKERS if not loaded(c,t["symbol"])]
    ln=sum(1 for t in TICKERS if loaded(c,t["symbol"]))
    print(f"Status: {ln}/{len(TICKERS)} carregados | Pendentes: {len(todo)}")
    if not single: todo=todo[:MAX_PER_DAY]
    print(f"Hoje: {', '.join(t['symbol'] for t in todo)}")
    print(f"Req: {len(todo)*5} de 25 disponíveis")
    if not todo: print("🎉 Todos carregados!"); c.close(); return
    print("\nIniciando em 3s... (Ctrl+C cancela)"); time.sleep(3)
    ok=fail=0
    for t in todo:
        if load_one(c,t["symbol"],t["name"],reload=reload_mode): ok+=1
        else: fail+=1
    ln2=sum(1 for t in TICKERS if loaded(c,t["symbol"]))
    print(f"\n{'='*50}")
    print(f"  Sucesso:{ok} | Falhas:{fail} | Banco AV:{ln2}/{len(TICKERS)} | Reqs:{_reqs}")
    if ln2<len(TICKERS): print(f"  Execute novamente amanhã para os restantes")
    print(f"{'='*50}")
    c.close()

if __name__=="__main__": main()
