"""O pregão de um dia, trade a trade, com o dinheiro já convertido.

Responde a pergunta que o operador faz ao sentar depois do meio-dia: **"o que eu perdi
enquanto não estava olhando?"**

Diferente de `diario.py`, que agrega o período em placar e destaques, aqui cada entrada
aparece individualmente, na ordem em que nasceu, com o que aconteceu depois dela. É o
extrato, não o resumo.

## Isto não é backtest, e não é promessa

Os sinais vêm do banco — foram emitidos pelo motor sobre os candles que de fato existiam
no instante de cada emissão. A pipeline é testada contra look-ahead
(`test_pipeline_inteira_nao_olha_para_o_futuro`), então o sinal das 10:05 usou só dados até
as 10:05, tenha ele sido gravado ao vivo ou por um replay depois do pregão.

O que **não** dá para afirmar é que o operador teria capturado exatamente estes números.
Entre o sinal e a ordem existem deslize, liquidez no preço da entrada e a decisão humana de
apertar o botão. Por isso `resultado_liquido` desconta custo por contrato, e por isso o
campo `observacao` diz de onde veio cada número.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time

from .instrumentos import resolver

# Um sinal que nasceu mas nunca foi acionado não é trade: o preço não chegou na entrada.
# Ele conta para "o motor viu", não para "o dinheiro fez".
STATUS_ACIONADOS = ("ACIONADO", "ALVO", "STOP")
STATUS_ENCERRADOS = ("ALVO", "STOP")


@dataclass(frozen=True, slots=True)
class Entrada:
    """Uma entrada do dia, do ponto de vista de quem operaria."""

    id: str
    ativo: str
    hora: str
    ts: datetime
    direcao: str
    padrao: str
    janela: str

    entrada: float
    stop: float
    alvo: float
    rr: float
    contratos: int
    risco_pontos: float

    score: float
    confiabilidade: float

    status: str
    resultado_pontos: float | None
    resultado_reais: float | None
    resultado_r: float | None

    observacao: str

    @property
    def acionada(self) -> bool:
        return self.status in STATUS_ACIONADOS

    @property
    def encerrada(self) -> bool:
        return self.status in STATUS_ENCERRADOS


@dataclass(frozen=True, slots=True)
class Pregao:
    dia: str
    ativo: str
    aberto: bool
    entradas: list[Entrada] = field(default_factory=list)

    emitidos: int = 0
    acionados: int = 0
    alvo: int = 0
    stop: int = 0
    abertos: int = 0
    expirados: int = 0

    resultado_reais: float = 0.0
    resultado_r: float = 0.0
    custo_total: float = 0.0

    @property
    def encerrados(self) -> int:
        return self.alvo + self.stop

    @property
    def taxa_acerto(self) -> float:
        return self.alvo / self.encerrados if self.encerrados else 0.0

    @property
    def expectancia_r(self) -> float:
        return self.resultado_r / self.encerrados if self.encerrados else 0.0


def _hora_legivel(ts: datetime) -> str:
    return ts.strftime("%H:%M")


def _observacao(status: str, resultado_pontos: float | None) -> str:
    """Uma frase que impede o número de ser lido como promessa."""
    if status == "ALVO":
        return "alvo atingido — resultado bruto menos custo por contrato, sem deslize"
    if status == "STOP":
        return "stop atingido — o preço passou pelo stop antes do alvo"
    if status == "ACIONADO":
        return "entrada acionada, ainda em curso — resultado só existe no encerramento"
    if status == "EXPIRADO":
        return "o preço nunca chegou na entrada: não virou trade"
    if status == "ABERTO":
        return "aguardando o preço chegar na entrada"
    return status.lower()


def montar(
    ativo: str,
    sinais: list[dict],
    dia: date,
    agora: datetime | None = None,
) -> Pregao:
    """Transforma os sinais crus do banco no extrato do dia.

    `sinais` vem de `persistencia.ler_sinais_periodo`, que já traz `janelaPregao`.
    """
    inst = resolver(ativo)
    agora = agora or datetime.now()

    entradas: list[Entrada] = []
    resultado_reais = 0.0
    resultado_r = 0.0
    custo_total = 0.0
    contagem = {"ALVO": 0, "STOP": 0, "EXPIRADO": 0, "ABERTO": 0, "ACIONADO": 0}

    # Ordem cronológica: o extrato conta a história do dia na ordem em que ela aconteceu.
    # `ler_sinais_periodo` devolve do mais novo para o mais velho, que serve ao histórico
    # mas atrapalha quem quer entender a sequência.
    for s in sorted(sinais, key=lambda x: x["ts"]):
        status = str(s["status"])
        contagem[status] = contagem.get(status, 0) + 1

        contratos = int(s["contratos"] or 0)
        risco = float(s["riscoPontos"] or 0)
        pontos = s["resultadoPontos"]
        pontos = float(pontos) if pontos is not None else None

        reais = None
        r = None
        if pontos is not None and status in STATUS_ENCERRADOS:
            custo = inst.custo_total(contratos)
            reais = inst.reais(pontos, contratos) - custo
            r = (pontos / risco) if risco > 0 else 0.0
            resultado_reais += reais
            resultado_r += r
            custo_total += custo

        entradas.append(
            Entrada(
                id=str(s["id"]),
                ativo=ativo,
                hora=_hora_legivel(s["ts"]),
                ts=s["ts"],
                direcao=str(s["direcao"]),
                padrao=str(s["padraoNome"]),
                janela=str(s.get("janelaPregao") or ""),
                entrada=float(s["entrada"]),
                stop=float(s["stop"]),
                alvo=float(s["alvo"]),
                rr=float(s["rr"]),
                contratos=contratos,
                risco_pontos=risco,
                score=float(s["score"]),
                confiabilidade=float(s["confiabilidade"]),
                status=status,
                resultado_pontos=pontos,
                resultado_reais=reais,
                resultado_r=r,
                observacao=_observacao(status, pontos),
            )
        )

    acionados = sum(contagem.get(s, 0) for s in STATUS_ACIONADOS)

    return Pregao(
        dia=dia.strftime("%d/%m/%Y"),
        ativo=ativo,
        aberto=_pregao_aberto(agora, dia),
        entradas=entradas,
        emitidos=len(entradas),
        acionados=acionados,
        alvo=contagem.get("ALVO", 0),
        stop=contagem.get("STOP", 0),
        abertos=contagem.get("ABERTO", 0) + contagem.get("ACIONADO", 0),
        expirados=contagem.get("EXPIRADO", 0),
        resultado_reais=resultado_reais,
        resultado_r=resultado_r,
        custo_total=custo_total,
    )


def _pregao_aberto(agora: datetime, dia: date) -> bool:
    """Se o dia consultado ainda está em curso.

    Importa para a tela: um placar de dia fechado é resultado; o de dia aberto é parcial, e
    apresentá-lo sem essa distinção convida a concluir cedo demais.
    """
    if agora.date() != dia:
        return False
    if agora.weekday() >= 5:
        return False
    return time(9, 0) <= agora.time() < time(18, 0)


def para_dict(pregao: Pregao) -> dict:
    return {
        "dia": pregao.dia,
        "ativo": pregao.ativo,
        "aberto": pregao.aberto,
        "placar": {
            "emitidos": pregao.emitidos,
            "acionados": pregao.acionados,
            "alvo": pregao.alvo,
            "stop": pregao.stop,
            "abertos": pregao.abertos,
            "expirados": pregao.expirados,
            "encerrados": pregao.encerrados,
            "taxaAcerto": round(pregao.taxa_acerto, 4),
            "expectanciaR": round(pregao.expectancia_r, 3),
            "resultadoReais": round(pregao.resultado_reais, 2),
            "resultadoR": round(pregao.resultado_r, 3),
            "custoTotal": round(pregao.custo_total, 2),
        },
        "entradas": [
            {
                "id": e.id,
                "ativo": e.ativo,
                "hora": e.hora,
                "ts": e.ts.isoformat(),
                "direcao": e.direcao,
                "padrao": e.padrao,
                "janela": e.janela,
                "entrada": e.entrada,
                "stop": e.stop,
                "alvo": e.alvo,
                "rr": round(e.rr, 2),
                "contratos": e.contratos,
                "riscoPontos": e.risco_pontos,
                "score": round(e.score, 3),
                "confiabilidade": round(e.confiabilidade, 3),
                "status": e.status,
                "resultadoPontos": e.resultado_pontos,
                "resultadoReais": (
                    round(e.resultado_reais, 2) if e.resultado_reais is not None else None
                ),
                "resultadoR": round(e.resultado_r, 3) if e.resultado_r is not None else None,
                "acionada": e.acionada,
                "encerrada": e.encerrada,
                "observacao": e.observacao,
            }
            for e in pregao.entradas
        ],
    }
