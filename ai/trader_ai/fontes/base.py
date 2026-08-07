"""Contrato das fontes de dados.

O motor **nunca** importa `MetaTrader5` diretamente. Toda leitura passa por este
protocolo, e isso não é purismo: o pacote MT5 só existe no Windows e exige o terminal
aberto e logado numa corretora. Se o motor dependesse dele, os testes, o backtest e
qualquer CI parariam de rodar.

Duas implementações:

- `mt5.MetaTrader5Fonte` — tempo real e histórico, precisa do terminal
- `csv_loader.ArquivoFonte` — histórico exportado, roda em qualquer lugar
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ..tipos import Serie, Timeframe


@runtime_checkable
class FonteDados(Protocol):
    """Origem de candles de WIN/WDO."""

    def ultimos(self, ativo: str, timeframe: Timeframe, quantidade: int) -> Serie:
        """Os `quantidade` candles mais recentes, do mais antigo para o mais novo."""
        ...

    def periodo(
        self, ativo: str, timeframe: Timeframe, inicio: datetime, fim: datetime
    ) -> Serie:
        """Candles no intervalo fechado `[inicio, fim]`."""
        ...


class FonteIndisponivel(RuntimeError):
    """A fonte existe mas não pode ser usada agora.

    Separada de `ValueError` de propósito: significa "tente de novo / conserte o
    ambiente", não "seu código está errado". O coletor ao vivo trata os dois casos de
    forma diferente — um justifica retry, o outro não.
    """
