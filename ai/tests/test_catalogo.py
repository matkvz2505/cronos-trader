"""Varredura de sanidade sobre o catálogo inteiro.

Estes testes não checam a semântica de nenhum padrão específico — checam invariantes que
valem para os 60. É o que pega o erro que passa despercebido ao adicionar um detector
novo: desempacotar 3 candles numa janela de 2, devolver um score fora de 0..1, esquecer
de declarar a tendência exigida.
"""

from __future__ import annotations

import math

import pytest

from trader_ai.limiares import PADRAO
from trader_ai.padroes import CATALOGO, catalogo_ordenado, detectar_em
from trader_ai.tipos import Contexto, Direcao, Familia, Serie, Tendencia, Timeframe

from .conftest import ATR, doji, forca_alta, forca_baixa, martelo, vela


def _ctx(tendencia: Tendencia, indice: int = 50) -> Contexto:
    return Contexto(
        tendencia=tendencia,
        forca_tendencia=0.8,
        atr=ATR,
        regime_volatilidade=1.0,
        janela_pregao="tendencia-manha",
        peso_horario=1.15,
        indice=indice,
    )


def _janelas_de_prova(n: int) -> list[list]:
    """Várias formas de janela com `n` candles, para exercitar os ramos dos detectores."""
    base = 130_000.0
    return [
        [forca_alta(base + i * 150, i=i) for i in range(n)],
        [forca_baixa(base - i * 150, i=i) for i in range(n)],
        [doji(base + i * 10, i=i) for i in range(n)],
        [martelo(base - i * 50, i=i) for i in range(n)],
        [vela(base, base, base, base, i=i) for i in range(n)],  # candle parado
    ]


@pytest.mark.parametrize("spec", catalogo_ordenado(), ids=lambda s: s.id)
def test_detector_aceita_a_propria_janela_e_devolve_score_valido(spec):
    """Nenhum detector pode levantar exceção nem devolver score fora de 0..1.

    O caso do 'candle parado' (OHLC todos iguais) não é teórico: acontece em leilão e em
    baixa liquidez no WDO. Um detector que divide pela amplitude sem checar quebra ali.
    """
    for tendencia in (Tendencia.ALTA, Tendencia.BAIXA, Tendencia.LATERAL):
        ctx = _ctx(tendencia)
        for janela in _janelas_de_prova(spec.n_candles):
            resultado = spec.detector(janela, ctx, PADRAO)
            assert resultado is None or (
                isinstance(resultado, float)
                and math.isfinite(resultado)
                and 0.0 <= resultado <= 1.0
            ), f"{spec.id} devolveu {resultado!r}"


def test_ids_sao_unicos():
    """Garantido pelo decorator, mas explicitado aqui: um id duplicado sobrescreveria
    silenciosamente um padrão se a checagem fosse removida."""
    assert len(CATALOGO) == len({s.id for s in CATALOGO.values()})


@pytest.mark.parametrize("spec", catalogo_ordenado(), ids=lambda s: s.id)
def test_metadados_coerentes(spec):
    assert spec.n_candles >= 1
    assert 0.0 < spec.confiabilidade_ebook <= 1.0
    assert spec.pagina_ebook > 0
    # Reversão e continuação são direcionais por definição; só isolados podem ser neutros.
    if spec.familia is not Familia.ISOLADO:
        assert spec.direcao is not Direcao.NEUTRA, f"{spec.id} não tem direção"


@pytest.mark.parametrize("spec", catalogo_ordenado(), ids=lambda s: s.id)
def test_padrao_derivado_declara_o_motivo(spec):
    """Espelho inferido pelo código precisa dizer que foi inferido — ERRATA item 9."""
    if spec.derivado_por_simetria:
        assert spec.observacao, f"{spec.id} é derivado mas não explica de onde veio"


def test_continuacao_sempre_exige_tendencia():
    """Continuação sem tendência definida é contradição: não há o que continuar."""
    for spec in CATALOGO.values():
        if spec.familia is Familia.CONTINUACAO:
            assert spec.tendencia_requerida is not None, spec.id


def test_detectar_em_respeita_a_tendencia_exigida():
    """Um padrão de tendência de baixa não pode aparecer num contexto de alta."""
    candles = [forca_baixa(130_000 - i * 20, i=i) for i in range(10)]
    # Último candle fecha em 129.670; o engolfo precisa abrir abaixo disso e cobrir tudo.
    candles.append(vela(129_650, 130_200, 129_640, 130_150, i=10))
    serie = Serie("WIN", Timeframe.M5, candles)

    em_baixa = detectar_em(serie, len(candles) - 1, _ctx(Tendencia.BAIXA, len(candles) - 1))
    em_alta = detectar_em(serie, len(candles) - 1, _ctx(Tendencia.ALTA, len(candles) - 1))

    assert any(d.padrao_id == "engolfo_alta" for d in em_baixa)
    assert not any(d.padrao_id == "engolfo_alta" for d in em_alta)


def test_deteccoes_vem_ordenadas_por_score():
    candles = [forca_baixa(130_000 - i * 20, i=i) for i in range(10)]
    candles.append(vela(129_800, 130_200, 129_780, 130_150, i=10))
    serie = Serie("WIN", Timeframe.M5, candles)

    achados = detectar_em(serie, len(candles) - 1, _ctx(Tendencia.BAIXA, len(candles) - 1))
    scores = [d.score_bruto for d in achados]
    assert scores == sorted(scores, reverse=True)


def test_deteccao_registra_os_extremos_da_formacao_inteira():
    """Stop é colocado no extremo do PADRÃO, não do último candle — se os extremos
    saírem errados, todo stop sai errado."""
    c1 = forca_baixa(130_000, i=0)  # máxima 130005, mínima 129845
    c2 = vela(129_800, 130_200, 129_700, 130_150, i=1)
    serie = Serie("WIN", Timeframe.M5, [c1, c2])

    achados = detectar_em(serie, 1, _ctx(Tendencia.BAIXA, 1), apenas=["engolfo_alta"])
    assert len(achados) == 1
    d = achados[0]
    assert d.extremo_superior == pytest.approx(130_200)
    assert d.extremo_inferior == pytest.approx(129_700)


def test_score_bruto_combina_forca_e_confiabilidade():
    c1 = forca_baixa(130_000, i=0)
    c2 = vela(129_800, 130_200, 129_700, 130_150, i=1)
    serie = Serie("WIN", Timeframe.M5, [c1, c2])
    d = detectar_em(serie, 1, _ctx(Tendencia.BAIXA, 1), apenas=["engolfo_alta"])[0]
    assert d.score_bruto == pytest.approx(d.forca * d.confiabilidade)


def test_janela_curta_nao_produz_deteccao():
    """Nos primeiros candles da série não há histórico para padrões longos."""
    serie = Serie("WIN", Timeframe.M5, [forca_alta(130_000, i=0)])
    achados = detectar_em(serie, 0, _ctx(Tendencia.ALTA, 0))
    assert all(d.n_candles == 1 for d in achados)
