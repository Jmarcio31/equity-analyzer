from flask import Blueprint, render_template, request, jsonify
from .data import analyze_ticker, fetch_price_history

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/api/analyze", methods=["POST"])
def analyze():
    body    = request.get_json(force=True)
    tickers = body.get("tickers", [])
    tickers = [t.strip().upper() for t in tickers if t.strip()][:3]

    if not tickers:
        return jsonify({"error": "Informe ao menos um ticker."}), 400

    results, errors = [], []
    for ticker in tickers:
        try:
            data = analyze_ticker(ticker)

            # Busca preço histórico alinhado ao período dos trimestres
            if data["rows"]:
                start = data["rows"][0]["date"]
                data["price_history"] = fetch_price_history(ticker, start)
            else:
                data["price_history"] = []

            # Serializa rows limpando campos internos e NaN
            clean_rows = []
            for r in data["rows"]:
                clean = {}
                for k, v in r.items():
                    if k.startswith("_"):
                        continue
                    if isinstance(v, float) and v != v:  # NaN
                        clean[k] = None
                    else:
                        clean[k] = v
                clean_rows.append(clean)
            data["rows"] = clean_rows
            results.append(data)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

    return jsonify({"results": results, "errors": errors})
