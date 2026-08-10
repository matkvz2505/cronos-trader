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
    """O caso exato de 10/08: venda com o 15min em alta.

    A regra existe e funciona — mas vem DESLIGADA por padrão, porque o walk-forward a
    reprovou nos dois ativos (WDO −0,036R, WIN −0,015R). Este teste liga explicitamente:
    ele guarda o mecanismo, não a decisão de usá-lo.
    """
    lim = replace(PADRAO, vetar_contra_vizinho=True)
    vies = _vies(Direcao.NEUTRA, {"15min": "alta", "30min": "lateral", "60min": "baixa"},
                 vizinho=Tendencia.ALTA)
    saida = mtf.aplicar(_avaliacao(Direcao.BAIXA), vies, lim)
    assert saida.vetos, "venda passou com o timeframe vizinho em alta"
    assert "vizinho" in saida.vetos[0]


def test_neutro_com_vizinho_a_favor_continua_passando():
    """Não inventar objeção é tão importante quanto respeitar as que existem."""
    vies = _vies(Direcao.NEUTRA, {"15min": "baixa", "60min": "alta"}, vizinho=Tendencia.BAIXA)
    assert not mtf.aplicar(_avaliacao(Direcao.BAIXA), vies).vetos


def test_neutro_com_vizinho_lateral_continua_passando():
    vies = _vies(Direcao.NEUTRA, {"15min": "lateral"}, vizinho=Tendencia.LATERAL)
    assert not mtf.aplicar(_avaliacao(Direcao.BAIXA), vies).vetos


def test_o_veto_do_vizinho_vem_desligado_por_padrao():
    """O padrão é o que a medição escolheu, não o que a intuição sugeriu.

    Foi a lição mais cara do dia: a regra é razoável, o caso que a motivou é real, e
    mesmo assim ela piora os dois ativos. Provavelmente porque o timeframe vizinho
    contrariar o gatilho é a assinatura de um pullback — que é onde entrada de reversão
    nasce. O veto matava o setup junto com o erro.
    """
    vies = _vies(Direcao.NEUTRA, {"15min": "alta"}, vizinho=Tendencia.ALTA)
    assert not mtf.aplicar(_avaliacao(Direcao.BAIXA), vies).vetos


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


def test_sem_medicao_o_padrao_usa_o_prior_do_ebook(calibracao_limpa):
    """Achatar para 0,50 parecia mais honesto. A medição discordou.

    Custou −0,076R no WDO, e o mecanismo aparece na contagem: 254 → 382 sinais. A regra
    não filtrou, **re-ranqueou** — vários padrões disparam no mesmo candle e
    `confluencia.melhor()` escolhe um; com todas as confiabilidades iguais o desempate
    muda, e passa a escolher pior.

    O que era mentira e continua consertado é a APRESENTAÇÃO: `foi_medida()` existe para
    a tela nunca mais escrever "confiabilidade medida em WDO" sobre um palpite de livro.
    """
    spec = padroes.CATALOGO["nuvem_negra"]
    assert spec.confiabilidade_ebook > 0.6
    assert confiabilidade_de(spec) == spec.confiabilidade_ebook
    assert not padroes.foi_medida(spec), "sem medição, a tela não pode dizer 'medido'"


def test_confiabilidade_achatada_continua_disponivel(calibracao_limpa):
    """A hipótese fica testável para quem mexer no desempate do `melhor()`."""
    spec = padroes.CATALOGO["nuvem_negra"]
    lim = replace(PADRAO, confiabilidade_sem_medicao=0.50)
    assert confiabilidade_de(spec, lim) == 0.50


def test_amostra_insuficiente_nao_conta_como_medicao(calibracao_limpa):
    """Três ocorrências não medem nada — e a tela não pode dizer que mediram."""
    spec = padroes.CATALOGO["nuvem_negra"]
    padroes.CALIBRACAO["nuvem_negra"] = (0.9, 3, 1.5)
    assert confiabilidade_de(spec) == spec.confiabilidade_ebook
    assert not padroes.foi_medida(spec)


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


# ---------------------------------------------------------------------------
# 4. Peso de janela do pregão — a única mudança que a medição aprovou
# ---------------------------------------------------------------------------


def test_peso_de_horario_vem_desligado():
    """Peso errado é pior que peso nenhum, e este estava preso à janela errada.

    Os pesos foram calibrados sobre a base deslocada 3h: o 1,15 da "manhã" premiava
    operações que aconteciam no meio da tarde. Desligá-los levou WDO de +0,001R para
    +0,088R e WIN de −0,060R para +0,019R — os dois ativos, mesmo sinal, com o número de
    operações praticamente igual (254→247, 297→300). Não foi filtro; foi tirar distorção.
    """
    assert PADRAO.usar_peso_horario is False


def test_com_peso_desligado_o_contexto_reporta_neutro():
    """O peso sai do score, mas o rótulo da janela continua — é informação, não nota."""
    from datetime import datetime

    from trader_ai import contexto as ctx_mod
    from trader_ai.tipos import Candle, Serie, Timeframe

    candles = [
        Candle(
            ts=datetime(2026, 8, 10, 10, 0),
            abertura=100.0,
            maxima=101.0,
            minima=99.0,
            fechamento=100.5,
            volume=10.0,
        )
    ]
    ctx = ctx_mod.ler(Serie("WDO", Timeframe.M5, candles), 0)
    assert ctx.peso_horario == 1.0
    assert ctx.janela_pregao == "manha", "o rótulo da janela não pode sumir junto"


def test_o_peso_volta_se_alguem_remedir():
    """A porta fica aberta para quem recalibrar sobre a base corrigida."""
    from datetime import datetime

    from trader_ai import contexto as ctx_mod
    from trader_ai.tipos import Candle, Serie, Timeframe

    candles = [
        Candle(
            ts=datetime(2026, 8, 10, 10, 0),
            abertura=100.0,
            maxima=101.0,
            minima=99.0,
            fechamento=100.5,
            volume=10.0,
        )
    ]
    lim = replace(PADRAO, usar_peso_horario=True)
    ctx = ctx_mod.ler(Serie("WDO", Timeframe.M5, candles), 0, lim)
    assert ctx.peso_horario == 1.15
