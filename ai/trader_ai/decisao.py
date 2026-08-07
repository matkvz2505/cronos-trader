"""Camada 5 — de padrão pontuado para operação concreta.

É aqui que o motor deixa de descrever o gráfico e passa a assumir risco. Três decisões
governam o módulo:

**1. Entrada por rompimento, não por fechamento.** O sinal só vale se o preço confirmar a
direção rompendo o extremo da formação. Entrar no fechamento do candle do padrão é entrar
antes de o mercado concordar — a maioria dos padrões do ebook, como o próprio texto avisa,
não se confirma.

**2. O stop nasce do padrão, não da conta.** O stop vai onde a leitura do padrão estaria
errada — além do extremo oposto da formação, com folga de ATR para não morrer de ruído.
Definir stop por "quanto eu aceito perder" é escolher o lugar errado pelo motivo errado.

**3. R:R manda no fim.** Um padrão excelente com alvo ruim continua sendo um trade ruim.
Sinais abaixo de `rr_minimo` são descartados por melhor que seja o score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from . import fibonacci as fib
from .confluencia import Avaliacao
from .instrumentos import Instrumento, resolver
from .limiares import PADRAO, Limiares
from .tipos import Contexto, Direcao, Serie, Timeframe


@dataclass(frozen=True, slots=True)
class Sinal:
    ativo: str
    timeframe: Timeframe
    ts: datetime
    indice: int
    direcao: Direcao
    padrao_id: str
    padrao_nome: str

    entrada: float
    stop: float
    alvo: float
    origem_alvo: str

    risco_pontos: float
    retorno_pontos: float
    rr: float
    contratos: int
    risco_reais: float
    retorno_reais: float

    score: float
    confiabilidade: float
    avaliacao: Avaliacao
    observacoes: list[str] = field(default_factory=list)

    @property
    def e_compra(self) -> bool:
        return self.direcao is Direcao.ALTA

    def resumo(self) -> str:
        lado = "COMPRA" if self.e_compra else "VENDA"
        return (
            f"{self.ts:%d/%m %H:%M} {self.ativo} {self.timeframe.rotulo} | {lado} "
            f"{self.padrao_nome} | entrada {self.entrada:.1f} stop {self.stop:.1f} "
            f"alvo {self.alvo:.1f} ({self.origem_alvo}) | R:R {self.rr:.2f} | "
            f"{self.contratos}c risco R$ {self.risco_reais:.2f} | score {self.score:.2f}"
        )


@dataclass
class EstadoDoDia:
    """Controle de risco da sessão. Vive fora do motor porque atravessa sinais.

    Os dois limites aqui existem contra o mesmo inimigo: a sequência de perdas que vira
    tentativa de recuperar. `max_trades_dia` é o freio menos intuitivo e o mais útil —
    over-trading é a causa mais comum de ruína em day trade, e nenhum score alto
    justifica o sétimo trade do dia.
    """

    dia: date
    capital: float
    resultado_reais: float = 0.0
    trades: int = 0

    def registrar(self, resultado: float) -> None:
        self.resultado_reais += resultado
        self.trades += 1

    def bloqueios(self, lim: Limiares = PADRAO) -> list[str]:
        motivos: list[str] = []
        perda_maxima = -abs(self.capital * lim.perda_diaria_maxima_pct / 100.0)
        if self.resultado_reais <= perda_maxima:
            motivos.append(
                f"limite de perda diaria atingido (R$ {self.resultado_reais:.2f})"
            )
        if self.trades >= lim.max_trades_dia:
            motivos.append(f"limite de {lim.max_trades_dia} trades no dia atingido")
        return motivos


def _alvo(
    serie: Serie,
    i: int,
    avaliacao: Avaliacao,
    entrada: float,
    risco: float,
    direcao: Direcao,
    lim: Limiares,
) -> tuple[float, str]:
    """Escolhe o alvo, em ordem de preferência, **descartando o que não paga o risco**.

    1. **Zona de S/R** — onde o movimento costuma parar, porque é onde há ordem
       contrária no book. Percorre da mais próxima à mais distante e fica na primeira
       que rende ao menos `rr_minimo`.
    2. **Projeção de Fibonacci 1.618** — quando nenhuma zona serve.
    3. **Múltiplo fixo do risco** — último recurso, para o sinal não ficar sem alvo.

    A validação por etapa é o ponto. Antes, bastava a zona estar do lado certo da entrada
    para ser adotada: uma zona logo acima do rompimento virava um alvo minúsculo, o R:R
    nascia morto e o sinal era descartado — **sem nunca tentar a opção seguinte**. Medido
    em 60 mil candles reais de WIN, isso matava 1.824 de 1.938 candidatas.

    A regra correta é a que um operador usa: se o alvo mais próximo não paga, olhe o
    próximo. Se nenhum paga, o trade realmente não existe.
    """
    sentido = 1.0 if direcao is Direcao.ALTA else -1.0

    def paga(alvo: float) -> bool:
        retorno = (alvo - entrada) * sentido
        return retorno > 0 and retorno / risco >= lim.rr_minimo

    for zona in avaliacao.alvos_candidatos:
        if paga(zona):
            return zona, "zona S/R"

    perna = fib.ultima_perna(serie, i, lim)
    if perna is not None:
        projetado = fib.alvo_por_projecao(perna, direcao, 1.618)
        if projetado is not None and paga(projetado):
            return projetado, "fib 1.618"

    return entrada + sentido * risco * 2.0, "2R fixo"


def montar(
    serie: Serie,
    i: int,
    avaliacao: Avaliacao,
    ctx: Contexto,
    capital: float,
    lim: Limiares = PADRAO,
    estado: EstadoDoDia | None = None,
    instrumento: Instrumento | None = None,
) -> Sinal | None:
    """Transforma uma avaliação aprovada num sinal executável, ou devolve `None`.

    Devolver `None` é o caso comum e desejável — a maior parte das detecções não vira
    operação. Um motor que aprova tudo o que detecta é um motor que perde dinheiro.
    """
    if avaliacao.vetos or not avaliacao.aprovado_com(lim):
        return None
    if estado is not None and estado.bloqueios(lim):
        return None

    inst = instrumento or resolver(serie.ativo)
    d = avaliacao.deteccao
    direcao = d.direcao
    if direcao is Direcao.NEUTRA:
        return None

    folga = lim.folga_stop_atr * ctx.atr

    if direcao is Direcao.ALTA:
        entrada = inst.arredondar_para_cima(d.extremo_superior + inst.tick)
        stop = inst.arredondar_para_baixo(d.extremo_inferior - folga)
        risco = entrada - stop
    else:
        entrada = inst.arredondar_para_baixo(d.extremo_inferior - inst.tick)
        stop = inst.arredondar_para_cima(d.extremo_superior + folga)
        risco = stop - entrada

    if risco <= 0:
        return None

    alvo_bruto, origem = _alvo(serie, i, avaliacao, entrada, risco, direcao, lim)
    alvo = inst.arredondar(alvo_bruto)
    retorno = (alvo - entrada) if direcao is Direcao.ALTA else (entrada - alvo)
    if retorno <= 0:
        return None

    rr = retorno / risco
    if rr < lim.rr_minimo:
        return None

    contratos = _dimensionar(risco, capital, inst, lim)
    if contratos < 1:
        return None

    observacoes: list[str] = []
    if avaliacao.zona_quente:
        observacoes.append("zona quente: fibonacci, média e S/R no mesmo preço")
    if d.detalhes.get("derivado_por_simetria"):
        observacoes.append("padrão espelhado por simetria — ver docs/ERRATA-EBOOK.md")
    if d.detalhes.get("exige_gap") and serie.timeframe.e_intraday:
        observacoes.append(
            "padrão dependente de gap em timeframe intraday — sensível a tolerancia_gap_atr"
        )

    return Sinal(
        ativo=serie.ativo,
        timeframe=serie.timeframe,
        ts=serie[i].ts,
        indice=i,
        direcao=direcao,
        padrao_id=d.padrao_id,
        padrao_nome=d.nome,
        entrada=entrada,
        stop=stop,
        alvo=alvo,
        origem_alvo=origem,
        risco_pontos=risco,
        retorno_pontos=retorno,
        rr=rr,
        contratos=contratos,
        risco_reais=inst.reais(risco, contratos) + inst.custo_total(contratos),
        retorno_reais=inst.reais(retorno, contratos) - inst.custo_total(contratos),
        score=avaliacao.score,
        confiabilidade=d.confiabilidade,
        avaliacao=avaliacao,
        observacoes=observacoes,
    )


def _dimensionar(
    risco_pontos: float, capital: float, inst: Instrumento, lim: Limiares
) -> int:
    """Contratos por risco fixo em % do capital, arredondado para baixo.

    Para baixo sempre: arredondar para cima seria assumir mais risco do que o
    configurado, exatamente no trade em que a conta não fecha.

    Também limita pela margem disponível — não adianta o risco permitir 10 contratos se
    o capital não cobre a garantia deles.
    """
    risco_maximo = capital * lim.risco_por_trade_pct / 100.0
    risco_unitario = inst.reais(risco_pontos) + inst.custo_total(1)
    if risco_unitario <= 0:
        return 0
    por_risco = int(risco_maximo // risco_unitario)
    por_margem = int(capital // inst.margem_estimada) if inst.margem_estimada > 0 else por_risco
    return max(0, min(por_risco, por_margem))
