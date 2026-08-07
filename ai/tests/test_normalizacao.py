"""Testes da mecânica de margem e dos predicados de geometria.

Esta é a camada que todos os 60 detectores compartilham. Um bug aqui não quebra um
padrão — quebra o catálogo inteiro, e em silêncio.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from trader_ai.limiares import PADRAO
from trader_ai.normalizacao import (
    MARGEM_MINIMA,
    coincidem,
    combinar,
    e_doji,
    e_martelo_geometrico,
    e_marubozu,
    e_spinning_top,
    gap_abertura_baixa,
    gap_corpo_alta,
    gap_extremo_alta,
    razao_sombra_corpo,
    satisfaz_max,
    satisfaz_min,
)
from trader_ai.tipos import Direcao

from .conftest import ATR, martelo, marubozu_alta, vela

# ---------------------------------------------------------------------------
# Margens
# ---------------------------------------------------------------------------


def test_satisfaz_min_reprova_abaixo_do_limiar():
    assert satisfaz_min(0.5, 1.0, 1.0) is None


def test_satisfaz_min_no_limiar_devolve_o_piso():
    assert satisfaz_min(1.0, 1.0, 1.0) == pytest.approx(MARGEM_MINIMA)


def test_satisfaz_min_satura_em_um():
    assert satisfaz_min(10.0, 1.0, 1.0) == pytest.approx(1.0)


def test_satisfaz_max_e_o_espelho():
    assert satisfaz_max(1.5, 1.0, 1.0) is None
    assert satisfaz_max(1.0, 1.0, 1.0) == pytest.approx(MARGEM_MINIMA)
    assert satisfaz_max(0.0, 1.0, 1.0) == pytest.approx(1.0)


def test_combinar_propaga_falha():
    assert combinar(1.0, 0.9, None) is None


def test_combinar_e_mais_severo_que_a_media_aritmetica():
    """O elo fraco tem que dominar — é a razão de usar média harmônica."""
    margens = (MARGEM_MINIMA, 1.0)
    harmonica = combinar(*margens)
    aritmetica = sum(margens) / len(margens)
    assert harmonica is not None
    assert harmonica < aritmetica


def test_combinar_de_valores_iguais_devolve_o_proprio_valor():
    assert combinar(0.6, 0.6, 0.6) == pytest.approx(0.6)


def test_razao_sombra_corpo_trata_corpo_nulo():
    """Doji com sombra: a sombra domina completamente, sem divisão por zero."""
    assert razao_sombra_corpo(50.0, 0.0) > 100
    assert razao_sombra_corpo(0.0, 0.0) == 0.0


# ---------------------------------------------------------------------------
# Predicados
# ---------------------------------------------------------------------------


def test_doji_reconhece_corpo_desprezivel():
    assert e_doji(vela(130_000, 130_040, 129_960, 130_002)) is not None


def test_doji_rejeita_corpo_relevante():
    assert e_doji(vela(130_000, 130_100, 129_900, 130_080)) is None


def test_marubozu_exige_direcao_quando_pedida():
    c = marubozu_alta(130_000)
    assert e_marubozu(c, PADRAO, Direcao.ALTA) is not None
    assert e_marubozu(c, PADRAO, Direcao.BAIXA) is None


def test_marubozu_rejeita_sombra_grande():
    assert e_marubozu(vela(130_000, 130_200, 129_900, 130_150)) is None


def test_spinning_top_exige_sombras_dos_dois_lados():
    dois_lados = vela(130_000, 130_100, 129_900, 130_010)
    um_lado = martelo(130_000)
    assert e_spinning_top(dois_lados) is not None
    assert e_spinning_top(um_lado) is None


def test_martelo_geometrico_ignora_a_cor_do_corpo():
    """O ebook insiste: 'a cor é irrelevante'. O que importa é a sombra."""
    verde = vela(130_000, 130_013, 129_940, 130_010)
    vermelho = vela(130_010, 130_013, 129_940, 130_000)
    assert e_martelo_geometrico(verde) is not None
    assert e_martelo_geometrico(vermelho) is not None


def test_candle_de_amplitude_zero_nao_quebra():
    """Candle sem negociação (todos os preços iguais) aparece em leilão e em baixa
    liquidez. Nenhum predicado pode levantar exceção nele."""
    parado = vela(130_000, 130_000, 130_000, 130_000)
    assert e_doji(parado) is None
    assert e_marubozu(parado) is None
    assert e_martelo_geometrico(parado) is None
    assert e_spinning_top(parado) is None


# ---------------------------------------------------------------------------
# Gaps e a tolerância intraday
# ---------------------------------------------------------------------------


def test_gap_estrito_exige_separacao_real():
    lim = replace(PADRAO, tolerancia_gap_atr=0.0)
    anterior = vela(130_000, 130_100, 129_900, 130_050)
    com_gap = vela(130_150, 130_250, 130_120, 130_220)
    sem_gap = vela(130_090, 130_200, 130_080, 130_180)  # mínima abaixo da máxima anterior

    assert gap_extremo_alta(anterior, com_gap, ATR, lim) is not None
    assert gap_extremo_alta(anterior, sem_gap, ATR, lim) is None


def test_tolerancia_intraday_aceita_quase_sobreposicao():
    """ERRATA item 10 — sem folga, ~8 padrões do ebook nunca disparariam em 5min."""
    estrito = replace(PADRAO, tolerancia_gap_atr=0.0)
    tolerante = replace(PADRAO, tolerancia_gap_atr=0.08)  # 8 pontos com ATR 100

    anterior = vela(130_000, 130_100, 129_900, 130_050)
    encosta = vela(130_098, 130_200, 130_095, 130_180)  # 5 pontos de sobreposição

    assert gap_extremo_alta(anterior, encosta, ATR, estrito) is None
    assert gap_extremo_alta(anterior, encosta, ATR, tolerante) is not None


def test_gap_de_abertura_aceita_candle_que_volta_para_dentro():
    """É o caso da Linha de Perfuração: abre abaixo da mínima e sobe através dela.

    Medir esse gap pelo range inteiro tornaria o padrão impossível por construção.
    """
    lim = replace(PADRAO, tolerancia_gap_atr=0.0)
    anterior = vela(130_000, 130_010, 129_800, 129_810)
    perfura = vela(129_780, 129_960, 129_775, 129_950)

    assert gap_abertura_baixa(anterior, perfura, ATR, lim) is not None
    from trader_ai.normalizacao import gap_extremo_baixa

    assert gap_extremo_baixa(anterior, perfura, ATR, lim) is None


def test_gap_de_corpo_e_mais_permissivo_que_o_de_extremo():
    """A sombra pode sobrepor — o ebook admite isso na Interrupção de alta."""
    lim = replace(PADRAO, tolerancia_gap_atr=0.0)
    anterior = vela(130_000, 130_100, 129_900, 130_050)  # corpo até 130050
    atual = vela(130_070, 130_200, 130_020, 130_180)  # abre acima do corpo, sombra sobrepõe

    assert gap_corpo_alta(anterior, atual, ATR, lim) is not None
    assert gap_extremo_alta(anterior, atual, ATR, lim) is None


def test_coincidem_dentro_da_vizinhanca():
    """Igualdade exata de float com tick de 5 pontos nunca aconteceria."""
    assert coincidem(130_000.0, 130_005.0, ATR) is not None  # 5 pontos < 10
    assert coincidem(130_000.0, 130_050.0, ATR) is None  # 50 pontos > 10


def test_gap_sem_atr_nao_quebra():
    """No aquecimento da série o ATR ainda é zero."""
    a = vela(130_000, 130_100, 129_900, 130_050)
    b = vela(130_150, 130_250, 130_120, 130_220)
    assert gap_extremo_alta(a, b, 0.0, PADRAO) is None
