from flask import Flask
from . import database

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')

    try:
        database.init_db()
        database.init_temp_table()
        print("Banco de dados inicializado com sucesso")
    except Exception as e:
        print(f"AVISO: Banco não disponível: {e}")

    from .routes import main
    app.register_blueprint(main)

    return app
