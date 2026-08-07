"""Testes da camada de tese.

O que se verifica aqui não é formatação: é que o dossiê **não mente**. Um cartão que diz
"convicção alta" com problemas graves embaixo é o motor discordando de si mesmo na mesma
tela — e é o defeito que faz alguém entrar num trade que não entendeu.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from trader_ai import tese as tese_mod
from trader_ai.confluencia import Avaliacao, Fator
from trader_ai.decisao import Sinal
from trader_ai.medias import RegimeMedias
from trader_ai.tipos import Contexto, Deteccao, Direcao, Familia, Tendencia, Timeframe

TS = datetime(2026, 8, 5, 15, 15)


def _ctx(volatilidade: float = 1.0) -> Contexto:
    return Contexto(
        tendencia=Tendencia.ALTA,
        forca_tendencia=0.8,
        atr=100.0,
        regime_volatilidade=volatilidade,
        janela_pregao="abertura-eua",
        peso_horario=1.15,
        indice=50,
    )


def _regime(direcao: Direcao = Direcao.ALTA) -> RegimeMedias:
    return RegimeMedias(
        ema9=130_000, sma21=129_900, sma200=129_500, rma400=129_000,
        direcao=direcao, alinhamento=1.0, distancia_atr=0.8,
        acima_da_200=True, disponivel=True,
    )


def _sinal(
    score: float = 0.8,
    confiabilidade: float = 0.7,
    rr: float = 2.5,
    regime: RegimeMedias | None = None,
    zona_quente: bool = False,
    fatores: list[Fator] | None = None,
) -> Sinal:
    deteccao = Deteccao(
        padrao_id="engolfo_alta",
        nome="Engolfo de Alta",
        familia=Familia.REVERSAO,
        direcao=Direcao.ALTA,
        indice_fim=50,
        n_candles=2,
        forca=0.9,
        confiabilidade=confiabilidade,
        extremo_superior=130_200.0,
        extremo_inferior=129_700.0,
        preco_referencia=130_150.0,
        pagina_ebook=9,
    )
    avaliacao = Avaliacao(
        deteccao=deteccao,
        score=score,
        score_sem_teto=score,
        fatores=fatores or [],
        zona_quente=zona_quente,
        regime=regime if regime is not None else _regime(),
    )
    return Sinal(
        ativo="WIN", timeframe=Timeframe.M5, ts=TS, indice=50, direcao=Direcao.ALTA,
        padrao_id="engolfo_alta", padrao_nome="Engolfo de Alta",
        entrada=130_205.0, stop=129_675.0, alvo=131_530.0, origem_alvo="zona S/R",
        risco_pontos=530.0, retorno_pontos=1325.0, rr=rr, contratos=2,
        risco_reais=214.0, retorno_reais=526.0,
        score=score, confiabilidade=confiabilidade, avaliacao=avaliacao,
    )


# ---------------------------------------------------------------------------
# Convicção
# ---------------------------------------------------------------------------


def test_score_alto_com_zona_quente_da_conviccao_alta():
    t = tese_mod.montar(_sinal(score=0.82, zona_quente=True), _ctx())
    assert t.confianca == "alta"


def test_confiabilidade_baixa_rebaixa_a_conviccao():
    """Score mede confluência; confiabilidade mede resultado. Um não cobre o outro."""
    t = tese_mod.montar(_sinal(score=0.82, confiabilidade=0.35), _ctx())
    assert t.confianca != "alta"
    assert "confiabilidade" in t.confianca_motivo


def test_dois_problemas_graves_derrubam_para_baixa():
    t = tese_mod.montar(_sinal(score=0.85, confiabilidade=0.30, rr=1.6), _ctx())
    assert t.confianca == "baixa"


def test_sem_estrutura_direcional_conta_como_problema():
    t = tese_mod.montar(_sinal(score=0.82, regime=_regime(Direcao.NEUTRA)), _ctx())
    assert t.confianca != "alta"


def test_conviccao_nunca_vem_sem_motivo():
    for score in (0.5, 0.65, 0.85):
        t = tese_mod.montar(_sinal(score=score), _ctx())
        assert t.confianca_motivo, "rótulo de convicção sem justificativa é inauditável"


# ---------------------------------------------------------------------------
# Conteúdo
# ---------------------------------------------------------------------------


def test_contra_nunca_fica_vazio():
    """Um dossiê que só lista o que favorece a operação é propaganda, não análise."""
    t = tese_mod.montar(_sinal(score=0.9, confiabilidade=0.8), _ctx())
    assert len(t.contra) >= 1


def test_fator_negativo_vira_objecao():
    fatores = [Fator("volume", 0.85, "0.4× a média")]
    t = tese_mod.montar(_sinal(fatores=fatores), _ctx())
    assert any("volume" in c for c in t.contra)


def test_volatilidade_baixa_aparece_no_contra():
    t = tese_mod.montar(_sinal(), _ctx(volatilidade=0.6))
    assert any("volatilidade" in c.lower() for c in t.contra)


def test_invalidacao_cita_o_stop_e_o_custo():
    t = tese_mod.montar(_sinal(), _ctx())
    assert "129.675" in t.invalidacao
    assert "R$" in t.invalidacao


def test_invalidacao_nao_embaralha_a_pontuacao_da_frase():
    """Regressão: formatar a frase inteira em pt-BR trocava os pontos finais por vírgulas.

    O número é formatado; a frase nunca.
    """
    t = tese_mod.montar(_sinal(), _ctx())
    assert t.invalidacao.endswith("contrato(s).")
    assert ", a leitura está errada:" in t.invalidacao
    assert "existir. Custo" in t.invalidacao


def test_quando_traz_horario_e_janela_legivel():
    t = tese_mod.montar(_sinal(), _ctx())
    assert "05/08 às 15:15" in t.quando
    assert "abertura americana" in t.quando


def test_porque_explica_o_padrao_em_portugues():
    t = tese_mod.montar(_sinal(), _ctx())
    assert any("recomprada" in r for r in t.porque)


def test_serializacao_tem_todos_os_campos():
    d = tese_mod.montar(_sinal(), _ctx()).para_dict()
    assert set(d) == {
        "onde", "quando", "porque", "contra", "invalidacao", "confianca", "confiancaMotivo",
    }
    assert isinstance(d["porque"], list)


@pytest.mark.parametrize(
    ("ativo", "stop_formatado"),
    [("WIN", "129.675,"), ("WDO", "129.675,0,")],
)
def test_invalidacao_usa_as_casas_decimais_do_ativo(ativo, stop_formatado):
    """WIN anda em passos de 5 pontos inteiros; WDO tem meio ponto.

    O `,` final de cada esperado é a vírgula da própria frase — é ela que garante que o
    número terminou ali, sem casa decimal sobrando.
    """
    s = _sinal()
    object.__setattr__(s, "ativo", ativo)
    assert f"fechar abaixo de {stop_formatado}" in tese_mod._invalidacao(s)


def test_numero_formata_no_padrao_brasileiro():
    assert tese_mod._numero(130250.5, 2) == "130.250,50"
    assert tese_mod._numero(5142.0, 1) == "5.142,0"
    assert tese_mod._numero(175750.0, 0) == "175.750"
