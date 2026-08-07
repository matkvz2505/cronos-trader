"""Mapa de níveis onde o preço já mostrou que reage.

O motor não usa isso para gerar sinal — usa para responder "o padrão aconteceu num lugar
que importava?". Um engolfo de alta exatamente na mínima de ontem é uma coisa; o mesmo
engolfo no meio do range do dia é outra.

Cinco famílias de nível, todas com a mesma justificativa: são preços onde há **ordem
pendurada no book** por motivos que independem do nosso gráfico.

| Origem | Por que há ordem ali |
|---|---|
| pivô | topos/fundos anteriores viraram stop de quem operou |
| dia anterior | máxima/mínima/fechamento são referência de todo mundo |
| abertura | range dos primeiros 30min baliza o dia inteiro |
| VWAP | institucional usa como benchmark de execução |
| redondo | número inteiro atrai ordem por puro viés psicológico |
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .indicadores import swings_confirmados, vwap
from .limiares import PADRAO, Limiares
from .tipos import Serie

ESCALA_REDONDA = (1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
"""Incrementos "redondos" candidatos. O escolhido depende do ATR, para funcionar tanto
no WIN (ATR ~100 pontos, redondo a cada 500) quanto no WDO (ATR ~15, redondo a cada 50).
"""

MINUTOS_ABERTURA = 30
"""Duração do range de abertura. Os primeiros 30 minutos costumam definir os extremos
que o resto do dia usa como referência."""


@dataclass(frozen=True, slots=True)
class Zona:
    preco: float
    origem: str
    forca: float
    """0..1 — quanto peso essa origem tem. Pivô tocado várias vezes vale mais que um
    número redondo qualquer."""

    def distancia_atr(self, preco: float, atr: float) -> float:
        if atr <= 0:
            return float("inf")
        return abs(self.preco - preco) / atr


def incremento_redondo(atr: float) -> int:
    """Escolhe o passo de "número redondo" adequado à volatilidade do ativo.

    Alvo: algo em torno de 5× o ATR. Mais fino que isso marca qualquer preço como
    redondo e o filtro perde sentido; mais grosso e quase nunca há um nível por perto.
    """
    if atr <= 0:
        return ESCALA_REDONDA[0]
    alvo = atr * 5.0
    return min(ESCALA_REDONDA, key=lambda passo: abs(passo - alvo))


def _mapa_de_dias(serie: Serie) -> dict[date, tuple[int, int]]:
    """Primeiro e último índice de cada pregão. Só usa timestamps, nunca preços."""

    def calcular() -> dict[date, tuple[int, int]]:
        mapa: dict[date, tuple[int, int]] = {}
        for i, candle in enumerate(serie.candles):
            dia = candle.ts.date()
            if dia not in mapa:
                mapa[dia] = (i, i)
            else:
                mapa[dia] = (mapa[dia][0], i)
        return mapa

    return serie.memo("mapa_dias", calcular)


def _dia_anterior(serie: Serie, i: int) -> tuple[int, int] | None:
    mapa = _mapa_de_dias(serie)
    hoje = serie[i].ts.date()
    anteriores = [d for d in mapa if d < hoje]
    if not anteriores:
        return None
    return mapa[max(anteriores)]


def _zonas_do_dia_anterior(serie: Serie, i: int) -> list[Zona]:
    faixa = _dia_anterior(serie, i)
    if faixa is None:
        return []
    inicio, fim = faixa
    candles = serie.candles[inicio : fim + 1]
    if not candles:
        return []
    return [
        Zona(max(c.maxima for c in candles), "maxima-dia-anterior", 0.85),
        Zona(min(c.minima for c in candles), "minima-dia-anterior", 0.85),
        Zona(candles[-1].fechamento, "fechamento-dia-anterior", 0.70),
    ]


def _zonas_da_abertura(serie: Serie, i: int) -> list[Zona]:
    """Range dos primeiros 30 minutos do pregão corrente, truncado em `i`.

    Truncar importa: às 9h10 o range de abertura ainda não terminou de se formar, e usar
    o range completo seria olhar para o futuro.
    """
    mapa = _mapa_de_dias(serie)
    hoje = serie[i].ts.date()
    if hoje not in mapa:
        return []
    inicio = mapa[hoje][0]
    minutos = serie.timeframe.value
    quantidade = max(1, MINUTOS_ABERTURA // minutos)
    fim = min(inicio + quantidade - 1, i)
    candles = serie.candles[inicio : fim + 1]
    if not candles:
        return []
    return [
        Zona(max(c.maxima for c in candles), "maxima-abertura", 0.70),
        Zona(min(c.minima for c in candles), "minima-abertura", 0.70),
    ]


def _zonas_de_pivo(serie: Serie, i: int, lim: Limiares) -> list[Zona]:
    """Topos e fundos confirmados, com peso maior para os mais recentes.

    Um pivô de duas semanas atrás ainda é um nível, mas os stops de quem operou nele já
    foram executados. O decaimento reflete isso.
    """
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)
    zonas: list[Zona] = []
    for indice, preco in list(topos) + list(fundos):
        idade = i - indice
        # Decai até um piso de 0.4: pivô antigo perde relevância, não desaparece.
        forca = max(0.40, 1.0 - idade / 400.0)
        zonas.append(Zona(preco, "pivo", forca))
    return zonas


def _zonas_redondas(preco: float, atr: float) -> list[Zona]:
    passo = incremento_redondo(atr)
    base = round(preco / passo) * passo
    return [
        Zona(float(base - passo), "redondo", 0.45),
        Zona(float(base), "redondo", 0.55),
        Zona(float(base + passo), "redondo", 0.45),
    ]


def mapear(serie: Serie, i: int, atr: float, lim: Limiares = PADRAO) -> list[Zona]:
    """Todas as zonas relevantes visíveis no candle `i`.

    Nada aqui olha para `i+1`.
    """
    preco = serie[i].fechamento
    zonas: list[Zona] = []
    zonas.extend(_zonas_de_pivo(serie, i, lim))
    zonas.extend(_zonas_do_dia_anterior(serie, i))
    zonas.extend(_zonas_da_abertura(serie, i))
    zonas.extend(_zonas_redondas(preco, atr))

    valores_vwap = vwap(serie)
    if i < len(valores_vwap) and valores_vwap[i] == valores_vwap[i]:  # não-NaN
        zonas.append(Zona(float(valores_vwap[i]), "vwap", 0.75))

    return zonas


def proximas(
    preco: float, zonas: list[Zona], atr: float, lim: Limiares = PADRAO
) -> list[Zona]:
    """Zonas dentro da tolerância, da mais forte para a mais fraca."""
    if atr <= 0:
        return []
    limite = lim.tolerancia_zona_atr
    perto = [z for z in zonas if z.distancia_atr(preco, atr) <= limite]
    return sorted(perto, key=lambda z: (-z.forca, z.distancia_atr(preco, atr)))


def mais_forte(
    preco: float, zonas: list[Zona], atr: float, lim: Limiares = PADRAO
) -> Zona | None:
    encontradas = proximas(preco, zonas, atr, lim)
    return encontradas[0] if encontradas else None


FORCA_MINIMA_ALVO = 0.60
"""Força mínima para uma zona servir de **alvo**.

