"""A tese de um sinal: por quê, quando, onde — e o que prova que está errado.

Isto é a resposta determinística à pergunta que o operador faz antes de clicar. Não
substitui os agentes de IA da Sprint 7: **antecipa** o que eles vão narrar. O motor já
sabe justificar o que fez; o LLM depois transforma esta estrutura em prosa.

A ordem dos campos não é arbitrária — segue a ordem em que a decisão precisa ser
auditada:

1. **onde** — o lugar. Um padrão fora de lugar não é sinal.
2. **quando** — o momento. Janela do pregão, viés dos timeframes maiores, gatilho.
3. **por que** — as evidências que empurraram o score para cima.
4. **contra** — o argumento adversário, montado dos fatores que puxaram para baixo.
5. **invalidação** — o preço que prova a leitura errada. É o stop, dito em palavras.

O campo `contra` existe porque um dossiê que só lista o que favorece a operação não é
análise, é propaganda. Se não houver nada contra, o campo diz isso explicitamente — e
isso também é informação.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .confluencia import Avaliacao
from .decisao import Sinal
from .instrumentos import resolver
from .padroes import CATALOGO
from .tipos import Contexto, Direcao

JANELAS_LEGIVEIS = {
    "abertura": "abertura do pregão (9h–10h), volátil e ruidosa",
    "tendencia-manha": "manhã (10h–12h)",
    "almoco": "meio-dia (12h–14h), liquidez baixa",
    "abertura-eua": "abertura americana (14h–16h)",
    "fechamento": "reta final (16h–17h30)",
    "ajuste": "ajuste (após 17h30)",
    "pre-abertura": "pré-abertura",
}


@dataclass(frozen=True, slots=True)
class Tese:
    onde: str
    quando: str
    porque: list[str] = field(default_factory=list)
    contra: list[str] = field(default_factory=list)
    invalidacao: str = ""
    confianca: str = "media"
    confianca_motivo: str = ""

    def para_dict(self) -> dict:
        return {
            "onde": self.onde,
            "quando": self.quando,
            "porque": self.porque,
            "contra": self.contra,
            "invalidacao": self.invalidacao,
            "confianca": self.confianca,
            "confiancaMotivo": self.confianca_motivo,
        }


def _onde(sinal: Sinal, avaliacao: Avaliacao) -> str:
    partes: list[str] = []

    if avaliacao.zona_sr:
        partes.append(f"na {_zona_legivel(avaliacao.zona_sr.origem)}")
    if avaliacao.media_proxima:
        partes.append(f"reagindo na {avaliacao.media_proxima}")
    if avaliacao.nivel_fib:
        from . import fibonacci as fib

        peso = fib.relevancia(sinal.ativo, avaliacao.nivel_fib.razao)
        if peso > 0:
            partes.append(f"na retração de {avaliacao.nivel_fib.razao:.1%} (nível medido)")
        else:
            partes.append(
                f"na retração de {avaliacao.nivel_fib.razao:.1%} — "
                f"sem peso medido em {sinal.ativo}"
            )

    preco = f"{sinal.avaliacao.deteccao.preco_referencia:,.0f}".replace(",", ".")
    if not partes:
        return f"{sinal.ativo} em {preco}, sem zona relevante por perto"

    if avaliacao.zona_quente:
        return (
            f"{sinal.ativo} em {preco}, numa **zona quente** — "
            + ", ".join(partes)
            + ". Três leituras independentes apontando o mesmo preço é onde há ordem grande."
        )
    return f"{sinal.ativo} em {preco}, " + ", ".join(partes) + "."


def _zona_legivel(origem: str) -> str:
    return {
        "maxima-dia-anterior": "máxima do dia anterior",
        "minima-dia-anterior": "mínima do dia anterior",
        "fechamento-dia-anterior": "fechamento do dia anterior",
        "maxima-abertura": "máxima do range de abertura",
        "minima-abertura": "mínima do range de abertura",
        "pivo": "região de um topo/fundo anterior",
        "vwap": "VWAP do dia",
        "redondo": "número redondo",
    }.get(origem, origem)


def _quando(sinal: Sinal, avaliacao: Avaliacao, ctx: Contexto) -> str:
    janela = JANELAS_LEGIVEIS.get(ctx.janela_pregao, ctx.janela_pregao)
    partes = [f"{sinal.ts:%d/%m às %H:%M}, na {janela}"]

    if avaliacao.regime and avaliacao.regime.disponivel:
        partes.append(avaliacao.regime.descricao)
    if avaliacao.cruzamento:
        partes.append(avaliacao.cruzamento)

    mtf = next((f for f in avaliacao.fatores if f.nome == "mtf"), None)
    if mtf:
        partes.append(mtf.detalhe)

    lado = "compra" if sinal.direcao is Direcao.ALTA else "venda"
    partes.append(
        f"gatilho de {lado} no rompimento de {sinal.entrada:,.0f}".replace(",", ".")
    )
    return " · ".join(partes)


def _porque(sinal: Sinal, avaliacao: Avaliacao) -> list[str]:
    spec = CATALOGO.get(sinal.padrao_id)
    razoes: list[str] = []

    if spec:
        razoes.append(
            f"{spec.nome}: {_leitura_do_padrao(spec.id)} "
            f"(ebook p.{spec.pagina_ebook})"
        )

    for f in avaliacao.fatores:
        if f.multiplicador <= 1.0 or f.nome in {"horario", "mtf"}:
            continue
        razoes.append(f"{_fator_legivel(f.nome)}: {f.detalhe} (×{f.multiplicador:.2f})")

    if sinal.confiabilidade >= 0.5:
        razoes.append(
            f"confiabilidade do padrão em {sinal.ativo}: {sinal.confiabilidade:.0%}"
        )

    risco = f"{sinal.risco_pontos:,.0f}".replace(",", ".")
    retorno = f"{sinal.retorno_pontos:,.0f}".replace(",", ".")
    razoes.append(
        f"relação risco/retorno de {sinal.rr:.2f} — "
        f"arrisca {risco} pontos para buscar {retorno}"
    )
    return razoes


def _leitura_do_padrao(padrao_id: str) -> str:
    """A frase que explica o que o padrão diz sobre a briga entre compra e venda."""
    return {
        "engolfo_alta": "toda a venda do candle anterior foi recomprada, e sobrou",
        "engolfo_baixa": "toda a compra do candle anterior foi devolvida, e sobrou",
        "martelo": "o fundo foi testado e rejeitado — apareceu comprador agressivo",
        "enforcado": "apareceu vendedor agressivo no topo, mesmo absorvido",
        "estrela_cadente": "o preço subiu e foi devolvido inteiro",
        "martelo_invertido": "comprador testando acima, dentro da queda",
        "linha_perfuracao": "abriu no pior lugar possível e devolveu mais da metade da queda",
        "nuvem_negra": "abriu acima da máxima e devolveu mais da metade da alta",
        "estrela_manha": "a venda parou de conseguir empurrar, e a compra confirmou",
        "estrela_noite": "a compra parou de conseguir empurrar, e a venda confirmou",
        "tres_soldados": "três candles de força seguidos, sem devolver terreno",
        "tres_corvos": "três candles de baixa seguidos, sem devolver terreno",
        "harami_alta": "a venda perdeu amplitude de um candle para o outro",
        "harami_baixa": "a compra perdeu amplitude de um candle para o outro",
        "tres_por_dentro_alta": "harami confirmado por rompimento da máxima",
        "tres_por_dentro_baixa": "harami confirmado por rompimento da mínima",
        "tres_por_fora_alta": "engolfo confirmado por um terceiro candle",
        "tres_por_fora_baixa": "engolfo confirmado por um terceiro candle",
        "bebe_abandonado_alta": "capitulação isolada por gap, seguida de retomada",
        "bebe_abandonado_baixa": "euforia isolada por gap, seguida de devolução",
        "dois_corvos": "o gap de alta foi devolvido e o fechamento apagou a alta anterior",
    }.get(padrao_id, "formação identificada no gráfico")


def _fator_legivel(nome: str) -> str:
    return {
        "fibonacci": "Fibonacci",
        "media": "média móvel",
        "suporte_resistencia": "suporte/resistência",
        "regime_medias": "regime de médias",
        "volume": "volume",
        "correlacao": "correlação",
        "zona_quente": "zona quente",
        "mtf": "multi-timeframe",
        "volatilidade": "volatilidade",
        "esticamento": "esticamento",
    }.get(nome, nome)


def _contra(sinal: Sinal, avaliacao: Avaliacao, ctx: Contexto) -> list[str]:
    """O argumento adversário. Montado dos fatores que puxaram o score para baixo."""
    objecoes: list[str] = []

    for f in avaliacao.fatores:
        if f.multiplicador >= 1.0:
            continue
        objecoes.append(f"{_fator_legivel(f.nome)}: {f.detalhe} (×{f.multiplicador:.2f})")

    spec = CATALOGO.get(sinal.padrao_id)
    if spec and spec.confiabilidade_ebook <= 0.35:
        objecoes.append(
            "o próprio ebook classifica este padrão como de baixa confiabilidade"
        )
    if spec and spec.derivado_por_simetria:
        objecoes.append("padrão espelhado por simetria — o ebook não descreve esta direção")
    if spec and spec.exige_gap:
        objecoes.append(
            "depende de gap, que em 5 minutos quase não existe — sensível à tolerância"
        )

    if sinal.confiabilidade < 0.45:
        objecoes.append(
            f"confiabilidade medida de apenas {sinal.confiabilidade:.0%} neste padrão"
        )
    if ctx.regime_volatilidade < 0.8:
        objecoes.append(
            f"volatilidade em {ctx.regime_volatilidade:.0%} da média — movimento curto"
        )
    regime = avaliacao.regime
    if regime and regime.disponivel and regime.direcao is Direcao.NEUTRA:
        objecoes.append("médias embaraçadas: o mercado não tem estrutura direcional clara")

    if not objecoes:
        objecoes.append("nenhum fator pesou contra — raro, e por isso mesmo merece atenção")
    return objecoes


def _numero(valor: float, casas: int = 0) -> str:
    """Formata um número no padrão pt-BR.

    Formata **o número**, nunca a frase. Trocar vírgulas e pontos na string inteira
    embaralha a pontuação do texto junto com os separadores — o tipo de bug que só
    aparece quando alguém lê a frase em voz alta.
    """
    return f"{valor:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _invalidacao(sinal: Sinal) -> str:
    inst = resolver(sinal.ativo)
    lado = "abaixo" if sinal.direcao is Direcao.ALTA else "acima"
    casas = 0 if sinal.ativo.startswith("WIN") else 1
    perda = inst.reais(sinal.risco_pontos, sinal.contratos)
    return (
        f"Se o preço fechar {lado} de {_numero(sinal.stop, casas)}, a leitura está errada: "
        f"o extremo da formação foi perdido e o motivo da entrada deixou de existir. "
        f"Custo dessa hipótese: {_numero(sinal.risco_pontos, casas)} pontos, "
        f"R$ {_numero(perda, 2)} com {sinal.contratos} contrato(s)."
    )


def _confianca(sinal: Sinal, avaliacao: Avaliacao, contra: list[str]) -> tuple[str, str]:
    """Rótulo de confiança, e a razão dele — nunca o rótulo sozinho.

    O score sozinho **não** decide. Ele mede confluência, e confluência forte convive
    perfeitamente com defeitos graves: um padrão pode acertar todas as zonas e ainda ser
    um padrão que o histórico mostra perder dinheiro, num horário morto, com volume fraco.

    Um cartão dizendo "convicção alta" com cinco objeções embaixo é pior que inútil — é
    o motor discordando de si mesmo na mesma tela. Por isso o score define o **teto** e
    os problemas medidos rebaixam a partir dele.
    """
    # Problemas que sozinhos já derrubam a convicção, por serem sobre a estatística do
    # trade e não sobre a estética da formação.
    graves: list[str] = []
    if sinal.confiabilidade < 0.45:
        graves.append(f"confiabilidade de apenas {sinal.confiabilidade:.0%}")
    if sinal.rr < 1.8:
        graves.append(f"R:R de {sinal.rr:.2f}, pouco acima do mínimo")
    regime = avaliacao.regime
    if regime and regime.disponivel and regime.direcao is Direcao.NEUTRA:
        graves.append("sem estrutura direcional")

    if sinal.score >= 0.70 and avaliacao.zona_quente:
        base, motivo = "alta", "score alto numa zona onde três leituras concordam"
    elif sinal.score >= 0.70:
        base, motivo = "alta", f"score {sinal.score:.2f}"
    elif sinal.score >= 0.55:
        base, motivo = "media", f"score {sinal.score:.2f}"
    else:
        return (
            "baixa",
            f"score {sinal.score:.2f}, pouco acima do corte — observe em vez de operar",
        )

    if len(graves) >= 2:
        return "baixa", f"{motivo}, mas {' e '.join(graves[:2])}"
    if graves or len(contra) >= 4:
        rebaixado = "media" if base == "alta" else "baixa"
        razao = graves[0] if graves else f"{len(contra)} fatores pesando contra"
        return rebaixado, f"{motivo}, rebaixado: {razao}"
    return base, motivo


def montar(sinal: Sinal, ctx: Contexto) -> Tese:
    """Constrói a tese completa a partir de um sinal já decidido."""
    avaliacao = sinal.avaliacao
    contra = _contra(sinal, avaliacao, ctx)
    confianca, motivo = _confianca(sinal, avaliacao, contra)
    return Tese(
        onde=_onde(sinal, avaliacao),
        quando=_quando(sinal, avaliacao, ctx),
        porque=_porque(sinal, avaliacao),
        contra=contra,
        invalidacao=_invalidacao(sinal),
        confianca=confianca,
        confianca_motivo=motivo,
    )
