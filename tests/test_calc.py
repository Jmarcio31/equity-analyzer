"""
Testes unitários para app/calc.py
Cobertura: compute_valuation, compute_valuation_financial, casos extremos.

Execução:
    cd C:/equity-analyzer
    python -m pytest tests/test_calc.py -v          # com pytest instalado
    python tests/test_calc.py                        # sem pytest (unittest nativo)
"""
import sys, os, math, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.calc import compute_valuation, compute_valuation_financial

TREASURY = 0.0428
PRICE    = 170.0
PRICE_FIN = 220.0


def approx_eq(a, b, rel=1e-4):
    """Igualdade aproximada — substitui pytest.approx."""
    if a is None and b is None: return True
    if a is None or b is None: return False
    if b == 0: return abs(a) < 1e-10
    return abs(a - b) / abs(b) <= rel


def make_row(**overrides):
    """Trimestre padrão realista (GOOGL-like)."""
    base = dict(
        date="2024-12-31", shares=12_000_000_000,
        cash_ps=8.0, debt_lease_ps=3.0, revenue_ps=22.0, ebit_ps=8.0,
        nopat_ps=5.6, net_income_ps=5.5, ocf_sbc_ps=7.0, fcf_sbc_ps=5.0,
        dividend_ps=0.0, repurchase_ps=2.0, cash_returned_ps=2.0,
        econ_profit_ps=4.0, invested_cap_ps=15.0,
        revenue_abs=264_000_000_000, ebit_abs=96_000_000_000,
        nopat_abs=67_200_000_000, ocf_sbc_abs=84_000_000_000,
        fcf_sbc_abs=60_000_000_000, econ_profit_abs=48_000_000_000,
        invested_cap_abs=180_000_000_000, invested_cap_ex_gw_abs=160_000_000_000,
        cash_abs=96_000_000_000, total_debt_abs=36_000_000_000,
        equity_abs=300_000_000_000, goodwill_abs=20_000_000_000,
        total_assets_abs=500_000_000_000, net_debt=-60_000_000_000,
        roic=0.24, roic_ex_gw=0.27, wacc=0.086, eff_tax=0.20,
        ebitda=110_000_000_000, capex_rev=0.09, opex_rev=0.65,
        debt_cap=0.11, equity_cap=0.89, net_debt_fcf=-1.0, roiic_1y=None,
        _ebit_cagr=0.18, _fcf_cagr=0.10, _ep_cagr=0.17,
        _div_cagr=None, _rev_cagr=0.12,
    )
    base.update(overrides)
    return base

def make_rows(n=20, **kw):
    return [make_row(**kw) for _ in range(n)]

def make_fin_row(**overrides):
    """Trimestre padrão para financeiras (JPM-like)."""
    base = dict(
        date="2024-12-31", shares=2_800_000_000,
        net_income_ps=20.0, dividend_ps=5.5, repurchase_ps=0.0,
        cash_returned_ps=5.5, equity_abs=360_000_000_000,
        goodwill_abs=52_000_000_000, total_assets_abs=3_900_000_000_000,
        revenue_abs=180_000_000_000, ebit_abs=52_000_000_000,
        opex_rev=0.71, roic=-0.004, roic_ex_gw=None, wacc=0.08, eff_tax=0.21,
        _ebit_cagr=0.08, _fcf_cagr=0.06, _div_cagr=0.07, _rev_cagr=0.05,
    )
    base.update(overrides)
    return base


# ─── Testes: compute_valuation (não-financeiras) ──────────────────────────────

