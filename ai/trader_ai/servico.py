"""Serviço HTTP do motor (FastAPI, porta 1841).

Quem consome é o backend Node — o frontend nunca fala com este serviço diretamente.
Sem autenticação de propósito: ele escuta em localhost e não expõe nada além do que o
backend já expõe autenticado. Se um dia sair da máquina, precisa de auth antes.

    cd ai
    pip install -e ".[servico]"
    python -m trader_ai.servico
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Literal

from . import __version__, padroes, persistencia
from . import backtest as bt
from .limiares import PADRAO
from .pipeline import analisar, deteccao_para_dict, sinal_para_dict
from .tipos import Timeframe

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except ImportError as erro:  # pragma: no cover
    raise SystemExit(
        'FastAPI não instalado. Rode: pip install -e ".[servico]"'
    ) from erro


app = FastAPI(
    title="cronos-trader — motor",
    version=__version__,
    description="Detecção de padrões, confluência e decisão para WIN e WDO. Só sinal.",
)

ATIVOS = ("WIN", "WDO")


class PedidoAnalise(BaseModel):
    ativo: Literal["WIN", "WDO"]
    timeframe: Literal["M5", "M15", "M30", "H1", "D1"] = "M5"
    capital: float = Field(default=10_000.0, gt=0)
    persistir: bool = True
    ultimos: int = Field(default=200, ge=1, le=5000)
    """Quantos candles recentes reavaliar. O histórico anterior ainda é lido — é dele que
    saem ATR, tendência e pivôs."""


class PedidoBacktest(BaseModel):
    ativo: Literal["WIN", "WDO"]
    timeframe: Literal["M5", "M15", "M30", "H1", "D1"] = "M5"
    capital: float = Field(default=20_000.0, gt=0)
    modo: Literal["backtest", "walkforward"] = "walkforward"
    janelas: int = Field(default=4, ge=2, le=12)
    limite_candles: int = Field(default=20_000, ge=500, le=200_000)


def _em_container() -> bool:
    return os.environ.get("EM_CONTAINER") == "1" or os.path.exists("/.dockerenv")


def _mt5_estado() -> dict:
    """Estado do MT5 sem derrubar o serviço se ele não estiver lá.

    Dentro de container o MT5 **nunca** vai estar disponível: o pacote é Windows-only e
    conversa com o terminal por IPC. Reportar "pacote não instalado" ali seria correto e
    inútil — parece defeito quando é arquitetura. Por isso o caso é distinguido, e quem
    responde pela chegada de dados passa a ser a frescura dos candles.
    """
    if _em_container():
        return {
            "disponivel": False,
            "emContainer": True,
            "detalhe": "coletor roda no host (MT5 é Windows-only) — veja a idade dos candles",
        }

    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError:
        return {"disponivel": False, "detalhe": "pacote MetaTrader5 não instalado"}
    try:
        if not mt5.initialize():
            return {"disponivel": False, "detalhe": f"terminal indisponível: {mt5.last_error()}"}
        conta = mt5.account_info()
        mt5.shutdown()
        if conta is None:
            return {"disponivel": False, "detalhe": "terminal aberto, sem conta logada"}
        return {"disponivel": True, "detalhe": f"{conta.company} · conta {conta.login}"}
    except Exception as erro:  # noqa: BLE001
        return {"disponivel": False, "detalhe": str(erro)[:200]}


@app.get("/saude")
def saude() -> dict:
    banco_ok, banco_detalhe = persistencia.testar() if persistencia.disponivel() else (
        False,
        "DATABASE_URL não configurada",
    )
    return {
        "ok": True,
        "versao": __version__,
        "padroes": len(padroes.CATALOGO),
        "banco": banco_ok,
        "bancoDetalhe": banco_detalhe,
        "mt5": _mt5_estado(),
        "candles": persistencia.resumo_candles() if banco_ok else [],
    }


@app.get("/catalogo")
def catalogo() -> dict:
    especificacoes = padroes.catalogo_ordenado()
    return {
        "total": len(especificacoes),
        "padroes": [
            {
                "id": s.id,
                "nome": s.nome,
                "familia": s.familia.value,
                "direcao": s.direcao.value,
                "n_candles": s.n_candles,
                "tendencia_requerida": (
                    s.tendencia_requerida.value if s.tendencia_requerida else None
                ),
                "confiabilidade_ebook": s.confiabilidade_ebook,
                # `foi_medida` é o que separa evidência de palpite. Sem ele a tela
                # escreveu "confiabilidade do padrão em WDO: 70%" para a Nuvem Negra,
                # que nunca foi medida em WDO uma única vez — o 70% era do ebook.
                "medido": padroes.foi_medida(s),
                "confiabilidade_medida": padroes.CALIBRACAO.get(s.id, (None, 0, 0.0))[0],
                "ocorrencias_medidas": padroes.CALIBRACAO.get(s.id, (None, 0, 0.0))[1],
                "expectancia_medida": padroes.expectancia_medida(s),
                "pagina_ebook": s.pagina_ebook,
                "exige_gap": s.exige_gap,
                "derivado_por_simetria": s.derivado_por_simetria,
                "observacao": s.observacao,
            }
            for s in especificacoes
        ],
    }


class PedidoDiario(BaseModel):
    ativo: Literal["WIN", "WDO"]
    periodo: Literal["dia", "semana", "mes"] = "dia"


@app.post("/diario")
def rota_diario(pedido: PedidoDiario) -> dict:
    """Fechamento do período e os níveis que o próximo pregão começa olhando.

    Sai tudo do banco — candles e sinais que de fato aconteceram. Onde não há dado, o
    relatório diz que não há em vez de preencher com frase de efeito.
    """
    from . import diario as dia_mod

    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    serie = persistencia.ler_candles(pedido.ativo, Timeframe.M5, limite=20_000)
    if not len(serie):
        raise HTTPException(422, f"sem candles de {pedido.ativo} no banco")

    agora = datetime.now()
    inicio, fim = dia_mod._janela(pedido.periodo, agora)
    sinais = persistencia.ler_sinais_periodo(pedido.ativo, inicio, fim)

    fechamento = dia_mod.montar(serie, sinais, pedido.periodo, agora)
    return {
        **dia_mod.para_dict(fechamento),
        "proximoPregao": dia_mod.proximo_pregao().isoformat(),
    }


class PedidoNarrativa(BaseModel):
    ativo: Literal["WIN", "WDO"]
    capital: float = Field(default=20_000.0, gt=0)
    modelo: str = "principal"


@app.post("/narrativa")
def rota_narrativa(pedido: PedidoNarrativa) -> dict:
    """A leitura da IA sobre o dossiê que o motor já produziu.

    **Degrada em silêncio, de propósito.** Devolve `disponivel: false` com o motivo em vez
    de erro HTTP: a narrativa é acréscimo sobre uma tela que funciona inteira sem ela, e
    derrubar a Sala porque a OpenRouter oscilou seria trocar um enfeite por um defeito.
    """
    from . import agentes
    from . import raciocinio as rac

    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    series = {}
    for tf in rac.TIMEFRAMES_PAINEL:
        serie = persistencia.ler_candles(pedido.ativo, tf, limite=1500)
        if len(serie) >= PADRAO.tendencia_min_candles:
            series[tf] = serie

    if Timeframe.M5 not in series:
        raise HTTPException(422, f"histórico de 5 minutos insuficiente para {pedido.ativo}")

    dados = rac.para_dict(rac.ler(series, pedido.capital))

    try:
        narrativa = agentes.narrar(dados, modelo=pedido.modelo)
    except agentes.IAIndisponivel as erro:
        return {"disponivel": False, "motivo": str(erro)[:300], "ativo": pedido.ativo}

    return {"disponivel": True, "ativo": pedido.ativo, **narrativa.para_dict()}


class PedidoPregao(BaseModel):
    ativo: Literal["WIN", "WDO"]
    dia: str | None = None
    """`AAAA-MM-DD`. Ausente = hoje."""


@app.post("/pregao")
def rota_pregao(pedido: PedidoPregao) -> dict:
    """O extrato do dia: cada entrada, na ordem, com o que aconteceu depois dela.

    É a resposta para "cheguei tarde, o que eu perdi?". Diferente de `/diario`, que agrega
    o período, aqui os trades aparecem um a um — o operador precisa ver a sequência para
    aprender o critério, não só o placar.
    """
    from . import pregao as pregao_mod

    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    try:
        dia = (
            datetime.strptime(pedido.dia, "%Y-%m-%d").date()
            if pedido.dia
            else datetime.now().date()
        )
    except ValueError as erro:
        raise HTTPException(422, f"data inválida: {pedido.dia!r}, use AAAA-MM-DD") from erro

    inicio = datetime.combine(dia, datetime.min.time())
    fim = datetime.combine(dia, datetime.max.time())
    sinais = persistencia.ler_sinais_periodo(pedido.ativo, inicio, fim)

    return pregao_mod.para_dict(pregao_mod.montar(pedido.ativo, sinais, dia))


class PedidoRaciocinio(BaseModel):
    ativo: Literal["WIN", "WDO"]
    capital: float = Field(default=20_000.0, gt=0)


@app.post("/raciocinio")
def rota_raciocinio(pedido: PedidoRaciocinio) -> dict:
    """O que o motor está pensando agora, com a conta aberta.

    Alimenta a Sala de Operações. Diferente de `/analisar`, não persiste nada e não
    decide nada — é leitura do estado atual das seis camadas, incluindo **os padrões que
    foram recusados e por quê**, que é o que a tela ao vivo existe para mostrar.
    """
    from . import raciocinio as rac

    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    series = {}
    for tf in rac.TIMEFRAMES_PAINEL:
        serie = persistencia.ler_candles(pedido.ativo, tf, limite=1500)
        if len(serie) >= PADRAO.tendencia_min_candles:
            series[tf] = serie

    if Timeframe.M5 not in series:
        raise HTTPException(
            422,
            f"histórico de 5 minutos insuficiente para {pedido.ativo}. "
            "Rode o coletor ou importe um CSV.",
        )

    return rac.para_dict(rac.ler(series, pedido.capital))


class PedidoEstrutura(BaseModel):
    ativo: Literal["WIN", "WDO"]
    timeframe: Literal["M5", "M15", "M30", "H1", "D1"] = "M5"
    candles: int = Field(default=600, ge=100, le=2000)


@app.post("/estrutura")
def rota_estrutura(pedido: PedidoEstrutura) -> dict:
    """O desenho do gráfico: canal, pivôs, rompimentos, zonas e linha de tendência.

    É o que transforma o gráfico de uma sequência de candles numa leitura — a mesma
    anotação que um analista faz à mão antes de decidir.
    """
    from . import estrutura as est

    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    tf = Timeframe[pedido.timeframe]
    serie = persistencia.ler_candles(pedido.ativo, tf, limite=pedido.candles)
    if len(serie) < PADRAO.tendencia_min_candles:
        raise HTTPException(422, f"histórico insuficiente: {len(serie)} candles")

    i = len(serie) - 1
    return {
        "ativo": pedido.ativo,
        "timeframe": pedido.timeframe,
        "candles": len(serie),
        **est.para_dict(est.ler(serie, i), serie),
    }


@app.get("/estudos")
def estudos() -> dict:
    """As medições que sustentam as decisões do motor.

    Existe para que a tela possa mostrar **por que** o motor pesa o que pesa, em vez de
    pedir confiança. Um usuário que vê "Fibonacci não vale nada no WIN" com o número ao
    lado entende o produto; um que só vê o score, não.
    """
    from . import fibonacci as fib
    from . import medias as medias_mod
    from .contexto import JANELAS_B3

    return {
        "fibonacci": {
            "metodo": (
                "Teste do pico: em bins de 2% de retração, a taxa de virada no bin do "
                "nível é comparada com a dos vizinhos imediatos. Um nível que o mercado "
                "enxerga produz pico local; um número sem significado produz curva lisa."
            ),
            "amostra": "60.000 candles M5 por ativo (jun/2024–ago/2026), ~2.400 correções",
            "corte": fib.RAZAO_MINIMA_PICO,
            "porAtivo": [
                {
                    "ativo": ativo,
                    "usaFibonacci": bool(niveis),
                    "niveis": [
                        {"nivel": n, "razao": r, "relevancia": fib.relevancia(ativo, n)}
                        for n, r in sorted(niveis.items())
                    ],
                }
                for ativo, niveis in fib.NIVEIS_RESPEITADOS.items()
            ],
            "conclusao": (
                "O WDO respeita 50% (1,34× os vizinhos) — único nível com pico real. "
                "38,2% e 61,8%, os mais citados na literatura, não se destacam em nenhum "
                "dos dois ativos. A faixa dos 30% é o oposto de suporte: é onde o preço "
                "menos para (0,79× no WDO, 0,74× no WIN)."
            ),
        },
        "medias": {
            "conjunto": [
                {"nome": "EMA 9", "periodo": medias_mod.PERIODO_CONDUCAO,
                 "papel": "condução do trade e stop móvel — rápida demais para filtrar"},
                {"nome": "SMA 21", "periodo": medias_mod.PERIODO_VIES,
                 "papel": "viés direcional do dia; funciona como suporte/resistência"},
                {"nome": "SMA 200", "periodo": medias_mod.PERIODO_GLOBAL,
                 "papel": "a mais observada do mundo; perdê-la ou superá-la é gatilho"},
                {"nome": "RMA 400 (Wilder)", "periodo": medias_mod.PERIODO_REGIME,
                 "papel": "regime de fundo; a inércia equivale a uma EMA de 799 períodos"},
            ],
            "comoEntra": (
                "Não é o valor das médias que pontua: é o alinhamento entre elas. Quatro "
                "médias empilhadas na ordem descrevem um mercado com estrutura; embaraçadas "
                "descrevem um sem direção, onde padrão de reversão é ruído."
            ),
        },
        "janelas": [
            {
                "rotulo": j.rotulo,
                "inicio": j.inicio.strftime("%H:%M"),
                "fim": j.fim.strftime("%H:%M"),
                "peso": j.peso,
                "opera": j.opera,
            }
            for j in JANELAS_B3
        ],
        "avisoJanelas": (
            "Os pesos das janelas são priors, e a medição em WIN já os contradiz: a janela "
            "10h–12h, que recebeu o peso mais alto, é a de pior expectância medida. "
            "Recalibrar exige validação fora da amostra — não está feito."
        ),
    }


@app.post("/analisar")
def rota_analisar(pedido: PedidoAnalise) -> dict:
    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    tf = Timeframe[pedido.timeframe]

    # Calibração medida antes de analisar: sem isto o motor usaria o prior do ebook
    # mesmo existindo evidência no banco.
    padroes.CALIBRACAO.update(persistencia.carregar_calibracao(pedido.ativo, tf))

    serie = persistencia.ler_candles(pedido.ativo, tf, limite=5000)
    if len(serie) < PADRAO.tendencia_min_candles:
        raise HTTPException(
            422,
            f"histórico insuficiente: {len(serie)} candles de {pedido.ativo} {tf.rotulo}. "
            "Rode o coletor (python -m trader_ai.coletor) ou importe um CSV.",
        )

    analise = analisar(serie, capital=pedido.capital, ultimos=pedido.ultimos)

    gravados = 0
    if pedido.persistir:
        vies = analise.vies.descrever() if analise.vies else None
        gravados = persistencia.gravar_sinais(analise.sinais, vies, analise.teses)
        persistencia.gravar_deteccoes(pedido.ativo, tf, analise.deteccoes, serie)
        persistencia.atualizar_sinais_abertos(pedido.ativo, tf, serie)

    return {
        "ativo": pedido.ativo,
        "timeframe": pedido.timeframe,
        "candles": len(serie),
        "resumo": analise.resumo,
        "sinaisNovos": gravados,
        "sinais": [sinal_para_dict(s, analise.tese_de(s)) for s in analise.sinais],
        "deteccoes": [deteccao_para_dict(d, serie) for d in analise.deteccoes[-200:]],
        "contexto": (
            {
                "tendencia": analise.contexto.tendencia.value,
                "forcaTendencia": round(analise.contexto.forca_tendencia, 3),
                "atr": round(analise.contexto.atr, 2),
                "regimeVolatilidade": round(analise.contexto.regime_volatilidade, 3),
                "janelaPregao": analise.contexto.janela_pregao,
                "pesoHorario": analise.contexto.peso_horario,
            }
            if analise.contexto
            else None
        ),
        "vies": analise.vies.descrever() if analise.vies else None,
    }


@app.post("/backtest")
def rota_backtest(pedido: PedidoBacktest) -> dict:
    if not persistencia.disponivel():
        raise HTTPException(503, "DATABASE_URL não configurada no serviço de IA")

    tf = Timeframe[pedido.timeframe]
    serie = persistencia.ler_candles(pedido.ativo, tf, limite=pedido.limite_candles)
    if len(serie) < PADRAO.tendencia_min_candles * 4:
        raise HTTPException(422, f"histórico insuficiente: {len(serie)} candles")

    inicio, fim = serie[0].ts, serie[-1].ts

    if pedido.modo == "walkforward":
        try:
            janelas = bt.walk_forward(serie, janelas=pedido.janelas, capital=pedido.capital)
        except ValueError as erro:
            raise HTTPException(422, str(erro)) from erro

        media = sum(j.teste.expectancia_r for j in janelas) / len(janelas)
        ultimo = janelas[-1].teste
        execucao_id = persistencia.gravar_execucao_backtest(
            pedido.ativo, tf, pedido.capital, "walkforward", ultimo, inicio, fim
        )
        persistencia.gravar_calibracoes(
            pedido.ativo, tf, ultimo, PADRAO.amostra_minima_confiabilidade
        )
        return {
            "id": execucao_id,
            "modo": "walkforward",
            "expectanciaMediaForaDaAmostra": round(media, 3),
            "temEdge": media > 0,
            "janelas": [
                {
                    "indice": j.indice,
                    "treinoExpectanciaR": round(j.treino.expectancia_r, 3),
                    "testeExpectanciaR": round(j.teste.expectancia_r, 3),
                    "testeTaxaAcerto": round(j.teste.taxa_acerto, 4),
                    "testeResultadoReais": round(j.teste.resultado_reais, 2),
                    "padroesCalibrados": len(j.calibrado),
                }
                for j in janelas
            ],
            "relatorio": ultimo.relatorio(),
        }

    resultado = bt.rodar(serie, capital=pedido.capital)
    execucao_id = persistencia.gravar_execucao_backtest(
        pedido.ativo, tf, pedido.capital, "backtest", resultado, inicio, fim
    )
    return {
        "id": execucao_id,
        "modo": "backtest",
        "sinaisGerados": len(resultado.operacoes),
        "acionados": len(resultado.acionadas),
        "taxaAcerto": round(resultado.taxa_acerto, 4),
        "expectanciaR": round(resultado.expectancia_r, 3),
        "resultadoReais": round(resultado.resultado_reais, 2),
        "rebaixamentoMax": round(resultado.rebaixamento_maximo, 2),
        "aviso": (
            "Backtest calibra e mede na mesma série — isso é memorização, não evidência. "
            "Use modo 'walkforward' para um número em que dá para confiar."
        ),
        "relatorio": resultado.relatorio(),
    }


def main() -> None:
    import uvicorn

    porta = int(os.environ.get("PORTA_IA", "1841"))
    print(f"motor cronos-trader em http://localhost:{porta}  ({len(padroes.CATALOGO)} padrões)")
    if not persistencia.disponivel():
        print("AVISO: DATABASE_URL não configurada — /analisar e /backtest vão recusar.")
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="info")


if __name__ == "__main__":
    main()
