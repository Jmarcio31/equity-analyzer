from flask import Blueprint, render_template, request, jsonify
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import TICKERS, SECTOR_COLORS
from . import database as db
from .calc import compute_valuation
from .data import fetch_current_price, fetch_quarterly_financials, fetch_price_history, fetch_treasury_yield

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html", tickers=TICKERS, sector_colors=SECTOR_COLORS)


@main.route("/api/tickers")
def api_tickers():
    """Retorna lista de tickers disponíveis com status de dados."""
    status_map = {}
    for s in db.get_update_status():
        symbol = s["symbol"]
        if symbol not in status_map:
            status_map[symbol] = {}
        status_map[symbol][s["update_type"]] = {
            "updated_at": s["updated_at"],
            "status": s["status"]
        }
    result = []
    for t in TICKERS:
        sym = t["symbol"]
        result.append({
            **t,
            "color": SECTOR_COLORS.get(t["sector"], "#4f7cff"),
            "has_data": db.has_financials(sym),
            "last_update": status_map.get(sym, {})
        })
    return jsonify(result)


@main.route("/api/analyze", methods=["POST"])
def analyze():
    body    = request.get_json(force=True)
    symbols = body.get("tickers", [])
    symbols = [s.strip().upper() for s in symbols if s.strip()][:3]

    valid_symbols = [t["symbol"] for t in TICKERS]
    symbols = [s for s in symbols if s in valid_symbols]

    if not symbols:
        return jsonify({"error": "Selecione ao menos um ticker válido."}), 400

    treasury = fetch_treasury_yield()
    results, errors = [], []

    for symbol in symbols:
        try:
            # 1. Carrega dados do banco
            rows = db.load_financials(symbol)

            # 2. Se não há dados, busca da API agora (primeira carga)
            if not rows:
                rows = fetch_quarterly_financials(symbol)
                if rows:
                    db.save_financials(symbol, rows)
                    db.log_update(symbol, "quarterly")

            # 3. Preço: do banco se recente, senão busca da API
            if db.needs_price_update(symbol):
                price = fetch_current_price(symbol)
                if price > 0:
                    db.save_current_price(symbol, price)
                    db.log_update(symbol, "price")
            else:
                price = db.load_current_price(symbol)

            # 4. Histórico de preços
            start_date = rows[0]["date"] if rows else None
            price_history = db.load_price_history(symbol, start_date)
            if not price_history:
                price_history = fetch_price_history(symbol)
                if price_history:
                    db.save_price_history(symbol, price_history)

            # 5. Calcula valuation
            val = compute_valuation(rows, price, treasury)

            # 6. Metadados do ticker
            ticker_info = next((t for t in TICKERS if t["symbol"] == symbol), {})

            # 7. Limpa campos internos das rows
            clean_rows = []
            for r in rows:
                clean = {k: v for k, v in r.items() if not k.startswith("_")}
                clean_rows.append(clean)

            results.append({
                "ticker":       symbol,
                "name":         ticker_info.get("name", symbol),
                "sector":       ticker_info.get("sector", ""),
                "industry":     "",
                "price":        price,
                "currency":     "USD",
                "exchange":     "",
                "description":  "",
                "rows":         clean_rows,
                "valuation":    val,
                "quarters":     [r["date"] for r in clean_rows],
                "price_history": price_history,
                "color":        SECTOR_COLORS.get(ticker_info.get("sector",""), "#4f7cff"),
            })

        except Exception as e:
            errors.append({"ticker": symbol, "error": str(e)})

    return jsonify({"results": results, "errors": errors})


@main.route("/api/status")
def api_status():
    """Painel de status de atualizações."""
    return jsonify(db.get_update_status())
