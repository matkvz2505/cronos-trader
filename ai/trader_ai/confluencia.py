"""Camada 4 — onde o padrão vira score.

O ebook repete, padrão após padrão, que a formação sozinha tem baixa confiabilidade. Ele
está certo, e é essa a razão de este módulo existir: **um produto que só detecta padrão
não vale nada**. O valor está em exigir que o padrão aconteça num lugar que já importava.

O score parte de `deteccao.score_bruto` (força × confiabilidade) e é ajustado por fatores
multiplicativos independentes. Cada fator é registrado com nome e valor, para que o sinal
na tela sempre possa responder "por que este número?".

**O score é uma nota de ranqueamento, não uma probabilidade.** A estimativa honesta de
acerto é `deteccao.confiabilidade`, que só vira número medido depois do backtest. Misturar
as duas coisas seria vender confiança que os dados não sustentam.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import fibonacci as fib
from . import medias as medias_mod
from . import suporte_resistencia as sr
from .contexto import opera_agora
from .indicadores import sma
from .limiares import PADRAO, Limiares
from .tipos import Contexto, Deteccao, Direcao, Familia, Serie, Tendencia


@dataclass(frozen=True, slots=True)
class ContextoExterno:
    """Leitura de um ativo correlacionado, quando disponível.

    WIN acompanha o futuro do S&P quase tick a tick; WDO acompanha o índice do dólar.
    Um sinal de compra em WIN contra um S&P despencando é um sinal pior — e o motor
    precisa saber disso.

    Entra como **penalidade**, nunca como veto: correlação intraday quebra, e vetar por
    ela transformaria uma dica em camisa de força.
    """

    direcao: Direcao
    forca: float
    fonte: str


@dataclass(frozen=True, slots=True)
class Fator:
    nome: str
    multiplicador: float
    detalhe: str


@dataclass(frozen=True, slots=True)
class Avaliacao:
    deteccao: Deteccao
    score: float
    """0..1, com teto. Nota de ranqueamento — ver docstring do módulo."""

    score_sem_teto: float
    """Antes do clamp. Preserva a ordenação entre sinais excepcionais."""

    fatores: list[Fator] = field(default_factory=list)
    vetos: list[str] = field(default_factory=list)
    zona_quente: bool = False
    nivel_fib: fib.NivelFib | None = None
    zona_sr: sr.Zona | None = None
    media_proxima: str | None = None
    regime: medias_mod.RegimeMedias | None = None
    cruzamento: str | None = None
    alvos_candidatos: list[float] = field(default_factory=list)
    """Zonas relevantes na direção do sinal, da mais próxima à mais distante.

    Lista, e não um valor único, porque `decisao` precisa poder descartar a mais próxima
    quando ela não paga o risco e olhar a seguinte.
    """

    @property
    def alvo_sugerido(self) -> float | None:
        """A zona mais próxima. Mantido para leitura; a decisão usa a lista."""
        return self.alvos_candidatos[0] if self.alvos_candidatos else None

    @property
    def aprovado(self) -> bool:
        return not self.vetos and self.score >= PADRAO.score_minimo_sinal

    def aprovado_com(self, lim: Limiares) -> bool:
        return not self.vetos and self.score >= lim.score_minimo_sinal

    def explicar(self) -> str:
        """Linha única auditável — vai para o log e para o dossiê dos agentes."""
        partes = " ".join(f"{f.nome}×{f.multiplicador:.2f}" for f in self.fatores)
        veto = f" VETO({', '.join(self.vetos)})" if self.vetos else ""
        return (
            f"{self.deteccao.nome}: {self.deteccao.score_bruto:.3f} → "
            f"{self.score:.3f} [{partes}]{veto}"
        )


def _valor(arr: np.ndarray, i: int) -> float | None:
    if i >= len(arr):
        return None
    v = float(arr[i])
    return None if np.isnan(v) else v


def _fator_fibonacci(
    serie: Serie, i: int, preco: float, ctx: Contexto, lim: Limiares
) -> tuple[Fator | None, fib.NivelFib | None]:
    """Bônus de Fibonacci **calibrado por ativo**, não pela literatura.

    O peso vem de `fib.relevancia()`, que só reconhece níveis que produziram pico local
    na medição sobre dados reais. Hoje isso significa: WDO ganha bônus em 50%, e o WIN
    não ganha bônus de Fibonacci nenhum — porque nenhum nível passou no teste nele.

    Deixar de pontuar onde não há evidência não é o motor ficando pior; é ele parando de
    inventar confluência.
    """
    perna = fib.ultima_perna(serie, i, lim)
    if perna is None or perna.amplitude <= 0:
        return None, None
    nivel = fib.nivel_proximo(preco, fib.retracoes(perna), ctx.atr, lim)
    if nivel is None:
        return None, None

    peso = fib.relevancia(serie.ativo, nivel.razao)
    if peso <= 0:
        # O nível existe no gráfico, mas não significa nada neste ativo. Devolvido como
        # informação para a tese, sem alterar o score.
        return None, nivel
    return Fator("fibonacci", 1.0 + lim.bonus_fibonacci * peso, f"{nivel.rotulo} (medido)"), nivel


def _fator_media(
    serie: Serie, i: int, preco: float, ctx: Contexto, lim: Limiares
) -> tuple[Fator | None, str | None]:
    """Reação numa média relevante.

    As quatro têm pesos diferentes porque têm públicos diferentes: a SMA200 é olhada por
    todo o mercado e a EMA9 é olhada por quem já está posicionado. Reagir na 200 é evento;
    tocar a 9 é rotina.
    """
    if ctx.atr <= 0:
        return None, None
    tolerancia = lim.tolerancia_zona_atr * ctx.atr

    m = medias_mod.conjunto(serie)
    candidatas: list[tuple[str, float, float]] = []  # (nome, valor, peso)
    for chave, nome, peso in (
        ("sma200", "SMA200", 1.0),
        ("rma400", "RMA400 (Wilder)", 0.9),
        ("sma21", "SMA21", 0.7),
        ("ema9", "EMA9", 0.4),
    ):
        valor = _valor(m[chave], i)
        if valor is not None and abs(valor - preco) <= tolerancia:
            candidatas.append((nome, valor, peso))

    if not candidatas:
        return None, None

    # A média de maior peso ganha, não a mais próxima: estar na SMA200 importa mais que
    # estar coladinho na EMA9.
    nome, _, peso = max(candidatas, key=lambda c: c[2])
    return Fator("media", 1.0 + lim.bonus_media * peso, nome), nome


def _fator_regime(
    regime: medias_mod.RegimeMedias, deteccao: Deteccao, lim: Limiares
) -> Fator | None:
    """Empilhamento das médias a favor ou contra o sinal.

    Diferente do fator anterior, que é sobre *lugar* (o preço está numa média). Este é
    sobre *estrutura*: as quatro médias na ordem descrevem um mercado com direção, e
    entrar contra essa estrutura é o trade que parece bom e sangra.

    Médias embaraçadas não penalizam nem bonificam — ausência de estrutura é informação
    neutra, e transformá-la em penalidade mataria toda operação de início de movimento.
    """
    if not regime.disponivel:
        return None
    if regime.concorda_com(deteccao.direcao):
        return Fator(
            "regime_medias",
            1.0 + lim.bonus_regime_medias * regime.alinhamento,
            regime.descricao,
        )
    if regime.contraria(deteccao.direcao):
        return Fator(
            "regime_medias",
            1.0 - lim.penalidade_regime_contra * regime.alinhamento,
            f"contra: {regime.descricao}",
        )
    return None


def _fator_esticamento(regime: medias_mod.RegimeMedias, lim: Limiares) -> Fator | None:
    """Preço longe demais da média de viés.

    Comprar três ATR acima da SMA21 é comprar o fim do impulso: a reversão à média passa
    a puxar contra a posição antes mesmo de o alvo ser atingido. É uma das formas mais
    comuns de acertar a direção e perder dinheiro.
    """
    if not regime.disponivel or regime.distancia_atr <= lim.esticamento_maximo_atr:
        return None
    excesso = regime.distancia_atr - lim.esticamento_maximo_atr
    fator = max(0.55, 1.0 - lim.penalidade_esticamento * excesso)
    return Fator("esticamento", fator, f"{regime.distancia_atr:.1f} ATR da SMA21")


def _fator_sr(
    zonas: list[sr.Zona], preco: float, ctx: Contexto, lim: Limiares
) -> tuple[Fator | None, sr.Zona | None]:
    zona = sr.mais_forte(preco, zonas, ctx.atr, lim)
    if zona is None:
        return None, None
    return (
        Fator("suporte_resistencia", 1.0 + lim.bonus_suporte_resistencia * zona.forca, zona.origem),
        zona,
    )


def _fator_volume(serie: Serie, i: int, deteccao: Deteccao, lim: Limiares) -> Fator | None:
    """Volume do padrão contra a média de 20 períodos.

    Padrão de reversão com volume abaixo da média é suspeito: se o mercado realmente
    mudou de mão, alguém negociou. Muitas séries vêm sem volume confiável (o MT5 entrega
    tick volume em alguns símbolos) — nesse caso o fator simplesmente não se aplica.
    """
    volumes = serie.volume
    if i >= len(volumes) or volumes[i] <= 0:
        return None
    media = _valor(serie.memo("sma_vol_20", lambda: sma(volumes, 20)), i)
    if media is None or media <= 0:
        return None

    # Volume do padrão inteiro, normalizado pelo número de candles.
    inicio = max(0, i - deteccao.n_candles + 1)
    do_padrao = float(np.mean(volumes[inicio : i + 1]))
    razao = do_padrao / media

    if razao >= 1.5:
        return Fator("volume", 1.0 + lim.bonus_volume, f"{razao:.1f}× a média")
    if razao <= 0.6:
        return Fator("volume", 1.0 - lim.penalidade_volume_fraco, f"{razao:.1f}× a média")
    return None


def _fator_correlacao(
    deteccao: Deteccao, externo: ContextoExterno | None, lim: Limiares
) -> Fator | None:
    if externo is None or externo.direcao is Direcao.NEUTRA:
        return None
    if externo.direcao is deteccao.direcao:
        return Fator(
            "correlacao",
            1.0 + lim.bonus_correlacao * externo.forca,
            f"{externo.fonte} a favor",
        )
    return Fator(
        "correlacao",
        1.0 - lim.penalidade_correlacao_contra * externo.forca,
        f"{externo.fonte} contra",
    )


def _fator_volatilidade(ctx: Contexto, lim: Limiares) -> Fator | None:
    """ATR muito abaixo do normal: o movimento não paga spread + corretagem.

    É o filtro que evita operar o meio-dia do WIN, quando o padrão até aparece mas o
    alvo cabe dentro do custo.
    """
    if ctx.regime_volatilidade >= lim.atr_minimo_operavel:
        return None
    return Fator(
        "volatilidade",
        1.0 - lim.penalidade_volatilidade_baixa,
        f"ATR em {ctx.regime_volatilidade:.0%} da média",
    )


def _zona_quente(
    nivel: fib.NivelFib | None, zona: sr.Zona | None, media: str | None
) -> bool:
    """Fibonacci, média e suporte/resistência apontando para o mesmo preço.

    É o sinal mais forte que o motor produz. Três leituras independentes concordando
    num nível é onde de fato existe ordem grande pendurada — e é ali que um martelo
    deixa de ser desenho e vira informação.
    """
    return nivel is not None and zona is not None and media is not None


def avaliar(
    serie: Serie,
    i: int,
    deteccao: Deteccao,
    ctx: Contexto,
    lim: Limiares = PADRAO,
    externo: ContextoExterno | None = None,
    zonas: list[sr.Zona] | None = None,
) -> Avaliacao:
    """Pontua uma detecção no seu contexto. Não decide trade — só pontua.

    `zonas` pode vir pronto para reaproveitamento: vários padrões disparam no mesmo
    candle e o mapa de suporte/resistência é idêntico para todos eles.
    """
    preco = deteccao.preco_referencia
    if zonas is None:
        zonas = sr.mapear(serie, i, ctx.atr, lim)

    regime = medias_mod.ler(serie, i, ctx.atr)
    fator_fib, nivel = _fator_fibonacci(serie, i, preco, ctx, lim)
    fator_media, media = _fator_media(serie, i, preco, ctx, lim)
    fator_zona, zona = _fator_sr(zonas, preco, ctx, lim)

    fatores = [
        f
        for f in (
            fator_fib,
            fator_media,
            fator_zona,
            _fator_regime(regime, deteccao, lim),
            _fator_esticamento(regime, lim),
            _fator_volume(serie, i, deteccao, lim),
            _fator_correlacao(deteccao, externo, lim),
            _fator_volatilidade(ctx, lim),
            Fator("horario", ctx.peso_horario, ctx.janela_pregao),
        )
        if f is not None
    ]

    quente = _zona_quente(nivel, zona, media)
    if quente:
        fatores.append(
            Fator("zona_quente", 1.0 + lim.bonus_zona_quente, "fib + média + S/R no mesmo preço")
        )

    produto = 1.0
    for f in fatores:
        produto *= f.multiplicador
    sem_teto = deteccao.score_bruto * produto

    # Alvos naturais: as zonas relevantes à frente, em ordem de proximidade.
    candidatos = sr.obstaculos(
        preco, zonas, acima=deteccao.direcao is Direcao.ALTA, atr=ctx.atr
    )

    return Avaliacao(
        deteccao=deteccao,
        score=min(1.0, max(0.0, sem_teto)),
        score_sem_teto=sem_teto,
        fatores=fatores,
        vetos=_vetos(deteccao, ctx, lim),
        zona_quente=quente,
        nivel_fib=nivel,
        zona_sr=zona,
        media_proxima=media,
        alvos_candidatos=[z.preco for z in candidatos],
        regime=regime,
        cruzamento=medias_mod.cruzamento_recente(serie, i),
    )


def _vetos(deteccao: Deteccao, ctx: Contexto, lim: Limiares) -> list[str]:
    """Condições que matam o sinal independentemente do score.

    Veto não é penalidade forte — é ausência de trade. Um score alto num horário em que
    não se abre posição continua não sendo uma operação.
    """
    motivos: list[str] = []

    if not opera_agora(ctx):
        motivos.append(f"fora do horario operacional ({ctx.janela_pregao})")

    # Reversão exige algo para reverter. Os padrões com `tendencia_requerida` já foram
    # filtrados em `detectar_em`; este veto pega os que não exigem tendência (Chute,
    # 3 Soldados, 3 Corvos) e que, em mercado lateral, são só ruído.
    if deteccao.familia is Familia.REVERSAO and ctx.tendencia is Tendencia.LATERAL:
        motivos.append("reversao em mercado lateral")

    if ctx.atr <= 0:
        motivos.append("ATR indisponivel")

    # Expectância medida negativa mata o sinal, e não só o penaliza.
    #
    # Antes a medição entrava apenas como taxa de acerto dentro do score, onde os outros
    # fatores a diluíam: o `tres_por_dentro_baixa` do WDO mede −0,300R com amostra
    # suficiente e saiu com score 0,61 numa venda real. Um padrão que já se provou
    # perdedor NESTE ativo não é um sinal fraco — é um sinal que não deve existir.
    #
    # Só dispara com amostra suficiente. Sem medição, `confiabilidade_de` já devolve
    # neutro em vez do prior do ebook, o que basta.
    if lim.vetar_expectancia_negativa:
        from .padroes import CATALOGO, expectancia_medida

        spec = CATALOGO.get(deteccao.padrao_id)
        if spec is not None:
            esperada = expectancia_medida(spec, lim)
            if esperada is not None and esperada < 0:
                motivos.append(f"expectancia medida negativa neste ativo ({esperada:+.2f}R)")

    return motivos


def melhor(
    serie: Serie,
    i: int,
    deteccoes: list[Deteccao],
    ctx: Contexto,
    lim: Limiares = PADRAO,
    externo: ContextoExterno | None = None,
) -> Avaliacao | None:
    """A melhor avaliação aprovada entre as detecções do candle.

    Vários padrões disparam no mesmo candle por construção (um Engolfo também é um
    "3 por fora" em formação). Escolher aqui, e não no detector, é o que permite que a
    confluência — e não a geometria — decida qual leitura vale.
    """
    zonas = sr.mapear(serie, i, ctx.atr, lim)  # idêntico para todas as detecções do candle
    avaliadas = [avaliar(serie, i, d, ctx, lim, externo, zonas) for d in deteccoes]
    aprovadas = [a for a in avaliadas if a.aprovado_com(lim)]
    if not aprovadas:
        return None
    return max(aprovadas, key=lambda a: a.score_sem_teto)
