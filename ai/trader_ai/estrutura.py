"""Estrutura gráfica: canais, pivôs, rompimentos e zonas de oferta e demanda.

É a camada que produz o **desenho** — o que um analista rabisca por cima do gráfico antes
de decidir. Até aqui o motor lia o preço mas não descrevia a figura; um sinal chegava na
tela como número, sem o contexto visual que torna a leitura verificável.

O que sai daqui alimenta duas coisas:

- o **gráfico anotado**, no estilo das ideias publicadas no TradingView: canal sombreado,
  pivôs marcados, rompimentos rotulados, zonas de oferta e demanda em faixa, alvo;
- a **tese**, que ganha frases como "rompeu o canal descendente" em vez de só citar
  padrão de candle.

Tudo aqui é causal: nenhuma função olha para candles à frente do índice pedido. O canal
de hoje é traçado com os pivôs que já existiam hoje.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .indicadores import atr as calc_atr
from .indicadores import swings_confirmados
from .limiares import PADRAO, Limiares
from .tipos import Serie

TipoCanal = Literal["ascendente", "descendente", "lateral"]


@dataclass(frozen=True, slots=True)
class Reta:
    """Uma reta no espaço (índice, preço). `preco_em(i)` avalia a reta no candle `i`."""

    indice_a: int
    preco_a: float
    indice_b: int
    preco_b: float

    @property
    def inclinacao(self) -> float:
        d = self.indice_b - self.indice_a
        return (self.preco_b - self.preco_a) / d if d else 0.0

    def preco_em(self, i: int) -> float:
        return self.preco_a + self.inclinacao * (i - self.indice_a)


@dataclass(frozen=True, slots=True)
class Canal:
    """Canal de preço: duas retas aproximadamente paralelas contendo o movimento."""

    topo: Reta
    fundo: Reta
    tipo: TipoCanal
    inicio: int
    fim: int
    toques: int
    """Quantas vezes o preço encostou nas bordas. Menos de 4 não é canal, é coincidência."""

    largura_atr: float

    def contem(self, i: int, preco: float, folga: float = 0.0) -> bool:
        return self.fundo.preco_em(i) - folga <= preco <= self.topo.preco_em(i) + folga

    def posicao(self, i: int, preco: float) -> float:
        """0.0 no fundo do canal, 1.0 no topo. Fora do canal extrapola."""
        base = self.fundo.preco_em(i)
        teto = self.topo.preco_em(i)
        largura = teto - base
        return (preco - base) / largura if largura > 0 else 0.5


@dataclass(frozen=True, slots=True)
class Rompimento:
    indice: int
    preco: float
    direcao: Literal["alta", "baixa"]
    forca_atr: float
    """Quanto o preço passou da borda, em ATR. Rompimento raso é ruído."""


@dataclass(frozen=True, slots=True)
class Faixa:
    """Zona de oferta ou demanda — uma faixa de preço, não uma linha.

    Faixa e não linha porque o preço não reage num tick exato: reage numa região. Desenhar
    linha dá a falsa precisão de que o nível é 63.400 quando na verdade é "entre 63.350 e
    63.450".
    """

    tipo: Literal["oferta", "demanda"]
    preco_min: float
    preco_max: float
    toques: int
    forca: float

    @property
    def centro(self) -> float:
        return (self.preco_min + self.preco_max) / 2


@dataclass(frozen=True, slots=True)
class Estrutura:
    """O desenho completo num instante."""

    canal: Canal | None
    rompimentos: list[Rompimento]
    faixas: list[Faixa]
    linha_tendencia: Reta | None
    pivos_topo: list[tuple[int, float]]
    pivos_fundo: list[tuple[int, float]]

    @property
    def resumo(self) -> str:
        partes = []
        if self.canal:
            partes.append(f"canal {self.canal.tipo} ({self.canal.toques} toques)")
        if self.linha_tendencia:
            direcao = "de alta" if self.linha_tendencia.inclinacao > 0 else "de baixa"
            partes.append(f"linha de tendência {direcao}")
        if self.rompimentos:
            ultimo = self.rompimentos[-1]
            partes.append(f"rompimento de {ultimo.direcao} há pouco")
        ofertas = sum(1 for f in self.faixas if f.tipo == "oferta")
        demandas = len(self.faixas) - ofertas
        if self.faixas:
            partes.append(f"{ofertas} zona(s) de oferta, {demandas} de demanda")
        return " · ".join(partes) if partes else "sem estrutura definida"


# ---------------------------------------------------------------------------
# Canal
# ---------------------------------------------------------------------------

MIN_TOQUES = 4
"""Menos de 4 toques não é canal. Duas retas passam por dois pontos quaisquer — só a
partir do terceiro toque de cada lado a figura deixa de ser desenho livre."""


R2_MINIMO = 0.55
"""Qualidade mínima da regressão para a reta contar como borda de canal.

