"""Testes das camadas acima do detector: instrumentos, contratos, Fibonacci, zonas,
confluência, decisão, multi-timeframe, leitura de arquivo e simulação.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from trader_ai import backtest as bt
from trader_ai import confluencia
from trader_ai import fibonacci as fib
from trader_ai import multitimeframe as mtf
from trader_ai import suporte_resistencia as sr
from trader_ai.confluencia import Avaliacao, ContextoExterno
from trader_ai.decisao import EstadoDoDia, montar
from trader_ai.fontes.contratos import (
    codigo_vigente,
    em_rollover,
    simbolo_continuo,
    vencimento,
)
from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.instrumentos import WDO, WIN, resolver
from trader_ai.limiares import PADRAO
from trader_ai.tipos import (
    Candle,
    Contexto,
    Deteccao,
    Direcao,
    Familia,
    Serie,
    Tendencia,
    Timeframe,
)

from .conftest import ATR

TS = datetime(2026, 8, 5, 10, 0)


def _serie(linhas, ativo="WIN", tf=Timeframe.M5, inicio=TS) -> Serie:
    candles = [
        Candle(inicio + timedelta(minutes=tf.value * i), a, mx, mn, f, 1000.0)
        for i, (a, mx, mn, f) in enumerate(linhas)
    ]
    return Serie(ativo, tf, candles)


def _ctx(tendencia=Tendencia.BAIXA, janela="manha", peso=1.15) -> Contexto:
    return Contexto(tendencia, 0.8, ATR, 1.0, janela, peso, 50)


def _deteccao(direcao=Direcao.ALTA, superior=130_200.0, inferior=129_700.0) -> Deteccao:
    return Deteccao(
        padrao_id="engolfo_alta",
        nome="Engolfo de Alta",
        familia=Familia.REVERSAO,
        direcao=direcao,
        indice_fim=50,
        n_candles=2,
        forca=0.9,
        confiabilidade=0.7,
        extremo_superior=superior,
        extremo_inferior=inferior,
        preco_referencia=130_150.0,
    )


# ===========================================================================
# Instrumentos
# ===========================================================================


def test_um_ponto_de_wdo_vale_cinquenta_vezes_um_ponto_de_win():
    """A diferença que mais estraga sizing: R$ 0,20 contra R$ 10,00 por ponto."""
    assert WDO.valor_ponto == WIN.valor_ponto * 50


def test_arredondamento_respeita_o_tick():
    assert WIN.arredondar(130_002.7) == 130_005.0
    assert WIN.arredondar_para_baixo(130_004.9) == 130_000.0
    assert WIN.arredondar_para_cima(130_000.1) == 130_005.0
    assert WDO.arredondar(5_432.4) == 5_432.5


def test_resolver_aceita_codigo_de_contrato():
    assert resolver("WINQ26") is WIN
    assert resolver("WDO$N") is WDO
    assert resolver("win") is WIN


def test_resolver_recusa_ativo_fora_do_escopo():
    """O produto é fechado em WIN e WDO. Aceitar PETR4 em silêncio daria sizing errado."""
    with pytest.raises(ValueError, match="fora do escopo"):
        resolver("PETR4")


# ===========================================================================
# Contratos e rollover
# ===========================================================================


def test_win_so_vence_em_meses_pares():
    with pytest.raises(ValueError, match="meses pares"):
        vencimento("WIN", 2026, 7)
    assert vencimento("WIN", 2026, 8).month == 8


def test_vencimento_do_win_cai_numa_quarta_perto_do_dia_15():
    venc = vencimento("WIN", 2026, 8)
    assert venc.weekday() == 2
    assert abs(venc.day - 15) <= 3


def test_vencimento_do_wdo_e_o_primeiro_dia_util():
    venc = vencimento("WDO", 2026, 8)
    assert venc.day <= 3
    assert venc.weekday() < 5


def test_codigo_vigente_tem_formato_de_contrato():
    codigo = codigo_vigente("WIN", date(2026, 8, 5))
    assert codigo.startswith("WIN")
    assert len(codigo) == 6
    assert codigo[3] in "FGHJKMNQUVXZ"


def test_codigo_vigente_do_win_aponta_para_mes_par():
    for mes in range(1, 13):
        codigo = codigo_vigente("WIN", date(2026, mes, 10))
        letra = codigo[3]
        mes_do_codigo = "FGHJKMNQUVXZ".index(letra) + 1
        assert mes_do_codigo % 2 == 0, f"{codigo} não é mês par"


def test_simbolo_continuo():
    assert simbolo_continuo("WINQ26") == "WIN$N"
    assert simbolo_continuo("wdo") == "WDO$N"


def test_janela_de_rollover_e_detectada():
    venc = vencimento("WIN", 2026, 8)
    assert em_rollover("WIN", venc)
    assert em_rollover("WIN", venc - timedelta(days=2))
    assert not em_rollover("WIN", venc - timedelta(days=20))


# ===========================================================================
# Fibonacci
# ===========================================================================


def _serie_com_perna_de_alta() -> Serie:
    """Cai, faz fundo, sobe, faz topo, corrige.

    A queda inicial não é enfeite: `swings` só confirma um pivô quando o preço se afasta
    dele dos dois lados. Uma série monotônica não produz nenhum fundo confirmado — e sem
    fundo **e** topo não existe perna para traçar Fibonacci.
    """
    linhas = []
    preco = 130_000.0
    for _ in range(15):  # queda inicial, forma o fundo pivô
        linhas.append((preco, preco + 10, preco - 60, preco - 50))
        preco -= 50
    for _ in range(25):  # subida, forma o topo pivô
        linhas.append((preco, preco + 60, preco - 10, preco + 50))
        preco += 50
    for _ in range(15):  # correção
        linhas.append((preco, preco + 10, preco - 60, preco - 50))
        preco -= 50
    return _serie(linhas)


def test_retracao_de_perna_de_alta_fica_abaixo_do_topo():
    perna = fib.Perna(0, 10, 129_000.0, 130_000.0)
    assert perna.direcao is Direcao.ALTA
    niveis = {n.razao: n.preco for n in fib.retracoes(perna)}
    assert niveis[0.5] == pytest.approx(129_500.0)
    assert niveis[0.618] == pytest.approx(129_382.0)
    assert all(p < 130_000.0 for p in niveis.values())


def test_retracao_de_perna_de_baixa_fica_acima_do_fundo():
    perna = fib.Perna(0, 10, 130_000.0, 129_000.0)
    assert perna.direcao is Direcao.BAIXA
    niveis = {n.razao: n.preco for n in fib.retracoes(perna)}
    assert niveis[0.5] == pytest.approx(129_500.0)
    assert all(p > 129_000.0 for p in niveis.values())


def test_niveis_nobres_sao_marcados():
    perna = fib.Perna(0, 10, 129_000.0, 130_000.0)
    nobres = {n.razao for n in fib.retracoes(perna) if n.nobre}
    assert nobres == {0.382, 0.5, 0.618}


def test_projecao_so_vale_na_direcao_da_perna():
    """Projetar alvo de compra a partir de uma perna de baixa daria um número sem
    significado — melhor devolver None."""
    perna = fib.Perna(0, 10, 129_000.0, 130_000.0)
    assert fib.alvo_por_projecao(perna, Direcao.ALTA, 1.618) == pytest.approx(130_618.0)
    assert fib.alvo_por_projecao(perna, Direcao.BAIXA, 1.618) is None


def test_nivel_proximo_respeita_a_tolerancia_em_atr():
    perna = fib.Perna(0, 10, 129_000.0, 130_000.0)
    niveis = fib.retracoes(perna)
    assert fib.nivel_proximo(129_500.0, niveis, ATR) is not None  # em cima do 50%
    assert fib.nivel_proximo(129_700.0, niveis, ATR) is None  # longe de todos


def test_ultima_perna_e_encontrada_na_serie():
    serie = _serie_com_perna_de_alta()
    perna = fib.ultima_perna(serie, len(serie) - 1)
    assert perna is not None
    assert perna.amplitude > 0


# ===========================================================================
# Suporte / resistência
# ===========================================================================


def test_incremento_redondo_se_adapta_ao_ativo():
    """WIN com ATR 100 e WDO com ATR 15 não podem usar o mesmo passo."""
    assert sr.incremento_redondo(100.0) >= 250
    assert sr.incremento_redondo(15.0) <= 100


def test_zonas_incluem_maxima_e_minima_do_dia_anterior():
    ontem = [(130_000, 130_400, 129_600, 130_100)] * 10
    hoje = [(130_100, 130_200, 130_000, 130_150)] * 10
    candles = _serie(ontem).candles + [
        Candle(TS + timedelta(days=1, minutes=5 * i), a, mx, mn, f, 1000.0)
        for i, (a, mx, mn, f) in enumerate(hoje)
    ]
    serie = Serie("WIN", Timeframe.M5, candles)

    zonas = sr.mapear(serie, len(serie) - 1, ATR)
    origens = {z.origem for z in zonas}
    assert "maxima-dia-anterior" in origens
    assert "minima-dia-anterior" in origens

    maxima = next(z for z in zonas if z.origem == "maxima-dia-anterior")
    assert maxima.preco == pytest.approx(130_400)


def test_proximo_obstaculo_ignora_zona_colada_no_preco():
    """Alvo a meio ATR não paga o risco e produziria R:R artificialmente ruim."""
    zonas = [sr.Zona(130_010.0, "pivo", 1.0), sr.Zona(130_400.0, "pivo", 1.0)]
    alvo = sr.proximo_obstaculo(130_000.0, zonas, acima=True, atr=ATR)
    assert alvo is not None
    assert alvo.preco == pytest.approx(130_400.0)


# ===========================================================================
# Confluência
# ===========================================================================


def test_horario_de_almoco_derruba_o_score():
    serie = _serie_com_perna_de_alta()
    d = _deteccao()
    bom = confluencia.avaliar(serie, len(serie) - 1, d, _ctx(janela="manha", peso=1.15))
    ruim = confluencia.avaliar(serie, len(serie) - 1, d, _ctx(janela="almoco", peso=0.60))
    assert ruim.score_sem_teto < bom.score_sem_teto


def test_correlacao_contra_penaliza_e_a_favor_bonifica():
    serie = _serie_com_perna_de_alta()
    d = _deteccao(direcao=Direcao.ALTA)
    i = len(serie) - 1

    neutro = confluencia.avaliar(serie, i, d, _ctx())
    a_favor = confluencia.avaliar(
        serie, i, d, _ctx(), externo=ContextoExterno(Direcao.ALTA, 1.0, "S&P")
    )
    contra = confluencia.avaliar(
        serie, i, d, _ctx(), externo=ContextoExterno(Direcao.BAIXA, 1.0, "S&P")
    )
    assert contra.score_sem_teto < neutro.score_sem_teto < a_favor.score_sem_teto


def test_fora_do_horario_e_veto_nao_penalidade():
    serie = _serie_com_perna_de_alta()
    avaliacao = confluencia.avaliar(
        serie, len(serie) - 1, _deteccao(), _ctx(janela="ajuste", peso=0.0)
    )
    assert avaliacao.vetos
    assert not avaliacao.aprovado_com(PADRAO)


def test_reversao_em_mercado_lateral_e_vetada():
    serie = _serie_com_perna_de_alta()
    avaliacao = confluencia.avaliar(
        serie, len(serie) - 1, _deteccao(), _ctx(tendencia=Tendencia.LATERAL)
    )
    assert any("lateral" in v for v in avaliacao.vetos)


def test_explicar_lista_os_fatores():
    serie = _serie_com_perna_de_alta()
    avaliacao = confluencia.avaliar(serie, len(serie) - 1, _deteccao(), _ctx())
    texto = avaliacao.explicar()
    assert "Engolfo de Alta" in texto
    assert "horario" in texto


# ===========================================================================
# Decisão
# ===========================================================================


def _avaliacao(score=0.8, alvo=None, direcao=Direcao.ALTA, alvos=None) -> Avaliacao:
    if alvos is None:
        alvos = [alvo] if alvo is not None else []
    return Avaliacao(
        deteccao=_deteccao(direcao=direcao),
        score=score,
        score_sem_teto=score,
        alvos_candidatos=list(alvos),
    )


def test_sinal_de_compra_tem_entrada_acima_e_stop_abaixo_do_padrao():
    serie = _serie_com_perna_de_alta()
    sinal = montar(serie, len(serie) - 1, _avaliacao(alvo=131_500.0), _ctx(), capital=50_000.0)
    assert sinal is not None
    assert sinal.entrada > sinal.avaliacao.deteccao.extremo_superior
    assert sinal.stop < sinal.avaliacao.deteccao.extremo_inferior
    assert sinal.alvo > sinal.entrada
    assert sinal.rr >= PADRAO.rr_minimo


def test_zona_que_nao_paga_o_risco_e_descartada_pela_seguinte():
    """A correção que destravou o motor em dados reais.

    Antes, bastava a zona estar do lado certo da entrada para ser adotada como alvo — uma
    zona logo acima do rompimento produzia R:R minúsculo e o sinal morria **sem nunca
    tentar a próxima**. Em 60 mil candles de WIN isso matava 1.824 de 1.938 candidatas.
    """
    serie = _serie_com_perna_de_alta()
    avaliacao = _avaliacao(alvos=[130_260.0, 131_500.0])  # a primeira não paga
    sinal = montar(serie, len(serie) - 1, avaliacao, _ctx(), capital=50_000.0)

    assert sinal is not None
    assert sinal.alvo == pytest.approx(131_500.0)
    assert sinal.origem_alvo == "zona S/R"


def test_sem_zona_que_pague_cai_para_alvo_medido():
    """Nenhuma zona serve: usa projeção de Fibonacci ou 2R fixo, nunca fica sem alvo."""
    serie = _serie_com_perna_de_alta()
    sinal = montar(
        serie, len(serie) - 1, _avaliacao(alvos=[130_260.0]), _ctx(), capital=50_000.0
    )
    assert sinal is not None
    assert sinal.origem_alvo in {"fib 1.618", "2R fixo"}
    assert sinal.rr >= PADRAO.rr_minimo


def test_precos_do_sinal_caem_em_tick_valido():
    serie = _serie_com_perna_de_alta()
    sinal = montar(serie, len(serie) - 1, _avaliacao(alvo=131_500.0), _ctx(), capital=50_000.0)
    assert sinal is not None
    for preco in (sinal.entrada, sinal.stop, sinal.alvo):
        assert preco % WIN.tick == pytest.approx(0.0)


def test_capital_maior_permite_mais_contratos():
    serie = _serie_com_perna_de_alta()
    pequeno = montar(serie, len(serie) - 1, _avaliacao(alvo=131_500.0), _ctx(), capital=20_000.0)
    grande = montar(serie, len(serie) - 1, _avaliacao(alvo=131_500.0), _ctx(), capital=200_000.0)
    assert pequeno is not None and grande is not None
    assert grande.contratos > pequeno.contratos


def test_capital_insuficiente_nao_gera_sinal():
    """Sem capital para um contrato dentro do risco configurado, não há operação."""
    serie = _serie_com_perna_de_alta()
    assert montar(serie, len(serie) - 1, _avaliacao(alvo=131_500.0), _ctx(), capital=100.0) is None


def test_avaliacao_vetada_nao_vira_sinal():
    serie = _serie_com_perna_de_alta()
    from dataclasses import replace

    vetada = replace(_avaliacao(alvo=131_500.0), vetos=["teste"])
    assert montar(serie, len(serie) - 1, vetada, _ctx(), capital=50_000.0) is None


def test_limite_de_trades_do_dia_bloqueia_novos_sinais():
    serie = _serie_com_perna_de_alta()
    estado = EstadoDoDia(dia=date(2026, 8, 5), capital=50_000.0)
    for _ in range(PADRAO.max_trades_dia):
        estado.registrar(10.0)
    assert estado.bloqueios(PADRAO)
    assert (
        montar(serie, len(serie) - 1, _avaliacao(alvo=131_500.0), _ctx(), 50_000.0, estado=estado)
        is None
    )


def test_limite_de_perda_diaria_bloqueia():
    """Capital 10.000 com limite de 3% = R$ 300 de perda máxima no dia."""
    estado = EstadoDoDia(dia=date(2026, 8, 5), capital=10_000.0)
    estado.registrar(-200.0)
    assert not estado.bloqueios(PADRAO)
    estado.registrar(-150.0)  # total -350, acima do limite
    assert any("perda diaria" in b for b in estado.bloqueios(PADRAO))


# ===========================================================================
# Multi-timeframe
# ===========================================================================


def test_agregacao_preserva_ohlc():
    linhas = [
        (100.0, 110.0, 95.0, 105.0),
        (105.0, 120.0, 100.0, 115.0),
        (115.0, 118.0, 90.0, 92.0),
    ]
    m5 = _serie(linhas, inicio=datetime(2026, 8, 5, 10, 0))
    m15 = mtf.agregar(m5, Timeframe.M15)

    assert len(m15) == 1
    barra = m15[0]
    assert barra.abertura == 100.0  # abertura do primeiro
    assert barra.maxima == 120.0  # maior das máximas
    assert barra.minima == 90.0  # menor das mínimas
    assert barra.fechamento == 92.0  # fechamento do último
    assert barra.volume == 3000.0  # soma


def test_agregacao_ancora_na_hora_cheia():
    """Ancorar no primeiro candle produziria uma barra de 15min começando às 10:07 —
    e nenhuma plataforma desenharia o mesmo gráfico."""
    linhas = [(100.0, 101.0, 99.0, 100.0)] * 6
    m5 = _serie(linhas, inicio=datetime(2026, 8, 5, 10, 7))
    m15 = mtf.agregar(m5, Timeframe.M15)
    assert m15[0].ts.minute % 15 == 0


def test_agregacao_recusa_alvo_invalido():
    m5 = _serie([(100.0, 101.0, 99.0, 100.0)] * 6)
    with pytest.raises(ValueError, match="maior"):
        mtf.agregar(m5, Timeframe.M5)


def test_indice_em_encontra_o_candle_que_contem_o_instante():
    serie = _serie([(100.0, 101.0, 99.0, 100.0)] * 10, inicio=datetime(2026, 8, 5, 10, 0))
    # 10:23 cai dentro do candle das 10:20 (índice 4)
    assert mtf.indice_em(serie, datetime(2026, 8, 5, 10, 23)) == 4
    assert mtf.indice_em(serie, datetime(2026, 8, 5, 9, 0)) is None


def test_indice_fechado_exclui_o_candle_em_formacao():
    """Às 10h35 o candle de 60min aberto às 10h ainda não fechou: sua máxima e seu
    fechamento dependem do que vai acontecer até as 11h. Usá-lo é ler o futuro."""
    h1 = _serie(
        [(100.0, 110.0, 90.0, 105.0)] * 5,
        tf=Timeframe.H1,
        inicio=datetime(2026, 8, 5, 10, 0),
    )
    momento = datetime(2026, 8, 5, 10, 35)

    assert mtf.indice_em(h1, momento) == 0  # o candle em formação
    assert mtf.indice_fechado_em(h1, momento) is None  # nenhum fechou ainda

    # Às 11h05 o candle das 10h já fechou; o das 11h está aberto.
    assert mtf.indice_fechado_em(h1, datetime(2026, 8, 5, 11, 5)) == 0
    # Exatamente às 11h o candle das 10h acabou de fechar e conta.
    assert mtf.indice_fechado_em(h1, datetime(2026, 8, 5, 11, 0)) == 0


def test_pipeline_inteira_nao_olha_para_o_futuro():
    """Invariante que sustenta passar a série inteira no laço do backtest.

    O motor roda sobre a série completa por performance — fatiar a cada candle torna o
    backtest quadrático. Isso só é legítimo porque todo indicador é causal e os pivôs
    passam por `swings_confirmados`. Este teste é a prova: rodar em `i` sobre a série
    completa tem que dar exatamente o mesmo que rodar sobre a série truncada em `i`.

    Se falhar, o backtest está lendo futuro e todo número que ele produz é ficção.
    """
    from trader_ai import contexto as ctx_mod
    from trader_ai import padroes

    serie = _serie_longa()
    for i in (80, 140, 200):
        truncada = serie.fatiar(i)

        ctx_todo = ctx_mod.ler(serie, i)
        ctx_trunc = ctx_mod.ler(truncada, i)
        assert ctx_todo.tendencia is ctx_trunc.tendencia
        assert ctx_todo.atr == pytest.approx(ctx_trunc.atr)
        assert ctx_todo.forca_tendencia == pytest.approx(ctx_trunc.forca_tendencia)

        det_todo = padroes.detectar_em(serie, i, ctx_todo)
        det_trunc = padroes.detectar_em(truncada, i, ctx_trunc)
        assert [d.padrao_id for d in det_todo] == [d.padrao_id for d in det_trunc]

        if det_todo:
            aval_todo = confluencia.avaliar(serie, i, det_todo[0], ctx_todo)
            aval_trunc = confluencia.avaliar(truncada, i, det_trunc[0], ctx_trunc)
            assert aval_todo.score_sem_teto == pytest.approx(aval_trunc.score_sem_teto)
            assert aval_todo.vetos == aval_trunc.vetos


def _serie_longa() -> Serie:
    """Série com regimes alternados, longa o bastante para todos os indicadores."""
    linhas = []
    preco = 129_000.0
    for i in range(260):
        subindo = (i // 35) % 2 == 0
        if subindo:
            linhas.append((preco, preco + 70, preco - 15, preco + 55))
            preco += 55
        else:
            linhas.append((preco, preco + 15, preco - 70, preco - 55))
            preco -= 55
    return _serie(linhas, inicio=datetime(2026, 8, 5, 10, 0))


def test_vies_neutro_quando_timeframes_divergem():
    vies = mtf.Vies(Direcao.NEUTRA, 0.0, {"15min": "alta", "30min": "baixa"}, alinhado=False)
    assert not vies.concorda_com(Direcao.ALTA)
    assert not vies.contraria(Direcao.ALTA)


def test_sinal_contra_o_vies_e_vetado():
    """O trade mais tentador e o que mais sangra: 5min contra 30 e 60."""
    avaliacao = _avaliacao(score=0.6, direcao=Direcao.ALTA)
    vies = mtf.Vies(Direcao.BAIXA, 0.9, {"15min": "baixa"}, alinhado=True)
    ajustada = mtf.aplicar(avaliacao, vies, PADRAO)
    assert ajustada.vetos


def test_sinal_excepcional_passa_contra_o_vies():
    avaliacao = _avaliacao(score=0.95, direcao=Direcao.ALTA)
    vies = mtf.Vies(Direcao.BAIXA, 0.9, {"15min": "baixa"}, alinhado=True)
    ajustada = mtf.aplicar(avaliacao, vies, PADRAO)
    assert not ajustada.vetos


def test_conjunto_de_vies_nao_inclui_o_proprio_gatilho():
    """O gatilho não pode servir de viés para si mesmo.

    Um padrão de **reversão** tem, por definição, direção oposta à tendência em que
    nasce. Se o timeframe do gatilho entrar no conjunto de viés, todo sinal de reversão
    se auto-veta. Medido antes da correção: 64 de 89 candidatas morriam nisso em WIN
    60min, sobrando 3 sinais em dois anos.
    """
    m5 = _serie([(100.0, 101.0, 99.0, 100.0)] * 600, inicio=datetime(2026, 8, 5, 10, 0))
    conjunto = mtf.montar_conjunto(m5)
    assert Timeframe.M5 not in conjunto
    assert set(conjunto) == {Timeframe.M15, Timeframe.M30, Timeframe.H1}

    h1 = _serie([(100.0, 101.0, 99.0, 100.0)] * 300, tf=Timeframe.H1)
    # Gatilho em 60min não tem timeframe acima no conjunto de viés: fica sem viés.
    assert mtf.montar_conjunto(h1) == {}


def test_sem_vies_a_avaliacao_passa_intacta():
    """Ausência de informação não é informação contrária."""
    vies = mtf.calcular_vies({}, datetime(2026, 8, 5, 10, 0))
    assert vies.direcao is Direcao.NEUTRA

    avaliacao = _avaliacao(score=0.6, direcao=Direcao.ALTA)
    ajustada = mtf.aplicar(avaliacao, vies, PADRAO)
    assert not ajustada.vetos
    assert ajustada.score_sem_teto == pytest.approx(avaliacao.score_sem_teto)


def test_vies_a_favor_aumenta_o_score():
    avaliacao = _avaliacao(score=0.6, direcao=Direcao.ALTA)
    vies = mtf.Vies(Direcao.ALTA, 1.0, {"15min": "alta"}, alinhado=True)
    ajustada = mtf.aplicar(avaliacao, vies, PADRAO)
    assert ajustada.score_sem_teto > avaliacao.score_sem_teto


# ===========================================================================
# Leitura de arquivo
# ===========================================================================


def test_le_csv_simples(tmp_path):
    caminho = tmp_path / "WIN_M5.csv"
    caminho.write_text(
        "datetime,open,high,low,close,volume\n"
        "2026-08-05 10:00:00,130000,130100,129900,130050,1500\n"
        "2026-08-05 10:05:00,130050,130200,130000,130150,1800\n",
        encoding="utf-8",
    )
    serie = ler_arquivo(caminho, "WIN", Timeframe.M5)
    assert len(serie) == 2
    assert serie[0].abertura == 130_000
    assert serie[1].volume == 1800


def test_le_exportacao_tabulada_do_mt5(tmp_path):
    caminho = tmp_path / "win.txt"
    caminho.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\n"
        "2026.08.05\t10:00:00\t130000\t130100\t129900\t130050\t1500\n",
        encoding="utf-8",
    )
    serie = ler_arquivo(caminho, "WIN", Timeframe.M5)
    assert len(serie) == 1
    assert serie[0].fechamento == 130_050


def test_aceita_virgula_decimal_brasileira(tmp_path):
    """`130.250,00` lido como 130250 e não como 130,25."""
    caminho = tmp_path / "wdo.csv"
    caminho.write_text(
        "datetime;open;high;low;close\n2026-08-05 10:00:00;5.432,50;5.440,00;5.430,00;5.438,50\n",
        encoding="utf-8",
    )
    serie = ler_arquivo(caminho, "WDO", Timeframe.M5)
    assert serie[0].abertura == pytest.approx(5432.50)
    assert serie[0].maxima == pytest.approx(5440.00)


def test_ordena_e_remove_duplicatas(tmp_path):
    """Concatenar dois arquivos com período sobreposto é o jeito comum de conseguir
    histórico longo — o loader precisa aguentar."""
    caminho = tmp_path / "WIN_M5.csv"
    caminho.write_text(
        "datetime,open,high,low,close\n"
        "2026-08-05 10:05:00,2,2,2,2\n"
        "2026-08-05 10:00:00,1,1,1,1\n"
        "2026-08-05 10:05:00,3,3,3,3\n",
        encoding="utf-8",
    )
    serie = ler_arquivo(caminho, "WIN", Timeframe.M5)
    assert len(serie) == 2
    assert [c.abertura for c in serie] == [1, 3]  # ordenado, última duplicata vence


def test_recusa_candle_incoerente(tmp_path):
    from trader_ai.fontes.base import FonteIndisponivel

    caminho = tmp_path / "WIN_M5.csv"
    caminho.write_text(
        "datetime,open,high,low,close\n2026-08-05 10:00:00,100,90,110,105\n", encoding="utf-8"
    )
    with pytest.raises(FonteIndisponivel, match="abaixo da mínima"):
        ler_arquivo(caminho, "WIN", Timeframe.M5)


# ===========================================================================
# Simulação
# ===========================================================================


def _sinal_de_teste(entrada=130_100.0, stop=129_900.0, alvo=130_500.0):
    from trader_ai.decisao import Sinal

    return Sinal(
        ativo="WIN",
        timeframe=Timeframe.M5,
        ts=TS,
        indice=0,
        direcao=Direcao.ALTA,
        padrao_id="engolfo_alta",
        padrao_nome="Engolfo de Alta",
        entrada=entrada,
        stop=stop,
        alvo=alvo,
        origem_alvo="teste",
        risco_pontos=entrada - stop,
        retorno_pontos=alvo - entrada,
        rr=(alvo - entrada) / (entrada - stop),
        contratos=1,
        risco_reais=40.0,
        retorno_reais=80.0,
        score=0.8,
        confiabilidade=0.7,
        avaliacao=_avaliacao(),
    )


def test_empate_entre_stop_e_alvo_resolve_como_stop():
    """Sem tick a tick não há como saber a ordem. Supor o alvo inflaria a estatística
    de toda estratégia de alvo curto — então o empate resolve contra nós."""
    serie = _serie(
        [
            (130_000, 130_050, 129_950, 130_000),  # sinal nasce aqui
            (130_050, 130_150, 130_000, 130_120),  # aciona a entrada em 130.100
            (130_120, 130_600, 129_800, 130_000),  # abraça stop E alvo
        ]
    )
    operacao = bt._simular(serie, 0, _sinal_de_teste(), WIN, max_espera=3)
    assert operacao.desfecho == "stop"
    assert operacao.resultado_reais < 0


def test_alvo_atingido_gera_resultado_positivo():
    serie = _serie(
        [
            (130_000, 130_050, 129_950, 130_000),
            (130_050, 130_150, 130_000, 130_120),
            (130_120, 130_600, 130_100, 130_550),
        ]
    )
    operacao = bt._simular(serie, 0, _sinal_de_teste(), WIN, max_espera=3)
    assert operacao.desfecho == "alvo"
    assert operacao.resultado_reais > 0
    assert operacao.resultado_em_r == pytest.approx(2.0)


def test_sinal_nao_acionado_nao_conta_como_perda():
    serie = _serie(
        [
            (130_000, 130_050, 129_950, 130_000),
            (130_000, 130_020, 129_900, 129_950),
            (129_950, 130_000, 129_800, 129_850),
        ]
    )
    operacao = bt._simular(serie, 0, _sinal_de_teste(), WIN, max_espera=2)
    assert operacao.desfecho == "nao_acionado"
    assert not operacao.acionada
    assert operacao.resultado_reais == 0.0


def test_posicao_e_encerrada_no_fim_do_pregao():
    """Day trade não carrega posição para o dia seguinte."""
    dia1 = [
        (130_000, 130_050, 129_950, 130_000),
        (130_050, 130_150, 130_000, 130_120),
        (130_120, 130_200, 130_050, 130_180),
    ]
    candles = _serie(dia1).candles + [
        Candle(TS + timedelta(days=1), 130_180, 130_600, 130_150, 130_550, 1000.0)
    ]
    serie = Serie("WIN", Timeframe.M5, candles)

    operacao = bt._simular(serie, 0, _sinal_de_teste(), WIN, max_espera=3)
    assert operacao.desfecho == "fim_do_dia"
    assert operacao.preco_saida == 130_180


def test_custos_sao_descontados_do_resultado():
    serie = _serie(
        [
            (130_000, 130_050, 129_950, 130_000),
            (130_050, 130_150, 130_000, 130_120),
            (130_120, 130_600, 130_100, 130_550),
        ]
    )
    operacao = bt._simular(serie, 0, _sinal_de_teste(), WIN, max_espera=3)
    bruto = WIN.reais(operacao.resultado_pontos, 1)
    assert operacao.resultado_reais == pytest.approx(bruto - WIN.custo_total(1))
    assert operacao.resultado_reais < bruto


def test_walk_forward_recusa_serie_curta():
    serie = _serie([(100.0, 101.0, 99.0, 100.0)] * 50)
    with pytest.raises(ValueError, match="curta demais"):
        bt.walk_forward(serie, janelas=4)


def test_backtest_roda_de_ponta_a_ponta_sem_quebrar():
    """Não afirma lucro — afirma que a pipeline inteira executa e produz relatório."""
    linhas = []
    preco = 129_000.0
    for i in range(400):
        subindo = (i // 40) % 2 == 0
        if subindo:
            linhas.append((preco, preco + 70, preco - 15, preco + 55))
            preco += 55
        else:
            linhas.append((preco, preco + 15, preco - 70, preco - 55))
            preco -= 55
    serie = _serie(linhas, inicio=datetime(2026, 8, 5, 10, 0))

    resultado = bt.rodar(serie, capital=50_000.0)
    assert isinstance(resultado.relatorio(), str)
    assert resultado.taxa_acerto >= 0.0
    for operacao in resultado.operacoes:
        assert operacao.desfecho in {
            "alvo",
            "stop",
            "fim_do_dia",
            "fim_da_serie",
            "nao_acionado",
        }


def test_calibracao_ignora_amostra_insuficiente():
    resultado = bt.Resultado(ativo="WIN", timeframe=Timeframe.M5)
    magro = bt.Estatistica(padrao_id="harami_alta", nome="Harami de Alta", n=3, acertos=3)
    gordo = bt.Estatistica(padrao_id="engolfo_alta", nome="Engolfo de Alta", n=50, acertos=30)
    resultado.por_padrao = {"harami_alta": magro, "engolfo_alta": gordo}

    from trader_ai import padroes

    anterior = dict(padroes.CALIBRACAO)
    try:
        padroes.CALIBRACAO.clear()
        calibrado = bt.calibrar(resultado)
        assert "harami_alta" not in calibrado  # 3 ocorrências não é evidência
        # A calibração guarda (taxa, n, expectância): acerto sozinho não decide nada.
        taxa, n, _expectancia = calibrado["engolfo_alta"]
        assert (taxa, n) == (pytest.approx(0.6), 50)
    finally:
        padroes.CALIBRACAO.clear()
        padroes.CALIBRACAO.update(anterior)
