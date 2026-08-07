# ai — o motor

Detecção de padrões, confluência, decisão e backtest para WIN e WDO. Python puro, sem
serviço e sem banco: entra série de candles, sai sinal.

## Instalar e verificar

```powershell
cd ai
pip install -e ".[dev]"
pytest
```

A suíte roda **sem corretora e sem rede** — todos os candles dos testes são sintéticos.

## Rodar sem ter conta no MT5

```powershell
python scripts/gerar_amostra.py --ativo WIN --dias 60
python -m trader_ai.cli backtest dados/WIN_M5.csv --ativo WIN --tf M5
```

Dado sintético serve para exercitar a pipeline inteira. **Não valida estratégia**: o
gerador é um random walk com perfil de volatilidade, e expectância medida ali não
significa nada.

## Rodar com dados reais

Requer MT5 aberto e logado numa corretora B3 (ver [../docs/FONTES-DE-DADOS.md](../docs/FONTES-DE-DADOS.md)):

```powershell
pip install -e ".[mt5]"
python -m trader_ai.cli baixar WIN --tf M5 --n 20000 --continuo --saida dados/WIN_M5.csv
python -m trader_ai.cli walkforward dados/WIN_M5.csv --ativo WIN --janelas 5
```

`--continuo` usa `WIN$N`, a série ajustada — é o correto para backtest, porque não tem o
salto artificial da virada de contrato.

## Módulos

| Arquivo | Papel |
|---|---|
| `tipos.py` | `Candle`, `Serie`, `Contexto`, `Deteccao` — estruturas puras |
| `limiares.py` | **todo número mágico do sistema**; é o que o backtest calibra |
| `normalizacao.py` | vocabulário do ebook virado em predicado + mecânica de força |
| `indicadores.py` | EMA, SMA, ATR, RSI, ADX, VWAP, pivôs |
| `contexto.py` | tendência, regime de volatilidade, janela do pregão |
| `padroes/` | os 60 detectores, registrados por decorator |
| `fibonacci.py` | retrações e projeções da última perna |
| `suporte_resistencia.py` | pivôs, dia anterior, abertura, VWAP, números redondos |
| `confluencia.py` | onde o padrão vira score |
| `instrumentos.py` | specs de WIN e WDO — tick, valor do ponto, custos |
| `decisao.py` | entrada, stop, alvo, R:R, sizing, vetos de risco |
| `multitimeframe.py` | viés 15/30/60min governando o gatilho de 5min |
| `fontes/` | MT5, CSV, resolução de contrato e rollover |
| `backtest.py` | simulação sem look-ahead, walk-forward, calibração |
| `cli.py` | interface de linha de comando |

## Usar como biblioteca

```python
from trader_ai import contexto, padroes, confluencia, decisao, multitimeframe
from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.tipos import Timeframe

serie = ler_arquivo("dados/WIN_M5.csv", "WIN", Timeframe.M5)
conjunto = multitimeframe.montar_conjunto(serie)   # deriva 15/30/60min da base
i = len(serie) - 1

ctx = contexto.ler(serie, i)
deteccoes = padroes.detectar_em(serie, i, ctx)
avaliacao = confluencia.melhor(serie, i, deteccoes, ctx)

if avaliacao:
    vies = multitimeframe.calcular_vies(conjunto, serie[i].ts)
    avaliacao = multitimeframe.aplicar(avaliacao, vies)
    sinal = decisao.montar(serie, i, avaliacao, ctx, capital=20_000)
    if sinal:
        print(sinal.resumo())
        print(avaliacao.explicar())   # por que este score
```

`decisao.montar` devolver `None` é o caso comum e desejável: a maior parte das detecções
não deve virar operação.

## Adicionar um padrão novo

```python
@padrao(
    id="meu_padrao",
    nome="Meu Padrão",
    familia=Familia.REVERSAO,
    direcao=Direcao.ALTA,
    n_candles=2,
    confiabilidade=PRIOR_NEUTRO,
    pagina=99,
    tendencia=Tendencia.BAIXA,
)
def meu_padrao(janela, ctx, lim):
    c1, c2 = janela
    return combinar(
        satisfaz(c1.e_baixa),
        e_corpo_longo(c1, ctx.atr, lim),
        engolfa_corpo(c2, c1, ctx.atr, lim),
    )
```

Depois: um teste que dispara **e** um vizinho que não dispara. O negativo é o que importa
— um detector frouxo passa em qualquer positivo. Os testes de `test_catalogo.py` já cobrem
o padrão novo automaticamente (score válido, sem exceção em candle parado, metadados
coerentes).

## Ler antes de mexer

- [../docs/ARQUITETURA.md](../docs/ARQUITETURA.md) — as sete camadas e por que existem
- [../docs/ERRATA-EBOOK.md](../docs/ERRATA-EBOOK.md) — onde o código diverge do ebook, e por quê
- [../CLAUDE.md](../CLAUDE.md) — as regras não negociáveis, principalmente as de look-ahead
