"""Interface de linha de comando do motor.

    trader catalogo
    trader detectar dados/WIN_M5.csv --ativo WIN --tf M5
    trader sinais   dados/WIN_M5.csv --ativo WIN --tf M5 --capital 20000
    trader backtest dados/WIN_M5.csv --ativo WIN --tf M5
    trader walkforward dados/WIN_M5.csv --ativo WIN --janelas 4
    trader baixar WIN --tf M5 --n 5000 --saida dados/WIN_M5.csv

Só `baixar` precisa do MetaTrader 5. Todo o resto roda sobre arquivo, em qualquer sistema.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import backtest as bt
from . import confluencia, multitimeframe, padroes
from . import contexto as ctx_mod
from .decisao import montar
from .fontes.base import FonteIndisponivel
from .fontes.csv_loader import ler_arquivo
from .limiares import PADRAO
from .tipos import Serie, Timeframe

TIMEFRAMES = {tf.name: tf for tf in Timeframe}


def _carregar(args) -> Serie:
    tf = TIMEFRAMES[args.tf]
    serie = ler_arquivo(args.arquivo, args.ativo, tf)
    if args.ultimos:
        serie = Serie(serie.ativo, tf, serie.candles[-args.ultimos :])
    print(
        f"{serie.ativo} {tf.rotulo}: {len(serie)} candles "
        f"de {serie[0].ts:%d/%m/%Y %H:%M} a {serie[-1].ts:%d/%m/%Y %H:%M}\n"
    )
    return serie


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------


def cmd_catalogo(args) -> int:
    especificacoes = padroes.catalogo_ordenado()
    print(f"{len(especificacoes)} padrões registrados\n")
    familia_atual = None
    for spec in especificacoes:
        if spec.familia.value != familia_atual:
            familia_atual = spec.familia.value
            print(f"\n── {familia_atual.upper()} ──")
        tendencia = spec.tendencia_requerida.value if spec.tendencia_requerida else "qualquer"
        marcas = []
        if spec.exige_gap:
            marcas.append("gap")
        if spec.derivado_por_simetria:
            marcas.append("espelhado")
        sufixo = f"  [{', '.join(marcas)}]" if marcas else ""
        print(
            f"  {spec.nome:<34} {spec.n_candles}c  {spec.direcao.value:<6} "
            f"tend={tendencia:<8} prior={spec.confiabilidade_ebook:.2f}  "
            f"p.{spec.pagina_ebook}{sufixo}"
        )
        if args.detalhado and spec.observacao:
            print(f"      {spec.observacao}")
    return 0


def cmd_detectar(args) -> int:
    serie = _carregar(args)
    lim = PADRAO.para_timeframe(serie.timeframe)
    achados = padroes.varrer(serie, lim)
    if not achados:
        print("nenhum padrão detectado.")
        return 0

    print(f"{len(achados)} detecções\n")
    for d in achados[-args.limite :]:
        print(
            f"  {serie[d.indice_fim].ts:%d/%m %H:%M}  {d.nome:<32} "
            f"{d.direcao.value:<6} força={d.forca:.2f} score={d.score_bruto:.3f}"
        )

    print("\nPor padrão:")
    contagem: dict[str, int] = {}
    for d in achados:
        contagem[d.nome] = contagem.get(d.nome, 0) + 1
    for nome, quantidade in sorted(contagem.items(), key=lambda kv: -kv[1]):
        print(f"  {nome:<34} {quantidade}")
    return 0


def cmd_sinais(args) -> int:
    serie = _carregar(args)
    lim = PADRAO.para_timeframe(serie.timeframe)
    conjunto = multitimeframe.montar_conjunto(serie)

    emitidos = 0
    for i in range(lim.tendencia_min_candles, len(serie)):
        # Série inteira: os indicadores são causais e os pivôs passam por
        # `swings_confirmados`. Ver a nota em backtest.rodar().
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
        sinal = montar(serie, i, avaliacao, ctx, args.capital, lim)
        if sinal is None:
            continue

        emitidos += 1
        print(sinal.resumo())
        if args.detalhado:
            print(f"      {avaliacao.explicar()}")
            for nota in sinal.observacoes:
                print(f"      · {nota}")

    print(f"\n{emitidos} sinais emitidos em {len(serie)} candles.")
    if emitidos == 0:
        print(
            "Zero sinais é um resultado válido: os filtros de confluência, R:R mínimo e "
            "viés multi-timeframe descartam a maior parte das detecções por construção."
        )
    return 0


def cmd_backtest(args) -> int:
    serie = _carregar(args)
    resultado = bt.rodar(
        serie,
        capital=args.capital,
        usar_multitimeframe=not args.sem_mtf,
        pular_rollover=not args.com_rollover,
    )
    print(resultado.relatorio())

    if args.calibrar:
        calibrado = bt.calibrar(resultado)
        print(f"\n{len(calibrado)} padrões calibrados com amostra suficiente.")
        print(
            "Atenção: calibrar e medir na MESMA série é memorização, não evidência. "
            "Use `walkforward` para um número em que dá para confiar."
        )
    return 0


def cmd_walkforward(args) -> int:
    serie = _carregar(args)
    try:
        janelas = bt.walk_forward(serie, janelas=args.janelas, capital=args.capital)
    except ValueError as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    print(f"Walk-forward em {args.janelas} janelas — o que vale é a coluna TESTE.\n")
    print(f"{'#':<3} {'treino exp':>12} {'teste exp':>12} {'teste acerto':>14} {'teste R$':>12}")
    for j in janelas:
        print(
            f"{j.indice:<3} {j.treino.expectancia_r:>+11.2f}R {j.teste.expectancia_r:>+11.2f}R "
            f"{j.teste.taxa_acerto:>13.1%} {j.teste.resultado_reais:>+12.2f}"
        )

    media_teste = sum(j.teste.expectancia_r for j in janelas) / len(janelas)
    print(f"\nExpectância média fora da amostra: {media_teste:+.2f}R por operação")
    if media_teste <= 0:
        print(
            "Negativa ou nula: a configuração atual não tem edge nesta série. "
            "Isto é informação, não falha — ajuste limiares ou reduza o catálogo."
        )
    return 0


def cmd_baixar(args) -> int:
    try:
        from .fontes.mt5 import MetaTrader5Fonte
    except ImportError as erro:  # pragma: no cover - depende do ambiente
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    tf = TIMEFRAMES[args.tf]
    try:
        with MetaTrader5Fonte(continuo=args.continuo) as fonte:
            simbolo = fonte.resolver_simbolo(args.ativo)
            print(f"baixando {simbolo} {tf.rotulo}...")
            serie = fonte.ultimos(args.ativo, tf, args.n)
    except FonteIndisponivel as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as fp:
        fp.write("datetime,open,high,low,close,volume\n")
        for c in serie.candles:
            fp.write(
                f"{c.ts:%Y-%m-%d %H:%M:%S},{c.abertura},{c.maxima},"
                f"{c.minima},{c.fechamento},{c.volume}\n"
            )
    print(f"{len(serie)} candles salvos em {destino}")
    return 0


# ---------------------------------------------------------------------------


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trader",
        description="Motor de padrões de candlestick para mini-índice (WIN) e mini-dólar (WDO).",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    def com_arquivo(p):
        p.add_argument("arquivo", help="CSV/TSV de candles")
        p.add_argument("--ativo", default="WIN", choices=["WIN", "WDO"])
        p.add_argument("--tf", default="M5", choices=list(TIMEFRAMES))
        p.add_argument("--ultimos", type=int, default=0, help="usar só os N últimos candles")
        return p

    p = sub.add_parser("catalogo", help="lista os padrões registrados")
    p.add_argument("--detalhado", action="store_true", help="inclui as observações")
    p.set_defaults(func=cmd_catalogo)

    p = com_arquivo(sub.add_parser("detectar", help="detecta padrões, sem filtrar"))
    p.add_argument("--limite", type=int, default=40, help="quantas detecções listar")
    p.set_defaults(func=cmd_detectar)

    p = com_arquivo(sub.add_parser("sinais", help="motor completo: detecção → sinal"))
    p.add_argument("--capital", type=float, default=10_000.0)
    p.add_argument("--detalhado", action="store_true")
    p.set_defaults(func=cmd_sinais)

    p = com_arquivo(sub.add_parser("backtest", help="simula e mede"))
    p.add_argument("--capital", type=float, default=10_000.0)
    p.add_argument("--sem-mtf", action="store_true", help="desliga o filtro multi-timeframe")
    p.add_argument("--com-rollover", action="store_true", help="não descarta a virada de contrato")
    p.add_argument("--calibrar", action="store_true")
    p.set_defaults(func=cmd_backtest)

    p = com_arquivo(sub.add_parser("walkforward", help="calibra numa janela, testa na seguinte"))
    p.add_argument("--janelas", type=int, default=4)
    p.add_argument("--capital", type=float, default=10_000.0)
    p.set_defaults(func=cmd_walkforward)

    p = sub.add_parser("baixar", help="exporta candles do MetaTrader 5 (Windows)")
    p.add_argument("ativo", choices=["WIN", "WDO"])
    p.add_argument("--tf", default="M5", choices=list(TIMEFRAMES))
    p.add_argument("--n", type=int, default=5000, help="quantidade de candles")
    p.add_argument("--saida", default="dados/candles.csv")
    p.add_argument(
        "--continuo",
        action="store_true",
        help="usa o símbolo contínuo ajustado (WIN$N) — o correto para backtest",
    )
    p.set_defaults(func=cmd_baixar)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    try:
        return args.func(args)
    except FonteIndisponivel as erro:
        print(f"erro de dados: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
