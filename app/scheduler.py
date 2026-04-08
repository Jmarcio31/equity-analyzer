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
    """
    Atualiza dados contábeis trimestrais via 3 chamadas separadas.
    Só atualiza tickers já carregados e com >90 dias desde último update.
    """
    updated = 0
    for symbol in symbols:
        if not db.needs_quarterly_update(symbol):
            continue
        try:
            inc  = av_fetch.fetch_income_statement(symbol)
            bs   = av_fetch.fetch_balance_sheet(symbol)
            cf   = av_fetch.fetch_cash_flow(symbol)
            rows = av_fetch.build_rows_from_statements(inc, bs, cf)
            if rows:
                db.save_financials(symbol, rows)
                db.log_update(symbol, "quarterly", "ok")
                updated += 1
                log.info(f"Financials atualizados: {symbol} ({len(rows)} trimestres)")
        except Exception as e:
            db.log_update(symbol, "quarterly", "error", str(e))
            log.warning(f"Erro ao atualizar financials {symbol}: {e}")
    return updated


def start_scheduler(av_fetch, db, calc, symbols, interval_hours=6):
    """
    Inicia scheduler em thread separada.
    SÓ atualiza preços de tickers que JÁ têm dados financeiros no banco.
    NÃO faz carga inicial automática — isso é feito manualmente pelo usuário.
    Roda a cada 6 horas para não desperdiçar requisições.
    """

    def _run():
        # Aguarda 10 minutos antes da primeira execução
        # para não interferir com o startup do app
        log.info("Scheduler iniciado — aguardando 10min antes da primeira execução")
        time.sleep(600)

        while True:
            try:
                now = datetime.now()
                log.info(f"Scheduler rodando: {now.strftime('%Y-%m-%d %H:%M')}")

                # Só atualiza preços de tickers que JÁ têm dados no banco
                symbols_with_data = [s for s in symbols if db.has_financials(s)]
                if symbols_with_data:
                    n_prices = _update_prices(av_fetch, db, symbols_with_data)
                    if n_prices:
                        log.info(f"{n_prices} preços atualizados")
                else:
                    log.info("Nenhum ticker com dados no banco ainda — aguardando carga manual")

                # Atualiza dados contábeis SOMENTE de tickers já carregados
                # e somente se >90 dias desde último update
                if symbols_with_data:
                    n_fin = _update_financials(av_fetch, db, calc, symbols_with_data)
                    if n_fin:
                        log.info(f"{n_fin} tickers com dados contábeis atualizados")

            except Exception as e:
                log.error(f"Erro no scheduler: {e}")

            time.sleep(interval_hours * 3600)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    log.info("Thread do scheduler iniciada")
