"""Acesso ao Postgres compartilhado com o backend.

O **backend Node é dono do schema** (Prisma); este módulo apenas lê e escreve nas mesmas
tabelas. Duas consequências práticas que valem lembrar ao mexer aqui:

1. **Colunas são camelCase e precisam de aspas.** Prisma não converte nomes de campo, só
   de tabela (`@@map`). Então é `sinais` (tabela) mas `"padraoId"` (coluna). Sem as aspas
   o Postgres normaliza para minúsculo e a coluna "não existe".

2. **`id` é gerado pelo cliente, não pelo banco.** `@default(uuid())` do Prisma roda no
   Node; a coluna não tem DEFAULT. Quem insere daqui precisa gerar o UUID.

Tudo é opcional: sem `DATABASE_URL` no ambiente, `disponivel()` devolve `False` e o motor
continua funcionando sobre CSV. O banco é para o produto; o motor não depende dele.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from .tipos import Candle, Serie, Timeframe

_URL_ENV = "DATABASE_URL"


def url() -> str | None:
    return os.environ.get(_URL_ENV) or None


def disponivel() -> bool:
    if not url():
        return False
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return False
    return True


@contextmanager
def conexao():
    """Conexão com autocommit desligado — cada operação decide quando confirmar."""
    import psycopg

    endereco = url()
    if not endereco:
        raise RuntimeError(
            f"{_URL_ENV} não definida. Configure-a ou use os comandos de arquivo da CLI."
        )
    # Prisma usa `?schema=public`, que o libpq não entende como parâmetro de conexão.
    endereco = endereco.split("?")[0]
    with psycopg.connect(endereco) as conn:
        yield conn


def testar() -> tuple[bool, str]:
    """`(ok, detalhe)` — usado pela rota de saúde."""
    if not url():
        return False, f"{_URL_ENV} não configurada"
    try:
        with conexao() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True, "conectado"
    except Exception as erro:  # noqa: BLE001 — a rota de saúde reporta qualquer falha
        return False, str(erro)[:200]


# ---------------------------------------------------------------------------
# Candles
# ---------------------------------------------------------------------------


def gravar_candles(serie: Serie) -> int:
    """Upsert idempotente por `(ativo, timeframe, ts)`.

    Idempotência importa muito aqui: o coletor relê as últimas N barras a cada ciclo, e o
    último candle muda de valor enquanto está em formação. Sem o `DO UPDATE`, ou
    duplicaria, ou congelaria o candle atual no primeiro valor lido.
    """
    if not serie.candles:
        return 0

    linhas = [
        (
            serie.ativo,
            serie.timeframe.name,
            c.ts,
            c.abertura,
            c.maxima,
            c.minima,
            c.fechamento,
            c.volume,
        )
        for c in serie.candles
    ]

    with conexao() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO candles
                (ativo, timeframe, ts, abertura, maxima, minima, fechamento, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ativo, timeframe, ts) DO UPDATE SET
                abertura   = EXCLUDED.abertura,
                maxima     = EXCLUDED.maxima,
                minima     = EXCLUDED.minima,
                fechamento = EXCLUDED.fechamento,
                volume     = EXCLUDED.volume
            """,
            linhas,
        )
        conn.commit()
    return len(linhas)


def ler_candles(ativo: str, timeframe: Timeframe, limite: int = 5000) -> Serie:
    """Os `limite` candles mais recentes, em ordem cronológica."""
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ts, abertura, maxima, minima, fechamento, volume
            FROM candles
            WHERE ativo = %s AND timeframe = %s
            ORDER BY ts DESC
            LIMIT %s
            """,
            (ativo, timeframe.name, limite),
        )
        linhas = cur.fetchall()

    candles = [
        Candle(
            ts=linha[0],
            abertura=float(linha[1]),
            maxima=float(linha[2]),
            minima=float(linha[3]),
            fechamento=float(linha[4]),
            volume=float(linha[5]),
        )
        for linha in reversed(linhas)
    ]
    return Serie(ativo, timeframe, candles)


def resumo_candles() -> list[dict[str, Any]]:
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ativo, timeframe, COUNT(*), MIN(ts), MAX(ts)
            FROM candles GROUP BY ativo, timeframe ORDER BY ativo, timeframe
            """
        )
        return [
            {
                "ativo": linha[0],
                "timeframe": linha[1],
                "total": linha[2],
                "primeiro": linha[3].isoformat() if linha[3] else None,
                "ultimo": linha[4].isoformat() if linha[4] else None,
            }
            for linha in cur.fetchall()
        ]


# ---------------------------------------------------------------------------
# Sinais e detecções
# ---------------------------------------------------------------------------


