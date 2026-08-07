"""Corrige CSVs exportados com o bug de fuso do MT5 (candles 3h no passado).

    python scripts/corrigir_fuso_csv.py dados/WIN_M5_real.csv
    python scripts/corrigir_fuso_csv.py dados/*.csv --conferir     # só diagnostica

## Por que existe

O campo `time` do MT5 é o relógio de parede do servidor codificado *como se fosse* UTC.
Ler com `datetime.fromtimestamp()` aplica o fuso da máquina por cima; no Brasil (UTC−3)
todo candle nasce 3 horas antes do que aconteceu. Ver `trader_ai/fontes/mt5.py`.

O adapter já foi corrigido, mas os CSVs exportados **antes** da correção carregam o
deslocamento. Eles são a única cópia de dois anos de histórico real — o símbolo contínuo
(`WIN$N`) não atualiza ao vivo nesta corretora, então não dá para simplesmente reexportar.
Daí um corretor em vez de um descarte.

## Como ele sabe que precisa corrigir

Não pergunta, mede. A B3 negocia mini-contratos das **9h às 18h25**. Um arquivo deslocado
tem o pregão em 6h–15h25: a assinatura é a existência de candles antes das 9h e a ausência
completa deles depois das 16h. Se o arquivo já estiver na faixa certa, o script recusa —
rodar duas vezes deslocaria 6 horas e o estrago seria pior que o original.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# Pregão dos mini-contratos na B3. `AGORA` é o fim do after-market do WIN/WDO.
ABERTURA_B3 = 9
FECHAMENTO_B3 = 19

FORMATOS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M")


def _momento(texto: str) -> datetime:
    limpo = texto.strip().replace("T", " ")
    for formato in FORMATOS:
        try:
            return datetime.strptime(limpo, formato)
        except ValueError:
            continue
    raise ValueError(f"data em formato não reconhecido: {texto!r}")


def _coluna_de_data(cabecalho: list[str]) -> int:
    nomes = {"datetime", "datahora", "timestamp", "data_hora", "date", "data"}
    for i, nome in enumerate(cabecalho):
        if nome.strip().lower().lstrip("﻿") in nomes:
            return i
    raise ValueError(f"nenhuma coluna de data em {cabecalho}")


def diagnosticar(caminho: Path) -> tuple[Counter, int, bool]:
    """Devolve (histograma de horas, total de linhas, precisa_corrigir)."""
    with caminho.open(newline="", encoding="utf-8-sig") as fp:
        leitor = csv.reader(fp)
        cabecalho = next(leitor)
        col = _coluna_de_data(cabecalho)
        horas = Counter()
        total = 0
        for linha in leitor:
            if not linha or not linha[col].strip():
                continue
            horas[_momento(linha[col]).hour] += 1
            total += 1

    antes_da_abertura = sum(n for h, n in horas.items() if h < ABERTURA_B3)
    depois_do_fechamento = sum(n for h, n in horas.items() if h >= FECHAMENTO_B3)
    # A assinatura do deslocamento: pregão inteiro antes das 9h e nada depois das 16h.
    tem_tarde = any(h >= 16 for h in horas)
    precisa = antes_da_abertura > 0 and not tem_tarde and depois_do_fechamento == 0
    return horas, total, precisa


def corrigir(caminho: Path, horas: int, seco: bool) -> None:
    with caminho.open(newline="", encoding="utf-8-sig") as fp:
        linhas = list(csv.reader(fp))

    cabecalho, corpo = linhas[0], linhas[1:]
    col = _coluna_de_data(cabecalho)
    delta = timedelta(hours=horas)

    for linha in corpo:
        if linha and linha[col].strip():
            linha[col] = (_momento(linha[col]) + delta).strftime("%Y-%m-%d %H:%M:%S")

    if seco:
        print(f"  [simulação] {len(corpo)} linhas seriam deslocadas em +{horas}h")
        return

    # Backup antes de sobrescrever: o arquivo é insubstituível.
    backup = caminho.with_suffix(caminho.suffix + ".antes-do-fuso")
    if not backup.exists():
        shutil.copy2(caminho, backup)
        print(f"  backup em {backup.name}")

    with caminho.open("w", newline="", encoding="utf-8") as fp:
        escritor = csv.writer(fp, lineterminator="\n")
        escritor.writerow(cabecalho)
        escritor.writerows(corpo)
    print(f"  {len(corpo)} linhas deslocadas em +{horas}h")


def _faixa(horas: Counter) -> str:
    if not horas:
        return "vazio"
    return f"{min(horas):02d}h–{max(horas):02d}h"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("arquivos", nargs="+", type=Path)
    p.add_argument("--horas", type=int, default=3, help="deslocamento a aplicar (padrão 3)")
    p.add_argument("--conferir", action="store_true", help="só diagnostica, não escreve")
    p.add_argument("--forcar", action="store_true", help="corrige mesmo se já parecer certo")
    args = p.parse_args(argv)

    problemas = 0
    for caminho in args.arquivos:
        if not caminho.exists():
            print(f"{caminho}: não existe", file=sys.stderr)
            problemas += 1
            continue

        horas, total, precisa = diagnosticar(caminho)
        print(f"\n{caminho.name}  ({total} linhas, pregão em {_faixa(horas)})")

        if not precisa and not args.forcar:
            print("  já está na faixa da B3 — nada a fazer.")
            continue
        if not precisa and args.forcar:
            print("  AVISO: não parece deslocado, corrigindo por --forcar.")

        corrigir(caminho, args.horas, args.conferir)
        if not args.conferir:
            depois, _, _ = diagnosticar(caminho)
            print(f"  agora: pregão em {_faixa(depois)}")

    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