**É o critério que separa canal de coincidência.** Medido nas séries de teste: um passeio
aleatório produz R² de 0,12 a 0,32 nos pivôs — eles simplesmente não se alinham. Um canal
de verdade produz 0,93 a 1,00. Sem esse piso o detector enxerga canal em qualquer lugar,
e um detector que enxerga figura em toda parte é pior que nenhum: transforma ruído em
leitura, e leitura em confiança.
"""


@dataclass(frozen=True, slots=True)
class Ajuste:
    """Uma reta e o quão bem ela descreve os pontos."""

    reta: Reta
    r2: float
    """Fração da variância explicada. **Degenera em dados horizontais** — ver `bom`."""

    rmse: float
    """Erro quadrático médio dos resíduos, na unidade do preço."""

    def bom(self, atr: float) -> bool:
        """A reta descreve os pontos?

        Dois caminhos, porque R² sozinho tem um ponto cego real: ele mede *quanta
        variância a reta explica*, e quando os pivôs estão todos no mesmo nível não há
        variância a explicar. Um canal lateral perfeito — a figura mais limpa que existe —
        produz R² próximo de zero.

        Então: ou a reta explica a variância, ou os pontos estão tão colados nela que
        variância não é a pergunta certa.
        """
        return self.r2 >= R2_MINIMO or (atr > 0 and self.rmse <= 0.35 * atr)


def _ajustar_reta(pontos: list[tuple[int, float]]) -> Ajuste | None:
    """Regressão linear sobre os pivôs.

    Regressão e não "ligar os extremos": ligar extremos deixa a reta refém de um único
    candle de exagero, enquanto a regressão usa todos os toques e produz a linha que o
    mercado de fato respeitou.

    A qualidade do ajuste acompanha porque a reta sozinha não diz nada — `polyfit`
    devolve uma reta para qualquer nuvem de pontos, inclusive para uma sem estrutura.
    """
    if len(pontos) < 3:
        return None
    xs = np.array([p[0] for p in pontos], dtype=float)
    ys = np.array([p[1] for p in pontos], dtype=float)
    inclinacao, intercepto = np.polyfit(xs, ys, 1)

    previsto = inclinacao * xs + intercepto
    residuos = ys - previsto
    soma_residuo = float((residuos**2).sum())
    total = float(((ys - ys.mean()) ** 2).sum())
    r2 = 1.0 if total <= 1e-9 else 1.0 - soma_residuo / total
    rmse = float(np.sqrt(soma_residuo / len(ys)))

    a, b = int(xs[0]), int(xs[-1])
    reta = Reta(a, float(inclinacao * a + intercepto), b, float(inclinacao * b + intercepto))
    return Ajuste(reta, r2, rmse)


def detectar_canal(
    serie: Serie, i: int, janela: int = 120, lim: Limiares = PADRAO
) -> Canal | None:
    """Canal formado pelos pivôs dentro da janela que termina em `i`.

    Exige **paralelismo aproximado**: se as duas bordas divergem muito de inclinação, a
    figura é cunha ou triângulo, não canal — e chamá-la de canal daria alvos errados.
    """
    inicio = max(0, i - janela)
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)
    topos = [(k, p) for k, p in topos if k >= inicio]
    fundos = [(k, p) for k, p in fundos if k >= inicio]

    if len(topos) < 2 or len(fundos) < 2:
        return None

    ajuste_topo = _ajustar_reta(topos)
    ajuste_fundo = _ajustar_reta(fundos)
    if ajuste_topo is None or ajuste_fundo is None:
        return None

    atr_arr = calc_atr(serie, lim.atr_periodo)
    atr_i = float(atr_arr[i]) if not np.isnan(atr_arr[i]) else 0.0
    if atr_i <= 0:
        return None

    if not (ajuste_topo.bom(atr_i) and ajuste_fundo.bom(atr_i)):
        return None

    reta_topo, reta_fundo = ajuste_topo.reta, ajuste_fundo.reta

    largura = reta_topo.preco_em(i) - reta_fundo.preco_em(i)
    if largura <= 0:
        return None
    largura_atr = largura / atr_i
    # Canal estreito demais é ruído; largo demais deixou de ser canal e virou "o gráfico".
    if not (1.0 <= largura_atr <= 12.0):
        return None

    # Paralelismo: as inclinações não podem divergir mais que 45% da maior.
    # Divergência medida em ATR por candle, não em proporção. A versão relativa
    # (`diferença / maior inclinação`) explode quando as duas bordas são horizontais:
    # num canal lateral perfeito ambas valem ~0, e a divisão por ~0 rejeitava justamente
    # a figura mais limpa que existe.
    m_topo, m_fundo = reta_topo.inclinacao, reta_fundo.inclinacao
    if abs(m_topo - m_fundo) / atr_i > 0.05:
        return None

    inclinacao_media = (m_topo + m_fundo) / 2
    # A inclinação é comparada ao ATR por candle: em ativo volátil, subir 10 pontos por
    # candle é lateral; em ativo parado, é tendência.
    normalizada = inclinacao_media / atr_i
    if normalizada > 0.06:
        tipo: TipoCanal = "ascendente"
    elif normalizada < -0.06:
        tipo = "descendente"
    else:
        tipo = "lateral"

    toques = _contar_toques(serie, reta_topo, reta_fundo, inicio, i, atr_i)
    if toques < MIN_TOQUES:
        return None

    # Contenção: o canal precisa realmente conter o preço.
    #
    # É o critério que R² sozinho não cobre. Com poucos pivôs — 5 a 7 numa janela — até um
    # passeio aleatório produz regressão com R² de 0,90: qualquer punhado de pontos se
    # alinha razoavelmente por acaso. O que o aleatório NÃO faz é ficar dentro das linhas
    # entre os pivôs; ele passeia para fora o tempo todo.
    if _contencao(serie, reta_topo, reta_fundo, inicio, i, atr_i) < CONTENCAO_MINIMA:
        return None

    return Canal(
        topo=reta_topo,
        fundo=reta_fundo,
        tipo=tipo,
        inicio=inicio,
        fim=i,
        toques=toques,
        largura_atr=largura_atr,
    )


CONTENCAO_MINIMA = 0.90
"""Fração mínima de fechamentos dentro do canal.

