"""Mede uma regra de cada vez, fora da amostra. É o que separa medição de palpite.

    python scripts/experimento.py --ativos WDO WIN

## Por que existe

Em 10/08/2026 eu apliquei três correções de uma vez no motor e medi o conjunto: o WDO
piorou de −0,027R para −0,092R. O conjunto piorar não diz **qual** das três custou, e sem
isso a próxima decisão é chute. Este script roda a matriz.

## O que ele NÃO faz, de propósito

Não escolhe a melhor configuração. Varrer parâmetros e adotar o que deu o melhor número
fora da amostra transforma o conjunto de teste em conjunto de treino — é a mesma
memorização que o walk-forward existe para impedir, só que uma camada acima e muito mais
difícil de enxergar depois.

O que ele produz é uma tabela para leitura humana. Uma diferença só merece crédito se
**aparecer nos dois ativos e em janelas diferentes**; se aparecer num e sumir no outro,
é ruído com aparência de descoberta.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from trader_ai import backtest as bt
from trader_ai import padroes
from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.limiares import PADRAO, Limiares
from trader_ai.tipos import Timeframe

# Cada linha isola UMA diferença em relação ao ponto de partida. `None` em
# `confiabilidade_sem_medicao` significa "usa o prior do ebook", o comportamento antigo.
EXPERIMENTOS: list[tuple[str, dict]] = [
    (
        "base (como estava antes de 10/08)",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
        },
    ),
    (
        "so veto do vizinho",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": True,
            "vetar_expectancia_negativa": False,
        },
    ),
    (
        "so veto de expectancia",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": True,
        },
    ),
    (
        "so confiabilidade neutra",
        {
            "confiabilidade_sem_medicao": 0.50,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
        },
    ),
    (
        "as tres juntas",
        {
            "confiabilidade_sem_medicao": 0.50,
            "vetar_contra_vizinho": True,
            "vetar_expectancia_negativa": True,
        },
    ),
    (
        "base + R:R minimo 2.0",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
            "rr_minimo": 2.0,
        },
    ),
    (
        "base + R:R minimo 2.5",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
            "rr_minimo": 2.5,
        },
    ),
    (
        "base + score minimo 0.55",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
            "score_minimo_sinal": 0.55,
        },
    ),
    # Os pesos de janela foram calibrados sobre a base deslocada 3h: cada peso ficou
    # preso à janela errada. Desligar é a pergunta honesta — ajudam ou atrapalham?
    (
        "base + sem peso de horario",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
            "usar_peso_horario": False,
        },
    ),
    (
        "base + sem peso + R:R 2.0",
        {
            "confiabilidade_sem_medicao": None,
            "vetar_contra_vizinho": False,
            "vetar_expectancia_negativa": False,
            "usar_peso_horario": False,
            "rr_minimo": 2.0,
        },
    ),
]


def rodar(serie, lim: Limiares, janelas: int, capital: float) -> dict:
    """Walk-forward com a calibração isolada entre execuções.

    `bt.walk_forward` mexe no dicionário global `padroes.CALIBRACAO`. Sem salvar e
    restaurar, o experimento seguinte herdaria a calibração do anterior e a comparação
    perderia o sentido.
    """
    anterior = dict(padroes.CALIBRACAO)
    try:
        padroes.CALIBRACAO.clear()
        resultado = bt.walk_forward(serie, janelas=janelas, capital=capital, lim=lim)
    finally:
        padroes.CALIBRACAO.clear()
        padroes.CALIBRACAO.update(anterior)

    testes = [j.teste for j in resultado]
    n = sum(len(t.acionadas) for t in testes)
    return {
        "expectancia": sum(t.expectancia_r for t in testes) / len(testes),
        "operacoes": n,
        "reais": sum(t.resultado_reais for t in testes),
        "acerto": (
            sum(t.taxa_acerto * len(t.acionadas) for t in testes) / n if n else 0.0
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ativos", nargs="+", default=["WDO", "WIN"])
    p.add_argument("--dados", default="dados")
    p.add_argument("--tf", default="M5")
    p.add_argument("--janelas", type=int, default=4)
    p.add_argument("--capital", type=float, default=20_000.0)
    args = p.parse_args(argv)

    tf = Timeframe[args.tf]
    series = {}
    for ativo in args.ativos:
        caminho = Path(args.dados) / f"{ativo}_{args.tf}_real.csv"
        if not caminho.exists():
            print(f"{caminho} não existe — pulando {ativo}")
            continue
        series[ativo] = ler_arquivo(caminho, ativo, tf)
        print(f"{ativo}: {len(series[ativo])} candles")

    if not series:
        return 1

    largura = max(len(nome) for nome, _ in EXPERIMENTOS) + 2
    cabecalho = f"\n{'experimento':<{largura}}"
    for ativo in series:
        cabecalho += f"{ativo + ' exp':>11}{ativo + ' n':>8}{ativo + ' R$':>11}"
    print(cabecalho)
    print("-" * len(cabecalho))

    base: dict[str, float] = {}
    for nome, ajustes in EXPERIMENTOS:
        lim = replace(PADRAO, **ajustes)
        linha = f"{nome:<{largura}}"
        for ativo, serie in series.items():
            r = rodar(serie, lim, args.janelas, args.capital)
            if nome.startswith("base ("):
                base[ativo] = r["expectancia"]
            delta = r["expectancia"] - base.get(ativo, r["expectancia"])
            marca = "" if nome.startswith("base (") else f" ({delta:+.3f})"
            linha += f"{r['expectancia']:>+8.3f}R{marca:<0}{r['operacoes']:>8}{r['reais']:>11,.0f}"
        print(linha)

    print(
        "\nLeitura: uma diferença só vale se aparecer NOS DOIS ativos. Num só, é ruído.\n"
        "Nenhuma configuração deve ser adotada por ter dado o melhor número aqui — "
        "escolher pelo teste transforma o teste em treino."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
