from flask import Flask
from . import database, scheduler
from .data import fetch_current_price, fetch_quarterly_financials, fetch_price_history
from .calc import compute_valuation
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SYMBOLS

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    # Inicializa banco de dados
    try:
        database.init_db()
        database.init_temp_table()
    except Exception as e:
        print(f"AVISO: Banco não disponível: {e}")

    # Inicia scheduler em background
    try:
        import data as av
        scheduler.start_scheduler(av, database, compute_valuation, SYMBOLS)
    except Exception as e:
        print(f"AVISO: Scheduler não iniciado: {e}")

    from .routes import main
    app.register_blueprint(main)

    return app
