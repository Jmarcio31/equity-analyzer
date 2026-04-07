# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE TICKERS
# Para adicionar uma nova ação: basta inserir um novo dicionário na lista.
# O resto do sistema se adapta automaticamente.
# ─────────────────────────────────────────────────────────────────────────────

TICKERS = [
    # Tecnologia
    {"symbol": "AAPL",  "name": "Apple Inc.",          "sector": "Technology"},
    {"symbol": "MSFT",  "name": "Microsoft",            "sector": "Technology"},
    {"symbol": "NVDA",  "name": "NVIDIA",               "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.",        "sector": "Technology"},
    {"symbol": "META",  "name": "Meta Platforms",       "sector": "Technology"},
    # Consumo / E-commerce
    {"symbol": "AMZN",  "name": "Amazon",               "sector": "Consumer"},
    {"symbol": "TSLA",  "name": "Tesla",                "sector": "Consumer"},
    {"symbol": "WMT",   "name": "Walmart",              "sector": "Consumer"},
    {"symbol": "NFLX",  "name": "Netflix",              "sector": "Consumer"},
    # Financeiro
    {"symbol": "JPM",   "name": "JPMorgan Chase",       "sector": "Financial"},
    {"symbol": "BRK-B", "name": "Berkshire Hathaway B", "sector": "Financial"},
    {"symbol": "V",     "name": "Visa",                 "sector": "Financial"},
    # Saúde
    {"symbol": "UNH",   "name": "UnitedHealth",         "sector": "Healthcare"},
    {"symbol": "JNJ",   "name": "Johnson & Johnson",    "sector": "Healthcare"},
    {"symbol": "LLY",   "name": "Eli Lilly",            "sector": "Healthcare"},
    # Energia
    {"symbol": "XOM",   "name": "Exxon Mobil",          "sector": "Energy"},
    # Industrial
    {"symbol": "CAT",   "name": "Caterpillar",          "sector": "Industrial"},
    {"symbol": "HON",   "name": "Honeywell",            "sector": "Industrial"},
    # Telecom
    {"symbol": "T",     "name": "AT&T",                 "sector": "Telecom"},
    # Semicondutores
    {"symbol": "ASML",  "name": "ASML Holding",         "sector": "Technology"},
]

SYMBOLS = [t["symbol"] for t in TICKERS]

# Cores por setor (usadas na UI)
SECTOR_COLORS = {
    "Technology": "#4f7cff",
    "Consumer":   "#22c55e",
    "Financial":  "#f59e0b",
    "Healthcare": "#a78bfa",
    "Energy":     "#f87171",
    "Industrial": "#94a3b8",
    "Telecom":    "#fb923c",
}
