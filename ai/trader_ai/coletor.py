"""Coletor: MetaTrader 5 → Postgres → motor.

Roda como processo **no host Windows**, não em container: precisa falar com o terminal
MT5, que não containeriza. É a única peça não portável do sistema.

    cd ai
    $env:DATABASE_URL = "postgresql://trader:trader@localhost:5460/cronos_trader"
    python -m trader_ai.coletor --ativos WIN WDO

A cada ciclo, para cada ativo e timeframe:

1. baixa as últimas N barras do MT5
2. faz upsert no Postgres (idempotente — o candle em formação é atualizado, não duplicado)
3. roda o motor nos candles recentes e persiste sinais novos
4. acompanha os sinais abertos contra os candles novos (alvo, stop, expiração)

Deixe rodando durante o pregão. Fora do horário ele continua vivo e apenas não encontra
nada novo — reiniciar a cada dia não é necessário.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from datetime import datetime

from . import padroes, persistencia
from .fontes.base import FonteIndisponivel
from .pipeline import analisar
from .tipos import Timeframe

TIMEFRAMES = (Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1)

_parar = False


def _sinal_de_parada(*_) -> None:
    global _parar
    _parar = True
    print("\nencerrando após o ciclo atual...")


def ciclo(fonte, ativos: list[str], capital: float, barras: int, verboso: bool) -> None:
    for ativo in ativos:
        for tf in TIMEFRAMES:
            try:
                serie_mt5 = fonte.ultimos(ativo, tf, barras)
            except FonteIndisponivel as erro:
                print(f"  {ativo} {tf.rotulo}: {erro}")
                continue

            gravados = persistencia.gravar_candles(serie_mt5)

            # Relê do banco: a série do MT5 tem só as últimas `barras`, e o motor precisa
            # de histórico mais longo para ATR, tendência e pivôs terem sentido.
            serie = persistencia.ler_candles(ativo, tf, limite=5000)
            if len(serie) < 60:
                if verboso:
                    print(f"  {ativo} {tf.rotulo}: {len(serie)} candles, aquecendo")
                continue

            padroes.CALIBRACAO.update(persistencia.carregar_calibracao(ativo, tf))

            # Só o gatilho de 5min emite sinal. Os timeframes maiores existem no banco
            # para formar o viés e alimentar o gráfico — emitir sinal em todos eles
            # geraria quatro versões do mesmo trade.
            if tf is Timeframe.M5:
                analise = analisar(serie, capital=capital, ultimos=30)
                vies = analise.vies.descrever() if analise.vies else None
                novos = persistencia.gravar_sinais(analise.sinais, vies, analise.teses)
                persistencia.gravar_deteccoes(ativo, tf, analise.deteccoes, serie)
                mudancas = persistencia.atualizar_sinais_abertos(ativo, tf, serie)

                if novos or mudancas or verboso:
                    marca = datetime.now().strftime("%H:%M:%S")
                    partes = [f"{gravados} candles"]
                    if novos:
                        partes.append(f"{novos} SINAIS NOVOS")
                    if mudancas:
                        partes.append(", ".join(f"{k}={v}" for k, v in mudancas.items()))
                    print(f"  [{marca}] {ativo} {tf.rotulo}: {' · '.join(partes)}")

                for sinal in analise.sinais[-3:]:
                    print(f"      → {sinal.resumo()}")
            elif verboso:
                print(f"  {ativo} {tf.rotulo}: {gravados} candles")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ativos", nargs="+", default=["WIN"], choices=["WIN", "WDO"])
    parser.add_argument("--intervalo", type=int, default=30, help="segundos entre ciclos")
    parser.add_argument("--barras", type=int, default=500, help="barras lidas por ciclo")
    parser.add_argument("--capital", type=float, default=20_000.0)
    parser.add_argument(
        "--continuo",
        action="store_true",
        help="usa o símbolo contínuo (WIN$N) em vez do contrato vigente",
    )
    parser.add_argument("--uma-vez", action="store_true", help="roda um ciclo e sai")
    parser.add_argument("--verboso", action="store_true")
    args = parser.parse_args(argv)

    if not persistencia.disponivel():
        print(
            "DATABASE_URL não configurada (ou psycopg não instalado).\n"
            '  pip install -e ".[servico]"\n'
            '  $env:DATABASE_URL = "postgresql://trader:trader@localhost:5460/cronos_trader"',
            file=sys.stderr,
        )
        return 1

    ok, detalhe = persistencia.testar()
    if not ok:
        print(f"banco inacessível: {detalhe}", file=sys.stderr)
        return 1

    try:
        from .fontes.mt5 import MetaTrader5Fonte
    except ImportError as erro:
        print(f"{erro}", file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, _sinal_de_parada)
    signal.signal(signal.SIGTERM, _sinal_de_parada)

    print(
        f"coletor: {', '.join(args.ativos)} · {len(TIMEFRAMES)} timeframes · "
        f"ciclo de {args.intervalo}s · capital R$ {args.capital:,.2f}"
    )

    try:
        with MetaTrader5Fonte(continuo=args.continuo) as fonte:
            print(f"MT5 conectado · símbolo: {fonte.resolver_simbolo(args.ativos[0])}\n")
            while not _parar:
                ciclo(fonte, args.ativos, args.capital, args.barras, args.verboso)
                if args.uma_vez:
                    break
                # Sono fatiado para que Ctrl+C responda em 1 segundo, não em 30.
                for _ in range(args.intervalo):
                    if _parar:
                        break
                    time.sleep(1)
    except FonteIndisponivel as erro:
        print(f"\nMT5 indisponível: {erro}", file=sys.stderr)
        print("Rode `python scripts/diagnostico_mt5.py` para ver o que falta.", file=sys.stderr)
        return 1

    print("coletor encerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
