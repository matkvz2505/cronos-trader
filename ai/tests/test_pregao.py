"""O extrato do dia — o que conta como trade e o que não conta.

A distinção que este arquivo protege: **sinal emitido não é trade**. Um sinal que expirou
sem o preço chegar na entrada não moveu dinheiro nenhum, e somá-lo ao placar inflaria a
amostra com operações que nunca existiram. Foi por confundir os dois que taxas de acerto
de produtos de sinal costumam parecer melhores do que são.
"""

from __future__ import annotations

from datetime import date, datetime

from trader_ai import pregao as pregao_mod


def _sinal(**troca):
    base = {
        "id": "1",
        "ts": datetime(2026, 8, 7, 10, 5),
        "direcao": "BAIXA",
        "padraoNome": "Engolfo de Baixa",
        "janelaPregao": "manha",
        "entrada": 175825.0,
        "stop": 176405.0,
        "alvo": 174360.0,
        "riscoPontos": 580.0,
        "rr": 2.53,
        "contratos": 1,
        "score": 0.77,
        "confiabilidade": 0.5,
        "status": "ALVO",
        "resultadoPontos": 1465.0,
    }
    base.update(troca)
    return base


def test_expirado_nao_entra_no_placar_financeiro():
    expirado = _sinal(status="EXPIRADO", resultadoPontos=None)
    p = pregao_mod.montar("WIN", [expirado], date(2026, 8, 7))
    assert p.emitidos == 1
    assert p.acionados == 0
    assert p.encerrados == 0
    assert p.resultado_reais == 0.0
    # E o extrato explica por quê, em vez de mostrar um traço sem contexto.
    assert "nunca chegou na entrada" in p.entradas[0].observacao


def test_alvo_desconta_o_custo_por_contrato():
    """R$ bruto menos custo. Uma estratégia de 5min vive ou morre no custo."""
    p = pregao_mod.montar("WIN", [_sinal()], date(2026, 8, 7))
    from trader_ai.instrumentos import resolver

    inst = resolver("WIN")
    bruto = inst.reais(1465.0, 1)
    assert p.resultado_reais == bruto - inst.custo_total(1)
    assert p.resultado_reais < bruto


def test_resultado_em_r_usa_o_risco_do_proprio_sinal():
    p = pregao_mod.montar("WIN", [_sinal()], date(2026, 8, 7))
    assert p.entradas[0].resultado_r == 1465.0 / 580.0


def test_acionado_em_curso_nao_conta_resultado():
    """Trade aberto não tem resultado — tem posição. Contar seria inventar desfecho."""
    em_curso = _sinal(status="ACIONADO", resultadoPontos=None)
    p = pregao_mod.montar("WIN", [em_curso], date(2026, 8, 7))
    assert p.acionados == 1
    assert p.encerrados == 0
    assert p.resultado_reais == 0.0
    assert p.entradas[0].resultado_reais is None


def test_entradas_saem_em_ordem_cronologica():
    """O banco devolve do mais novo para o mais velho; o extrato conta a história na ordem."""
    cedo = _sinal(id="cedo", ts=datetime(2026, 8, 7, 10, 5))
    tarde = _sinal(id="tarde", ts=datetime(2026, 8, 7, 14, 30))
    p = pregao_mod.montar("WIN", [tarde, cedo], date(2026, 8, 7))
    assert [e.id for e in p.entradas] == ["cedo", "tarde"]


def test_taxa_de_acerto_ignora_os_que_nao_encerraram():
    sinais = [
        _sinal(id="a", status="ALVO", resultadoPontos=1465.0),
        _sinal(id="b", status="STOP", resultadoPontos=-580.0),
        _sinal(id="c", status="EXPIRADO", resultadoPontos=None),
        _sinal(id="d", status="ABERTO", resultadoPontos=None),
    ]
    p = pregao_mod.montar("WIN", sinais, date(2026, 8, 7))
    assert p.encerrados == 2
    assert p.taxa_acerto == 0.5


def test_dia_passado_nunca_e_reportado_como_aberto():
    p = pregao_mod.montar(
        "WIN", [], date(2026, 8, 6), agora=datetime(2026, 8, 7, 10, 0)
    )
    assert p.aberto is False


def test_dia_em_curso_dentro_do_pregao_e_aberto():
    p = pregao_mod.montar(
        "WIN", [], date(2026, 8, 7), agora=datetime(2026, 8, 7, 15, 30)
    )
    assert p.aberto is True


def test_fora_do_horario_no_mesmo_dia_nao_e_aberto():
    p = pregao_mod.montar(
        "WIN", [], date(2026, 8, 7), agora=datetime(2026, 8, 7, 19, 0)
    )
    assert p.aberto is False
