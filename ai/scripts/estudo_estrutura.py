"""Mede se estrutura gráfica e indicadores de momento **acrescentam** algo ao sinal.

O motor já detecta canal, rompimento, zona de oferta/demanda, RSI e Bollinger. Nada disso
entrou na confluência ainda, e a razão é simples: **peso inventado é pior que peso
nenhum**. Um fator sem medição vira sinal ruim com aparência de bom.

    python scripts/estudo_estrutura.py dados/WIN_M5_real.csv --ativo WIN --tf M5

## Método

Roda o motor sobre a série inteira exatamente como o backtest — mesma pipeline, mesmas
regras, sem look-ahead. Para **cada operação acionada**, anota o contexto estrutural no
instante da emissão e o resultado em R.

Depois compara: operações COM a condição contra operações SEM ela. A diferença de
expectância é o que o fator vale.

## O que decide

Um fator só entra na confluência se passar em três coisas ao mesmo tempo:

1. **Amostra** — pelo menos 30 operações de cada lado. Abaixo disso é anedota.
2. **Diferença de expectância** — ao menos 0,15 R entre ter e não ter a condição.
   Diferenças menores não sobrevivem a custo e a variação de regime.
3. **Sinal consistente** — se a condição só ajuda em WIN e atrapalha em WDO, ela não é um
   fator, é um acaso que encontrou um ativo.

O resultado esperado e perfeitamente aceitável é **nenhum fator passar**. Isso significa
que a estrutura serve para desenhar o gráfico e explicar a tese — que já é o trabalho dela
— mas não para mexer no score.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from trader_ai import backtest as bt
from trader_ai import confluencia, multitimeframe, padroes
from trader_ai import contexto as ctx_mod
from trader_ai import estrutura as est
from trader_ai.decisao import EstadoDoDia, montar
from trader_ai.fontes.contratos import em_rollover
from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.indicadores import atr as calc_atr
from trader_ai.indicadores import bollinger, rsi
from trader_ai.instrumentos import resolver
from trader_ai.limiares import PADRAO
from trader_ai.tipos import Direcao, Serie, Timeframe

AMOSTRA_MINIMA = 30
DIFERENCA_MINIMA_R = 0.15


@dataclass
class Observacao:
    """Uma operação acionada, com o contexto estrutural do momento da emissão."""

    resultado_r: float
    condicoes: dict[str, bool] = field(default_factory=dict)


@dataclass
class Comparacao:
    nome: str
    com: list[float] = field(default_factory=list)
    sem: list[float] = field(default_factory=list)

    @property
    def exp_com(self) -> float:
        return float(np.mean(self.com)) if self.com else 0.0

    @property
    def exp_sem(self) -> float:
        return float(np.mean(self.sem)) if self.sem else 0.0

    @property
    def diferenca(self) -> float:
        return self.exp_com - self.exp_sem

    @property
    def amostra_suficiente(self) -> bool:
        return len(self.com) >= AMOSTRA_MINIMA and len(self.sem) >= AMOSTRA_MINIMA

    @property
    def relevante(self) -> bool:
        return self.amostra_suficiente and abs(self.diferenca) >= DIFERENCA_MINIMA_R

    def linha(self) -> str:
        marca = ""
        if not self.amostra_suficiente:
            marca = "  (amostra insuficiente)"
        elif not self.relevante:
            marca = "  (diferença pequena demais)"
        elif self.diferenca > 0:
            marca = "  ← FAVORECE"
        else:
            marca = "  ← ATRAPALHA"
        return (
            f"{self.nome:<30} com={self.exp_com:>+6.2f}R (n={len(self.com):>4})  "
            f"sem={self.exp_sem:>+6.2f}R (n={len(self.sem):>4})  "
            f"Δ={self.diferenca:>+6.2f}R{marca}"
        )


def _condicoes(
    serie: Serie, i: int, direcao: Direcao, atr_i: float, lim
) -> dict[str, bool]:
    """O contexto estrutural e de momento no instante da emissão do sinal."""
    estrutura = est.ler(serie, i, lim)
    preco = serie[i].fechamento
    cond: dict[str, bool] = {}

    # --- canal ---
    canal = estrutura.canal
    cond["canal existe"] = canal is not None
    if canal is not None:
        posicao = canal.posicao(i, preco)
        # Comprar no fundo do canal e vender no topo é a leitura clássica.
        cond["a favor da borda do canal"] = (
            posicao <= 0.35 if direcao is Direcao.ALTA else posicao >= 0.65
        )
        alta = direcao is Direcao.ALTA
        cond["canal a favor do sinal"] = (
            canal.tipo == "ascendente" if alta else canal.tipo == "descendente"
        )
    else:
        cond["a favor da borda do canal"] = False
        cond["canal a favor do sinal"] = False

    # --- rompimento recente na direção do sinal ---
    alvo = "alta" if direcao is Direcao.ALTA else "baixa"
    cond["rompimento recente a favor"] = any(
        r.direcao == alvo and 0 <= i - r.indice <= 10 for r in estrutura.rompimentos
    )

    # --- zona de oferta/demanda ---
    # Compra na demanda, venda na oferta: o sinal nasce onde há ordem do lado dele.
    tipo_util = "demanda" if direcao is Direcao.ALTA else "oferta"
    cond["na zona certa"] = any(
        f.tipo == tipo_util and f.preco_min - 0.4 * atr_i <= preco <= f.preco_max + 0.4 * atr_i
        for f in estrutura.faixas
    )

    # --- RSI extremo contra o sinal ---
    valores_rsi = serie.memo("rsi_14", lambda: rsi(serie.fechamento, 14))
    r = float(valores_rsi[i]) if i < len(valores_rsi) and not np.isnan(valores_rsi[i]) else 50.0
    cond["RSI extremo contra"] = (
        r >= 70.0 if direcao is Direcao.ALTA else r <= 30.0
    )

    # --- Bollinger: preço fora da banda na direção do sinal ---
    sup, _, inf = serie.memo("bb_20", lambda: bollinger(serie.fechamento, 20, 2.0))
    if i < len(sup) and not np.isnan(sup[i]):
        cond["fora da banda de Bollinger"] = (
            preco >= sup[i] if direcao is Direcao.ALTA else preco <= inf[i]
        )
    else:
        cond["fora da banda de Bollinger"] = False

    return cond


def coletar(serie: Serie, capital: float) -> list[Observacao]:
    """Roda o motor e anota contexto + resultado de cada operação acionada.

    Espelha `backtest.rodar`: uma operação por vez, rollover descartado, estado de risco
    diário respeitado. Sem isso os números não seriam comparáveis com os do backtest.
    """
    lim = PADRAO.para_timeframe(serie.timeframe)
    inst = resolver(serie.ativo)
    conjunto = multitimeframe.montar_conjunto(serie)
    atr_arr = calc_atr(serie, lim.atr_periodo)

    observacoes: list[Observacao] = []
    estado: EstadoDoDia | None = None
    ocupado_ate = -1

    for i in range(lim.tendencia_min_candles, len(serie)):
        dia = serie[i].ts.date()
        if estado is None or estado.dia != dia:
            estado = EstadoDoDia(dia=dia, capital=capital)
        if i <= ocupado_ate or em_rollover(serie.ativo, dia) or estado.bloqueios(lim):
            continue

        ctx = ctx_mod.ler(serie, i, lim)
        deteccoes = padroes.detectar_em(serie, i, ctx, lim)
        if not deteccoes:
            continue
        avaliacao = confluencia.melhor(serie, i, deteccoes, ctx, lim)
        if avaliacao is None:
            continue

        vies = multitimeframe.calcular_vies(conjunto, serie[i].ts, lim)
        avaliacao = multitimeframe.aplicar(avaliacao, vies, lim)
        if not avaliacao.aprovado_com(lim):
            continue

        sinal = montar(serie, i, avaliacao, ctx, capital, lim, estado, inst)
        if sinal is None:
            continue

        operacao = bt._simular(serie, i, sinal, inst, bt.MAX_CANDLES_ESPERA)
        if operacao.acionada:
            estado.registrar(operacao.resultado_reais)
            ocupado_ate = operacao.indice_saida or i
            atr_i = float(atr_arr[i]) if not np.isnan(atr_arr[i]) else 0.0
            observacoes.append(
                Observacao(
                    resultado_r=operacao.resultado_em_r,
                    condicoes=_condicoes(serie, i, sinal.direcao, atr_i, lim),
                )
            )

    return observacoes


def comparar(observacoes: list[Observacao]) -> list[Comparacao]:
    if not observacoes:
        return []
    nomes = list(observacoes[0].condicoes)
    comparacoes = [Comparacao(nome) for nome in nomes]
    for obs in observacoes:
        for c in comparacoes:
            destino = c.com if obs.condicoes.get(c.nome) else c.sem
            destino.append(obs.resultado_r)
    return comparacoes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo")
    parser.add_argument("--ativo", default="WIN", choices=["WIN", "WDO"])
    parser.add_argument("--tf", default="M5", choices=[tf.name for tf in Timeframe])
    parser.add_argument("--capital", type=float, default=20_000.0)
    args = parser.parse_args(argv)

    tf = Timeframe[args.tf]
    serie = ler_arquivo(Path(args.arquivo), args.ativo, tf)
    print(
        f"{args.ativo} {tf.rotulo}: {len(serie)} candles de "
        f"{serie[0].ts:%d/%m/%Y} a {serie[-1].ts:%d/%m/%Y}\n"
    )

    observacoes = coletar(serie, args.capital)
    if not observacoes:
        print("nenhuma operação acionada — nada a medir.")
        return 0

    todos = [o.resultado_r for o in observacoes]
    print(f"{len(observacoes)} operações acionadas · expectância geral "
          f"{float(np.mean(todos)):+.3f}R\n")

    comparacoes = sorted(comparar(observacoes), key=lambda c: -abs(c.diferenca))
    print("EFEITO DE CADA CONDIÇÃO")
    for c in comparacoes:
        print(f"  {c.linha()}")

    aprovados = [c for c in comparacoes if c.relevante]
    print(
        f"\n{len(aprovados)} de {len(comparacoes)} condições passam nos dois critérios "
        f"(amostra ≥ {AMOSTRA_MINIMA} de cada lado e |Δ| ≥ {DIFERENCA_MINIMA_R}R)."
    )
    if not aprovados:
        print(
            "  Nenhuma passa. A estrutura continua servindo para desenhar o gráfico e\n"
            "  explicar a tese — que já é o trabalho dela — mas não entra no score."
        )
    else:
        print("  Candidatas a virar fator de confluência:")
        for c in aprovados:
            direcao = "bônus" if c.diferenca > 0 else "penalidade"
            print(f"    {c.nome}: {direcao} de {abs(c.diferenca):.2f}R de efeito medido")
        print(
            "\n  Antes de ligar: confirme o mesmo sinal no OUTRO ativo. Uma condição que\n"
            "  só funciona num deles é acaso que encontrou um ativo, não fator."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
