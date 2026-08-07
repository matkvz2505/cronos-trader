"""trader_ai — motor de análise de padrões para mini-índice (WIN) e mini-dólar (WDO).

Escopo fechado: só WIN e WDO, só sinal (o motor não envia ordem).

Uso típico:

    from trader_ai import Serie, Timeframe, contexto, padroes

    serie = ...                       # via fontes.csv_loader ou fontes.mt5
    for d in padroes.varrer(serie):
        print(d.nome, d.forca, d.score_bruto)

Camadas, em ordem: `normalizacao` → `contexto` → `padroes` → `confluencia` → `decisao`.
Ver docs/ARQUITETURA.md.
"""

from .limiares import PADRAO, Limiares
from .tipos import (
    Candle,
    Contexto,
    Deteccao,
    Direcao,
    Familia,
    Serie,
    Tendencia,
    Timeframe,
)

__all__ = [
    "PADRAO",
    "Candle",
    "Contexto",
    "Deteccao",
    "Direcao",
    "Familia",
    "Limiares",
    "Serie",
    "Tendencia",
    "Timeframe",
]

__version__ = "0.1.0"
