"""Testes da camada de contexto.

O que está sendo verificado aqui não é "o ADX está certo" (isso é matemática de
biblioteca) — é que o **veredito** sai certo: tendência clara vira ALTA/BAIXA,
lateralização vira LATERAL, e nada olha para o futuro.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest

from trader_ai import contexto as ctx_mod
from trader_ai.contexto import janela_de, opera_agora
from trader_ai.indicadores import atr, ema, sma
from trader_ai.tipos import Candle, Serie, Tendencia, Timeframe

TS = datetime(2026, 8, 5, 10, 0)


def _serie(precos_ohlc: list[tuple[float, float, float, float]]) -> Serie:
    candles = [
        Candle(TS + timedelta(minutes=5 * i), a, mx, mn, f, 1000.0)
        for i, (a, mx, mn, f) in enumerate(precos_ohlc)
    ]
    return Serie("WIN", Timeframe.M5, candles)


def serie_em_alta(n: int = 150, passo: float = 60.0) -> Serie:
    preco = 128_000.0
    linhas = []
    for _ in range(n):
        linhas.append((preco, preco + 55, preco - 5, preco + 50))
        preco += passo
    return _serie(linhas)


def serie_em_baixa(n: int = 150, passo: float = 60.0) -> Serie:
    preco = 134_000.0
    linhas = []
    for _ in range(n):
        linhas.append((preco, preco + 5, preco - 55, preco - 50))
        preco -= passo
    return _serie(linhas)


def serie_lateral(n: int = 150, amplitude: float = 80.0) -> Serie:
    """Oscilação em torno de um nível — sem tendência para reverter nem continuar."""
    base = 130_000.0
    linhas = []
    for i in range(n):
        alto = i % 2 == 0
        abertura = base + (amplitude if alto else 0.0)
        fechamento = base + (0.0 if alto else amplitude)
        linhas.append((abertura, base + amplitude + 10, base - 10, fechamento))
    return _serie(linhas)


# ---------------------------------------------------------------------------
# Veredito de tendência
# ---------------------------------------------------------------------------


def test_serie_em_alta_e_lida_como_alta():
    serie = serie_em_alta()
    ctx = ctx_mod.ler(serie, len(serie) - 1)
    assert ctx.tendencia is Tendencia.ALTA
    assert ctx.forca_tendencia > 0


def test_serie_em_baixa_e_lida_como_baixa():
    serie = serie_em_baixa()
    ctx = ctx_mod.ler(serie, len(serie) - 1)
    assert ctx.tendencia is Tendencia.BAIXA


def test_serie_lateral_e_lida_como_lateral():
    """ADX baixo tem poder de veto: sem força, não há tendência.

    É o que impede o motor de gerar reversão em cima de oscilação de ruído.
    """
    serie = serie_lateral()
    ctx = ctx_mod.ler(serie, len(serie) - 1)
    assert ctx.tendencia is Tendencia.LATERAL
    assert ctx.forca_tendencia == 0.0


def test_historico_curto_nao_afirma_tendencia():
    """Declarar tendência com 10 candles seria inventar."""
    serie = serie_em_alta(n=10)
    ctx = ctx_mod.ler(serie, len(serie) - 1)
    assert ctx.tendencia is Tendencia.LATERAL


def test_contexto_nao_olha_para_o_futuro():
    """Ler o candle `i` na série inteira e na série truncada em `i` tem que dar igual.

    Esta é a defesa central contra look-ahead. Se falhar, todo backtest fica inválido —
    e fica inválido *para melhor*, que é o modo mais perigoso de errar.
    """
    serie = serie_em_alta()
    i = 100
    completo = ctx_mod.ler(serie, i)
    truncado = ctx_mod.ler(serie.fatiar(i), i)

    assert completo.tendencia is truncado.tendencia
    assert completo.atr == pytest.approx(truncado.atr)
    assert completo.forca_tendencia == pytest.approx(truncado.forca_tendencia)


def test_atr_e_positivo_apos_o_aquecimento():
    serie = serie_em_alta()
    ctx = ctx_mod.ler(serie, len(serie) - 1)
    assert ctx.atr > 0


# ---------------------------------------------------------------------------
# Janelas do pregão
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("momento", "esperado"),
    [
        (time(8, 30), "pre-abertura"),
        (time(9, 30), "abertura"),
        (time(10, 30), "tendencia-manha"),
        (time(12, 30), "almoco"),
        (time(15, 0), "abertura-eua"),
        (time(16, 30), "fechamento"),
        (time(18, 0), "ajuste"),
    ],
)
def test_janela_do_pregao(momento, esperado):
    assert janela_de(momento).rotulo == esperado


def test_almoco_pesa_menos_que_a_abertura_americana():
    """Não é estética: WIN/WDO lateralizam no meio do dia e ganham direção às 14h."""
    assert janela_de(time(12, 30)).peso < janela_de(time(15, 0)).peso


def test_nao_opera_fora_do_pregao():
    serie = serie_em_alta()
    # Índice 50 = 10h00 + 250min = 14h10, dentro da janela da abertura americana.
    # (a série sintética não reseta o dia, então os índices altos caem de madrugada)
    ctx = ctx_mod.ler(serie, 50)
    assert opera_agora(ctx)

    fora = ctx_mod.Contexto(
        tendencia=Tendencia.ALTA,
        forca_tendencia=1.0,
        atr=100.0,
        regime_volatilidade=1.0,
        janela_pregao="ajuste",
        peso_horario=0.0,
        indice=0,
    )
    assert not opera_agora(fora)


# ---------------------------------------------------------------------------
# Indicadores — alinhamento de índice
# ---------------------------------------------------------------------------


def test_indicadores_preservam_o_tamanho_da_serie():
    """Deslocamento silencioso de um candle é o bug que faz backtest parecer lucrativo."""
    serie = serie_em_alta()
    n = len(serie)
    assert len(atr(serie, 14)) == n
    assert len(sma(serie.fechamento, 20)) == n
    assert len(ema(serie.fechamento, 9)) == n


def test_sma_bate_com_a_media_calculada_na_mao():
    serie = serie_em_alta(n=50)
    valores = serie.fechamento
    calculado = sma(valores, 10)
    esperado = sum(valores[20:30]) / 10
    assert calculado[29] == pytest.approx(esperado)


def test_memo_da_serie_e_invalidado_ao_pedir():
    serie = serie_em_alta(n=50)
    primeiro = atr(serie, 14)
    assert atr(serie, 14) is primeiro  # veio do cache
    serie.invalidar_cache()
    assert atr(serie, 14) is not primeiro
