"""Camada 2 — leitura de mercado antes de olhar para a geometria.

Praticamente toda descrição do ebook começa com *"numa tendência de baixa…"*. Isso não é
enfeite: um engolfo de alta no meio de uma alta não é reversão, é continuação de ruído.
Detectar geometria sem contexto é a causa número um de sinal falso, e é por isso que
`Contexto` é argumento **obrigatório** de todo detector.

A tendência é decidida por três evidências, nunca por uma:

1. **Inclinação da EMA** — EMA(9) contra EMA(21), normalizada por ATR (direção)
2. **Estrutura de Dow** — topos e fundos ascendentes ou descendentes (confirmação)
3. **ADX** — força; abaixo do limiar, o veredito é LATERAL e ponto final

O ADX tem poder de veto sobre os outros dois de propósito. EMA e Dow sempre apontam
*alguma* direção, mesmo numa lateralização — é geometria de ruído. O ADX é a única das
três que sabe dizer "não há tendência aqui".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

import numpy as np

from .indicadores import adx as calc_adx
from .indicadores import atr as calc_atr
from .indicadores import ema, swings_confirmados
from .limiares import PADRAO, Limiares
from .tipos import Contexto, Serie, Tendencia


@dataclass(frozen=True, slots=True)
class JanelaPregao:
    """Uma faixa de horário do pregão e como o motor a trata."""

    rotulo: str
    inicio: time
    fim: time
    peso: float
    opera: bool = True


JANELAS_B3 = (
    JanelaPregao("pre-abertura", time(0, 0), time(9, 0), 0.0, opera=False),
    JanelaPregao("abertura", time(9, 0), time(10, 0), 0.85),
    JanelaPregao("manha", time(10, 0), time(12, 0), 1.15),
    JanelaPregao("almoco", time(12, 0), time(14, 0), 0.60),
    JanelaPregao("tarde", time(14, 0), time(16, 0), 1.15),
    JanelaPregao("fechamento", time(16, 0), time(17, 30), 1.00),
    JanelaPregao("ajuste", time(17, 30), time(23, 59, 59), 0.0, opera=False),
)
"""Janelas do pregão em horário de Brasília, com o peso de confluência de cada uma.

**Os pesos abaixo estão pendentes de remedição e não devem ser tratados como evidência.**
Eles foram calibrados sobre uma base que estava 3 horas deslocada (ver
`fontes/mt5.py:hora_do_servidor`), então cada peso está preso à janela errada. A medição
anterior atribuía +0,40R à faixa que ela chamava de "abertura americana"; com o
deslocamento desfeito, aquelas operações eram na verdade das 17h às 18h25 — o fechamento.

Os rótulos eram geográficos e agora são horários, de propósito. `abertura-eua` era
factualmente errado em 14h–16h: a bolsa americana abre 9h30 ET, o que dá **10h30 de
Brasília** no horário de verão de lá e 11h30 fora dele — dentro de `manha`, não de
`tarde`. Um nome que afirma causa ("é a abertura americana que traz direção") convida a
raciocinar por cima de uma premissa não medida; um nome que só diz a hora, não.

