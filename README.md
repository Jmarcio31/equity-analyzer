# Equity Analyzer

Análise fundamentalista profissional com 45 trimestres de dados históricos, ROIC, EVA/Economic Profit, FCF-SBC, Fórmula de Graham e Margem de Segurança.

**Desenvolvido por Jmarcio31**

---

## Funcionalidades

- 45 trimestres de dados por empresa (via Financial Modeling Prep)
- Métricas per share: EBIT, NOPAT, FCF-SBC, Economic Profit, Dividendos, Recompras
- ROIC, ROIC ex-Goodwill, ROIIC (1 ano)
- WACC calculado dinamicamente trimestre a trimestre
- Economic Profit = NOPAT − WACC × Capital Investido
- Fórmula de Graham: `V = EPS × (8,5 + 2 × CAGR%) × 4,4 / Y`
- Margem de Segurança: `MS = (V − Preço) / V`
- Comparação lado a lado de até 3 tickers
- Gráficos de evolução histórica
- Tabela completa de 45 trimestres com export CSV

---

## Stack

- **Backend**: Python 3.11 + Flask + Gunicorn
- **Frontend**: HTML/CSS/JS vanilla + Chart.js
- **Dados**: Financial Modeling Prep API
- **Deploy**: Railway

---

## Setup Local

```bash
git clone https://github.com/Jmarcio31/equity-analyzer.git
cd equity-analyzer
pip install -r requirements.txt
export FMP_API_KEY=sua_chave_aqui
python run.py
```

Acesse: http://localhost:5000

---

## Deploy no Railway

1. Fork/clone este repositório no seu GitHub
2. Em [railway.app](https://railway.app), clique em **New Project → Deploy from GitHub Repo**
3. Selecione este repositório
4. Vá em **Variables** e adicione:
   ```
   FMP_API_KEY = sua_chave_do_financial_modeling_prep
   ```
5. Railway detecta automaticamente o `Procfile` e faz o deploy

---

## Obter API Key (FMP)

1. Acesse https://financialmodelingprep.com
2. Crie uma conta gratuita (250 req/dia — suficiente para uso pessoal)
3. Copie sua API key do dashboard
4. Cole como variável de ambiente `FMP_API_KEY`

---

## Tickers suportados

Qualquer ticker listado na FMP — US, BR (ex: PETR4.SA), EU, etc.

Exemplos testados: `GOOGL`, `AAPL`, `META`, `NVDA`, `MSFT`, `AMZN`, `TSLA`, `BRK-B`

---

## Metodologia

| Métrica | Fórmula |
|---|---|
| NOPAT | EBIT × (1 − Tax Rate Efetivo) |
| Capital Investido | NWC + PP&E + Goodwill + Intangíveis |
| ROIC | NOPAT / Capital Investido |
| ROIIC (1A) | ΔNOPAT / ΔCapital Investido |
| WACC | Ke × E% + Kd × (1−T) × D% |
| Economic Profit | NOPAT − WACC × Capital Investido |
| FCF-SBC | OCF − Capex − SBC |
| Graham | EPS × (8,5 + 2g%) × 4,4 / Y% |
| Margem de Segurança | (Graham − Preço) / Graham |

---

## Licença

Uso pessoal. Dados fornecidos por Financial Modeling Prep.
