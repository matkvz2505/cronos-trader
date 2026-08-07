"""Indicadores técnicos em numpy.

Todos devolvem um array do **mesmo tamanho** da entrada, com `NaN` no período de
aquecimento. Isso é o que permite indexar indicador e candle pelo mesmo índice sem
deslocamento — e deslocamento silencioso de um candle é o bug clássico que faz um
backtest parecer lucrativo (você olhou o futuro sem perceber).

Suavização de Wilder onde o indicador original a define (ATR, ADX, RSI), não EMA comum:
os valores publicados por qualquer plataforma seguem Wilder, e divergir aqui faria o
nosso "ADX 22" não bater com o ADX 22 da tela do usuário.
"""

from __future__ import annotations

import numpy as np

from .tipos import Serie


def _vazio(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=float)


def _wilder(valores: np.ndarray, periodo: int) -> np.ndarray:
    """Suavização de Wilder: primeiro ponto é a média simples, depois recursivo.

    `s[i] = (s[i-1] * (periodo - 1) + valores[i]) / periodo`

    A semente pula o prefixo de `NaN` da entrada em vez de tentar promediá-lo. Isso é
    necessário porque o ADX aplica Wilder sobre o DX, que já nasce com aquecimento
    próprio — semear na posição fixa `periodo - 1` cairia em cima de NaN e envenenaria
    toda a recursão daí para frente.
    """
    n = len(valores)
    saida = _vazio(n)
    if n < periodo or periodo <= 0:
        return saida

    validos = np.flatnonzero(~np.isnan(valores))
    if validos.size < periodo:
        return saida

    inicio = int(validos[0])
    semente = inicio + periodo - 1
    if semente >= n:
        return saida

    saida[semente] = float(np.mean(valores[inicio : semente + 1]))
    for i in range(semente + 1, n):
        anterior = saida[i - 1]
        atual = valores[i]
        if np.isnan(anterior) or np.isnan(atual):
            continue
        saida[i] = (anterior * (periodo - 1) + atual) / periodo
    return saida


def rma(valores: np.ndarray, periodo: int) -> np.ndarray:
    """Média móvel de Wilder (RMA), exposta publicamente.

    É a mesma suavização que ATR, ADX e RSI usam internamente. Como média de preço ela
    tem uma característica própria: a inércia de uma RMA(N) equivale à de uma EMA(2N-1),
    então a RMA(400) responde como uma EMA(799).

    Isso a torna inútil para timing e ótima para **regime** — a pergunta "de que lado do
    mercado estamos" não deveria mudar a cada cinco minutos, e uma média que quase não se
    move é exatamente o instrumento certo para respondê-la.
    """
    return _wilder(valores, periodo)


def sma(valores: np.ndarray, periodo: int) -> np.ndarray:
    """Média móvel aritmética — a 'média aritmética' pedida no escopo."""
    n = len(valores)
    saida = _vazio(n)
    if n < periodo or periodo <= 0:
        return saida
    acumulado = np.cumsum(np.insert(valores, 0, 0.0))
    saida[periodo - 1 :] = (acumulado[periodo:] - acumulado[:-periodo]) / periodo
    return saida


def ema(valores: np.ndarray, periodo: int) -> np.ndarray:
    """Média exponencial, semeada com a SMA do primeiro período."""
    n = len(valores)
    saida = _vazio(n)
    if n < periodo or periodo <= 0:
        return saida
    k = 2.0 / (periodo + 1.0)
    saida[periodo - 1] = float(np.mean(valores[:periodo]))
    for i in range(periodo, n):
        saida[i] = valores[i] * k + saida[i - 1] * (1.0 - k)
    return saida


def true_range(maxima: np.ndarray, minima: np.ndarray, fechamento: np.ndarray) -> np.ndarray:
    n = len(fechamento)
    tr = _vazio(n)
    if n == 0:
        return tr
    tr[0] = maxima[0] - minima[0]
    if n > 1:
        anterior = fechamento[:-1]
        tr[1:] = np.maximum.reduce(
            [
                maxima[1:] - minima[1:],
                np.abs(maxima[1:] - anterior),
                np.abs(minima[1:] - anterior),
            ]
        )
    return tr


