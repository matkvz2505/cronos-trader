"""Testes do módulo de estrutura gráfica.

O que se verifica aqui é que o desenho **não inventa figura**. Um detector de canal que
enxerga canal em qualquer lugar é pior que nenhum: transforma ruído em leitura, e leitura
em confiança.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from trader_ai import estrutura as est
from trader_ai.indicadores import atr as calc_atr
from trader_ai.indicadores import swings_confirmados
from trader_ai.tipos import Candle, Serie, Timeframe

TS = datetime(2026, 8, 5, 10, 0)


def _serie(linhas: list[tuple[float, float, float, float]]) -> Serie:
    candles = [
        Candle(TS + timedelta(minutes=5 * i), a, mx, mn, f, 1000.0)
        for i, (a, mx, mn, f) in enumerate(linhas)
    ]
    return Serie("WIN", Timeframe.M5, candles)


def serie_em_canal(
    n: int = 200, inclinacao: float = -12.0, amplitude: float = 400.0, periodo: float = 4.0
) -> Serie:
    """Oscila dentro de um canal inclinado — a figura que o detector deve encontrar.

    `periodo` controla a frequência da oscilação. O default produz um ciclo a cada ~25
    candles, o que dá 4 a 5 pivôs de cada lado dentro da janela de 120 que o detector
    examina. Oscilação mais lenta geraria pivôs de menos e a figura ficaria indetectável
    por falta de pontos, não por falta de estrutura.
    """
    import math

    linhas = []
    base = 130_000.0
    for i in range(n):
        centro = base + inclinacao * i
        # Oscilação senoidal encostando nas duas bordas repetidamente.
        abertura = centro + math.sin(i / periodo) * (amplitude / 2)
        fechamento = centro + math.sin((i + 1) / periodo) * (amplitude / 2)
        linhas.append(
            (abertura, max(abertura, fechamento) + 25, min(abertura, fechamento) - 25, fechamento)
        )
    return _serie(linhas)


def serie_aleatoria(n: int = 200) -> Serie:
    """Passeio sem estrutura. O detector não pode encontrar canal aqui."""
    import random

    rng = random.Random(7)
    linhas = []
    preco = 130_000.0
    for _ in range(n):
        fechamento = preco + rng.gauss(0, 180)
        linhas.append(
            (preco, max(preco, fechamento) + 40, min(preco, fechamento) - 40, fechamento)
        )
        preco = fechamento
    return _serie(linhas)


# ---------------------------------------------------------------------------
# Reta
# ---------------------------------------------------------------------------


def test_reta_avalia_o_preco_no_indice():
    r = est.Reta(0, 100.0, 10, 200.0)
    assert r.inclinacao == pytest.approx(10.0)
    assert r.preco_em(5) == pytest.approx(150.0)
    assert r.preco_em(20) == pytest.approx(300.0)


def test_reta_horizontal_tem_inclinacao_zero():
    assert est.Reta(0, 100.0, 10, 100.0).inclinacao == 0.0


# ---------------------------------------------------------------------------
# Canal
# ---------------------------------------------------------------------------


def test_encontra_canal_descendente_em_serie_construida():
    serie = serie_em_canal(inclinacao=-12.0)
    canal = est.detectar_canal(serie, len(serie) - 1)
    assert canal is not None
    assert canal.tipo == "descendente"
    assert canal.toques >= est.MIN_TOQUES


def test_encontra_canal_ascendente():
    canal = est.detectar_canal(serie_em_canal(inclinacao=12.0), 199)
    assert canal is not None
    assert canal.tipo == "ascendente"


def test_canal_lateral_quando_a_inclinacao_e_desprezivel():
    canal = est.detectar_canal(serie_em_canal(inclinacao=0.0), 199)
    assert canal is not None
    assert canal.tipo == "lateral"


def test_nao_inventa_canal_em_serie_aleatoria():
    """O teste que importa: figura em toda parte é o mesmo que figura em lugar nenhum."""
    assert est.detectar_canal(serie_aleatoria(), 199) is None


def test_canal_posiciona_o_preco_entre_as_bordas():
    canal = est.detectar_canal(serie_em_canal(), 199)
    assert canal is not None
    i = 150
    meio = (canal.topo.preco_em(i) + canal.fundo.preco_em(i)) / 2
    assert canal.posicao(i, meio) == pytest.approx(0.5, abs=0.02)
    assert canal.posicao(i, canal.topo.preco_em(i)) == pytest.approx(1.0, abs=0.02)


def test_historico_curto_nao_produz_canal():
    assert est.detectar_canal(serie_em_canal(n=25), 24) is None


def test_r2_alto_sozinho_nao_basta_precisa_conter_o_preco():
    """O critério que R² não cobre, e a razão de `_contencao` existir.

    Com poucos pivôs — 5 a 7 numa janela — até um passeio aleatório produz regressão com
    R² de 0,90: qualquer punhado de pontos se alinha razoavelmente por acaso. O que o
    aleatório **não** faz é ficar dentro das linhas entre os pivôs.

    Medido nesta série: R² 0,91/0,75 (passaria no piso) mas contenção de 86,8%, abaixo
    dos 90% exigidos. É a contenção que rejeita.
    """
    serie = serie_aleatoria()
    i = len(serie) - 1
    inicio = max(0, i - 120)
    topos, fundos = swings_confirmados(serie, i, 5)
    topos = [(k, p) for k, p in topos if k >= inicio]
    fundos = [(k, p) for k, p in fundos if k >= inicio]

    ajuste_topo, ajuste_fundo = est._ajustar_reta(topos), est._ajustar_reta(fundos)
    assert ajuste_topo and ajuste_fundo
    atr_i = float(calc_atr(serie, 14)[i])

    # As retas passam no teste de ajuste...
    assert ajuste_topo.bom(atr_i)
    # ...e ainda assim não há canal, porque o preço não fica dentro.
    contencao = est._contencao(serie, ajuste_topo.reta, ajuste_fundo.reta, inicio, i, atr_i)
    assert contencao < est.CONTENCAO_MINIMA
    assert est.detectar_canal(serie, i) is None


def test_ajuste_horizontal_e_aceito_apesar_do_r2_baixo():
    """R² degenera em dados horizontais — e um canal lateral é a figura mais limpa que existe.

    R² mede *quanta variância a reta explica*. Quando os pivôs estão todos no mesmo nível
    não há variância a explicar, e o R² despenca mesmo com ajuste perfeito. Por isso
    `Ajuste.bom` aceita também pelo erro absoluto em ATR.
    """
    pivos = [(0, 130_000.0), (10, 130_002.0), (20, 129_998.0), (30, 130_001.0)]
    ajuste = est._ajustar_reta(pivos)
    assert ajuste is not None

    assert ajuste.r2 < est.R2_MINIMO  # o R² não ajuda aqui
    assert ajuste.rmse < 5.0  # mas os pontos estão colados na reta
    assert ajuste.bom(atr=70.0)  # e é isso que decide


def test_canal_lateral_perfeito_e_detectado():
    """Consequência direta do teste anterior, no caminho completo."""
    canal = est.detectar_canal(serie_em_canal(inclinacao=0.0), 199)
    assert canal is not None
    assert canal.tipo == "lateral"


# ---------------------------------------------------------------------------
# Rompimento
# ---------------------------------------------------------------------------


def test_rompimento_exige_fechamento_fora_nao_pavio():
    """Pavio furando a borda é o canal sendo RESPEITADO — é o toque que a valida."""
    serie = serie_em_canal()
    canal = est.detectar_canal(serie, len(serie) - 1)
    assert canal is not None

    i = len(serie) - 1
    topo = canal.topo.preco_em(i)

    # Pavio muito acima, fechamento dentro: não é rompimento.
    candles = list(serie.candles)
    candles[i] = Candle(candles[i].ts, topo - 50, topo + 900, topo - 100, topo - 40, 1000.0)
    so_pavio = Serie("WIN", Timeframe.M5, candles)
    assert not any(
        r.indice == i for r in est.detectar_rompimentos(so_pavio, canal, i)
    )

    # Fechamento bem acima: é rompimento.
    candles[i] = Candle(candles[i].ts, topo, topo + 900, topo - 20, topo + 800, 1000.0)
    fechou_fora = Serie("WIN", Timeframe.M5, candles)
    achados = [r for r in est.detectar_rompimentos(fechou_fora, canal, i) if r.indice == i]
    assert len(achados) == 1
    assert achados[0].direcao == "alta"


def test_rompimentos_consecutivos_contam_como_um_evento():
    serie = serie_em_canal()
    canal = est.detectar_canal(serie, len(serie) - 1)
    assert canal is not None
    rompimentos = est.detectar_rompimentos(serie, canal, len(serie) - 1)
    indices = [r.indice for r in rompimentos]
    assert all(b - a > 3 for a, b in zip(indices, indices[1:], strict=False)) or len(indices) < 2


# ---------------------------------------------------------------------------
# Zonas
# ---------------------------------------------------------------------------


def test_faixa_precisa_de_ao_menos_dois_toques():
    """Um pivô isolado é acidente; a zona só existe com repetição."""
    assert est._faixa_do_grupo([130_000.0], "oferta") == []
    assert len(est._faixa_do_grupo([130_000.0, 130_020.0], "oferta")) == 1


def test_faixa_e_intervalo_e_nao_ponto():
    faixa = est._faixa_do_grupo([130_000.0, 130_050.0, 130_030.0], "demanda")[0]
    assert faixa.preco_min == 130_000.0
    assert faixa.preco_max == 130_050.0
    assert faixa.centro == pytest.approx(130_025.0)
    assert faixa.toques == 3


def test_detecta_zonas_quando_o_preco_repete_o_nivel():
    """Zona é repetição de preço. Numa oscilação lateral os pivôs caem sempre no mesmo
    lugar, e é exatamente isso que constitui oferta e demanda."""
    faixas = est.detectar_faixas(serie_em_canal(inclinacao=0.0), 199)
    assert len(faixas) > 0
    assert all(f.preco_max >= f.preco_min for f in faixas)
    assert all(f.tipo in {"oferta", "demanda"} for f in faixas)
    assert {f.tipo for f in faixas} == {"oferta", "demanda"}


def test_canal_inclinado_nao_produz_zona_horizontal():
    """Comportamento correto, e contraintuitivo o bastante para merecer teste.

    Num canal inclinado cada pivô acontece num preço diferente — não há nível repetido,
    logo não há zona. Um detector que "encontrasse" zonas aqui estaria agrupando preços
    que só têm em comum o fato de serem pivôs.
    """
    assert est.detectar_faixas(serie_em_canal(inclinacao=-12.0), 199) == []


# ---------------------------------------------------------------------------
# Leitura completa e serialização
# ---------------------------------------------------------------------------


def test_leitura_completa_nao_quebra_em_serie_aleatoria():
    e = est.ler(serie_aleatoria(), 199)
    assert isinstance(e.resumo, str)
    assert isinstance(e.faixas, list)


def test_serializacao_converte_indice_em_timestamp():
    serie = serie_em_canal()
    d = est.para_dict(est.ler(serie, 199), serie)

    assert "resumo" in d and "faixas" in d and "pivos" in d
    if d["canal"]:
        assert d["canal"]["topo"]["de"]["ts"] is not None
        assert d["canal"]["tipo"] in {"ascendente", "descendente", "lateral"}
    for p in d["pivos"]:
        assert p["ts"] is not None
        assert p["tipo"] in {"topo", "fundo"}


def test_estrutura_nao_olha_para_o_futuro():
    """Mesma invariante do resto do motor: ler em `i` só pode usar candles ≤ i."""
    serie = serie_em_canal(n=260)
    i = 200
    completo = est.ler(serie, i)
    truncado = est.ler(serie.fatiar(i), i)

    assert (completo.canal is None) == (truncado.canal is None)
    if completo.canal and truncado.canal:
        assert completo.canal.tipo == truncado.canal.tipo
        assert completo.canal.toques == truncado.canal.toques
    assert len(completo.pivos_topo) == len(truncado.pivos_topo)
