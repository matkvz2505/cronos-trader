"""Resolução de contrato vigente e detecção da janela de rollover.

WIN e WDO **vencem**. Se o coletor gravar `WINQ26` e depois `WINV26` na mesma série sem
tratar a virada, o gráfico ganha um salto artificial de centenas de pontos — e todo padrão
de gap detectado ali é falso. Pior: isso corrompe o backtest inteiro **sem gerar erro
nenhum**, produzindo estatística que parece boa e não é.

Regra prática do produto:

- **Backtest** → use o símbolo contínuo da corretora (`WIN$N`, `WDO$N`), já ajustado.
- **Tempo real** → use o contrato cheio (`WINQ26`), que é onde está a liquidez.
- **Sempre** → descarte a janela de rollover do backtest, via `em_rollover()`.

> ⚠️ As datas aqui seguem a regra padrão da B3, mas **feriados deslocam vencimento** e
> este módulo não modela o calendário de feriados. Antes de rodar backtest valendo,
> confira as datas contra o calendário oficial da B3.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

CODIGOS_MES = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}

MESES_WIN = (2, 4, 6, 8, 10, 12)
"""WIN vence só em meses pares."""

DIAS_ROLLOVER = 3
"""Quantos dias antes do vencimento a liquidez já migrou para o contrato seguinte."""


def _quarta_mais_proxima_do_dia_15(ano: int, mes: int) -> date:
    """Vencimento do WIN: a quarta-feira mais próxima do dia 15."""
    candidatas = [
        date(ano, mes, dia)
        for dia in range(1, calendar.monthrange(ano, mes)[1] + 1)
        if date(ano, mes, dia).weekday() == 2  # 2 = quarta
    ]
    return min(candidatas, key=lambda d: abs(d.day - 15))


def _primeiro_dia_util(ano: int, mes: int) -> date:
    """Vencimento do WDO: o primeiro dia útil do mês (feriados não modelados)."""
    dia = date(ano, mes, 1)
    while dia.weekday() >= 5:  # sábado/domingo
        dia += timedelta(days=1)
    return dia


def vencimento(ativo: str, ano: int, mes: int) -> date:
    codigo = ativo.strip().upper()
    if codigo.startswith("WIN"):
        if mes not in MESES_WIN:
            raise ValueError(f"WIN não tem vencimento em {mes:02d}; só meses pares")
        return _quarta_mais_proxima_do_dia_15(ano, mes)
    if codigo.startswith("WDO"):
        return _primeiro_dia_util(ano, mes)
    raise ValueError(f"ativo fora do escopo: {ativo!r}")


def _proximo_mes_win(ano: int, mes: int) -> tuple[int, int]:
    for candidato in MESES_WIN:
        if candidato >= mes:
            return ano, candidato
    return ano + 1, MESES_WIN[0]


def codigo_vigente(ativo: str, dia: date | None = None) -> str:
    """Código do contrato com liquidez em `dia`. Ex.: `WINQ26`, `WDOU26`.

    "Vigente" é o contrato que ainda não venceu **e** cujo vencimento não está dentro da
    janela de rollover — porque nela o volume já migrou, e operar o contrato velho é
    operar um book vazio.
    """
    hoje = dia or date.today()
    base = ativo.strip().upper()[:3]

    if base == "WIN":
        ano, mes = _proximo_mes_win(hoje.year, hoje.month)
        while hoje > vencimento(base, ano, mes) - timedelta(days=DIAS_ROLLOVER):
            proximo = mes + 1 if mes < 12 else 1
            ano = ano + 1 if proximo == 1 else ano
            ano, mes = _proximo_mes_win(ano, proximo)
        return f"WIN{CODIGOS_MES[mes]}{ano % 100:02d}"

    if base == "WDO":
        ano, mes = hoje.year, hoje.month
        while hoje > vencimento(base, ano, mes) - timedelta(days=DIAS_ROLLOVER):
            mes += 1
            if mes > 12:
                mes = 1
                ano += 1
        return f"WDO{CODIGOS_MES[mes]}{ano % 100:02d}"

    raise ValueError(f"ativo fora do escopo: {ativo!r}")


def simbolo_continuo(ativo: str) -> str:
    """Símbolo da série contínua ajustada, para backtest.

    Convenção da maioria das corretoras brasileiras no MT5. Confira o nome exato no
    Observador de Mercado do seu terminal — algumas usam `WIN$` sem o `N`.
    """
    return f"{ativo.strip().upper()[:3]}$N"


def em_rollover(ativo: str, dia: date, dias: int = DIAS_ROLLOVER) -> bool:
    """Se `dia` cai na janela de virada de contrato.

    O backtest deve **descartar** esses dias: o volume está partido entre dois contratos,
    o spread abre, e os padrões detectados ali refletem a migração de posição, não a
    leitura de mercado que estamos tentando medir.
    """
    base = ativo.strip().upper()[:3]
    if base == "WIN":
        meses = [(dia.year, m) for m in MESES_WIN]
    elif base == "WDO":
        meses = [(dia.year, m) for m in range(1, 13)]
    else:
        raise ValueError(f"ativo fora do escopo: {ativo!r}")

    for ano, mes in meses:
        try:
            venc = vencimento(base, ano, mes)
        except ValueError:
            continue
        if abs((dia - venc).days) <= dias:
            return True
    return False
