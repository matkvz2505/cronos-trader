"""Fontes de candles para WIN e WDO.

`mt5` NÃO é importado aqui de propósito: o pacote `MetaTrader5` é Windows-only, e
importá-lo no `__init__` quebraria o motor inteiro em qualquer outro sistema. Importe
sob demanda:

    from trader_ai.fontes.mt5 import MetaTrader5Fonte
"""

from .base import FonteDados, FonteIndisponivel
from .contratos import codigo_vigente, em_rollover, simbolo_continuo, vencimento
from .csv_loader import ArquivoFonte, ler_arquivo

__all__ = [
    "ArquivoFonte",
    "FonteDados",
    "FonteIndisponivel",
    "codigo_vigente",
    "em_rollover",
    "ler_arquivo",
    "simbolo_continuo",
    "vencimento",
]
