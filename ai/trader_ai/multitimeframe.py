"""Camada 6 — os timeframes maiores mandam no menor.

Foi o desenho pedido no escopo: **15/30/60min avaliam, 5min dispara.**

```
60m ─┐
30m ─┼─▶ VIÉS  (alta / baixa / neutro, com força)
15m ─┘           │
                 ▼
 5m ───────▶ GATILHO ── só passa se concordar com o viés
```

O trade que este módulo mata é o mais tentador de todos: o padrão bonito de 5 minutos
contra a tendência de 30 e 60. Na tela ele parece o melhor sinal do dia; na conta ele é o
que sangra. Quando os três timeframes altos divergem entre si, o viés é neutro e só um
sinal quase perfeito passa — que na prática significa quase nenhum, e é essa a intenção.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from . import contexto as ctx_mod
from .confluencia import Avaliacao, Fator
from .limiares import PADRAO, Limiares
from .tipos import Candle, Direcao, Serie, Tendencia, Timeframe

TIMEFRAMES_DE_VIES = (Timeframe.M15, Timeframe.M30, Timeframe.H1)
TIMEFRAME_DE_GATILHO = Timeframe.M5


@dataclass(frozen=True, slots=True)
class Vies:
    direcao: Direcao
    forca: float
    votos: dict[str, str]
    alinhado: bool
    """Os três timeframes concordando entre si."""

    def concorda_com(self, direcao: Direcao) -> bool:
        return self.direcao is not Direcao.NEUTRA and self.direcao is direcao

    def contraria(self, direcao: Direcao) -> bool:
        return self.direcao is not Direcao.NEUTRA and self.direcao is direcao.oposta

    def descrever(self) -> str:
        detalhe = ", ".join(f"{tf}={t}" for tf, t in sorted(self.votos.items()))
        return f"viés {self.direcao.value} ({self.forca:.0%}) [{detalhe}]"


def indice_em(serie: Serie, ts: datetime) -> int | None:
    """Último candle da série cujo timestamp de abertura é <= `ts`.

    Busca binária sobre os timestamps memoizados. **Pode devolver um candle ainda em
    formação** — para leitura causal use `indice_fechado_em`.
    """
    marcos = serie.memo("timestamps", lambda: [c.ts for c in serie.candles])
    if not marcos or ts < marcos[0]:
        return None
    pos = bisect.bisect_right(marcos, ts) - 1
    return pos if pos >= 0 else None


def indice_fechado_em(serie: Serie, ts: datetime) -> int | None:
    """Último candle **já fechado** em `ts`.

    A distinção não é detalhe. Às 10h35, o candle de 60 minutos que começou às 10h ainda
    está aberto: sua máxima, mínima e fechamento dependem do que vai acontecer até as
    11h. Ler esse candle para decidir o viés é ler o futuro — e é o vazamento mais fácil
    de cometer num motor multi-timeframe, porque nada no gráfico denuncia.

    Um candle que abre em `t` fecha em `t + duração`. Só entra se `t + duração <= ts`.
    """
    i = indice_em(serie, ts)
    if i is None:
        return None
    duracao = timedelta(minutes=serie.timeframe.value)
    while i >= 0 and serie[i].ts + duracao > ts:
        i -= 1
    return i if i >= 0 else None


def calcular_vies(
    series: dict[Timeframe, Serie], ts: datetime, lim: Limiares = PADRAO
) -> Vies:
    """Combina a leitura de tendência dos timeframes maiores no instante `ts`."""
    votos: dict[str, str] = {}
    tendencias: list[Tendencia] = []
    forcas: list[float] = []

    for tf in TIMEFRAMES_DE_VIES:
        serie = series.get(tf)
        if serie is None or not len(serie):
            continue
        i = indice_fechado_em(serie, ts)
        if i is None:
            continue
        ctx = ctx_mod.ler(serie, i, lim)
        votos[tf.rotulo] = ctx.tendencia.value
        tendencias.append(ctx.tendencia)
        forcas.append(ctx.forca_tendencia)

    if not tendencias:
        return Vies(Direcao.NEUTRA, 0.0, votos, alinhado=False)

    direcionais = [t for t in tendencias if t is not Tendencia.LATERAL]
    if not direcionais:
        return Vies(Direcao.NEUTRA, 0.0, votos, alinhado=False)

    altas = sum(1 for t in direcionais if t is Tendencia.ALTA)
    baixas = len(direcionais) - altas

    if altas and baixas:
        # Timeframes brigando entre si é indefinição, não tendência fraca.
        return Vies(Direcao.NEUTRA, 0.0, votos, alinhado=False)

    direcao = Direcao.ALTA if altas else Direcao.BAIXA
    alinhado = len(direcionais) == len(TIMEFRAMES_DE_VIES) == len(tendencias)
    forca = sum(forcas) / len(forcas) if forcas else 0.0
    # Consenso parcial vale menos: dois de três concordando não é a mesma coisa que três.
    if not alinhado:
        forca *= len(direcionais) / len(TIMEFRAMES_DE_VIES)

    return Vies(direcao, min(1.0, forca), votos, alinhado)


def aplicar(avaliacao: Avaliacao, vies: Vies, lim: Limiares = PADRAO) -> Avaliacao:
    """Reescreve a avaliação do gatilho à luz do viés dos timeframes maiores.

    A favor do viés: bônus. Contra: exige score quase perfeito, senão veta. Neutro:
    passa sem alteração — não há informação para usar.
    """
    direcao = avaliacao.deteccao.direcao

    if vies.concorda_com(direcao):
        fator = Fator("mtf", 1.0 + lim.bonus_mtf_alinhado * vies.forca, vies.descrever())
        sem_teto = avaliacao.score_sem_teto * fator.multiplicador
        return replace(
            avaliacao,
            fatores=[*avaliacao.fatores, fator],
            score=min(1.0, sem_teto),
            score_sem_teto=sem_teto,
        )

    if vies.contraria(direcao):
        if avaliacao.score >= lim.score_minimo_contra_vies:
            # Sinal excepcional contra o viés: passa, mas fica marcado.
            return replace(
                avaliacao,
                fatores=[*avaliacao.fatores, Fator("mtf", 1.0, f"contra o {vies.descrever()}")],
            )
        return replace(
            avaliacao,
            vetos=[*avaliacao.vetos, f"contra o {vies.descrever()}"],
        )

    return avaliacao


# ---------------------------------------------------------------------------
# Agregação de timeframe
# ---------------------------------------------------------------------------


def agregar(serie: Serie, alvo: Timeframe) -> Serie:
    """Constrói uma série de timeframe maior a partir de uma menor.

    Útil quando a fonte entrega só 5 minutos: em vez de baixar quatro séries, deriva-se
    15/30/60 da mesma base — o que também garante que os quatro timeframes contem
    exatamente a mesma história, sem discrepância de fornecedor.

    Os buckets são ancorados na hora cheia (`09:00`, `09:15`, …), não no primeiro candle
    da série. Ancorar no primeiro candle produziria um "candle de 15min" começando às
    09:07 se a base começasse ali — e nenhuma plataforma desenharia o mesmo gráfico.
    """
    if alvo.value <= serie.timeframe.value:
        raise ValueError(
            f"alvo {alvo.rotulo} não é maior que a origem {serie.timeframe.rotulo}"
        )
    if alvo.value % serie.timeframe.value != 0:
        raise ValueError(
            f"{alvo.rotulo} não é múltiplo inteiro de {serie.timeframe.rotulo}"
        )

    minutos = alvo.value
    baldes: dict[datetime, list[Candle]] = {}
    ordem: list[datetime] = []

    for candle in serie.candles:
        ts = candle.ts
        if alvo is Timeframe.D1:
            chave = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            offset = (ts.hour * 60 + ts.minute) % minutos
            chave = ts.replace(second=0, microsecond=0) - _minutos(offset)
        if chave not in baldes:
            baldes[chave] = []
            ordem.append(chave)
        baldes[chave].append(candle)

    agregados = [
        Candle(
            ts=chave,
            abertura=baldes[chave][0].abertura,
            maxima=max(c.maxima for c in baldes[chave]),
            minima=min(c.minima for c in baldes[chave]),
            fechamento=baldes[chave][-1].fechamento,
            volume=sum(c.volume for c in baldes[chave]),
        )
        for chave in ordem
    ]
    return Serie(serie.ativo, alvo, agregados)


def _minutos(quantidade: int) -> timedelta:
    return timedelta(minutes=quantidade)


def montar_conjunto(serie_base: Serie) -> dict[Timeframe, Serie]:
    """Os timeframes de viés, derivados da série de gatilho.

    Devolve **apenas timeframes estritamente maiores** que o da base — a série de gatilho
    não entra no próprio conjunto de viés.

    A distinção não é cosmética. Incluir a base fazia o gatilho servir de viés para si
    mesmo, e um padrão de **reversão** tem, por definição, direção oposta à tendência em
    que nasce. O resultado era todo sinal de reversão se auto-vetar. Medido em 5.284
    candles de WIN 60min: 64 de 89 candidatas morriam nisso, sobrando 3 sinais em dois
    anos. Em 5min o defeito não aparecia, porque ali o viés vem de 15/30/60 — timeframes
    diferentes do gatilho.

    Conjunto vazio (gatilho em 60min ou mais) significa **sem viés**, e `aplicar` deixa a
    avaliação passar intacta. É o comportamento correto: ausência de informação não é
    informação contrária.
    """
    return {
        tf: agregar(serie_base, tf)
        for tf in TIMEFRAMES_DE_VIES
        if tf.value > serie_base.timeframe.value
    }
