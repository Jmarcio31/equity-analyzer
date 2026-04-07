"""
Scheduler de atualizações automáticas.
- Cotação: 1x por dia (23h de intervalo)
- Dados contábeis: 1x por trimestre (90 dias)
Roda em thread separada para não bloquear o servidor.
"""
import time
import threading
import logging
from datetime import datetime

log = logging.getLogger(__name__)


def _update_prices(av_fetch, db, symbols):
    """Atualiza cotação dos tickers que precisam de update."""
    updated = 0
    for symbol in symbols:
        if not db.needs_price_update(symbol):
            continue
        try:
            price = av_fetch.fetch_current_price(symbol)
            if price > 0:
                db.save_current_price(symbol, price)
                db.log_update(symbol, "price", "ok")
                updated += 1
                log.info(f"Preço atualizado: {symbol} = {price}")
            time.sleep(1.2)  # rate limit AV gratuito
        except Exception as e:
            db.log_update(symbol, "price", "error", str(e))
            log.warning(f"Erro ao atualizar preço {symbol}: {e}")
    return updated


def _update_financials(av_fetch, db, calc, symbols):
    """Atualiza dados contábeis dos tickers que precisam de update."""
    updated = 0
    for symbol in symbols:
        if not db.needs_quarterly_update(symbol):
            continue
        try:
            rows = av_fetch.fetch_quarterly_financials(symbol)
            if rows:
                db.save_financials(symbol, rows)
                db.log_update(symbol, "quarterly", "ok")
                updated += 1
                log.info(f"Financials atualizados: {symbol} ({len(rows)} trimestres)")
        except Exception as e:
            db.log_update(symbol, "quarterly", "error", str(e))
            log.warning(f"Erro ao atualizar financials {symbol}: {e}")
    return updated


def start_scheduler(av_fetch, db, calc, symbols, interval_hours=1):
    """Inicia scheduler em thread separada."""

    def _run():
        log.info("Scheduler iniciado")
        while True:
            try:
                now = datetime.now()
                log.info(f"Scheduler rodando: {now.strftime('%Y-%m-%d %H:%M')}")

                # Atualiza preços (verifica diariamente)
                n_prices = _update_prices(av_fetch, db, symbols)
                if n_prices:
                    log.info(f"{n_prices} preços atualizados")

                # Atualiza dados contábeis (verifica trimestralmente)
                n_fin = _update_financials(av_fetch, db, calc, symbols)
                if n_fin:
                    log.info(f"{n_fin} tickers com dados contábeis atualizados")

            except Exception as e:
                log.error(f"Erro no scheduler: {e}")

            time.sleep(interval_hours * 3600)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log.info("Thread do scheduler iniciada")
