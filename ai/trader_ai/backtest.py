"""Camada 7 — simulação honesta e calibração das confiabilidades.

O backtest **não existe para provar que a estratégia funciona.** Existe para descobrir
quais padrões realmente funcionam em WIN e WDO, e apagar os que não funcionam. Se o
resultado for "o Harami não presta em 5 minutos", o backtest fez seu trabalho.

Quatro decisões que separam um backtest útil de um que engana:

**1. Zero look-ahead.** O motor roda sobre `serie.fatiar(i)` — enxerga exatamente o que
existiria naquele instante. Não é paranoia: vazar um único candle de futuro produz
resultado bom demais, e o erro é indetectável no gráfico final.

**2. Empate resolve contra nós.** Quando um candle contém stop e alvo, assume-se **stop**.
Sem tick a tick não dá para saber a ordem, e a suposição otimista inverteria a estatística
de qualquer estratégia de alvo curto.

**3. Custos entram sempre.** Corretagem, emolumento e slippage nas duas pontas. Uma
estratégia de 5 minutos com 55% de acerto pode perder dinheiro depois dos custos.

**4. Amostra pequena não vira confiança.** Abaixo de `amostra_minima_confiabilidade`
ocorrências, o padrão mantém o prior do ebook e é marcado como insuficiente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from . import confluencia, multitimeframe, padroes
from . import contexto as ctx_mod
from .decisao import EstadoDoDia, Sinal, montar
from .fontes.contratos import em_rollover
from .instrumentos import Instrumento, resolver
from .limiares import PADRAO, Limiares
from .tipos import Direcao, Serie, Timeframe

MAX_CANDLES_ESPERA = 3
"""Quantos candles o rompimento tem para acontecer antes de o sinal expirar.

