"""Leitura de candles de arquivo — histórico exportado, backtest e testes.

Aceita os dois formatos que aparecem na prática:

**Exportação do MT5** (tabulado, `<DATE>\\t<TIME>\\t<OPEN>\\t…`) — é o que sai de
*Ferramentas → Central de Cotações → Exportar barras* no terminal.

**CSV genérico** com cabeçalho, separado por vírgula ou ponto-e-vírgula, onde as colunas
são reconhecidas por nome em português ou inglês.

Números aceitam vírgula decimal: exportação brasileira de planilha gera `130.250,00`, e
um parser que só entende ponto silenciosamente lê `130.250` como cento e trinta.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ..tipos import Candle, Serie, Timeframe
from .base import FonteIndisponivel

ALIAS = {
    "abertura": {"open", "abertura", "<open>", "o"},
    "maxima": {"high", "maxima", "máxima", "max", "<high>", "h"},
    "minima": {"low", "minima", "mínima", "min", "<low>", "l"},
    "fechamento": {"close", "fechamento", "fech", "<close>", "c"},
    "volume": {"volume", "vol", "<vol>", "<tickvol>", "tickvol", "real_volume"},
    "data": {"date", "data", "<date>"},
    "hora": {"time", "hora", "<time>"},
    "datahora": {"datetime", "datahora", "timestamp", "data_hora"},
}

FORMATOS_DATA = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y.%m.%d",
    "%d/%m/%Y",
)


def _numero(bruto: str) -> float:
    """Converte texto para float tolerando formato brasileiro.

    `130.250,00` → 130250.0 · `130250.00` → 130250.0 · `1 234,5` → 1234.5
    """
    texto = bruto.strip().replace(" ", "").replace(" ", "")
    if not texto:
        return 0.0
    if "," in texto:
        # Vírgula presente = separador decimal brasileiro; ponto é milhar.
        texto = texto.replace(".", "").replace(",", ".")
    return float(texto)


def _momento(texto: str) -> datetime:
    limpo = texto.strip().replace("T", " ")
    for formato in FORMATOS_DATA:
        try:
            return datetime.strptime(limpo, formato)
        except ValueError:
            continue
    raise FonteIndisponivel(f"data em formato não reconhecido: {texto!r}")


def _mapear_colunas(cabecalho: list[str]) -> dict[str, int]:
    normalizado = [c.strip().lower().lstrip("﻿") for c in cabecalho]
    mapa: dict[str, int] = {}
    for campo, nomes in ALIAS.items():
        for i, coluna in enumerate(normalizado):
            if coluna in nomes:
                mapa[campo] = i
                break
    faltando = {"abertura", "maxima", "minima", "fechamento"} - mapa.keys()
    if faltando:
        raise FonteIndisponivel(
            f"colunas obrigatórias ausentes: {sorted(faltando)}. Cabeçalho lido: {cabecalho}"
        )
    if "datahora" not in mapa and "data" not in mapa:
        raise FonteIndisponivel(f"nenhuma coluna de data encontrada em {cabecalho}")
    return mapa


def _dialeto(amostra: str) -> str:
    if "\t" in amostra:
        return "\t"
    if amostra.count(";") > amostra.count(","):
        return ";"
    return ","


def ler_arquivo(
    caminho: str | Path, ativo: str, timeframe: Timeframe, limite: int | None = None
) -> Serie:
    """Carrega uma série de um CSV/TSV.

    Ordena por timestamp e **remove duplicatas**, mantendo a última ocorrência. As duas
    coisas importam: exportação do MT5 pode vir invertida, e concatenar dois arquivos com
    sobreposição de período é o jeito mais comum de conseguir histórico longo.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise FonteIndisponivel(f"arquivo não encontrado: {caminho}")

    with caminho.open("r", encoding="utf-8-sig", newline="") as fp:
        primeira = fp.readline()
        if not primeira:
            raise FonteIndisponivel(f"arquivo vazio: {caminho}")
        fp.seek(0)
        leitor = csv.reader(fp, delimiter=_dialeto(primeira))
        linhas = list(leitor)

    if len(linhas) < 2:
        raise FonteIndisponivel(f"arquivo sem dados: {caminho}")

    mapa = _mapear_colunas(linhas[0])
    por_ts: dict[datetime, Candle] = {}

    for numero, linha in enumerate(linhas[1:], start=2):
        if not linha or all(not celula.strip() for celula in linha):
            continue
        try:
            if "datahora" in mapa:
                ts = _momento(linha[mapa["datahora"]])
            else:
                data = linha[mapa["data"]]
                hora = linha[mapa["hora"]] if "hora" in mapa else "00:00"
                ts = _momento(f"{data} {hora}")

            candle = Candle(
                ts=ts,
                abertura=_numero(linha[mapa["abertura"]]),
                maxima=_numero(linha[mapa["maxima"]]),
                minima=_numero(linha[mapa["minima"]]),
                fechamento=_numero(linha[mapa["fechamento"]]),
                volume=_numero(linha[mapa["volume"]]) if "volume" in mapa else 0.0,
            )
        except (IndexError, ValueError) as erro:
            raise FonteIndisponivel(f"{caminho}:{numero} — linha inválida: {erro}") from erro

        if candle.maxima < candle.minima:
            raise FonteIndisponivel(
                f"{caminho}:{numero} — máxima {candle.maxima} abaixo da mínima {candle.minima}"
            )
        por_ts[ts] = candle

    candles = [por_ts[ts] for ts in sorted(por_ts)]
    if limite is not None:
        candles = candles[-limite:]
    if not candles:
        raise FonteIndisponivel(f"nenhum candle válido em {caminho}")
    return Serie(ativo, timeframe, candles)


class ArquivoFonte:
    """Implementa `FonteDados` sobre um diretório de arquivos exportados.

    Convenção de nome: `<ATIVO>_<TIMEFRAME>.csv` — ex.: `WIN_M5.csv`, `WDO_M15.csv`.
    """

    def __init__(self, diretorio: str | Path):
        self.diretorio = Path(diretorio)

    def _caminho(self, ativo: str, timeframe: Timeframe) -> Path:
        base = ativo.strip().upper()[:3]
        for sufixo in (".csv", ".txt", ".tsv"):
            candidato = self.diretorio / f"{base}_{timeframe.name}{sufixo}"
            if candidato.exists():
                return candidato
        raise FonteIndisponivel(
            f"nenhum arquivo para {base} {timeframe.name} em {self.diretorio}"
        )

    def ultimos(self, ativo: str, timeframe: Timeframe, quantidade: int) -> Serie:
        return ler_arquivo(self._caminho(ativo, timeframe), ativo, timeframe, limite=quantidade)

    def periodo(
        self, ativo: str, timeframe: Timeframe, inicio: datetime, fim: datetime
    ) -> Serie:
        serie = ler_arquivo(self._caminho(ativo, timeframe), ativo, timeframe)
        filtrados = [c for c in serie.candles if inicio <= c.ts <= fim]
        return Serie(ativo, timeframe, filtrados)
