"""
Camada de acesso ao banco de dados PostgreSQL.
Todas as operações de leitura e escrita passam por aqui.
"""
import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, date

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Cria as tabelas se não existirem. Chamado na inicialização do app."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS financials (
                    id            SERIAL PRIMARY KEY,
                    symbol        VARCHAR(10)  NOT NULL,
                    period_date   DATE         NOT NULL,
                    data          JSONB        NOT NULL,
                    updated_at    TIMESTAMP    DEFAULT NOW(),
                    UNIQUE(symbol, period_date)
                );

                CREATE TABLE IF NOT EXISTS prices (
                    id          SERIAL PRIMARY KEY,
                    symbol      VARCHAR(10)  NOT NULL,
                    price_date  DATE         NOT NULL,
                    close       NUMERIC(12,4) NOT NULL,
                    updated_at  TIMESTAMP    DEFAULT NOW(),
                    UNIQUE(symbol, price_date)
                );

                CREATE TABLE IF NOT EXISTS price_history (
                    id          SERIAL PRIMARY KEY,
                    symbol      VARCHAR(10)  NOT NULL,
                    price_date  DATE         NOT NULL,
                    close       NUMERIC(12,4) NOT NULL,
                    UNIQUE(symbol, price_date)
                );

                CREATE TABLE IF NOT EXISTS update_log (
                    id           SERIAL PRIMARY KEY,
                    symbol       VARCHAR(10)  NOT NULL,
                    update_type  VARCHAR(20)  NOT NULL,
                    updated_at   TIMESTAMP    DEFAULT NOW(),
                    status       VARCHAR(20)  DEFAULT 'ok',
                    message      TEXT,
                    UNIQUE(symbol, update_type)
                );

                CREATE INDEX IF NOT EXISTS idx_financials_symbol
                    ON financials(symbol);
                CREATE INDEX IF NOT EXISTS idx_price_history_symbol
                    ON price_history(symbol);
            """)
        conn.commit()


def save_financials(symbol, rows):
    with get_conn() as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute("""
                    INSERT INTO financials (symbol, period_date, data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (symbol, period_date)
                    DO UPDATE SET data = EXCLUDED.data, updated_at = NOW()
                """, (symbol, row["date"], json.dumps(row)))
        conn.commit()


def load_financials(symbol):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT data FROM financials
                WHERE symbol = %s
                ORDER BY period_date ASC
            """, (symbol,))
            rows = cur.fetchall()
    return [row["data"] for row in rows]


def has_financials(symbol):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM financials WHERE symbol = %s", (symbol,))
            count = cur.fetchone()[0]
    return count > 0


def needs_quarterly_update(symbol):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT updated_at FROM update_log
                WHERE symbol = %s AND update_type = 'quarterly'
            """, (symbol,))
            row = cur.fetchone()
    if not row:
        return True
    return (datetime.now() - row[0]).days > 90


def save_current_price(symbol, price):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO prices (symbol, price_date, close)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol, price_date)
                DO UPDATE SET close = EXCLUDED.close, updated_at = NOW()
            """, (symbol, date.today(), price))
        conn.commit()


def load_current_price(symbol):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT close FROM prices
                WHERE symbol = %s
                ORDER BY price_date DESC LIMIT 1
            """, (symbol,))
            row = cur.fetchone()
    return float(row[0]) if row else 0.0


def needs_price_update(symbol):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT updated_at FROM update_log
                WHERE symbol = %s AND update_type = 'price'
            """, (symbol,))
            row = cur.fetchone()
    if not row:
        return True
    return (datetime.now() - row[0]).total_seconds() / 3600 > 23


def save_price_history(symbol, history):
    with get_conn() as conn:
        with conn.cursor() as cur:
            for item in history:
                cur.execute("""
                    INSERT INTO price_history (symbol, price_date, close)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (symbol, price_date) DO NOTHING
                """, (symbol, item["date"], item["close"]))
        conn.commit()


def load_price_history(symbol, start_date=None):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if start_date:
                cur.execute("""
                    SELECT price_date::text as date, close::float as close
                    FROM price_history
                    WHERE symbol = %s AND price_date >= %s
                    ORDER BY price_date ASC
                """, (symbol, start_date))
            else:
                cur.execute("""
                    SELECT price_date::text as date, close::float as close
                    FROM price_history WHERE symbol = %s
                    ORDER BY price_date ASC
                """, (symbol,))
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def log_update(symbol, update_type, status="ok", message=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO update_log (symbol, update_type, status, message)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, update_type)
                DO UPDATE SET updated_at = NOW(), status = EXCLUDED.status,
                              message = EXCLUDED.message
            """, (symbol, update_type, status, message))
        conn.commit()


def get_update_status():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT symbol, update_type, updated_at::text, status, message
                FROM update_log ORDER BY symbol, update_type
            """)
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ── Temp storage (para carga em múltiplos steps) ──────────────────────────────

def init_temp_table():
    """Cria tabela temporária se não existir."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS temp_data (
                    symbol      VARCHAR(10)  NOT NULL,
                    data_type   VARCHAR(20)  NOT NULL,
                    data        JSONB        NOT NULL,
                    created_at  TIMESTAMP    DEFAULT NOW(),
                    UNIQUE(symbol, data_type)
                );
            """)
        conn.commit()


def save_temp(symbol, data_type, data):
    import json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO temp_data (symbol, data_type, data)
                VALUES (%s, %s, %s)
                ON CONFLICT (symbol, data_type)
                DO UPDATE SET data = EXCLUDED.data, created_at = NOW()
            """, (symbol, data_type, json.dumps(data)))
        conn.commit()


def load_temp(symbol, data_type):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT data FROM temp_data
                WHERE symbol = %s AND data_type = %s
            """, (symbol, data_type))
            row = cur.fetchone()
    return row[0] if row else None


def clear_temp(symbol):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM temp_data WHERE symbol = %s", (symbol,))
        conn.commit()