def gravar_sinais(
    sinais: list[Any], vies: str | None = None, teses: dict[int, Any] | None = None
) -> int:
    """Persiste sinais do motor. Devolve quantos foram **novos**.

    `ON CONFLICT DO NOTHING` pela chave `(ativo, timeframe, ts, padraoId)`: reprocessar o
    mesmo candle — restart do coletor, análise manual repetida — não pode gerar sinal
    duplicado nem sobrescrever o status de um sinal que já está sendo acompanhado.
    """
    if not sinais:
        return 0

    teses = teses or {}
    linhas = []
    for s in sinais:
        fatores = [
            {"nome": f.nome, "multiplicador": f.multiplicador, "detalhe": f.detalhe}
            for f in s.avaliacao.fatores
        ]
        tese = teses.get(s.indice)
        linhas.append(
            (
                str(uuid.uuid4()),
                s.ativo,
                s.timeframe.name,
                s.ts,
                s.direcao.value.upper(),
                s.padrao_id,
                s.padrao_nome,
                s.entrada,
                s.stop,
                s.alvo,
                s.origem_alvo,
                s.risco_pontos,
                s.retorno_pontos,
                s.rr,
                s.contratos,
                s.score,
                s.confiabilidade,
                json.dumps(fatores, ensure_ascii=False),
                list(s.observacoes),
                s.avaliacao.zona_quente,
                vies,
                json.dumps(tese.para_dict(), ensure_ascii=False) if tese else None,
            )
        )

    with conexao() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO sinais (
                id, ativo, timeframe, ts, direcao, "padraoId", "padraoNome",
                entrada, stop, alvo, "origemAlvo", "riscoPontos", "retornoPontos", rr,
                contratos, score, confiabilidade, fatores, observacoes, "zonaQuente",
                "viesMtf", tese, status
            ) VALUES (
                %s, %s, %s, %s, %s::"Direcao", %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s::jsonb, %s, %s,
                %s, %s::jsonb, 'ABERTO'::"StatusSinal"
            )
            ON CONFLICT (ativo, timeframe, ts, "padraoId") DO NOTHING
            """,
            linhas,
        )
        gravados = cur.rowcount
        conn.commit()
    return max(0, gravados)


def gravar_deteccoes(ativo: str, timeframe: Timeframe, deteccoes: list[Any], serie: Serie) -> int:
    """Detecções para marcar no gráfico — inclui as que não viraram sinal."""
    if not deteccoes:
        return 0

    linhas = [
        (
            str(uuid.uuid4()),
            ativo,
            timeframe.name,
            serie[d.indice_fim].ts,
            d.padrao_id,
            d.nome,
            d.direcao.value,
            d.forca,
            d.score_bruto,
        )
        for d in deteccoes
        if d.indice_fim < len(serie)
    ]

    with conexao() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO deteccoes
                (id, ativo, timeframe, ts, "padraoId", "padraoNome", direcao, forca, "scoreBruto")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ativo, timeframe, ts, "padraoId") DO NOTHING
            """,
            linhas,
        )
        conn.commit()
    return len(linhas)