Um padrão de 5 minutos que só é acionado 40 minutos depois não é mais aquele padrão —
o contexto mudou.
"""


@dataclass(frozen=True, slots=True)
class Operacao:
    sinal: Sinal
    desfecho: str
    """`alvo` · `stop` · `fim_do_dia` · `fim_da_serie` · `nao_acionado`"""

    indice_entrada: int | None = None
    indice_saida: int | None = None
    preco_saida: float | None = None
    resultado_pontos: float = 0.0
    resultado_reais: float = 0.0

    @property
    def acionada(self) -> bool:
        return self.indice_entrada is not None

    @property
    def ganhou(self) -> bool:
        return self.acionada and self.resultado_reais > 0

    @property
    def resultado_em_r(self) -> float:
        """Resultado em múltiplos do risco. É a unidade que permite comparar trades de
        tamanhos diferentes — e a única que faz sentido somar."""
        if not self.acionada or self.sinal.risco_pontos <= 0:
            return 0.0
        return self.resultado_pontos / self.sinal.risco_pontos


@dataclass
class Estatistica:
    padrao_id: str
    nome: str
    n: int = 0
    acertos: int = 0
    soma_r: float = 0.0
    resultado_reais: float = 0.0
    nao_acionados: int = 0

    @property
    def taxa_acerto(self) -> float:
        return self.acertos / self.n if self.n else 0.0

    @property
    def expectancia_r(self) -> float:
        """R médio por operação. É o número que decide se o padrão fica ou sai.

        Taxa de acerto alta com expectância negativa é comum e é uma armadilha: acertar
        70% das vezes ganhando 1 e perder 30% perdendo 3 dá prejuízo.
        """
        return self.soma_r / self.n if self.n else 0.0

    def suficiente(self, lim: Limiares = PADRAO) -> bool:
        return self.n >= lim.amostra_minima_confiabilidade

    def linha(self, lim: Limiares = PADRAO) -> str:
        marca = "" if self.suficiente(lim) else "  (amostra insuficiente)"
        return (
            f"{self.nome:<32} n={self.n:>4}  acerto={self.taxa_acerto:>6.1%}  "
            f"exp={self.expectancia_r:>+6.2f}R  R$ {self.resultado_reais:>+10.2f}{marca}"
        )


@dataclass
class Resultado:
    ativo: str
    timeframe: Timeframe
    operacoes: list[Operacao] = field(default_factory=list)
    por_padrao: dict[str, Estatistica] = field(default_factory=dict)
    por_janela: dict[str, Estatistica] = field(default_factory=dict)
    capital_inicial: float = 0.0

    @property
    def acionadas(self) -> list[Operacao]:
        return [o for o in self.operacoes if o.acionada]

    @property
    def resultado_reais(self) -> float:
        return sum(o.resultado_reais for o in self.operacoes)

    @property
    def taxa_acerto(self) -> float:
        feitas = self.acionadas
        if not feitas:
            return 0.0
        return sum(1 for o in feitas if o.ganhou) / len(feitas)

    @property
    def expectancia_r(self) -> float:
        feitas = self.acionadas
        if not feitas:
            return 0.0
        return sum(o.resultado_em_r for o in feitas) / len(feitas)

    @property
    def rebaixamento_maximo(self) -> float:
        """Maior queda do pico ao vale da curva de capital.

        Mais importante que o lucro final: é o número que determina se dá para operar a
        estratégia sem desistir no meio.
        """
        pico = 0.0
        acumulado = 0.0
        pior = 0.0
        for op in self.operacoes:
            acumulado += op.resultado_reais
            pico = max(pico, acumulado)
            pior = min(pior, acumulado - pico)
        return pior

    def relatorio(self, lim: Limiares = PADRAO) -> str:
        feitas = self.acionadas
        linhas = [
            f"Backtest {self.ativo} {self.timeframe.rotulo}",
            f"  sinais gerados .... {len(self.operacoes)}",
            f"  acionados ......... {len(feitas)}",
            f"  taxa de acerto .... {self.taxa_acerto:.1%}",
            f"  expectância ....... {self.expectancia_r:+.2f} R por operação",
            f"  resultado ......... R$ {self.resultado_reais:+.2f}",
            f"  rebaixamento máx .. R$ {self.rebaixamento_maximo:+.2f}",
            "",
            "Por padrão (ordenado por expectância):",
        ]
        ordenados = sorted(
            self.por_padrao.values(), key=lambda e: e.expectancia_r, reverse=True
        )
        linhas.extend("  " + e.linha(lim) for e in ordenados)

        if self.por_janela:
            linhas.append("")
            linhas.append("Por janela do pregão:")
            linhas.extend(
                "  " + e.linha(lim)
                for e in sorted(self.por_janela.values(), key=lambda e: -e.expectancia_r)
            )
        return "\n".join(linhas)


def _fim_de_pregao(serie: Serie, k: int) -> bool:
    return k + 1 >= len(serie) or serie[k + 1].ts.date() != serie[k].ts.date()


def _simular(
    serie: Serie, i: int, sinal: Sinal, inst: Instrumento, max_espera: int
) -> Operacao:
    """Caminha candle a candle a partir de `i+1` e resolve a operação.

    O sinal nasce do padrão fechado em `i`; a entrada é uma ordem de rompimento, então
    a simulação começa no candle **seguinte**. Entrar no fechamento de `i` seria entrar
    antes de o mercado confirmar — e o backtest ficaria melhor que a realidade.
    """
    compra = sinal.direcao is Direcao.ALTA
    entrada = sinal.entrada
    fim_espera = min(i + 1 + max_espera, len(serie))

    indice_entrada = None
    for j in range(i + 1, fim_espera):
        c = serie[j]
        if (compra and c.maxima >= entrada) or (not compra and c.minima <= entrada):
            indice_entrada = j
            break

    if indice_entrada is None:
        return Operacao(sinal=sinal, desfecho="nao_acionado")

    for k in range(indice_entrada, len(serie)):
        c = serie[k]
        bateu_stop = c.minima <= sinal.stop if compra else c.maxima >= sinal.stop
        bateu_alvo = c.maxima >= sinal.alvo if compra else c.minima <= sinal.alvo

        # Empate resolve contra nós: sem tick a tick não há como saber a ordem, e supor
        # o alvo primeiro inflaria artificialmente toda estratégia de alvo curto.
        if bateu_stop:
            return _fechar(sinal, inst, indice_entrada, k, sinal.stop, "stop")
        if bateu_alvo:
            return _fechar(sinal, inst, indice_entrada, k, sinal.alvo, "alvo")
        if _fim_de_pregao(serie, k):
            desfecho = "fim_da_serie" if k + 1 >= len(serie) else "fim_do_dia"
            return _fechar(sinal, inst, indice_entrada, k, c.fechamento, desfecho)

    ultimo = len(serie) - 1
    return _fechar(
        sinal, inst, indice_entrada, ultimo, serie[ultimo].fechamento, "fim_da_serie"
    )


def _fechar(
    sinal: Sinal,
    inst: Instrumento,
    indice_entrada: int,
    indice_saida: int,
    preco_saida: float,
    desfecho: str,
) -> Operacao:
    pontos = (
        preco_saida - sinal.entrada
        if sinal.direcao is Direcao.ALTA
        else sinal.entrada - preco_saida
    )
    bruto = inst.reais(pontos, sinal.contratos)
    return Operacao(
        sinal=sinal,
        desfecho=desfecho,
        indice_entrada=indice_entrada,
        indice_saida=indice_saida,
        preco_saida=preco_saida,
        resultado_pontos=pontos,
        resultado_reais=bruto - inst.custo_total(sinal.contratos),
    )


def rodar(
    serie: Serie,
    capital: float = 10_000.0,
    lim: Limiares = PADRAO,
    usar_multitimeframe: bool = True,
    pular_rollover: bool = True,
    max_espera: int = MAX_CANDLES_ESPERA,
) -> Resultado:
    """Executa o motor completo sobre a série e mede o que aconteceu.

    Uma operação por vez: enquanto houver posição aberta, novos sinais são ignorados.
    Simular trades sobrepostos daria uma curva de capital que nenhuma conta real
    conseguiria reproduzir.
    """
    lim = lim.para_timeframe(serie.timeframe)
    inst = resolver(serie.ativo)
    resultado = Resultado(
        ativo=serie.ativo, timeframe=serie.timeframe, capital_inicial=capital
    )

    conjunto = multitimeframe.montar_conjunto(serie) if usar_multitimeframe else {}
    estado: EstadoDoDia | None = None
    ocupado_ate = -1

    for i in range(lim.tendencia_min_candles, len(serie)):
        dia: date = serie[i].ts.date()

        if estado is None or estado.dia != dia:
            estado = EstadoDoDia(dia=dia, capital=capital)
        if i <= ocupado_ate:
            continue
        if pular_rollover and em_rollover(serie.ativo, dia):
            continue
        if estado.bloqueios(lim):
            continue

        # Passa a série INTEIRA, não uma fatia. Todos os indicadores do motor são
        # causais por construção — ATR, EMA, SMA, ADX e VWAP em `i` só dependem de
        # candles <= i — e os pivôs passam por `swings_confirmados`, que exige
        # `indice + lookback <= i`. Fatiar a cada candle daria o mesmo resultado (há
        # teste garantindo isso) ao custo de invalidar o cache e tornar o backtest
        # quadrático: 6.500 candles levavam minutos.
        ctx = ctx_mod.ler(serie, i, lim)
        deteccoes = padroes.detectar_em(serie, i, ctx, lim)
        if not deteccoes:
            continue

        avaliacao = confluencia.melhor(serie, i, deteccoes, ctx, lim)
        if avaliacao is None:
            continue

        if usar_multitimeframe:
            vies = multitimeframe.calcular_vies(conjunto, serie[i].ts, lim)
            avaliacao = multitimeframe.aplicar(avaliacao, vies, lim)
            if not avaliacao.aprovado_com(lim):
                continue

        sinal = montar(serie, i, avaliacao, ctx, capital, lim, estado, inst)
        if sinal is None:
            continue

        operacao = _simular(serie, i, sinal, inst, max_espera)
        resultado.operacoes.append(operacao)

        if operacao.acionada:
            estado.registrar(operacao.resultado_reais)
            ocupado_ate = operacao.indice_saida or i

        _acumular(resultado.por_padrao, sinal.padrao_id, sinal.padrao_nome, operacao)
        _acumular(
            resultado.por_janela,
            ctx.janela_pregao,
            ctx.janela_pregao,
            operacao,
        )

    return resultado


def _acumular(
    destino: dict[str, Estatistica], chave: str, nome: str, operacao: Operacao
) -> None:
    estatistica = destino.setdefault(chave, Estatistica(padrao_id=chave, nome=nome))
    if not operacao.acionada:
        estatistica.nao_acionados += 1
        return
    estatistica.n += 1
    estatistica.soma_r += operacao.resultado_em_r
    estatistica.resultado_reais += operacao.resultado_reais
    if operacao.ganhou:
        estatistica.acertos += 1


def calibrar(resultado: Resultado, lim: Limiares = PADRAO) -> dict[str, tuple[float, int, float]]:
    """Grava as medições em `padroes.CALIBRACAO` e devolve o que foi gravado.

    A partir daí, `confiabilidade_de()` passa a usar evidência no lugar do palpite — mas
    só onde a amostra sustenta. Padrões com poucas ocorrências ficam de fora e valem
    `confiabilidade_sem_medicao`.

    Guarda a **expectância** junto da taxa de acerto porque as duas discordam com
    frequência: o `tres_por_dentro_baixa` do WDO acerta 50% e mede −0,300R. Sem a
    expectância, essa informação não chegaria a lugar nenhum onde pudesse vetar.
    """
    calibrado: dict[str, tuple[float, int, float]] = {}
    for padrao_id, estatistica in resultado.por_padrao.items():
        if estatistica.suficiente(lim):
            calibrado[padrao_id] = (
                estatistica.taxa_acerto,
                estatistica.n,
                estatistica.expectancia_r,
            )
    padroes.CALIBRACAO.update(calibrado)
    return calibrado


@dataclass
class JanelaWalkForward:
    indice: int
    treino: Resultado
    teste: Resultado
    calibrado: dict[str, tuple[float, int]]


def walk_forward(
    serie: Serie,
    janelas: int = 4,
    capital: float = 10_000.0,
    lim: Limiares = PADRAO,
) -> list[JanelaWalkForward]:
    """Calibra numa janela, testa na seguinte, anda para frente.

    É a diferença entre evidência e memorização. Uma taxa de acerto medida no mesmo
    período em que os pesos foram ajustados não prova nada — só diz que o ajuste
    funcionou onde foi ajustado.

    Devolve uma entrada por par (treino, teste). **O resultado que vale é o do teste.**
    """
    if janelas < 2:
        raise ValueError("walk-forward precisa de ao menos 2 janelas")

    tamanho = len(serie) // janelas
    if tamanho <= lim.tendencia_min_candles * 2:
        raise ValueError(
            f"série curta demais para {janelas} janelas "
            f"({len(serie)} candles; precisa de ~{lim.tendencia_min_candles * 2 * janelas})"
        )

    saida: list[JanelaWalkForward] = []
    calibracao_anterior = dict(padroes.CALIBRACAO)

    try:
        for k in range(janelas - 1):
            treino_candles = serie.candles[k * tamanho : (k + 1) * tamanho]
            teste_candles = serie.candles[(k + 1) * tamanho : (k + 2) * tamanho]

            padroes.CALIBRACAO.clear()
            treino = rodar(
                Serie(serie.ativo, serie.timeframe, treino_candles), capital, lim
            )
            calibrado = calibrar(treino, lim)

            teste = rodar(
                Serie(serie.ativo, serie.timeframe, teste_candles), capital, lim
            )
            saida.append(JanelaWalkForward(k, treino, teste, calibrado))
    finally:
        # Não deixar a calibração da última janela vazando para o resto do processo.
        padroes.CALIBRACAO.clear()
        padroes.CALIBRACAO.update(calibracao_anterior)

    return saida
