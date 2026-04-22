from flask import Blueprint, render_template, request, jsonify
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import TICKERS, SECTOR_COLORS, FINANCIAL_TICKERS
from . import database as db
from .calc import compute_valuation, compute_valuation_financial
from .data import (fetch_current_price, fetch_overview,
                   fetch_income_statement, fetch_balance_sheet,
                   fetch_cash_flow, fetch_price_history,
                   build_rows_from_statements, fetch_treasury_yield)

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html", tickers=TICKERS, sector_colors=SECTOR_COLORS)


@main.route("/api/tickers")
def api_tickers():
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


@main.route("/api/load/<symbol>", methods=["POST"])
def load_symbol(symbol):
    symbol = symbol.upper()
    valid  = [t["symbol"] for t in TICKERS]
    if symbol not in valid:
        return jsonify({"error": "Ticker não disponível"}), 400

    step = request.args.get("step", "1")

    try:
        if step == "1":
            price = fetch_current_price(symbol)
            if price > 0:
                db.save_current_price(symbol, price)
                db.log_update(symbol, "price")
            inc = fetch_income_statement(symbol)
            db.save_temp(symbol, "inc", inc)
            return jsonify({"ok": True, "step": 1, "price": price})

        elif step == "2":
            bs = fetch_balance_sheet(symbol)
            db.save_temp(symbol, "bs", bs)
            return jsonify({"ok": True, "step": 2})

        elif step == "3":
            cf  = fetch_cash_flow(symbol)
            inc = db.load_temp(symbol, "inc")
            bs  = db.load_temp(symbol, "bs")
            if not inc or not bs:
                return jsonify({"error": "Dados incompletos — reinicie a carga"}), 400
            rows = build_rows_from_statements(inc, bs, cf)
            if rows:
                db.save_financials(symbol, rows)
                db.log_update(symbol, "quarterly")
                db.clear_temp(symbol)
            return jsonify({"ok": True, "step": 3, "quarters": len(rows)})

        elif step == "4":
            history = fetch_price_history(symbol)
            if history:
                db.save_price_history(symbol, history)
            return jsonify({"ok": True, "step": 4, "history_points": len(history)})

        else:
            return jsonify({"error": "Step inválido"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@main.route("/api/analyze", methods=["POST"])
def analyze():
    body    = request.get_json(force=True)
    symbols = body.get("tickers", [])
    symbols = [s.strip().upper() for s in symbols if s.strip()][:3]
    valid   = [t["symbol"] for t in TICKERS]
    symbols = [s for s in symbols if s in valid]

    if not symbols:
        return jsonify({"error": "Selecione ao menos um ticker válido."}), 400

    treasury = fetch_treasury_yield()
    results, errors = [], []

    for symbol in symbols:
        try:
            rows = db.load_financials(symbol)
            if not rows:
                return jsonify({"error": f"{symbol} ainda não foi carregado."}), 400

            if db.needs_price_update(symbol):
                try:
                    price = fetch_current_price(symbol)
                    if price > 0:
                        db.save_current_price(symbol, price)
                        db.log_update(symbol, "price")
                except Exception:
                    pass

            price, price_date = db.load_current_price_with_date(symbol)
            start_date    = rows[0]["date"] if rows else None
            price_history = db.load_price_history(symbol, start_date)

            if not price and price_history:
                last_ph    = price_history[-1]
                price      = last_ph.get("close", 0)
                price_date = last_ph.get("date")

            is_fin = symbol in FINANCIAL_TICKERS
            val    = compute_valuation_financial(rows, price, treasury) if is_fin \
                     else compute_valuation(rows, price, treasury)

            ticker_info = next((t for t in TICKERS if t["symbol"] == symbol), {})
            clean_rows  = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]

            results.append({
                "ticker":        symbol,
                "name":          ticker_info.get("name", symbol),
                "sector":        ticker_info.get("sector", ""),
                "industry":      "",
                "price":         price,
                "price_date":    price_date,
                "currency":      "USD",
                "exchange":      "",
                "description":   "",
                "rows":          clean_rows,
                "valuation":     val,
                "quarters":      [r["date"] for r in clean_rows],
                "price_history": price_history,
                "color":         SECTOR_COLORS.get(ticker_info.get("sector", ""), "#4f7cff"),
            })

        except Exception as e:
            errors.append({"ticker": symbol, "error": str(e)})

    return jsonify({"results": results, "errors": errors})


@main.route("/api/quota-check")
def quota_check():
    result = []
    for t in TICKERS:
        result.append({
            "symbol":   t["symbol"],
            "name":     t["name"],
            "has_data": db.has_financials(t["symbol"]),
        })
    loaded = sum(1 for r in result if r["has_data"])
    return jsonify({
        "tickers":        result,
        "loaded":         loaded,
        "pending":        len(result) - loaded,
        "req_per_ticker": 4,
        "daily_limit":    25,
        "max_per_day":    6,
    })


@main.route("/api/status")
def api_status():
    status = db.get_update_status()
    loaded = sum(1 for s in status
                 if s.get("update_type") == "quarterly" and s.get("status") == "ok")
    return jsonify({
        "updates":        status,
        "loaded_tickers": loaded,
        "total_tickers":  len(TICKERS),
        "remaining":      len(TICKERS) - loaded,
    })
