# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE TICKERS
# Para adicionar uma nova ação: basta inserir um novo dicionário na lista.
# O resto do sistema se adapta automaticamente.
# ─────────────────────────────────────────────────────────────────────────────

TICKERS = [
    # Technology
    {"symbol": "AAPL",  "name": "Apple Inc.",          "sector": "Technology"},
    {"symbol": "MSFT",  "name": "Microsoft",            "sector": "Technology"},
    {"symbol": "NVDA",  "name": "NVIDIA",               "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.",        "sector": "Technology"},
    {"symbol": "META",  "name": "Meta Platforms",       "sector": "Technology"},
    {"symbol": "ASML",  "name": "ASML Holding",         "sector": "Technology"},
    # Consumer
    {"symbol": "AMZN",  "name": "Amazon",               "sector": "Consumer"},
    {"symbol": "TSLA",  "name": "Tesla",                "sector": "Consumer"},
    {"symbol": "WMT",   "name": "Walmart",              "sector": "Consumer"},
    {"symbol": "NFLX",  "name": "Netflix",              "sector": "Consumer"},
    {"symbol": "MELI",  "name": "MercadoLibre",         "sector": "Consumer"},
    {"symbol": "ABEV",  "name": "Ambev",                "sector": "Consumer"},
    {"symbol": "JBS",   "name": "JBS S.A.",             "sector": "Consumer"},
    # Financial
    {"symbol": "JPM",   "name": "JPMorgan Chase",       "sector": "Financial"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway B", "sector": "Financial"},
    {"symbol": "V",     "name": "Visa",                 "sector": "Financial"},
    {"symbol": "ITUB",  "name": "Itaú Unibanco",        "sector": "Financial"},
    {"symbol": "NU",    "name": "Nubank",               "sector": "Financial"},
    {"symbol": "BBD",   "name": "Bradesco",             "sector": "Financial"},
    {"symbol": "BDORY", "name": "Banco do Brasil",      "sector": "Financial"},
    # Healthcare
    {"symbol": "JNJ",   "name": "Johnson & Johnson",    "sector": "Healthcare"},
    {"symbol": "LLY",   "name": "Eli Lilly",            "sector": "Healthcare"},
    # Energy
    {"symbol": "XOM",   "name": "Exxon Mobil",          "sector": "Energy"},
    {"symbol": "PBR",   "name": "Petrobras",            "sector": "Energy"},
    {"symbol": "AXIA",  "name": "Eletrobrás (AXIA)",   "sector": "Energy"},
    # Materials
    {"symbol": "VALE",  "name": "Vale S.A.",            "sector": "Materials"},
    {"symbol": "SUZ",   "name": "Suzano S.A.",          "sector": "Materials"},
]

SYMBOLS = [t["symbol"] for t in TICKERS]

# Instituições financeiras — usam motor analítico separado (ROE/P·TBV/NIM)
# Visa (V) é excluída propositalmente: empresa de tecnologia de pagamentos,
# sem captação de depósitos ou risco de crédito → analisada como não-financeira
FINANCIAL_TICKERS = {"JPM", "BRK-B", "ITUB", "NU", "BBD", "BDORY"}

# Cores por setor (usadas na UI)
SECTOR_COLORS = {
    "Technology": "#4f7cff",
    "Consumer":   "#22c55e",
    "Financial":  "#f59e0b",
    "Healthcare": "#a78bfa",
    "Energy":     "#f87171",
    "Materials":  "#2dd4bf",
}
