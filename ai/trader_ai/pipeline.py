"""A pipeline completa num lugar só: série de candles → sinais.

Existe para que CLI, serviço HTTP e coletor executem **exatamente** o mesmo caminho. Antes
disso a sequência estava repetida em três lugares, e três cópias de uma regra divergem —
a versão do serviço ganharia um filtro que a do backtest não teria, e os números parariam
de bater sem ninguém entender por quê.

O backtest tem seu próprio laço (`backtest.rodar`) porque precisa simular candle a candle
com estado de risco diário; mas as etapas de decisão são as mesmas chamadas daqui.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import confluencia, multitimeframe, padroes
from . import contexto as ctx_mod
from . import tese as tese_mod
from .decisao import Sinal, montar
from .limiares import PADRAO, Limiares
from .tipos import Contexto, Deteccao, Serie


@dataclass(frozen=True, slots=True)
class Analise:
    serie: Serie
    contexto: Contexto | None
    deteccoes: list[Deteccao]
    sinais: list[Sinal]
    vies: multitimeframe.Vies | None
    teses: dict[int, tese_mod.Tese] = field(default_factory=dict)
    """Tese por índice do candle que gerou o sinal."""

    def tese_de(self, sinal: Sinal) -> tese_mod.Tese | None:
        return self.teses.get(sinal.indice)

    @property
    def resumo(self) -> str:
        if self.contexto is None:
            return "histórico insuficiente"
        return (
            f"{self.serie.ativo} {self.serie.timeframe.rotulo} · "
            f"tendência {self.contexto.tendencia.value} · "
            f"{self.contexto.janela_pregao} · "
            f"{len(self.deteccoes)} detecções · {len(self.sinais)} sinais"
        )


def analisar_candle(
    serie: Serie,
    i: int,
    capital: float,
    lim: Limiares,
    conjunto: dict | None = None,
) -> tuple[Contexto, list[Deteccao], Sinal | None, multitimeframe.Vies | None]:
    """Roda as seis camadas no candle `i`.

    Recebe a série **inteira**, não uma fatia: todos os indicadores são causais e os
    pivôs passam por `swings_confirmados`. Ver a nota em `backtest.rodar`.
    """
    ctx = ctx_mod.ler(serie, i, lim)
    deteccoes = padroes.detectar_em(serie, i, ctx, lim)
    if not deteccoes:
        return ctx, [], None, None

    avaliacao = confluencia.melhor(serie, i, deteccoes, ctx, lim)
    if avaliacao is None:
        return ctx, deteccoes, None, None

    vies = None
    if conjunto:
        vies = multitimeframe.calcular_vies(conjunto, serie[i].ts, lim)
        avaliacao = multitimeframe.aplicar(avaliacao, vies, lim)
        if not avaliacao.aprovado_com(lim):
            return ctx, deteccoes, None, vies

    return ctx, deteccoes, montar(serie, i, avaliacao, ctx, capital, lim), vies


def analisar(
    serie: Serie,
    capital: float = 10_000.0,
    lim: Limiares | None = None,
    ultimos: int | None = None,
    usar_multitimeframe: bool = True,
) -> Analise:
    """Varre a série (ou só os `ultimos` candles) e devolve tudo o que o motor viu.

    `ultimos` é o modo do tempo real: o coletor chama a cada ciclo e só precisa reavaliar
    o que chegou desde a última vez. Varrer 5.000 candles a cada 30 segundos seria
    desperdício puro.
    """
    limiares = (lim or PADRAO).para_timeframe(serie.timeframe)
    conjunto = multitimeframe.montar_conjunto(serie) if usar_multitimeframe else {}

    inicio = limiares.tendencia_min_candles
    if ultimos is not None:
        inicio = max(inicio, len(serie) - ultimos)

    deteccoes: list[Deteccao] = []
    sinais: list[Sinal] = []
    teses: dict[int, tese_mod.Tese] = {}
    ultimo_ctx: Contexto | None = None
    ultimo_vies: multitimeframe.Vies | None = None

    for i in range(inicio, len(serie)):
        ctx, achados, sinal, vies = analisar_candle(serie, i, capital, limiares, conjunto)
        ultimo_ctx = ctx
        if vies is not None:
            ultimo_vies = vies
        deteccoes.extend(achados)
        if sinal is not None:
            sinais.append(sinal)
            # A tese é montada aqui, com o contexto vivo. Reconstruí-la depois daria
            # outra resposta — o mercado já andou.
            teses[i] = tese_mod.montar(sinal, ctx)

    return Analise(
        serie=serie,
        contexto=ultimo_ctx,
        deteccoes=deteccoes,
        sinais=sinais,
        vies=ultimo_vies,
        teses=teses,
    )


def sinal_para_dict(s: Sinal, tese: tese_mod.Tese | None = None) -> dict:
    """Serialização usada pelo serviço HTTP e pelo log da CLI."""
    return {
        "tese": tese.para_dict() if tese else None,
        "ativo": s.ativo,
        "timeframe": s.timeframe.name,
        "ts": s.ts.isoformat(),
        "direcao": s.direcao.value,
        "padraoId": s.padrao_id,
        "padraoNome": s.padrao_nome,
        "entrada": s.entrada,
        "stop": s.stop,
        "alvo": s.alvo,
        "origemAlvo": s.origem_alvo,
        "riscoPontos": s.risco_pontos,
        "retornoPontos": s.retorno_pontos,
        "rr": round(s.rr, 2),
        "contratos": s.contratos,
        "riscoReais": round(s.risco_reais, 2),
        "retornoReais": round(s.retorno_reais, 2),
        "score": round(s.score, 4),
        "confiabilidade": round(s.confiabilidade, 4),
        "zonaQuente": s.avaliacao.zona_quente,
        "observacoes": s.observacoes,
        "fatores": [
            {"nome": f.nome, "multiplicador": round(f.multiplicador, 3), "detalhe": f.detalhe}
            for f in s.avaliacao.fatores
        ],
        "explicacao": s.avaliacao.explicar(),
        "resumo": s.resumo(),
    }


def deteccao_para_dict(d: Deteccao, serie: Serie) -> dict:
    return {
        "ts": serie[d.indice_fim].ts.isoformat(),
        "padraoId": d.padrao_id,
        "padraoNome": d.nome,
        "familia": d.familia.value,
        "direcao": d.direcao.value,
        "forca": round(d.forca, 4),
        "scoreBruto": round(d.score_bruto, 4),
        "paginaEbook": d.pagina_ebook,
    }