class TestComputeValuation(unittest.TestCase):

    def test_retorna_dict_nao_vazio(self):
        v = compute_valuation(make_rows(), PRICE, TREASURY)
        self.assertIsInstance(v, dict)
        self.assertGreater(len(v), 10)

    def test_rows_vazio_retorna_dict_vazio(self):
        self.assertEqual(compute_valuation([], PRICE, TREASURY), {})

    def test_price_zero_sem_excecao(self):
        v = compute_valuation(make_rows(), 0, TREASURY)
        self.assertIsInstance(v, dict)
        self.assertIn("mktcap", v)

    def test_mktcap_correto(self):
        rows = make_rows()
        v = compute_valuation(rows, PRICE, TREASURY)
        expected = PRICE * rows[-1]["shares"]
        self.assertTrue(approx_eq(v["mktcap"], expected))

    def test_ev_correto(self):
        rows = make_rows()
        v = compute_valuation(rows, PRICE, TREASURY)
        last = rows[-1]
        expected = PRICE * last["shares"] + last["total_debt_abs"] - last["cash_abs"]
        self.assertTrue(approx_eq(v["ev"], expected))

    def test_roic_last_preservado_sem_cap(self):
        """ROIC off-scale (748%) deve ser preservado — sem filtro."""
        rows = make_rows(roic=7.48)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertTrue(approx_eq(v["roic_last"], 7.48))

    def test_econ_spread_none_quando_roic_off_scale(self):
        """Spread deve ser None quando ROIC > 500% (não interpretável)."""
        rows = make_rows(roic=7.48)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertIsNone(v["econ_spread"])

    def test_econ_spread_calculado_quando_roic_normal(self):
        rows = make_rows(roic=0.24, wacc=0.086)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertTrue(approx_eq(v["econ_spread"], 0.24 - 0.086))

    def test_graham_none_com_eps_negativo(self):
        rows = make_rows(ebit_ps=-2.0)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertIsNone(v["graham_ebit"])
        self.assertIsNone(v["ms_ebit"])

    def test_graham_none_com_treasury_zero(self):
        rows = make_rows()
        v = compute_valuation(rows, PRICE, treasury_yield=0.0)
        self.assertIsNone(v["graham_ebit"])

    def test_avg_ms_exclui_div_sem_historico_suficiente(self):
        """< 8 trimestres pagando dividendo → ms_div excluído do avg."""
        rows = make_rows(n=20, dividend_ps=0.0)
        for i in range(-5, 0):
            rows[i] = make_row(dividend_ps=1.0, _div_cagr=0.5)
        v = compute_valuation(rows, PRICE, TREASURY)
        if v.get("ms_fcf") is not None and v.get("avg_ms") is not None:
            # avg deve ser só ms_fcf (div excluído)
            self.assertTrue(approx_eq(v["avg_ms"], v["ms_fcf"]))

    def test_avg_ms_inclui_div_com_historico_suficiente(self):
        """≥ 8 trimestres pagando dividendo → ms_div incluído."""
        rows = [make_row(dividend_ps=2.0, _div_cagr=0.05) for _ in range(20)]
        v = compute_valuation(rows, PRICE, TREASURY)
        if (v.get("graham_div") and v["graham_div"] > 0
                and v.get("ms_fcf") is not None and v.get("ms_div") is not None):
            expected = (v["ms_fcf"] + v["ms_div"]) / 2
            self.assertTrue(approx_eq(v["avg_ms"], expected))

    def test_cash_excess_nao_negativo(self):
        rows = make_rows(cash_ps=1.0, debt_lease_ps=10.0)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertGreaterEqual(v["cash_excess_ps"], 0)

    def test_fcf_yield_positivo(self):
        rows = make_rows()
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertGreater(v["fcf_yield"], 0)

    def test_div_yield_zero_sem_dividendo(self):
        rows = make_rows(dividend_ps=0.0)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertEqual(v["div_yield"], 0.0)

    def test_1_trimestre_nao_quebra(self):
        v = compute_valuation(make_rows(n=1), PRICE, TREASURY)
        self.assertIsInstance(v, dict)


# ─── Testes: compute_valuation_financial ─────────────────────────────────────

