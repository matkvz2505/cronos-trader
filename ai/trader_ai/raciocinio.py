"""O que o motor está pensando agora — com a conta aberta.

Este módulo existe porque o diferencial do produto não é acertar mais que os outros: é
**mostrar a conta**. Um robô que só diz "COMPRA 175.750" pede fé. Uma sala ao vivo diz
"olha o repique aí" e some quando dá errado. Aqui a pergunta que se responde é outra:

    o que você está vendo, com que número, e por que ainda NÃO é entrada?

O último pedaço é o que mais importa. Em 60 mil candles, 33.751 detecções viraram 293
sinais — 99,1% foram recusadas. Um produto que esconde as recusas parece um oráculo; um
que as mostra vira ferramenta de estudo. É a recusa explicada que ensina a operar.

Nada aqui decide nada. É leitura: pega o estado das seis camadas do motor num instante e
organiza para consumo humano.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from . import confluencia, multitimeframe, padroes
from . import contexto as ctx_mod
from . import estrutura as est
from . import fibonacci as fib
from . import medias as medias_mod
from .decisao import montar
from .indicadores import bollinger, macd, rsi
from .limiares import PADRAO, Limiares
from .tipos import Contexto, Direcao, Serie, Tendencia, Timeframe

TIMEFRAMES_PAINEL = (Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1)

MINUTOS_PARA_DADO_VELHO = 15.0
"""Acima disso a leitura deixa de ser "ao vivo".

