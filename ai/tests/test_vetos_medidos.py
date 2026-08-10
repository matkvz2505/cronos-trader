"""As três regras nascidas do pregão de 10/08/2026, em que o motor vendeu na alta.

Naquele dia o WDO marcou `viés neutra (0%) [15min=alta, 30min=lateral, 60min=baixa]` e o
motor aprovou duas vendas. A informação para recusar as duas já estava dentro dele — 15min
em alta, expectância medida negativa, confiabilidade que era palpite de livro — e nenhuma
tinha poder de veto. Estes testes dão esse poder e o mantêm.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from trader_ai import multitimeframe as mtf
from trader_ai import padroes
from trader_ai.limiares import PADRAO
from trader_ai.padroes.base import EspecPadrao, confiabilidade_de, expectancia_medida
from trader_ai.tipos import Direcao, Familia, Tendencia


def _vies(direcao, votos, vizinho, forca=0.0):
    return mtf.Vies(direcao, forca, votos, alinhado=False, vizinho=vizinho)


# ---------------------------------------------------------------------------
# 1. Viés neutro por discordância não é permissão
# ---------------------------------------------------------------------------


def _avaliacao(direcao=Direcao.BAIXA, score=0.5):
    from trader_ai.confluencia import Avaliacao
    from trader_ai.tipos import Deteccao

    deteccao = Deteccao(
        padrao_id="nuvem_negra",
        nome="Nuvem Negra",
        familia=Familia.REVERSAO,
        direcao=direcao,
        indice_fim=10,
        n_candles=2,
        forca=1.0,
        confiabilidade=0.5,
        extremo_superior=5130.0,
        extremo_inferior=5120.0,
        preco_referencia=5124.0,
    )
    return Avaliacao(deteccao=deteccao, score=score, score_sem_teto=score, fatores=[])


def test_neutro_com_vizinho_contrario_veta():
    """O caso exato de 10/08: venda com o 15min em alta."""
    vies = _vies(Direcao.NEUTRA, {"15min": "alta", "30min": "lateral", "60min": "baixa"},
                 vizinho=Tendencia.ALTA)
    saida = mtf.aplicar(_avaliacao(Direcao.BAIXA), vies)
    assert saida.vetos, "venda passou com o timeframe vizinho em alta"
    assert "vizinho" in saida.vetos[0]


def test_neutro_com_vizinho_a_favor_continua_passando():
    """Não inventar objeção é tão importante quanto respeitar as que existem."""
    vies = _vies(Direcao.NEUTRA, {"15min": "baixa", "60min": "alta"}, vizinho=Tendencia.BAIXA)
    assert not mtf.aplicar(_avaliacao(Direcao.BAIXA), vies).vetos


def test_neutro_com_vizinho_lateral_continua_passando():
    vies = _vies(Direcao.NEUTRA, {"15min": "lateral"}, vizinho=Tendencia.LATERAL)
    assert not mtf.aplicar(_avaliacao(Direcao.BAIXA), vies).vetos


def test_o_veto_do_vizinho_pode_ser_desligado_para_medicao():
    """É um flag para o walk-forward medir com e sem — não uma verdade assumida."""
    vies = _vies(Direcao.NEUTRA, {"15min": "alta"}, vizinho=Tendencia.ALTA)
    lim = replace(PADRAO, vetar_contra_vizinho=False)
    assert not mtf.aplicar(_avaliacao(Direcao.BAIXA), vies, lim).vetos


def test_vies_direcional_contrario_continua_vetando():
    """A regra antiga não pode ter sido substituída pela nova."""
    votos = {"15min": "alta", "30min": "alta"}
    vies = _vies(Direcao.ALTA, votos, vizinho=Tendencia.ALTA, forca=0.8)
    assert mtf.aplicar(_avaliacao(Direcao.BAIXA, score=0.5), vies).vetos


# ---------------------------------------------------------------------------
# 2. Prior do ebook não vale ponto
# ---------------------------------------------------------------------------


def _spec(id_: str, prior: float) -> EspecPadrao:
    return padroes.CATALOGO[id_] if id_ in padroes.CATALOGO else None


@pytest.fixture
def calibracao_limpa():
    anterior = dict(padroes.CALIBRACAO)
    padroes.CALIBRACAO.clear()
    yield
    padroes.CALIBRACAO.clear()
    padroes.CALIBRACAO.update(anterior)


def test_padrao_sem_medicao_vale_neutro_e_nao_o_prior(calibracao_limpa):
    """A Nuvem Negra entrou numa venda de WDO com "confiabilidade 70%" do ebook.

    Não havia uma única medição dela em WDO. O prior é palpite de livro sobre ações
    americanas; usá-lo como peso empurra para cima o score de quem não se conhece.
    """
    spec = padroes.CATALOGO["nuvem_negra"]
    assert spec.confiabilidade_ebook > 0.6, "o prior do ebook é alto — é esse o problema"
    assert confiabilidade_de(spec) == PADRAO.confiabilidade_sem_medicao


def test_amostra_insuficiente_tambem_vale_neutro(calibracao_limpa):
    spec = padroes.CATALOGO["nuvem_negra"]
    padroes.CALIBRACAO["nuvem_negra"] = (0.9, 3, 1.5)
    assert confiabilidade_de(spec) == PADRAO.confiabilidade_sem_medicao


def test_medicao_com_amostra_manda(calibracao_limpa):
    spec = padroes.CATALOGO["nuvem_negra"]
    padroes.CALIBRACAO["nuvem_negra"] = (0.42, PADRAO.amostra_minima_confiabilidade, -0.1)
    assert confiabilidade_de(spec) == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# 3. Expectância medida negativa mata o sinal
# ---------------------------------------------------------------------------


def test_expectancia_negativa_medida_e_visivel(calibracao_limpa):
    """`tres_por_dentro_baixa` do WDO: 50% de acerto e −0,300R."""
    spec = padroes.CATALOGO["tres_por_dentro_baixa"]
    padroes.CALIBRACAO["tres_por_dentro_baixa"] = (
        0.5,
        PADRAO.amostra_minima_confiabilidade,
        -0.300,
    )
    assert expectancia_medida(spec) == pytest.approx(-0.300)


def test_expectancia_sem_amostra_nao_e_reportada(calibracao_limpa):
    """Dois trades não medem expectância — e não podem vetar nem liberar."""
    spec = padroes.CATALOGO["tres_por_dentro_baixa"]
    padroes.CALIBRACAO["tres_por_dentro_baixa"] = (0.5, 2, -0.300)
    assert expectancia_medida(spec) is None
