"""Importa um CSV de candles para o Postgres e roda o motor em cima.

Serve para dois casos:

- **Ver o produto funcionando sem corretora**, usando dados sintéticos do
  `gerar_amostra.py`. A tela inteira ganha vida: gráfico, sinais, placar, backtest.
- **Carregar histórico exportado do MT5** de uma vez, em vez de esperar o coletor
  acumular tick a tick.

    python scripts/importar_csv.py dados/WIN_M5.csv --ativo WIN --tf M5 --analisar

O upsert é idempotente — rodar duas vezes não duplica candle.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from trader_ai import multitimeframe, padroes, persistencia
from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.pipeline import analisar
from trader_ai.tipos import Timeframe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo", help="CSV/TSV de candles")
    parser.add_argument("--ativo", default="WIN", choices=["WIN", "WDO"])
    parser.add_argument("--tf", default="M5", choices=[tf.name for tf in Timeframe])
    parser.add_argument(
        "--derivar",
        action="store_true",
        default=True,
        help="também grava 15/30/60min derivados da base (padrão: sim)",
    )
    parser.add_argument(
        "--analisar",
        action="store_true",
        help="roda o motor depois de importar e grava os sinais",
    )
    parser.add_argument("--capital", type=float, default=20_000.0)
    parser.add_argument(
        "--ultimos",
        type=int,
        default=2000,
        help="quantos candles recentes analisar (o histórico anterior alimenta os indicadores)",
    )
    args = parser.parse_args(argv)

    if not persistencia.disponivel():
        print(
            "DATABASE_URL não configurada (ou psycopg ausente).\n"
            '  pip install -e ".[servico]"\n'
            '  $env:DATABASE_URL = "postgresql://trader:trader@localhost:5460/cronos_trader"',
            file=sys.stderr,
        )
        return 1

    ok, detalhe = persistencia.testar()
    if not ok:
        print(f"banco inacessível: {detalhe}", file=sys.stderr)
        return 1

    caminho = Path(args.arquivo)
    tf = Timeframe[args.tf]
    serie = ler_arquivo(caminho, args.ativo, tf)
    print(
        f"{caminho.name}: {len(serie)} candles de {serie[0].ts:%d/%m/%Y %H:%M} "
        f"a {serie[-1].ts:%d/%m/%Y %H:%M}"
    )

    total = persistencia.gravar_candles(serie)
    print(f"  {args.ativo} {tf.rotulo}: {total} candles gravados")

    # Derivar os timeframes maiores da mesma base garante que os quatro contem
    # exatamente a mesma história — sem discrepância entre fornecedores.
    if args.derivar and tf is Timeframe.M5:
        for alvo in (Timeframe.M15, Timeframe.M30, Timeframe.H1):
            derivada = multitimeframe.agregar(serie, alvo)
            gravados = persistencia.gravar_candles(derivada)
            print(f"  {args.ativo} {alvo.rotulo}: {gravados} candles derivados")

    if not args.analisar:
        print("\nPronto. Use --analisar para já gerar os sinais.")
        return 0

    print("\nrodando o motor...")
    padroes.CALIBRACAO.update(persistencia.carregar_calibracao(args.ativo, tf))
    do_banco = persistencia.ler_candles(args.ativo, tf, limite=50_000)
    analise = analisar(do_banco, capital=args.capital, ultimos=args.ultimos)

    vies = analise.vies.descrever() if analise.vies else None
    novos = persistencia.gravar_sinais(analise.sinais, vies, analise.teses)
    deteccoes = persistencia.gravar_deteccoes(args.ativo, tf, analise.deteccoes, do_banco)
    mudancas = persistencia.atualizar_sinais_abertos(args.ativo, tf, do_banco)

    print(f"  {len(analise.deteccoes)} detecções ({deteccoes} gravadas)")
    print(f"  {len(analise.sinais)} sinais gerados ({novos} novos no banco)")
    if mudancas:
        print(f"  acompanhamento: {', '.join(f'{k}={v}' for k, v in mudancas.items())}")
    print(f"  {analise.resumo}")

    for sinal in analise.sinais[-5:]:
        print(f"    → {sinal.resumo()}")

    if not analise.sinais:
        print(
            "\n  Zero sinais é um resultado válido: os filtros de confluência, R:R mínimo e\n"
            "  viés multi-timeframe descartam a maior parte das detecções por construção."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
