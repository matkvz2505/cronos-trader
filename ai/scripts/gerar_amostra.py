"""Gera uma série sintética de WIN ou WDO, no formato que o motor lê.

Existe para uma coisa só: **permitir rodar a pipeline inteira antes de ter conta no
MT5**. Não substitui dados reais e não serve para validar estratégia — o gerador não
reproduz microestrutura, leilão, agenda econômica nem correlação externa, e uma
expectância medida aqui não significa absolutamente nada.

    python scripts/gerar_amostra.py --ativo WIN --dias 60 --saida dados/WIN_M5.csv

O que ele reproduz, e que basta para exercitar o motor:

- pregão das 09:00 às 17:55 em barras de 5 minutos
- perfil de volatilidade intraday em U (abertura e fechamento agitados, almoço parado)
- regimes alternando entre tendência e lateralização, como o mercado de fato faz
- volume correlacionado com a volatilidade da barra
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

BARRAS_POR_DIA = 108  # 09:00 → 17:55 em passos de 5 minutos

PERFIL_VOLATILIDADE = {
    # hora do pregão -> multiplicador de volatilidade
    9: 1.7,
    10: 1.2,
    11: 1.0,
    12: 0.6,
    13: 0.6,
    14: 1.3,
    15: 1.4,
    16: 1.1,
    17: 1.3,
}

PARAMETROS = {
    # ativo: (preço inicial, volatilidade base por barra, tick)
    "WIN": (130_000.0, 90.0, 5.0),
    "WDO": (5_400.0, 4.5, 0.5),
}


def _arredondar(preco: float, tick: float) -> float:
    return round(preco / tick) * tick


Barra = tuple[datetime, float, float, float, float, int]


def gerar(ativo: str, dias: int, semente: int) -> list[Barra]:
    rng = random.Random(semente)
    preco_inicial, volatilidade, tick = PARAMETROS[ativo]

    preco = preco_inicial
    inicio = datetime(2026, 3, 2, 9, 0)  # uma segunda-feira
    linhas = []

    dia = 0
    entregues = 0
    # Regime: quantas barras faltam no regime atual e qual a deriva dele.
    barras_no_regime = 0
    deriva = 0.0

    while entregues < dias:
        data = inicio + timedelta(days=dia)
        dia += 1
        if data.weekday() >= 5:  # pula fim de semana
            continue
        entregues += 1

        for barra in range(BARRAS_POR_DIA):
            momento = data + timedelta(minutes=5 * barra)

            if barras_no_regime <= 0:
                # Alterna entre tendência (deriva não-nula) e lateralização.
                barras_no_regime = rng.randint(20, 70)
                if rng.random() < 0.55:
                    deriva = rng.uniform(-0.35, 0.35) * volatilidade
                else:
                    deriva = 0.0
            barras_no_regime -= 1

            escala = volatilidade * PERFIL_VOLATILIDADE.get(momento.hour, 1.0)
            abertura = preco
            fechamento = abertura + deriva + rng.gauss(0, escala)

            corpo = abs(fechamento - abertura)
            # Sombras proporcionais ao corpo, com cauda ocasional (rejeição de preço).
            cauda = escala * (2.5 if rng.random() < 0.08 else 0.45)
            maxima = max(abertura, fechamento) + abs(rng.gauss(0, cauda * 0.5))
            minima = min(abertura, fechamento) - abs(rng.gauss(0, cauda * 0.5))

            volume = int(800 + (corpo / max(escala, 1e-9)) * 900 + rng.uniform(0, 400))

            linhas.append(
                (
                    momento,
                    _arredondar(abertura, tick),
                    _arredondar(maxima, tick),
                    _arredondar(minima, tick),
                    _arredondar(fechamento, tick),
                    volume,
                )
            )
            preco = fechamento

    return linhas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ativo", default="WIN", choices=sorted(PARAMETROS))
    parser.add_argument("--dias", type=int, default=60, help="pregões a gerar")
    parser.add_argument("--semente", type=int, default=42, help="reprodutibilidade")
    parser.add_argument("--saida", default=None)
    args = parser.parse_args()

    linhas = gerar(args.ativo, args.dias, args.semente)
    destino = Path(args.saida or f"dados/{args.ativo}_M5.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)

    with destino.open("w", encoding="utf-8", newline="") as fp:
        fp.write("datetime,open,high,low,close,volume\n")
        for ts, abertura, maxima, minima, fechamento, volume in linhas:
            fp.write(
                f"{ts:%Y-%m-%d %H:%M:%S},{abertura},{maxima},{minima},{fechamento},{volume}\n"
            )

    print(f"{len(linhas)} candles ({args.dias} pregões) de {args.ativo} em {destino}")
    print("Lembrete: dado sintético serve para exercitar a pipeline, não para validar estratégia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
