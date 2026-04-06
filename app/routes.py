from flask import Blueprint, render_template, request, jsonify
from .data import analyze_ticker

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/api/analyze", methods=["POST"])
def analyze():
    body = request.get_json(force=True)
    tickers = body.get("tickers", [])
    tickers = [t.strip().upper() for t in tickers if t.strip()][:3]

    if not tickers:
        return jsonify({"error": "Informe ao menos um ticker."}), 400

    results = []
    errors = []
    for ticker in tickers:
        try:
            data = analyze_ticker(ticker)
            # Serialize rows for JSON (drop internal fields)
            clean_rows = []
            for r in data["rows"]:
                clean = {k: v for k, v in r.items() if not k.startswith("_")}
                # Replace None with null-safe float
                for k, v in clean.items():
                    if isinstance(v, float) and (v != v):  # NaN check
                        clean[k] = None
                clean_rows.append(clean)
            data["rows"] = clean_rows
            results.append(data)
        except Exception as e:
            errors.append({"ticker": ticker, "error": str(e)})

    return jsonify({"results": results, "errors": errors})