def atr(serie: Serie, periodo: int = 14) -> np.ndarray:
    """Average True Range — o denominador de praticamente todo limiar do motor.

    Memoizado na série: o backtest pede ATR a cada candle, e recalcular seria quadrático.
    """

    def calcular() -> np.ndarray:
        return _wilder(true_range(serie.maxima, serie.minima, serie.fechamento), periodo)

    return serie.memo(f"atr_{periodo}", calcular)


def rsi(valores: np.ndarray, periodo: int = 14) -> np.ndarray:
    n = len(valores)
    saida = _vazio(n)
    if n <= periodo:
        return saida
    delta = np.diff(valores, prepend=valores[0])
    ganhos = _wilder(np.where(delta > 0, delta, 0.0), periodo)
    perdas = _wilder(np.where(delta < 0, -delta, 0.0), periodo)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(perdas > 0, ganhos / perdas, np.inf)
        saida = 100.0 - (100.0 / (1.0 + rs))
    saida[: periodo - 1] = np.nan
    return saida


def adx(serie: Serie, periodo: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ADX de Wilder. Devolve `(adx, +DI, -DI)`.

    O ADX mede **força** de tendência, não direção — é o que permite ao contexto dizer
    "isto é lateral" e desligar os padrões de reversão, que precisam de algo para
    reverter.
    """

    def calcular():
        maxima, minima, fechamento = serie.maxima, serie.minima, serie.fechamento
        n = len(fechamento)
        if n < periodo * 2:
            return _vazio(n), _vazio(n), _vazio(n)

        sobe = np.diff(maxima, prepend=maxima[0])
        desce = -np.diff(minima, prepend=minima[0])
        dm_mais = np.where((sobe > desce) & (sobe > 0), sobe, 0.0)
        dm_menos = np.where((desce > sobe) & (desce > 0), desce, 0.0)

        tr_suave = _wilder(true_range(maxima, minima, fechamento), periodo)
        with np.errstate(divide="ignore", invalid="ignore"):
            di_mais = 100.0 * _wilder(dm_mais, periodo) / tr_suave
            di_menos = 100.0 * _wilder(dm_menos, periodo) / tr_suave
            soma = di_mais + di_menos
            dx = np.where(soma > 0, 100.0 * np.abs(di_mais - di_menos) / soma, np.nan)
        return _wilder(dx, periodo), di_mais, di_menos

    return serie.memo(f"adx_{periodo}", calcular)


def vwap(serie: Serie) -> np.ndarray:
    """VWAP com **reset diário**.

    O reset não é detalhe: VWAP acumulado desde o início da base não significa nada
    para day trade. O que os operadores olham é o preço médio ponderado *do dia*, e é
    contra ele que o preço reage.
    """

    def calcular() -> np.ndarray:
        n = len(serie)
        saida = _vazio(n)
        if n == 0:
            return saida
        tipico = (serie.maxima + serie.minima + serie.fechamento) / 3.0
        volume = serie.volume
        soma_pv = 0.0
        soma_v = 0.0
        dia_atual = None
        for i, candle in enumerate(serie.candles):
            dia = candle.ts.date()
            if dia != dia_atual:
                dia_atual = dia
                soma_pv = 0.0
                soma_v = 0.0
            soma_pv += tipico[i] * volume[i]
            soma_v += volume[i]
            saida[i] = soma_pv / soma_v if soma_v > 0 else tipico[i]
        return saida

    return serie.memo("vwap", calcular)


def macd(
    valores: np.ndarray, rapida: int = 12, lenta: int = 26, sinal: int = 9
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD clássico. Devolve `(linha, sinal, histograma)`.

    O histograma é o que carrega informação operacional: ele muda de sinal antes do
    cruzamento das linhas, então mede aceleração e não só direção.
    """
    linha = ema(valores, rapida) - ema(valores, lenta)
    # A linha de sinal é uma EMA da linha do MACD, que já tem NaN no aquecimento — daí
    # semear a partir do primeiro valor válido em vez da posição fixa.
    validos = np.flatnonzero(~np.isnan(linha))
    linha_sinal = _vazio(len(valores))
    if validos.size >= sinal:
        inicio = int(validos[0])
        parcial = ema(linha[inicio:], sinal)
        linha_sinal[inicio:] = parcial
    return linha, linha_sinal, linha - linha_sinal


def estocastico(
    serie: Serie, periodo: int = 14, suavizacao_k: int = 3, suavizacao_d: int = 3
) -> tuple[np.ndarray, np.ndarray]:
    """Estocástico lento. Devolve `(%K, %D)`.

    Mede onde o fechamento caiu dentro do range do período — perto da máxima indica
    força compradora. Diferente do RSI, que compara ganhos e perdas: os dois podem
    divergir, e a divergência costuma ser mais informativa que qualquer um sozinho.
    """

    def calcular():
        maxima, minima, fechamento = serie.maxima, serie.minima, serie.fechamento
        n = len(fechamento)
        bruto = _vazio(n)
        for i in range(periodo - 1, n):
            janela_max = maxima[i - periodo + 1 : i + 1].max()
            janela_min = minima[i - periodo + 1 : i + 1].min()
            amplitude = janela_max - janela_min
            if amplitude > 0:
                bruto[i] = 100.0 * (fechamento[i] - janela_min) / amplitude
        k = sma(bruto, suavizacao_k)
        return k, sma(k, suavizacao_d)

    return serie.memo(f"estocastico_{periodo}_{suavizacao_k}_{suavizacao_d}", calcular)


def obv(serie: Serie) -> np.ndarray:
    """On-Balance Volume — volume acumulado com o sinal da variação de preço.

    Serve para divergência: preço fazendo máxima nova com OBV sem acompanhar significa
    que a alta está acontecendo com menos gente do que a anterior.
    """

    def calcular() -> np.ndarray:
        fechamento, volume = serie.fechamento, serie.volume
        n = len(fechamento)
        saida = np.zeros(n, dtype=float)
        for i in range(1, n):
            if fechamento[i] > fechamento[i - 1]:
                saida[i] = saida[i - 1] + volume[i]
            elif fechamento[i] < fechamento[i - 1]:
                saida[i] = saida[i - 1] - volume[i]
            else:
                saida[i] = saida[i - 1]
        return saida

    return serie.memo("obv", calcular)


def bollinger(
    valores: np.ndarray, periodo: int = 20, desvios: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Devolve `(superior, media, inferior)`."""
    media = sma(valores, periodo)
    n = len(valores)
    desvio = _vazio(n)
    for i in range(periodo - 1, n):
        desvio[i] = float(np.std(valores[i - periodo + 1 : i + 1]))
    return media + desvios * desvio, media, media - desvios * desvio


def swings(
    serie: Serie, lookback: int = 5
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Topos e fundos pivô confirmados. Devolve `(topos, fundos)` como `(índice, preço)`.

    Um topo é um candle cuja máxima supera as `lookback` máximas de cada lado. Note que
    isso só é confirmável `lookback` candles **depois** — a lista nunca inclui pivôs da
    borda direita. Essa defasagem é real, não um defeito: no tempo real você também não
    sabe que fez um topo até o preço se afastar dele.
    """

    def calcular():
        maxima, minima = serie.maxima, serie.minima
        n = len(serie)
        topos: list[tuple[int, float]] = []
        fundos: list[tuple[int, float]] = []
        for i in range(lookback, n - lookback):
            janela_max = maxima[i - lookback : i + lookback + 1]
            janela_min = minima[i - lookback : i + lookback + 1]
            if maxima[i] == janela_max.max() and maxima[i] > maxima[i - 1]:
                topos.append((i, float(maxima[i])))
            if minima[i] == janela_min.min() and minima[i] < minima[i - 1]:
                fundos.append((i, float(minima[i])))
        return topos, fundos

    return serie.memo(f"swings_{lookback}", calcular)


def swings_confirmados(
    serie: Serie, i: int, lookback: int = 5
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Os pivôs que **já estavam confirmados** no candle `i`.

    A condição correta é `indice + lookback <= i`, não `indice <= i`. Um pivô em `j` só
    se confirma quando existem `lookback` candles depois dele — filtrar apenas por
    `indice <= i` deixaria vazar até `lookback` candles de futuro para dentro da leitura
    de tendência, de Fibonacci e das zonas de suporte.

    São poucos candles, e é exatamente o tipo de vazamento que não aparece em nenhum
    gráfico e faz o backtest inteiro parecer melhor do que é.

    Use esta função em todo consumo causal. `swings()` cru serve para inspeção e para
    desenhar o gráfico, onde olhar a série inteira é legítimo.
    """
    topos, fundos = swings(serie, lookback)
    limite = i - lookback
    return (
        [t for t in topos if t[0] <= limite],
        [f for f in fundos if f[0] <= limite],
    )
