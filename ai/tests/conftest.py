"""Fábrica de candles sintéticos.

Todos os candles são construídos em torno de um ATR fixo de **100 pontos** (escala do
WIN), para que os limiares relativos do motor tenham valores fáceis de conferir na mão:

- corpo longo   = corpo >= 0.8 × ATR = 80 pontos
- candle força  = amplitude >= 1.2 × ATR = 120 pontos, com corpo >= 60% da amplitude
- coincidência  = distância < 0.10 × ATR = 10 pontos

Os detectores recebem `Contexto` direto nos testes unitários, sem passar por
`contexto.ler()`. É de propósito: um teste de geometria não deve falhar porque o ADX
sintético ficou abaixo do limiar de lateralidade.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from trader_ai.tipos import Candle, Contexto, Tendencia

ATR = 100.0
TS_BASE = datetime(2026, 8, 5, 10, 0)


def vela(
    abertura: float,
    maxima: float,
    minima: float,
    fechamento: float,
    volume: float = 1000.0,
    i: int = 0,
) -> Candle:
    return Candle(TS_BASE + timedelta(minutes=5 * i), abertura, maxima, minima, fechamento, volume)


# ---------------------------------------------------------------------------
# Candles canônicos
# ---------------------------------------------------------------------------


def forca_alta(base: float, tamanho: float = 150.0, sombra: float = 5.0, i: int = 0) -> Candle:
    """Candle de força de alta: corpo grande, sombras mínimas."""
    fechamento = base + tamanho
    return vela(base, fechamento + sombra, base - sombra, fechamento, i=i)


def forca_baixa(topo: float, tamanho: float = 150.0, sombra: float = 5.0, i: int = 0) -> Candle:
    fechamento = topo - tamanho
    return vela(topo, topo + sombra, fechamento - sombra, fechamento, i=i)


def marubozu_alta(base: float, tamanho: float = 150.0, i: int = 0) -> Candle:
    """Sem sombra nenhuma."""
    return vela(base, base + tamanho, base, base + tamanho, i=i)


def marubozu_baixa(topo: float, tamanho: float = 150.0, i: int = 0) -> Candle:
    return vela(topo, topo, topo - tamanho, topo - tamanho, i=i)


def doji(preco: float, sombra: float = 40.0, i: int = 0) -> Candle:
    return vela(preco, preco + sombra, preco - sombra, preco + 0.5, i=i)


def martelo(preco: float, corpo: float = 10.0, cauda: float = 60.0, i: int = 0) -> Candle:
    """Corpo pequeno no topo do range, sombra inferior longa."""
    fechamento = preco + corpo
    return vela(preco, fechamento + 3.0, preco - cauda, fechamento, i=i)


def martelo_invertido(preco: float, corpo: float = 10.0, cauda: float = 60.0, i: int = 0) -> Candle:
    """Corpo pequeno na base do range, sombra superior longa."""
    fechamento = preco - corpo
    return vela(preco, preco + cauda, fechamento - 3.0, fechamento, i=i)


def corpo_pequeno_alta(
    base: float, tamanho: float = 20.0, sombra: float = 25.0, i: int = 0
) -> Candle:
    """Corpo pequeno com sombras generosas: corpo_pct ≈ 0.29, abaixo do limiar de 0.30."""
    fechamento = base + tamanho
    return vela(base, fechamento + sombra, base - sombra, fechamento, i=i)


def corpo_pequeno_baixa(
    topo: float, tamanho: float = 20.0, sombra: float = 25.0, i: int = 0
) -> Candle:
    fechamento = topo - tamanho
    return vela(topo, topo + sombra, fechamento - sombra, fechamento, i=i)


# ---------------------------------------------------------------------------
# Contextos
# ---------------------------------------------------------------------------


def _ctx(tendencia: Tendencia) -> Contexto:
    return Contexto(
        tendencia=tendencia,
        forca_tendencia=0.8,
        atr=ATR,
        regime_volatilidade=1.0,
        janela_pregao="tendencia-manha",
        peso_horario=1.15,
        indice=50,
    )


@pytest.fixture
def ctx_baixa() -> Contexto:
    return _ctx(Tendencia.BAIXA)


@pytest.fixture
def ctx_alta() -> Contexto:
    return _ctx(Tendencia.ALTA)


@pytest.fixture
def ctx_lateral() -> Contexto:
    return _ctx(Tendencia.LATERAL)


@pytest.fixture
def lim():
    """Limiares default, com tolerância de gap ZERADA.

    Os testes de geometria constroem gaps explícitos; deixar a tolerância intraday
    ligada mascararia um detector que exige gap e não o está checando de verdade.
    A tolerância tem teste próprio em `test_gaps.py`.
    """
    from dataclasses import replace

    from trader_ai.limiares import PADRAO

    return replace(PADRAO, tolerancia_gap_atr=0.0)