class TestComputeValuationFinancial(unittest.TestCase):

    def test_is_financial_true(self):
        v = compute_valuation_financial([make_fin_row()]*20, PRICE_FIN, TREASURY)
        self.assertTrue(v.get("is_financial"))

    def test_rows_vazio(self):
        self.assertEqual(compute_valuation_financial([], PRICE_FIN, TREASURY), {})

    def test_roe_calculado(self):
        rows = [make_fin_row()]*20
        v = compute_valuation_financial(rows, PRICE_FIN, TREASURY)
        last = rows[-1]
        expected = (last["net_income_ps"] * last["shares"]) / last["equity_abs"]
        self.assertTrue(approx_eq(v["roe"], expected))

    def test_tbv_nunca_negativo(self):
        """Equity menor que goodwill → TBV = 1 (proteção)."""
        rows = [make_fin_row(equity_abs=1_000_000, goodwill_abs=999_000_000_000)]*20
        v = compute_valuation_financial(rows, PRICE_FIN, TREASURY)
        self.assertGreaterEqual(v["tbv_abs"], 1)

    def test_p_tbv_positivo(self):
        v = compute_valuation_financial([make_fin_row()]*20, PRICE_FIN, TREASURY)
        self.assertGreater(v["p_tbv"], 0)

    def test_p_e_none_eps_negativo(self):
        rows = [make_fin_row(net_income_ps=-5.0)]*20
        v = compute_valuation_financial(rows, PRICE_FIN, TREASURY)
        self.assertIsNone(v["p_e"])

    def test_eficiencia_preservada(self):
        rows = [make_fin_row(opex_rev=0.65)]*20
        v = compute_valuation_financial(rows, PRICE_FIN, TREASURY)
        self.assertTrue(approx_eq(v["efficiency"], 0.65))

    def test_nim_proxy_entre_0_e_1(self):
        v = compute_valuation_financial([make_fin_row()]*20, PRICE_FIN, TREASURY)
        self.assertGreaterEqual(v["nim_proxy"], 0)
        self.assertLessEqual(v["nim_proxy"], 1)

    def test_avg_ms_filtrado_absurdo(self):
        """avg_ms deve ficar entre -5 e +5 (filtro aplicado)."""
        rows = [make_fin_row(net_income_ps=0.01, _ebit_cagr=0.50)]*20
        v = compute_valuation_financial(rows, PRICE_FIN, TREASURY)
        if v.get("avg_ms") is not None:
            self.assertGreater(v["avg_ms"], -5)
            self.assertLess(v["avg_ms"], 5)

    def test_sem_net_income_nao_quebra(self):
        rows = [make_fin_row(net_income_ps=0.0)]*20
        v = compute_valuation_financial(rows, PRICE_FIN, TREASURY)
        self.assertIsInstance(v, dict)
        self.assertEqual(v.get("roe"), 0.0)
        self.assertIsNone(v.get("p_e"))


# ─── Testes: casos extremos e regressão ──────────────────────────────────────

class TestCasosExtremos(unittest.TestCase):

    def test_aapl_ic_negativo_nao_quebra(self):
        row = make_row(
            invested_cap_abs=None, invested_cap_ex_gw_abs=None,
            invested_cap_ps=None, roic=0, roic_ex_gw=None, econ_profit_ps=None,
        )
        v = compute_valuation([row]*20, 200.0, TREASURY)
        self.assertIsInstance(v, dict)

    def test_empresa_sem_divida(self):
        rows = make_rows(total_debt_abs=0, debt_lease_ps=0.0, debt_cap=0.0, equity_cap=1.0)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertIsInstance(v, dict)

    def test_nvda_roic_alto_valido_98pct(self):
        """NVDA ROIC ~98% — válido, spread deve ser calculado."""
        rows = make_rows(roic=0.98, wacc=0.086)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertTrue(approx_eq(v["roic_last"], 0.98))
        self.assertTrue(approx_eq(v["econ_spread"], 0.98 - 0.086))

    def test_aapl_roic_748pct_spread_none(self):
        """AAPL ROIC 748% — spread deve ser None (off-scale)."""
        rows = make_rows(roic=7.48)
        v = compute_valuation(rows, 200.0, TREASURY)
        self.assertTrue(approx_eq(v["roic_last"], 7.48))
        self.assertIsNone(v["econ_spread"])

    def test_preco_alto_ms_negativa(self):
        rows = make_rows(_ebit_cagr=0.05, ebit_ps=8.0)
        v = compute_valuation(rows, 99999.0, TREASURY)
        if v.get("ms_ebit") is not None:
            self.assertLess(v["ms_ebit"], 0)

    def test_preco_baixo_ms_positiva(self):
        rows = make_rows(_ebit_cagr=0.25, ebit_ps=20.0)
        v = compute_valuation(rows, 5.0, TREASURY)
        if v.get("graham_ebit") and v["graham_ebit"] > 5:
            self.assertGreater(v["ms_ebit"], 0)

    def test_treasury_muito_baixo_nao_quebra(self):
        v = compute_valuation(make_rows(), PRICE, treasury_yield=0.001)
        self.assertIsInstance(v, dict)

    def test_empresa_sem_cagr_historico(self):
        rows = make_rows(_ebit_cagr=None, _fcf_cagr=None, _ep_cagr=None, _div_cagr=None)
        v = compute_valuation(rows, PRICE, TREASURY)
        self.assertIsInstance(v, dict)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [TestComputeValuation, TestComputeValuationFinancial, TestCasosExtremos]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
