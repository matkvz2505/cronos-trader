"""Fechamento de período e preparação do dia seguinte.

A rotina que separa quem opera de quem aposta é sempre a mesma: **fechar o dia com número
e abrir o seguinte com plano**. Este módulo produz os dois lados.

Tudo aqui sai do banco — candles e sinais que de fato aconteceram. Nada é estimado, nada é
conselho genérico. Quando não há dado, o relatório diz que não há em vez de preencher com
frase de efeito.

Três períodos, três perguntas diferentes:

- **dia** — o que aconteceu, o que o motor viu, quanto custou ou rendeu
- **semana** — o padrão está se repetindo, ou foi um dia solto?
- **mês** — o fechamento: dá para dizer alguma coisa com amostra?
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np

from . import contexto as ctx_mod
from . import estrutura as est
from . import fibonacci as fib
from . import medias as medias_mod
from .indicadores import atr as calc_atr
from .instrumentos import resolver
from .limiares import PADRAO
from .tipos import Serie

Periodo = Literal["dia", "semana", "mes"]

ROTULO_PERIODO: dict[Periodo, str] = {
    "dia": "pregão",
    "semana": "semana",
    "mes": "mês",
}


@dataclass(frozen=True, slots=True)
class MovimentoPreco:
    """O que o preço fez no período — a moldura de tudo o mais."""

    abertura: float
    maxima: float
    minima: float
    fechamento: float
    variacao_pct: float
    amplitude: float
    amplitude_atr: float
    candles: int
    pregoes: int


@dataclass(frozen=True, slots=True)
class Placar:
    emitidos: int = 0
    acionados: int = 0
    alvo: int = 0
    stop: int = 0
    expirados: int = 0
    abertos: int = 0
    resultado_r: float = 0.0
    resultado_reais: float = 0.0

    @property
    def encerrados(self) -> int:
        return self.alvo + self.stop

    @property
    def taxa_acerto(self) -> float:
        return self.alvo / self.encerrados if self.encerrados else 0.0

    @property
    def expectancia_r(self) -> float:
        return self.resultado_r / self.encerrados if self.encerrados else 0.0

    @property
    def taxa_acionamento(self) -> float:
        """Dos sinais emitidos, quantos o preço de fato acionou.

        Baixo demais indica entrada mal posicionada — o rompimento pedido não acontece.
        """
        return self.acionados / self.emitidos if self.emitidos else 0.0


@dataclass(frozen=True, slots=True)
class LinhaDesempenho:
    chave: str
    n: int
    acertos: int
    resultado_r: float

    @property
    def taxa(self) -> float:
        return self.acertos / self.n if self.n else 0.0

    @property
    def expectancia(self) -> float:
        return self.resultado_r / self.n if self.n else 0.0


@dataclass(frozen=True, slots=True)
class NivelAmanha:
    preco: float
    rotulo: str
    origem: str
    nota: str = ""


@dataclass(frozen=True, slots=True)
class Fechamento:
    ativo: str
    periodo: Periodo
    inicio: str
    fim: str
    movimento: MovimentoPreco | None
    placar: Placar
    por_padrao: list[LinhaDesempenho] = field(default_factory=list)
    por_janela: list[LinhaDesempenho] = field(default_factory=list)
    destaques: list[str] = field(default_factory=list)
    niveis_amanha: list[NivelAmanha] = field(default_factory=list)
    contexto_atual: dict = field(default_factory=dict)


def _janela(periodo: Periodo, referencia: datetime) -> tuple[datetime, datetime]:
    """Início e fim do período que contém `referencia`.

    A semana começa na segunda: o pregão de segunda a sexta é a unidade que o operador
    vive, e uma semana que começa no domingo cortaria a análise no meio para ninguém.
    """
    fim = referencia
    if periodo == "dia":
        inicio = referencia.replace(hour=0, minute=0, second=0, microsecond=0)
    elif periodo == "semana":
        segunda = referencia.date() - timedelta(days=referencia.weekday())
        inicio = datetime.combine(segunda, datetime.min.time())
    else:
        inicio = referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return inicio, fim


def _movimento(serie: Serie, inicio: datetime, fim: datetime) -> MovimentoPreco | None:
    candles = [c for c in serie.candles if inicio <= c.ts <= fim]
    if not candles:
        return None

    abertura = candles[0].abertura
    fechamento = candles[-1].fechamento
    maxima = max(c.maxima for c in candles)
    minima = min(c.minima for c in candles)

    atr_arr = calc_atr(serie, PADRAO.atr_periodo)
    i = len(serie) - 1
    atr_i = float(atr_arr[i]) if not np.isnan(atr_arr[i]) else 0.0
    amplitude = maxima - minima

    return MovimentoPreco(
        abertura=abertura,
        maxima=maxima,
        minima=minima,
        fechamento=fechamento,
        variacao_pct=((fechamento - abertura) / abertura * 100) if abertura else 0.0,
        amplitude=amplitude,
        amplitude_atr=(amplitude / atr_i) if atr_i > 0 else 0.0,
        candles=len(candles),
        pregoes=len({c.ts.date() for c in candles}),
    )


def _placar_e_desempenho(
    sinais: list[dict], ativo: str
) -> tuple[Placar, list[LinhaDesempenho], list[LinhaDesempenho]]:
    """Agrega os sinais do período. `sinais` vem de `persistencia.ler_sinais_periodo`."""
    inst = resolver(ativo)
    contagem = Counter(s["status"] for s in sinais)

    por_padrao: dict[str, list[dict]] = defaultdict(list)
    por_janela: dict[str, list[dict]] = defaultdict(list)
    resultado_r = 0.0
    resultado_reais = 0.0

    for s in sinais:
        if s["status"] not in ("ALVO", "STOP"):
            continue
        risco = float(s["riscoPontos"] or 0)
        pontos = float(s["resultadoPontos"] or 0)
        # Resultado em R: a única unidade que permite somar trades de tamanhos diferentes.
        r = (pontos / risco) if risco > 0 else 0.0
        resultado_r += r
        resultado_reais += inst.reais(pontos, int(s["contratos"] or 0)) - inst.custo_total(
            int(s["contratos"] or 0)
        )
        por_padrao[s["padraoNome"]].append({"r": r, "ganhou": s["status"] == "ALVO"})
        janela = (s.get("janelaPregao") or "").strip()
        if janela:
            por_janela[janela].append({"r": r, "ganhou": s["status"] == "ALVO"})

    placar = Placar(
        emitidos=len(sinais),
        acionados=contagem["ACIONADO"] + contagem["ALVO"] + contagem["STOP"],
        alvo=contagem["ALVO"],
        stop=contagem["STOP"],
        expirados=contagem["EXPIRADO"],
        abertos=contagem["ABERTO"] + contagem["ACIONADO"],
        resultado_r=resultado_r,
        resultado_reais=resultado_reais,
    )

    def linhas(mapa: dict[str, list[dict]]) -> list[LinhaDesempenho]:
        saida = [
            LinhaDesempenho(
                chave=chave,
                n=len(itens),
                acertos=sum(1 for i in itens if i["ganhou"]),
                resultado_r=sum(i["r"] for i in itens),
            )
            for chave, itens in mapa.items()
        ]
        return sorted(saida, key=lambda linha: -linha.expectancia)

    return placar, linhas(por_padrao), linhas(por_janela)


def _destaques(
    placar: Placar,
    movimento: MovimentoPreco | None,
    por_padrao: list[LinhaDesempenho],
    por_janela: list[LinhaDesempenho],
    periodo: Periodo,
) -> list[str]:
    """As observações que valem ser lidas. Só o que os números sustentam."""
    notas: list[str] = []

    if movimento is None:
        return ["Sem candles no período. O coletor não estava rodando."]

    if movimento.amplitude_atr > 0:
        if movimento.amplitude_atr > 8:
            notas.append(
                f"Amplitude de {movimento.amplitude_atr:.1f} ATR — {ROTULO_PERIODO[periodo]} "
                "de movimento largo, favorável a alvo distante."
            )
        elif movimento.amplitude_atr < 3:
            notas.append(
                f"Amplitude de apenas {movimento.amplitude_atr:.1f} ATR — mercado comprimido. "
                "Alvo curto não paga o custo em dias assim."
            )

    if placar.emitidos == 0:
        notas.append(
            "Nenhum sinal emitido. Não é defeito: 99,1% das detecções são recusadas por "
            "construção, e há períodos inteiros sem confluência suficiente."
        )
    else:
        if placar.taxa_acionamento < 0.5 and placar.emitidos >= 4:
            notas.append(
                f"Só {placar.taxa_acionamento:.0%} dos sinais foram acionados. Quando isso se "
                "repete, a entrada por rompimento está pedindo um movimento que não vem."
            )
        if placar.encerrados >= 3:
            notas.append(
                f"{placar.encerrados} operações encerradas: {placar.alvo} no alvo, "
                f"{placar.stop} no stop — {placar.expectancia_r:+.2f}R por operação."
            )

    melhor = next((linha for linha in por_padrao if linha.n >= 2), None)
    if melhor and melhor.expectancia > 0:
        notas.append(
            f"Melhor padrão do período: {melhor.chave} ({melhor.expectancia:+.2f}R em "
            f"{melhor.n} operações)."
        )
    pior = next((linha for linha in reversed(por_padrao) if linha.n >= 2), None)
    if pior and pior.expectancia < 0 and pior.chave != (melhor.chave if melhor else None):
        notas.append(
            f"Pior padrão do período: {pior.chave} ({pior.expectancia:+.2f}R em {pior.n})."
        )

    boa_janela = next((linha for linha in por_janela if linha.n >= 3), None)
    if boa_janela:
        notas.append(
            f"Janela mais produtiva: {boa_janela.chave} ({boa_janela.expectancia:+.2f}R em "
            f"{boa_janela.n})."
        )

    if placar.encerrados > 0 and placar.encerrados < 30:
        notas.append(
            f"Amostra de {placar.encerrados} operações. Abaixo de 30 nenhum número aqui é "
            "evidência — é observação."
        )

    return notas


def _niveis_para_amanha(serie: Serie, movimento: MovimentoPreco | None) -> list[NivelAmanha]:
    """Os preços que amanhã começa olhando.

    Máxima, mínima e fechamento do último pregão são as referências que todo mundo tem na
    tela — e é por isso que funcionam. As médias e zonas entram porque o motor já as mede.
    """
    if not len(serie):
        return []

    i = len(serie) - 1
    ctx = ctx_mod.ler(serie, i)
    niveis: list[NivelAmanha] = []

    if movimento is not None:
        niveis.extend(
            [
                NivelAmanha(movimento.maxima, "Máxima do período", "pregao",
                            "resistência de referência"),
                NivelAmanha(movimento.minima, "Mínima do período", "pregao",
                            "suporte de referência"),
                NivelAmanha(movimento.fechamento, "Fechamento", "pregao",
                            "abrir acima ou abaixo já é informação"),
            ]
        )

    regime = medias_mod.ler(serie, i, ctx.atr)
    for nome, valor in (
        ("EMA 9", regime.ema9),
        ("SMA 21", regime.sma21),
        ("SMA 200", regime.sma200),
        ("RMA 400", regime.rma400),
    ):
        if valor is not None:
            niveis.append(NivelAmanha(valor, nome, "media"))

    for faixa in est.ler(serie, i).faixas[:4]:
        niveis.append(
            NivelAmanha(
                faixa.centro,
                f"Zona de {faixa.tipo}",
                "estrutura",
                f"{faixa.toques} toques",
            )
        )

    perna = fib.ultima_perna(serie, i)
    if perna is not None and perna.amplitude > 0:
        for nivel in fib.retracoes(perna):
            if fib.relevancia(serie.ativo, nivel.razao) > 0:
                niveis.append(
                    NivelAmanha(nivel.preco, nivel.rotulo, "fibonacci", "nível medido")
                )

    referencia = movimento.fechamento if movimento else serie[i].fechamento
    niveis.sort(key=lambda n: abs(n.preco - referencia))
    return niveis[:12]


def montar(
    serie: Serie,
    sinais: list[dict],
    periodo: Periodo = "dia",
    referencia: datetime | None = None,
) -> Fechamento:
    """O relatório completo do período."""
    agora = referencia or datetime.now()
    inicio, fim = _janela(periodo, agora)

    movimento = _movimento(serie, inicio, fim)
    placar, por_padrao, por_janela = _placar_e_desempenho(sinais, serie.ativo)

    ctx_atual: dict = {}
    if len(serie) > PADRAO.tendencia_min_candles:
        i = len(serie) - 1
        ctx = ctx_mod.ler(serie, i)
        regime = medias_mod.ler(serie, i, ctx.atr)
        ctx_atual = {
            "tendencia": ctx.tendencia.value,
            "forcaTendencia": round(ctx.forca_tendencia, 2),
            "atr": round(ctx.atr, 2),
            "regimeMedias": regime.descricao,
            "ultimoCandle": serie[i].ts.isoformat(),
        }

    return Fechamento(
        ativo=serie.ativo,
        periodo=periodo,
        inicio=inicio.isoformat(),
        fim=fim.isoformat(),
        movimento=movimento,
        placar=placar,
        por_padrao=por_padrao,
        por_janela=por_janela,
        destaques=_destaques(placar, movimento, por_padrao, por_janela, periodo),
        niveis_amanha=_niveis_para_amanha(serie, movimento),
        contexto_atual=ctx_atual,
    )


def para_dict(f: Fechamento) -> dict:
    def linha(linha_: LinhaDesempenho) -> dict:
        return {
            "chave": linha_.chave,
            "n": linha_.n,
            "acertos": linha_.acertos,
            "taxa": round(linha_.taxa, 4),
            "expectanciaR": round(linha_.expectancia, 3),
            "resultadoR": round(linha_.resultado_r, 2),
        }

    return {
        "ativo": f.ativo,
        "periodo": f.periodo,
        "inicio": f.inicio,
        "fim": f.fim,
        "movimento": (
            {
                "abertura": f.movimento.abertura,
                "maxima": f.movimento.maxima,
                "minima": f.movimento.minima,
                "fechamento": f.movimento.fechamento,
                "variacaoPct": round(f.movimento.variacao_pct, 2),
                "amplitude": round(f.movimento.amplitude, 2),
                "amplitudeAtr": round(f.movimento.amplitude_atr, 2),
                "candles": f.movimento.candles,
                "pregoes": f.movimento.pregoes,
            }
            if f.movimento
            else None
        ),
        "placar": {
            "emitidos": f.placar.emitidos,
            "acionados": f.placar.acionados,
            "alvo": f.placar.alvo,
            "stop": f.placar.stop,
            "expirados": f.placar.expirados,
            "abertos": f.placar.abertos,
            "encerrados": f.placar.encerrados,
            "taxaAcerto": round(f.placar.taxa_acerto, 4),
            "taxaAcionamento": round(f.placar.taxa_acionamento, 4),
            "expectanciaR": round(f.placar.expectancia_r, 3),
            "resultadoR": round(f.placar.resultado_r, 2),
            "resultadoReais": round(f.placar.resultado_reais, 2),
            "amostraSuficiente": f.placar.encerrados >= PADRAO.amostra_minima_confiabilidade,
        },
        "porPadrao": [linha(x) for x in f.por_padrao],
        "porJanela": [linha(x) for x in f.por_janela],
        "destaques": f.destaques,
        "niveisAmanha": [
            {"preco": n.preco, "rotulo": n.rotulo, "origem": n.origem, "nota": n.nota}
            for n in f.niveis_amanha
        ],
        "contextoAtual": f.contexto_atual,
    }


def proximo_pregao(referencia: date | None = None) -> date:
    """O próximo dia útil. Feriados não são modelados — só fim de semana."""
    dia = (referencia or date.today()) + timedelta(days=1)
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia
