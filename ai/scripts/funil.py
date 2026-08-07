"""Onde os sinais morrem — o funil de rejeição do motor, estágio por estágio.

Quando o backtest devolve poucos sinais, a pergunta não é "a estratégia é ruim?" e sim
"o que está matando as candidatas?". Um filtro calibrado errado pode zerar o motor sem
que nada pareça quebrado — não há exceção, não há log, só ausência.

    python scripts/funil.py dados/WIN_M5_real.csv --ativo WIN --tf M5

Percorre a série exatamente como o backtest, mas contando as mortes por causa em vez de
simular resultado.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from trader_ai import confluencia, multitimeframe, padroes
from trader_ai import contexto as ctx_mod
from trader_ai.decisao import montar
from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.limiares import PADRAO
from trader_ai.tipos import Direcao, Timeframe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo")
    parser.add_argument("--ativo", default="WIN", choices=["WIN", "WDO"])
    parser.add_argument("--tf", default="M5", choices=[tf.name for tf in Timeframe])
    parser.add_argument("--capital", type=float, default=20_000.0)
    parser.add_argument("--ultimos", type=int, default=0, help="0 = série inteira")
    args = parser.parse_args(argv)

    tf = Timeframe[args.tf]
    serie = ler_arquivo(Path(args.arquivo), args.ativo, tf)
    if args.ultimos:
        from trader_ai.tipos import Serie

        serie = Serie(serie.ativo, tf, serie.candles[-args.ultimos :])

    lim = PADRAO.para_timeframe(tf)
    conjunto = multitimeframe.montar_conjunto(serie)

    print(f"{args.ativo} {tf.rotulo}: {len(serie)} candles "
          f"de {serie[0].ts:%d/%m/%Y} a {serie[-1].ts:%d/%m/%Y}\n")

    candles = 0
    com_deteccao = 0
    deteccoes = 0
    vetos = Counter()
    tendencias = Counter()
    reprovadas_score = 0
    scores_reprovados: list[float] = []
    aprovadas_conf = 0
    mortas_mtf = 0
    aprovadas_mtf = 0
    sinais = 0
    mortes_decisao = Counter()

    for i in range(lim.tendencia_min_candles, len(serie)):
        candles += 1
        ctx = ctx_mod.ler(serie, i, lim)
        tendencias[ctx.tendencia.value] += 1

        achadas = padroes.detectar_em(serie, i, ctx, lim)
        if not achadas:
            continue
        com_deteccao += 1
        deteccoes += len(achadas)

        zonas_avaliadas = [confluencia.avaliar(serie, i, d, ctx, lim) for d in achadas]
        for a in zonas_avaliadas:
            for v in a.vetos:
                vetos[v.split("(")[0].strip()] += 1

        sem_veto = [a for a in zonas_avaliadas if not a.vetos]
        if not sem_veto:
            continue

        melhor = max(sem_veto, key=lambda a: a.score_sem_teto)
        if melhor.score < lim.score_minimo_sinal:
            reprovadas_score += 1
            scores_reprovados.append(melhor.score)
            continue
        aprovadas_conf += 1

        vies = multitimeframe.calcular_vies(conjunto, serie[i].ts, lim)
        ajustada = multitimeframe.aplicar(melhor, vies, lim)
        if not ajustada.aprovado_com(lim):
            mortas_mtf += 1
            continue
        aprovadas_mtf += 1

        sinal = montar(serie, i, ajustada, ctx, args.capital, lim)
        if sinal is None:
            mortes_decisao[_porque_morreu(serie, i, ajustada, ctx, args.capital, lim)] += 1
            continue
        sinais += 1

    # ---- relatório ----------------------------------------------------
    def linha(rotulo: str, valor: int, de: int | None = None) -> None:
        pct = f"  ({valor / de:.1%} do anterior)" if de else ""
        print(f"  {rotulo:<42} {valor:>7,}{pct}".replace(",", "."))

    print("FUNIL")
    linha("candles avaliados", candles)
    linha("candles com ao menos uma detecção", com_deteccao, candles)
    linha("detecções brutas", deteccoes)
    linha("candles aprovados na confluência", aprovadas_conf, com_deteccao)
    linha("sobreviveram ao viés multi-timeframe", aprovadas_mtf, aprovadas_conf)
    linha("viraram SINAL", sinais, aprovadas_mtf)

    print("\nCONTEXTO (tendência por candle)")
    for nome, n in tendencias.most_common():
        print(f"  {nome:<42} {n:>7,}  ({n / candles:.1%})".replace(",", "."))

    print("\nVETOS na confluência (por detecção)")
    for motivo, n in vetos.most_common(8):
        print(f"  {motivo:<42} {n:>7,}".replace(",", "."))

    if scores_reprovados:
        media = sum(scores_reprovados) / len(scores_reprovados)
        acima = sum(1 for s in scores_reprovados if s > lim.score_minimo_sinal * 0.8)
        print(f"\nREPROVADAS POR SCORE (mínimo {lim.score_minimo_sinal})")
        print(
            f"  quantidade                                 {reprovadas_score:>7,}".replace(",", ".")
        )
        print(f"  score médio das reprovadas                 {media:>7.3f}")
        print(f"  a menos de 20% do corte                    {acima:>7,}".replace(",", "."))

    print(f"\nMORTAS PELO MULTI-TIMEFRAME                  {mortas_mtf:>7,}".replace(",", "."))

    if mortes_decisao:
        print("\nMORTAS NA DECISÃO")
        for motivo, n in mortes_decisao.most_common():
            print(f"  {motivo:<42} {n:>7,}".replace(",", "."))

    return 0


def _porque_morreu(serie, i, avaliacao, ctx, capital, lim) -> str:
    """Reconstrói o motivo da recusa em `decisao.montar`.

    Duplica a aritmética do módulo de decisão de propósito: `montar` devolve `None` sem
    dizer por quê, e mudá-lo para devolver um motivo poluiria a assinatura do caminho
    quente por causa de uma ferramenta de diagnóstico.
    """
    from trader_ai.instrumentos import resolver

    inst = resolver(serie.ativo)
    d = avaliacao.deteccao
    folga = lim.folga_stop_atr * ctx.atr

    if d.direcao is Direcao.ALTA:
        entrada = inst.arredondar_para_cima(d.extremo_superior + inst.tick)
        stop = inst.arredondar_para_baixo(d.extremo_inferior - folga)
        risco = entrada - stop
    else:
        entrada = inst.arredondar_para_baixo(d.extremo_inferior - inst.tick)
        stop = inst.arredondar_para_cima(d.extremo_superior + folga)
        risco = stop - entrada

    if risco <= 0:
        return "risco <= 0 (formação degenerada)"

    risco_unitario = inst.reais(risco) + inst.custo_total(1)
    if int((capital * lim.risco_por_trade_pct / 100.0) // risco_unitario) < 1:
        return f"capital nao cobre 1 contrato (risco R$ {risco_unitario:.0f})"

    return f"R:R abaixo de {lim.rr_minimo}"


if __name__ == "__main__":
    raise SystemExit(main())