Três candles de 5 minutos. Com o coletor rodando, o atraso normal é de segundos; passar
de 15 minutos significa que o coletor caiu, o terminal fechou ou o pregão acabou. Em
qualquer um dos casos a tela precisa parar de se apresentar como tempo real.
"""


@dataclass(frozen=True, slots=True)
class Conta:
    """Uma conta que o motor fez, com o número e o que ele significa.

    `formula` existe para que nenhum número apareça na tela sem procedência. É a
    diferença entre "força 0,72" e "força 0,72 = média harmônica de (0,9 · 0,6)".
    """

    rotulo: str
    valor: str
    formula: str = ""
    veredito: str = ""
    tom: str = "neutro"  # neutro | favoravel | contrario


@dataclass(frozen=True, slots=True)
class LeituraTimeframe:
    timeframe: str
    tendencia: str
    forca_tendencia: float
    fechamento: float
    atr: float
    regime_medias: str
    direcao_medias: str
    alinhamento: float
    contas: list[Conta] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Vigilancia:
    """Um padrão que apareceu e **não** virou sinal, com o motivo exato.

    É o coração da tela ao vivo. Um operador aprende mais vendo por que 40 setups foram
    recusados do que vendo os 2 aprovados.
    """

    padrao: str
    direcao: str
    forca: float
    score: float
    motivo: str
    faltou: str


@dataclass(frozen=True, slots=True)
class Raciocinio:
    ativo: str
    momento: str
    """Timestamp do último candle — não é a hora atual."""

    idade_minutos: float
    """Quantos minutos se passaram desde o último candle.

    É o número que diz se a tela está **de fato** ao vivo. Sem ele, uma leitura de ontem
    às 15h30 aparece com a mesma cara de uma leitura de agora — e o operador acredita
    estar vendo o mercado quando está vendo história.
    """

    dados_frescos: bool
    preco: float
    variacao_dia: float

    vies: str
    vies_direcao: str
    alinhado: bool

    timeframes: list[LeituraTimeframe] = field(default_factory=list)
    estrutura: dict = field(default_factory=dict)
    niveis: list[dict] = field(default_factory=list)
    vigiando: list[Vigilancia] = field(default_factory=list)
    sinal: dict | None = None
    janela_pregao: str = ""
    opera_agora: bool = False
    veredito: str = ""


def _contas_do_timeframe(
    serie: Serie, i: int, ctx: Contexto, regime: medias_mod.RegimeMedias
) -> list[Conta]:
    """Os números que sustentam a leitura daquele timeframe."""
    contas: list[Conta] = []
    preco = serie[i].fechamento

    if regime.disponivel and regime.sma21 is not None:
        distancia = regime.distancia_atr
        contas.append(
            Conta(
                rotulo="Distância da SMA21",
                valor=f"{distancia:+.2f} ATR",
                formula=f"({preco:,.0f} − {regime.sma21:,.0f}) ÷ {ctx.atr:,.0f}".replace(",", "."),
                veredito=(
                    "esticado — reversão à média puxa contra"
                    if abs(distancia) > 2.0
                    else "dentro da faixa normal"
                ),
                tom="contrario" if abs(distancia) > 2.0 else "neutro",
            )
        )

    valores_rsi = serie.memo("rsi_14", lambda: rsi(serie.fechamento, 14))
    if i < len(valores_rsi) and not np.isnan(valores_rsi[i]):
        r = float(valores_rsi[i])
        contas.append(
            Conta(
                rotulo="IFR (14)",
                valor=f"{r:.0f}",
                formula="Wilder 14 sobre fechamentos",
                veredito=(
                    "sobrecomprado" if r >= 70 else "sobrevendido" if r <= 30 else "neutro"
                ),
                tom="contrario" if r >= 70 or r <= 30 else "neutro",
            )
        )

    linha, sinal_macd, _ = serie.memo("macd", lambda: macd(serie.fechamento))
    if i < len(linha) and not np.isnan(linha[i]) and not np.isnan(sinal_macd[i]):
        hist = linha[i] - sinal_macd[i]
        contas.append(
            Conta(
                rotulo="MACD histograma",
                valor=f"{hist:+.1f}",
                formula="EMA12 − EMA26, menos a EMA9 disso",
                veredito="momento comprador" if hist > 0 else "momento vendedor",
                tom="favoravel" if hist > 0 else "contrario",
            )
        )

    sup, meio, inf = serie.memo("bb_20", lambda: bollinger(serie.fechamento, 20, 2.0))
    if i < len(sup) and not np.isnan(sup[i]) and ctx.atr > 0:
        largura = (sup[i] - inf[i]) / ctx.atr
        posicao = (preco - inf[i]) / (sup[i] - inf[i]) if sup[i] > inf[i] else 0.5
        contas.append(
            Conta(
                rotulo="Bollinger",
                valor=f"{posicao:.0%} da banda",
                formula=f"largura {largura:.1f} ATR (20 períodos, 2σ)",
                veredito=(
                    "compressão — costuma preceder movimento, sem dizer a direção"
                    if largura < 2.0
                    else "banda aberta"
                ),
            )
        )

    contas.append(
        Conta(
            rotulo="ADX",
            valor=f"{ctx.forca_tendencia:.0%} de força",
            formula="Wilder 14; abaixo de 20 o contexto vira LATERAL",
            veredito=(
                "sem tendência — padrão de reversão não tem o que reverter"
                if ctx.tendencia is Tendencia.LATERAL
                else f"tendência de {ctx.tendencia.value}"
            ),
            tom="contrario" if ctx.tendencia is Tendencia.LATERAL else "favoravel",
        )
    )

    return contas


def _niveis_ativos(serie: Serie, i: int, ctx: Contexto, lim: Limiares) -> list[dict]:
    """Preços que importam agora, ordenados por distância."""
    preco = serie[i].fechamento
    niveis: list[dict] = []

    perna = fib.ultima_perna(serie, i, lim)
    if perna is not None and perna.amplitude > 0:
        for nivel in fib.retracoes(perna):
            relevancia = fib.relevancia(serie.ativo, nivel.razao)
            if relevancia <= 0:
                continue
            niveis.append(
                {
                    "preco": nivel.preco,
                    "rotulo": nivel.rotulo,
                    "origem": "fibonacci",
                    "peso": relevancia,
                    "nota": f"medido: {relevancia:.2f}× a vizinhança em {serie.ativo}",
                }
            )

    regime = medias_mod.ler(serie, i, ctx.atr)
    for nome, valor in (
        ("EMA 9", regime.ema9),
        ("SMA 21", regime.sma21),
        ("SMA 200", regime.sma200),
        ("RMA 400", regime.rma400),
    ):
        if valor is not None:
            niveis.append(
                {"preco": valor, "rotulo": nome, "origem": "media", "peso": 1.0, "nota": ""}
            )

    estrutura = est.ler(serie, i, lim)
    for faixa in estrutura.faixas:
        faixa_texto = f"{faixa.preco_min:,.0f}–{faixa.preco_max:,.0f}".replace(",", ".")
        niveis.append(
            {
                "preco": faixa.centro,
                "rotulo": f"zona de {faixa.tipo}",
                "origem": "estrutura",
                "peso": faixa.forca,
                "nota": f"{faixa.toques} toques · {faixa_texto}",
            }
        )

    niveis.sort(key=lambda n: abs(n["preco"] - preco))
    return niveis[:10]


def _vigilancia(
    serie: Serie, i: int, ctx: Contexto, lim: Limiares, conjunto: dict
) -> list[Vigilancia]:
    """Padrões detectados que **não** viraram sinal, com o motivo de cada recusa.

    Reconstrói a recusa em vez de pedir o motivo ao motor: `decisao.montar` devolve
    `None` sem explicar, e mudá-lo para devolver motivo poluiria a assinatura do caminho
    quente por causa de uma tela.
    """
    achados: list[Vigilancia] = []

    for deteccao in padroes.detectar_em(serie, i, ctx, lim)[:8]:
        avaliacao = confluencia.avaliar(serie, i, deteccao, ctx, lim)

        if avaliacao.vetos:
            achados.append(
                Vigilancia(
                    padrao=deteccao.nome,
                    direcao=deteccao.direcao.value,
                    forca=round(deteccao.forca, 2),
                    score=round(avaliacao.score, 2),
                    motivo="vetado",
                    faltou=avaliacao.vetos[0],
                )
            )
            continue

        if avaliacao.score < lim.score_minimo_sinal:
            falta = lim.score_minimo_sinal - avaliacao.score
            achados.append(
                Vigilancia(
                    padrao=deteccao.nome,
                    direcao=deteccao.direcao.value,
                    forca=round(deteccao.forca, 2),
                    score=round(avaliacao.score, 2),
                    motivo="score abaixo do corte",
                    faltou=f"faltam {falta:.2f} para o mínimo de {lim.score_minimo_sinal:.2f}",
                )
            )
            continue

        if conjunto:
            vies = multitimeframe.calcular_vies(conjunto, serie[i].ts, lim)
            ajustada = multitimeframe.aplicar(avaliacao, vies, lim)
            if not ajustada.aprovado_com(lim):
                achados.append(
                    Vigilancia(
                        padrao=deteccao.nome,
                        direcao=deteccao.direcao.value,
                        forca=round(deteccao.forca, 2),
                        score=round(ajustada.score, 2),
                        motivo="contra o viés dos timeframes maiores",
                        faltou=vies.descrever(),
                    )
                )
                continue
            avaliacao = ajustada

        if montar(serie, i, avaliacao, ctx, capital=20_000.0, lim=lim) is None:
            achados.append(
                Vigilancia(
                    padrao=deteccao.nome,
                    direcao=deteccao.direcao.value,
                    forca=round(deteccao.forca, 2),
                    score=round(avaliacao.score, 2),
                    motivo="R:R insuficiente",
                    faltou=f"nenhum alvo à frente paga {lim.rr_minimo:.1f}× o risco",
                )
            )

    return achados


def ler(
    series: dict[Timeframe, Serie], capital: float = 20_000.0, lim: Limiares = PADRAO
) -> Raciocinio:
    """Monta o dossiê ao vivo a partir das séries de todos os timeframes."""
    base = series.get(Timeframe.M5)
    if base is None or len(base) < lim.tendencia_min_candles:
        raise ValueError("série de 5 minutos insuficiente para raciocinar")

    limiares = lim.para_timeframe(Timeframe.M5)
    i = len(base) - 1
    ctx = ctx_mod.ler(base, i, limiares)
    preco = base[i].fechamento

    # Variação do dia: contra a abertura do pregão corrente, não contra o candle anterior.
    hoje = base[i].ts.date()
    do_dia = [c for c in base.candles if c.ts.date() == hoje]
    abertura = do_dia[0].abertura if do_dia else preco
    variacao = ((preco - abertura) / abertura * 100) if abertura else 0.0

    leituras: list[LeituraTimeframe] = []
    for tf in TIMEFRAMES_PAINEL:
        serie_tf = series.get(tf)
        if serie_tf is None or len(serie_tf) < limiares.tendencia_min_candles:
            continue
        j = len(serie_tf) - 1
        ctx_tf = ctx_mod.ler(serie_tf, j, lim.para_timeframe(tf))
        regime = medias_mod.ler(serie_tf, j, ctx_tf.atr)
        leituras.append(
            LeituraTimeframe(
                timeframe=tf.rotulo,
                tendencia=ctx_tf.tendencia.value,
                forca_tendencia=round(ctx_tf.forca_tendencia, 3),
                fechamento=serie_tf[j].fechamento,
                atr=round(ctx_tf.atr, 2),
                regime_medias=regime.descricao,
                direcao_medias=regime.direcao.value,
                alinhamento=round(regime.alinhamento, 2),
                contas=_contas_do_timeframe(serie_tf, j, ctx_tf, regime),
            )
        )

    conjunto = {tf: s for tf, s in series.items() if tf.value > Timeframe.M5.value}
    vies = multitimeframe.calcular_vies(conjunto, base[i].ts, limiares)
    estrutura = est.ler(base, i, limiares)
    vigiando = _vigilancia(base, i, ctx, limiares, conjunto)

    # Se algum padrão passou por tudo, ele vira o sinal do momento.
    sinal_dict = None
    deteccoes = padroes.detectar_em(base, i, ctx, limiares)
    if deteccoes:
        avaliacao = confluencia.melhor(base, i, deteccoes, ctx, limiares)
        if avaliacao is not None:
            if conjunto:
                avaliacao = multitimeframe.aplicar(avaliacao, vies, limiares)
            if avaliacao.aprovado_com(limiares):
                sinal = montar(base, i, avaliacao, ctx, capital, limiares)
                if sinal is not None:
                    from .pipeline import sinal_para_dict

                    sinal_dict = sinal_para_dict(sinal)

    # Estado do mercado pelo RELÓGIO, não pelo candle.
    #
    # `ctx.janela_pregao` descreve a janela em que aquele **candle** aconteceu — é o que
    # a confluência precisa, e está certo para o backtest. Mas para a tela ao vivo a
    # pergunta é outra: o mercado está aberto AGORA? Usar o candle aqui fazia a tela
    # dizer "pregão aberto · abertura-eua" às 4 da manhã, porque o último candle era das
    # 15h30 do dia anterior.
    agora = datetime.now()
    janela_agora = ctx_mod.janela_de(agora.time())
    mercado_aberto = janela_agora.opera and agora.weekday() < 5
    idade = max(0.0, (agora - base[i].ts).total_seconds() / 60.0)
    frescos = idade <= MINUTOS_PARA_DADO_VELHO

    return Raciocinio(
        ativo=base.ativo,
        momento=base[i].ts.isoformat(),
        idade_minutos=round(idade, 1),
        dados_frescos=frescos,
        preco=preco,
        variacao_dia=round(variacao, 2),
        vies=vies.descrever(),
        vies_direcao=vies.direcao.value,
        alinhado=vies.alinhado,
        timeframes=leituras,
        estrutura=est.para_dict(estrutura, base),
        niveis=_niveis_ativos(base, i, ctx, limiares),
        vigiando=vigiando,
        sinal=sinal_dict,
        janela_pregao=janela_agora.rotulo,
        opera_agora=mercado_aberto,
        veredito=_veredito(ctx, vies, sinal_dict, vigiando, mercado_aberto, idade, frescos),
    )


def _veredito(
    ctx: Contexto,
    vies,
    sinal: dict | None,
    vigiando: list[Vigilancia],
    mercado_aberto: bool,
    idade_minutos: float,
    frescos: bool,
) -> str:
    """A frase de uma linha que resume o estado. É o que o operador lê primeiro.

    A ordem das checagens importa: **dado velho vem antes de tudo**. Qualquer leitura
    sobre tendência ou padrão é irrelevante se o candle mais recente é de ontem — dizer
    "aguardando padrão" nesse caso sugere que o motor está observando o mercado quando
    ele está olhando para uma foto.
    """
    if not frescos:
        horas = idade_minutos / 60
        quanto = f"{horas:.0f} h" if horas >= 1 else f"{idade_minutos:.0f} min"
        return (
            f"Dados parados há {quanto}. Isto não é o mercado agora — é a última leitura "
            "gravada. Ligue o coletor com o MetaTrader 5 aberto para voltar ao tempo real."
        )
    if sinal is not None:
        return "Entrada aprovada — os filtros passaram."
    if not mercado_aberto:
        return "Pregão fechado. Nenhuma posição é aberta fora do horário."
    if ctx.tendencia is Tendencia.LATERAL:
        return (
            "Mercado lateral. Padrão de reversão não tem o que reverter — "
            "o motor exige tendência antes de aprovar."
        )
    if vigiando:
        return (
            f"{len(vigiando)} padrão(ões) na tela, nenhum aprovado. "
            f"Motivo do mais próximo: {vigiando[0].motivo}."
        )
    if vies.direcao is Direcao.NEUTRA:
        return "Timeframes maiores divergindo. Sem viés definido, o corte sobe."
    return "Nenhum padrão formado agora. Aguardando."


def para_dict(r: Raciocinio) -> dict:
    return {
        "ativo": r.ativo,
        "momento": r.momento,
        "idadeMinutos": r.idade_minutos,
        "dadosFrescos": r.dados_frescos,
        "preco": r.preco,
        "variacaoDia": r.variacao_dia,
        "vies": r.vies,
        "viesDirecao": r.vies_direcao,
        "alinhado": r.alinhado,
        "janelaPregao": r.janela_pregao,
        "operaAgora": r.opera_agora,
        "veredito": r.veredito,
        "timeframes": [
            {
                "timeframe": t.timeframe,
                "tendencia": t.tendencia,
                "forcaTendencia": t.forca_tendencia,
                "fechamento": t.fechamento,
                "atr": t.atr,
                "regimeMedias": t.regime_medias,
                "direcaoMedias": t.direcao_medias,
                "alinhamento": t.alinhamento,
                "contas": [
                    {
                        "rotulo": c.rotulo,
                        "valor": c.valor,
                        "formula": c.formula,
                        "veredito": c.veredito,
                        "tom": c.tom,
                    }
                    for c in t.contas
                ],
            }
            for t in r.timeframes
        ],
        "estrutura": r.estrutura,
        "niveis": r.niveis,
        "vigiando": [
            {
                "padrao": v.padrao,
                "direcao": v.direcao,
                "forca": v.forca,
                "score": v.score,
                "motivo": v.motivo,
                "faltou": v.faltou,
            }
            for v in r.vigiando
        ],
        "sinal": r.sinal,
    }