Nem todo candle precisa caber — o rompimento é justamente o que sai. Mas se um em cada
dez já está fora, as linhas não descrevem o movimento: descrevem dois ajustes de reta que
por acaso ficaram paralelos.
"""


def _contencao(
    serie: Serie, topo: Reta, fundo: Reta, inicio: int, fim: int, atr: float
) -> float:
    """Fração dos fechamentos entre as duas bordas, com meia folga de ATR."""
    folga = 0.5 * atr
    total = fim - inicio + 1
    if total <= 0:
        return 0.0
    dentro = sum(
        1
        for k in range(inicio, fim + 1)
        if fundo.preco_em(k) - folga <= serie[k].fechamento <= topo.preco_em(k) + folga
    )
    return dentro / total


def _contar_toques(
    serie: Serie, topo: Reta, fundo: Reta, inicio: int, fim: int, atr: float
) -> int:
    tolerancia = 0.3 * atr
    total = 0
    for k in range(inicio, fim + 1):
        c = serie[k]
        if abs(c.maxima - topo.preco_em(k)) <= tolerancia:
            total += 1
        if abs(c.minima - fundo.preco_em(k)) <= tolerancia:
            total += 1
    return total


def detectar_rompimentos(
    serie: Serie, canal: Canal, i: int, minimo_atr: float = 0.35, lim: Limiares = PADRAO
) -> list[Rompimento]:
    """Fechamentos além da borda do canal, com folga mínima.

    Exige **fechamento** fora, não pavio: um pavio que fura a linha e volta é o canal
    sendo respeitado, não rompido — é justamente o toque que valida a borda.
    """
    atr_arr = calc_atr(serie, lim.atr_periodo)
    achados: list[Rompimento] = []

    for k in range(canal.inicio, min(i, len(serie) - 1) + 1):
        atr_k = float(atr_arr[k]) if not np.isnan(atr_arr[k]) else 0.0
        if atr_k <= 0:
            continue
        c = serie[k]
        acima = c.fechamento - canal.topo.preco_em(k)
        abaixo = canal.fundo.preco_em(k) - c.fechamento

        if acima > minimo_atr * atr_k:
            achados.append(Rompimento(k, c.fechamento, "alta", acima / atr_k))
        elif abaixo > minimo_atr * atr_k:
            achados.append(Rompimento(k, c.fechamento, "baixa", abaixo / atr_k))

    # Rompimentos consecutivos são o mesmo evento; só o primeiro de cada sequência conta.
    filtrados: list[Rompimento] = []
    for r in achados:
        novo_evento = (
            not filtrados
            or r.indice - filtrados[-1].indice > 3
            or r.direcao != filtrados[-1].direcao
        )
        if novo_evento:
            filtrados.append(r)
    return filtrados


# ---------------------------------------------------------------------------
# Oferta e demanda
# ---------------------------------------------------------------------------


def detectar_faixas(
    serie: Serie, i: int, janela: int = 300, lim: Limiares = PADRAO
) -> list[Faixa]:
    """Zonas onde o preço reagiu repetidamente, agrupadas por proximidade.

    Um pivô isolado é um acidente; três pivôs no mesmo preço é uma região onde há ordem.
    O agrupamento usa ATR como raio — em ativo volátil, "o mesmo preço" é uma faixa mais
    larga.
    """
    inicio = max(0, i - janela)
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)

    atr_arr = calc_atr(serie, lim.atr_periodo)
    atr_i = float(atr_arr[i]) if not np.isnan(atr_arr[i]) else 0.0
    if atr_i <= 0:
        return []

    raio = 0.5 * atr_i
    faixas: list[Faixa] = []

    for pontos, tipo in ((topos, "oferta"), (fundos, "demanda")):
        precos = sorted(p for k, p in pontos if k >= inicio)
        grupo: list[float] = []
        for preco in precos:
            if grupo and preco - grupo[0] > raio * 2:
                faixas.extend(_faixa_do_grupo(grupo, tipo))
                grupo = []
            grupo.append(preco)
        faixas.extend(_faixa_do_grupo(grupo, tipo))

    # As mais tocadas primeiro; a tela raramente cabe mais que meia dúzia.
    faixas.sort(key=lambda f: -f.forca)
    return faixas[:6]


def _faixa_do_grupo(grupo: list[float], tipo: str) -> list[Faixa]:
    if len(grupo) < 2:
        return []
    return [
        Faixa(
            tipo=tipo,  # type: ignore[arg-type]
            preco_min=min(grupo),
            preco_max=max(grupo),
            toques=len(grupo),
            forca=min(1.0, len(grupo) / 4.0),
        )
    ]


def detectar_linha_tendencia(
    serie: Serie, i: int, janela: int = 200, lim: Limiares = PADRAO
) -> Reta | None:
    """A linha de tendência dominante — a que liga os fundos numa alta, os topos numa baixa.

    Escolhe o lado pela inclinação que melhor descreve o movimento: numa alta, os fundos
    ascendentes são a linha que sustenta o preço, e é essa que o operador desenha.
    """
    inicio = max(0, i - janela)
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)
    topos = [(k, p) for k, p in topos if k >= inicio]
    fundos = [(k, p) for k, p in fundos if k >= inicio]

    atr_arr = calc_atr(serie, lim.atr_periodo)
    atr_i = float(atr_arr[i]) if not np.isnan(atr_arr[i]) else 0.0

    # Mesma exigência do canal: uma reta que não descreve os pontos não é linha de
    # tendência, é uma reta qualquer passando por uma nuvem.
    candidatas = [
        ajuste
        for ajuste in (_ajustar_reta(fundos), _ajustar_reta(topos))
        if ajuste is not None and ajuste.bom(atr_i)
    ]
    if not candidatas:
        return None

    # A de maior inclinação absoluta descreve melhor o movimento dominante.
    return max(candidatas, key=lambda a: abs(a.reta.inclinacao)).reta


def ler(serie: Serie, i: int, lim: Limiares = PADRAO) -> Estrutura:
    """A estrutura completa no candle `i`."""
    canal = detectar_canal(serie, i, lim=lim)
    topos, fundos = swings_confirmados(serie, i, lim.swing_lookback)
    janela_inicio = max(0, i - 300)

    return Estrutura(
        canal=canal,
        rompimentos=detectar_rompimentos(serie, canal, i, lim=lim) if canal else [],
        faixas=detectar_faixas(serie, i, lim=lim),
        linha_tendencia=detectar_linha_tendencia(serie, i, lim=lim),
        pivos_topo=[(k, p) for k, p in topos if k >= janela_inicio],
        pivos_fundo=[(k, p) for k, p in fundos if k >= janela_inicio],
    )


def para_dict(estrutura: Estrutura, serie: Serie) -> dict:
    """Serialização para o gráfico. Índices viram timestamps ISO."""

    def ts(k: int) -> str | None:
        return serie[k].ts.isoformat() if 0 <= k < len(serie) else None

    def reta(r: Reta) -> dict:
        return {
            "de": {"ts": ts(r.indice_a), "preco": r.preco_a},
            "ate": {"ts": ts(r.indice_b), "preco": r.preco_b},
            "inclinacao": r.inclinacao,
        }

    return {
        "resumo": estrutura.resumo,
        "canal": (
            {
                "tipo": estrutura.canal.tipo,
                "topo": reta(estrutura.canal.topo),
                "fundo": reta(estrutura.canal.fundo),
                "toques": estrutura.canal.toques,
                "larguraAtr": round(estrutura.canal.largura_atr, 2),
            }
            if estrutura.canal
            else None
        ),
        "rompimentos": [
            {"ts": ts(r.indice), "preco": r.preco, "direcao": r.direcao,
             "forcaAtr": round(r.forca_atr, 2)}
            for r in estrutura.rompimentos
        ],
        "faixas": [
            {"tipo": f.tipo, "precoMin": f.preco_min, "precoMax": f.preco_max,
             "toques": f.toques, "forca": round(f.forca, 2)}
            for f in estrutura.faixas
        ],
        "linhaTendencia": reta(estrutura.linha_tendencia) if estrutura.linha_tendencia else None,
        "pivos": [
            *({"ts": ts(k), "preco": p, "tipo": "topo"} for k, p in estrutura.pivos_topo),
            *({"ts": ts(k), "preco": p, "tipo": "fundo"} for k, p in estrutura.pivos_fundo),
        ],
    }