Zona fraca não segura movimento. Um número redondo (0.45) ou um pivô de meses atrás
(0.40) são referências úteis para julgar *onde entrar*, mas usá-los como teto do alvo é
outra coisa: o preço passa por eles sem desacelerar.

Medido em 60 mil candles reais de WIN, aceitar qualquer zona como alvo matava **1.820 de
1.938 candidatas** por R:R insuficiente — 94% das rejeições da camada de decisão. O
motor não estava sendo seletivo, estava mirando em obstáculos que não existem.
"""


def obstaculos(
    preco: float,
    zonas: list[Zona],
    acima: bool,
    atr: float,
    distancia_minima_atr: float = 0.5,
    forca_minima: float = FORCA_MINIMA_ALVO,
) -> list[Zona]:
    """Zonas **relevantes** na direção do movimento, da mais próxima à mais distante.

    Devolve a lista inteira, e não só a primeira, porque quem escolhe o alvo precisa
    poder descartar a mais próxima e olhar a seguinte: uma zona logo acima da entrada é
    um alvo que não paga o risco, e mirar nela mata a operação em vez de protegê-la.

    Dois filtros, com motivos diferentes:

    - `distancia_minima_atr` descarta zonas coladas no preço — não pagam nem o custo.
    - `forca_minima` descarta zonas fracas: elas não param o preço, então não são alvo.
      Continuam valendo como confluência de **entrada**, onde a pergunta é outra.
    """
    if atr <= 0:
        return []
    candidatas = [
        z
        for z in zonas
        if (z.preco > preco if acima else z.preco < preco)
        and z.distancia_atr(preco, atr) >= distancia_minima_atr
        and z.forca >= forca_minima
    ]
    return sorted(candidatas, key=lambda z: abs(z.preco - preco))


def proximo_obstaculo(
    preco: float,
    zonas: list[Zona],
    acima: bool,
    atr: float,
    distancia_minima_atr: float = 0.5,
    forca_minima: float = FORCA_MINIMA_ALVO,
) -> Zona | None:
    """A zona relevante mais próxima. Conveniência sobre `obstaculos`."""
    encontradas = obstaculos(preco, zonas, acima, atr, distancia_minima_atr, forca_minima)
    return encontradas[0] if encontradas else None
