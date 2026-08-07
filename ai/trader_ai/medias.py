"""Camada de médias móveis — o esqueleto direcional que sustenta a leitura.

Quatro médias, cada uma com um papel diferente. Não são quatro versões da mesma coisa:

| Média | Papel |
|---|---|
| **EMA 9** | condução do trade e stop móvel — reage rápido demais para ser filtro |
| **SMA 21** | viés direcional do dia; funciona bem como suporte/resistência |
| **SMA 200** | a média mais observada do mundo; perdê-la ou superá-la é gatilho |
| **RMA 400 (Wilder)** | regime de fundo; quase não se move, e é isso que a torna útil |

A de Wilder merece nota. A suavização de Wilder com período N tem a inércia de uma EMA de
`2N-1` — a RMA(400) responde como uma EMA(799). Ela não serve para timing e nunca deveria
ser usada assim; serve para responder "de que lado do mercado estamos", uma pergunta que
não muda em cinco minutos.

O que a camada entrega não é o valor das médias: é o **alinhamento** entre elas. Quatro
médias empilhadas na ordem e com o preço do lado certo descrevem um mercado com estrutura;
médias embaraçadas descrevem um mercado sem direção, onde padrão de reversão é ruído.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .indicadores import ema, rma, sma
from .tipos import Direcao, Serie

PERIODO_CONDUCAO = 9
PERIODO_VIES = 21
PERIODO_GLOBAL = 200
PERIODO_REGIME = 400


@dataclass(frozen=True, slots=True)
class RegimeMedias:
    """Leitura do conjunto de médias num candle."""

    ema9: float | None
    sma21: float | None
    sma200: float | None
    rma400: float | None

    direcao: Direcao
    """Direção do empilhamento. NEUTRA quando as médias estão embaraçadas."""

    alinhamento: float
    """0..1 — quantas das comparações de ordem estão a favor da direção.

    1.0 significa preço > EMA9 > SMA21 > SMA200 > RMA400 (ou o espelho na baixa).
    """

    distancia_atr: float
    """Distância do preço à SMA21, em ATR. Mede esticamento.

    Preço muito longe da média de viés é onde a reversão à média puxa contra a entrada —
    comprar 3 ATR acima da 21 é comprar o topo do impulso.
    """

    acima_da_200: bool | None
    disponivel: bool

    @property
    def descricao(self) -> str:
        if not self.disponivel:
            return "médias ainda aquecendo"
        if self.direcao is Direcao.NEUTRA:
            return "médias embaraçadas — sem estrutura direcional"
        lado = "alta" if self.direcao is Direcao.ALTA else "baixa"
        return f"médias empilhadas para {lado} ({self.alinhamento:.0%} de alinhamento)"

    def concorda_com(self, direcao: Direcao) -> bool:
        return self.direcao is not Direcao.NEUTRA and self.direcao is direcao

    def contraria(self, direcao: Direcao) -> bool:
        return self.direcao is not Direcao.NEUTRA and self.direcao is direcao.oposta


def _valor(arr: np.ndarray, i: int) -> float | None:
    if i >= len(arr):
        return None
    v = float(arr[i])
    return None if np.isnan(v) else v


def conjunto(serie: Serie) -> dict[str, np.ndarray]:
    """As quatro médias, memoizadas na série."""
    return {
        "ema9": serie.memo("m_ema9", lambda: ema(serie.fechamento, PERIODO_CONDUCAO)),
        "sma21": serie.memo("m_sma21", lambda: sma(serie.fechamento, PERIODO_VIES)),
        "sma200": serie.memo("m_sma200", lambda: sma(serie.fechamento, PERIODO_GLOBAL)),
        "rma400": serie.memo("m_rma400", lambda: rma(serie.fechamento, PERIODO_REGIME)),
    }


def ler(serie: Serie, i: int, atr: float) -> RegimeMedias:
    """Regime de médias no candle `i`. Só olha para trás."""
    m = conjunto(serie)
    e9 = _valor(m["ema9"], i)
    s21 = _valor(m["sma21"], i)
    s200 = _valor(m["sma200"], i)
    r400 = _valor(m["rma400"], i)
    preco = serie[i].fechamento

    # A RMA 400 pode não existir em série curta; o regime ainda é legível sem ela, com
    # peso menor. Exigir as quatro deixaria o motor cego nos primeiros meses de dados.
    disponiveis = [v for v in (e9, s21, s200, r400) if v is not None]
    if len(disponiveis) < 2 or s21 is None:
        return RegimeMedias(e9, s21, s200, r400, Direcao.NEUTRA, 0.0, 0.0, None, False)

    escada = [preco, e9, s21, s200, r400]
    presentes = [v for v in escada if v is not None]

    # Conta quantos pares consecutivos estão na ordem de alta e de baixa.
    pares = list(zip(presentes, presentes[1:], strict=False))
    para_alta = sum(1 for a, b in pares if a > b)
    para_baixa = sum(1 for a, b in pares if a < b)
    total = len(pares)

    if total == 0:
        direcao, alinhamento = Direcao.NEUTRA, 0.0
    elif para_alta == total:
        direcao, alinhamento = Direcao.ALTA, 1.0
    elif para_baixa == total:
        direcao, alinhamento = Direcao.BAIXA, 1.0
    elif para_alta / total >= 0.75:
        direcao, alinhamento = Direcao.ALTA, para_alta / total
    elif para_baixa / total >= 0.75:
        direcao, alinhamento = Direcao.BAIXA, para_baixa / total
    else:
        # Nem 75% de concordância: as médias estão cruzadas entre si. Isso não é
        # "tendência fraca", é ausência de estrutura — e é o cenário onde padrão de
        # reversão mais engana.
        direcao, alinhamento = Direcao.NEUTRA, max(para_alta, para_baixa) / total

    distancia = abs(preco - s21) / atr if atr > 0 else 0.0

    return RegimeMedias(
        ema9=e9,
        sma21=s21,
        sma200=s200,
        rma400=r400,
        direcao=direcao,
        alinhamento=alinhamento,
        distancia_atr=distancia,
        acima_da_200=(preco > s200) if s200 is not None else None,
        disponivel=True,
    )


def cruzamento_recente(serie: Serie, i: int, janela: int = 5) -> str | None:
    """Cruzamento de EMA9 × SMA21 nos últimos `janela` candles.

    Cruzamento é evento, não estado: importa porque marca o instante em que o viés virou,
    e um padrão que aparece logo depois pega o movimento no começo em vez do fim.
    """
    m = conjunto(serie)
    e9, s21 = m["ema9"], m["sma21"]
    if i < janela or i >= len(e9):
        return None

    for k in range(i, max(i - janela, 0), -1):
        atual_e9, atual_s21 = _valor(e9, k), _valor(s21, k)
        ant_e9, ant_s21 = _valor(e9, k - 1), _valor(s21, k - 1)
        if None in (atual_e9, atual_s21, ant_e9, ant_s21):
            continue
        if ant_e9 <= ant_s21 and atual_e9 > atual_s21:
            return f"EMA9 cruzou a SMA21 para cima há {i - k} candle(s)"
        if ant_e9 >= ant_s21 and atual_e9 < atual_s21:
            return f"EMA9 cruzou a SMA21 para baixo há {i - k} candle(s)"
    return None