def atualizar_sinais_abertos(ativo: str, timeframe: Timeframe, serie: Serie) -> dict[str, int]:
    """Acompanha os sinais vivos contra os candles novos.

    É o que fecha o ciclo: sem isto, todo sinal ficaria ABERTO para sempre e a taxa de
    acerto na tela seria zero.

    Aplica a mesma regra conservadora do backtest — **candle que contém stop e alvo conta
    como stop**. Sem tick a tick não há como saber a ordem, e supor o alvo inflaria a
    estatística de toda estratégia de alvo curto.
    """
    if not serie.candles:
        return {}

    with conexao() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, direcao::text, entrada, stop, alvo, status::text, ts
            FROM sinais
            WHERE ativo = %s AND timeframe = %s AND status IN ('ABERTO', 'ACIONADO')
            """,
            (ativo, timeframe.name),
        )
        abertos = cur.fetchall()
        if not abertos:
            return {}

        contagem = {"acionado": 0, "alvo": 0, "stop": 0, "expirado": 0}
        agora = datetime.now()

        for sinal_id, direcao, entrada, stop, alvo, status, ts_sinal in abertos:
            entrada, stop, alvo = float(entrada), float(stop), float(alvo)
            compra = direcao == "ALTA"
            posteriores = [c for c in serie.candles if c.ts > ts_sinal]
            if not posteriores:
                continue

            acionado = status == "ACIONADO"
            novo_status: str | None = None
            preco_saida: float | None = None

            for candle in posteriores:
                if not acionado:
                    tocou = candle.maxima >= entrada if compra else candle.minima <= entrada
                    if tocou:
                        acionado = True
                        contagem["acionado"] += 1
                    else:
                        continue

                bateu_stop = candle.minima <= stop if compra else candle.maxima >= stop
                bateu_alvo = candle.maxima >= alvo if compra else candle.minima <= alvo
                if bateu_stop:
                    novo_status, preco_saida = "STOP", stop
                    break
                if bateu_alvo:
                    novo_status, preco_saida = "ALVO", alvo
                    break

            # Sinal antigo que nunca acionou expira: o contexto que o gerou já passou.
            if novo_status is None and not acionado:
                idade_min = (agora - ts_sinal).total_seconds() / 60
                if idade_min > timeframe.value * 4:
                    novo_status = "EXPIRADO"

            if novo_status:
                resultado = None
                if preco_saida is not None:
                    resultado = (preco_saida - entrada) if compra else (entrada - preco_saida)
                cur.execute(
                    """
                    UPDATE sinais
                    SET status = %s::"StatusSinal", "precoSaida" = %s,
                        "resultadoPontos" = %s, "fechadoEm" = NOW()
                    WHERE id = %s
                    """,
                    (novo_status, preco_saida, resultado, sinal_id),
                )
                contagem[novo_status.lower()] = contagem.get(novo_status.lower(), 0) + 1
            elif acionado and status != "ACIONADO":
                cur.execute(
                    """UPDATE sinais SET status = 'ACIONADO'::"StatusSinal" WHERE id = %s""",
                    (sinal_id,),
                )

        conn.commit()
        return {k: v for k, v in contagem.items() if v}


# ---------------------------------------------------------------------------
# Backtest e calibração
# ---------------------------------------------------------------------------


def gravar_execucao_backtest(
    ativo: str,
    timeframe: Timeframe,
    capital: float,
    modo: str,
    resultado: Any,
    inicio: datetime,
    fim: datetime,
) -> str:
    por_padrao = {
        pid: {
            "nome": e.nome,
            "n": e.n,
            "acertos": e.acertos,
            "taxaAcerto": e.taxa_acerto,
            "expectanciaR": e.expectancia_r,
            "resultadoReais": e.resultado_reais,
        }
        for pid, e in resultado.por_padrao.items()
    }
    por_janela = {
        janela: {
            "n": e.n,
            "taxaAcerto": e.taxa_acerto,
            "expectanciaR": e.expectancia_r,
            "resultadoReais": e.resultado_reais,
        }
        for janela, e in resultado.por_janela.items()
    }

    execucao_id = str(uuid.uuid4())
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO execucoes_backtest (
                id, ativo, timeframe, inicio, fim, capital, modo,
                "sinaisGerados", acionados, "taxaAcerto", "expectanciaR",
                "resultadoReais", "rebaixamentoMax", "porPadrao", "porJanela"
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)
            """,
            (
                execucao_id,
                ativo,
                timeframe.name,
                inicio,
                fim,
                capital,
                modo,
                len(resultado.operacoes),
                len(resultado.acionadas),
                resultado.taxa_acerto,
                resultado.expectancia_r,
                resultado.resultado_reais,
                resultado.rebaixamento_maximo,
                json.dumps(por_padrao, ensure_ascii=False),
                json.dumps(por_janela, ensure_ascii=False),
            ),
        )
        conn.commit()
    return execucao_id


def gravar_calibracoes(ativo: str, timeframe: Timeframe, resultado: Any, minimo: int) -> int:
    """Escreve a confiabilidade **medida** por padrão.

    Grava também os insuficientes, com `suficiente = false`: a tela precisa poder mostrar
    "3 ocorrências, sem evidência" em vez de simplesmente omitir o padrão.
    """
    linhas = [
        (
            pid,
            ativo,
            timeframe.name,
            e.taxa_acerto,
            e.expectancia_r,
            e.n,
            e.n >= minimo,
        )
        for pid, e in resultado.por_padrao.items()
    ]
    if not linhas:
        return 0

    with conexao() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO calibracoes_padrao
                ("padraoId", ativo, timeframe, "taxaAcerto", "expectanciaR",
                 ocorrencias, suficiente, "atualizadoEm")
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT ("padraoId", ativo, timeframe) DO UPDATE SET
                "taxaAcerto"   = EXCLUDED."taxaAcerto",
                "expectanciaR" = EXCLUDED."expectanciaR",
                ocorrencias    = EXCLUDED.ocorrencias,
                suficiente     = EXCLUDED.suficiente,
                "atualizadoEm" = NOW()
            """,
            linhas,
        )
        conn.commit()
    return len(linhas)


def carregar_calibracao(ativo: str, timeframe: Timeframe) -> dict[str, tuple[float, int]]:
    """Alimenta `padroes.CALIBRACAO` no boot do serviço.

    É o que faz o motor usar evidência em vez do prior do ebook assim que existir
    histórico medido.
    """
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT "padraoId", "taxaAcerto", ocorrencias
            FROM calibracoes_padrao
            WHERE ativo = %s AND timeframe = %s AND suficiente = true
            """,
            (ativo, timeframe.name),
        )
        return {linha[0]: (float(linha[1]), int(linha[2])) for linha in cur.fetchall()}