Continuam sendo dado e não `if` no meio do código para que o backtest possa substituí-los.
"""


def janela_de(momento: time, janelas=JANELAS_B3) -> JanelaPregao:
    for j in janelas:
        if j.inicio <= momento < j.fim:
            return j
    return janelas[-1]


def _voto_ema(serie: Serie, i: int, atr_i: float, lim: Limiares) -> Tendencia:
    rapida = serie.memo(f"ema_{lim.ema_rapida}", lambda: ema(serie.fechamento, lim.ema_rapida))
    lenta = serie.memo(f"ema_{lim.ema_lenta}", lambda: ema(serie.fechamento, lim.ema_lenta))
    if np.isnan(rapida[i]) or np.isnan(lenta[i]) or atr_i <= 0:
        return Tendencia.LATERAL
    # Separação normalizada: quanto as médias estão distantes em unidades de ATR.
    # Sem normalizar, o mesmo limiar seria frouxo no WDO e severo no WIN.
    separacao = (rapida[i] - lenta[i]) / atr_i
    if separacao > 0.15:
        return Tendencia.ALTA
    if separacao < -0.15:
        return Tendencia.BAIXA
    return Tendencia.LATERAL


def _voto_dow(serie: Serie, i: int, lim: Limiares) -> Tendencia:
    """Topos e fundos ascendentes = alta; descendentes = baixa.

    Só considera pivôs já confirmados em `i` — no tempo real você não sabe que fez um
    topo enquanto o preço não se afastar dele.
    """
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)
    if len(topos) < 2 or len(fundos) < 2:
        return Tendencia.LATERAL

    topos_sobem = topos[-1][1] > topos[-2][1]
    fundos_sobem = fundos[-1][1] > fundos[-2][1]
    if topos_sobem and fundos_sobem:
        return Tendencia.ALTA
    if not topos_sobem and not fundos_sobem:
        return Tendencia.BAIXA
    return Tendencia.LATERAL


def ler(serie: Serie, i: int, lim: Limiares = PADRAO) -> Contexto:
    """Contexto no candle `i`. Só olha para trás — nunca para `i+1`."""
    atr_arr = calc_atr(serie, lim.atr_periodo)
    atr_i = float(atr_arr[i]) if not np.isnan(atr_arr[i]) else 0.0

    # Regime de volatilidade: ATR atual contra a média das últimas ~100 barras.
    # No aquecimento o histórico é só NaN — daí filtrar antes de promediar.
    janela_ini = max(0, i - 100)
    historico = atr_arr[janela_ini : i + 1]
    validos = historico[~np.isnan(historico)]
    media_atr = float(validos.mean()) if validos.size else 0.0
    regime = atr_i / media_atr if media_atr > 0 else 1.0

    momento = serie[i].ts.time()
    janela = janela_de(momento)

    adx_arr, _, _ = calc_adx(serie, lim.adx_periodo)
    adx_i = float(adx_arr[i]) if not np.isnan(adx_arr[i]) else 0.0

    if i < lim.tendencia_min_candles or atr_i <= 0:
        # Histórico insuficiente: declarar tendência aqui seria inventar.
        return Contexto(
            tendencia=Tendencia.LATERAL,
            forca_tendencia=0.0,
            atr=atr_i,
            regime_volatilidade=regime,
            janela_pregao=janela.rotulo,
            peso_horario=(janela.peso if lim.usar_peso_horario else 1.0),
            indice=i,
        )

    # ADX manda: sem força, não há tendência para reverter nem para continuar.
    if adx_i < lim.adx_lateral_max:
        tendencia = Tendencia.LATERAL
        forca = 0.0
    else:
        voto_ema = _voto_ema(serie, i, atr_i, lim)
        voto_dow = _voto_dow(serie, i, lim)
        forca = min(1.0, max(0.0, (adx_i - lim.adx_lateral_max) / 20.0))

        if voto_ema is voto_dow and voto_ema is not Tendencia.LATERAL:
            tendencia = voto_ema
        elif voto_ema is not Tendencia.LATERAL and voto_dow is Tendencia.LATERAL:
            # Médias já viraram, estrutura ainda não confirmou: aceita com força menor.
            tendencia = voto_ema
            forca *= 0.6
        elif voto_dow is not Tendencia.LATERAL and voto_ema is Tendencia.LATERAL:
            tendencia = voto_dow
            forca *= 0.6
        else:
            # Médias e estrutura discordando é indefinição, não tendência fraca.
            tendencia = Tendencia.LATERAL
            forca = 0.0

    return Contexto(
        tendencia=tendencia,
        forca_tendencia=forca,
        atr=atr_i,
        regime_volatilidade=regime,
        janela_pregao=janela.rotulo,
        peso_horario=(janela.peso if lim.usar_peso_horario else 1.0),
        indice=i,
    )


def opera_agora(ctx: Contexto, janelas=JANELAS_B3) -> bool:
    """Se a janela atual permite abrir posição nova.

    Separado do peso: `ajuste` e `pre-abertura` têm peso 0, mas o motor precisa
    distinguir "vale pouco" de "não abrir de jeito nenhum".
    """
    return any(j.rotulo == ctx.janela_pregao and j.opera for j in janelas)
