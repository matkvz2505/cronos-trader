"""Especificação dos dois contratos do escopo: WIN e WDO.

Sem isto não existe dimensionamento de posição — "arriscar 1% do capital" só vira número
de contratos quando se sabe quanto vale um ponto. E é aqui que mora a diferença mais
traiçoeira entre os dois ativos: **um ponto de WIN vale R$ 0,20 e um ponto de WDO vale
R$ 10,00**, cinquenta vezes mais. Um sizing que ignore isso erra por 50×.

> ⚠️ Valores conferidos contra a especificação padrão da B3, mas contratos mudam.
> Confirme margem e valor do ponto no site da B3 antes de operar dinheiro real —
> especialmente `margem_estimada`, que a corretora ajusta livremente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Instrumento:
    codigo: str
    nome: str
    tick: float
    """Menor variação de preço possível."""

    valor_ponto: float
    """Reais por ponto, por contrato."""

    custo_operacao: float
    """Corretagem + emolumentos por contrato, ida e volta. Estimativa conservadora —
    day trade zero-corretagem ainda paga emolumento da B3."""

    slippage_ticks: float
    """Deslize esperado na execução, em ticks. Entra no backtest: uma estratégia de 5
    minutos com 55% de acerto pode perder dinheiro depois do deslize, e é melhor
    descobrir isso na simulação."""

    margem_estimada: float
    """Margem de garantia aproximada por contrato em day trade."""

    @property
    def valor_tick(self) -> float:
        return self.tick * self.valor_ponto

    def arredondar(self, preco: float) -> float:
        """Ajusta um preço para um múltiplo válido do tick.

        Obrigatório em qualquer preço que vire ordem: uma entrada em 130.002,7 no WIN
        não existe, e um stop calculado fora do tick é rejeitado ou arredondado pela
        corretora — para o lado que ela quiser.
        """
        return round(preco / self.tick) * self.tick

    def arredondar_para_baixo(self, preco: float) -> float:
        return math.floor(preco / self.tick) * self.tick

    def arredondar_para_cima(self, preco: float) -> float:
        return math.ceil(preco / self.tick) * self.tick

    def reais(self, pontos: float, contratos: int = 1) -> float:
        return pontos * self.valor_ponto * contratos

    def custo_total(self, contratos: int) -> float:
        """Custo de ida e volta, incluindo o slippage estimado nas duas pontas."""
        deslize = self.slippage_ticks * self.valor_tick * 2
        return (self.custo_operacao + deslize) * contratos


WIN = Instrumento(
    codigo="WIN",
    nome="Mini Índice Bovespa Futuro",
    tick=5.0,
    valor_ponto=0.20,
    custo_operacao=1.50,
    slippage_ticks=1.0,
    margem_estimada=150.0,
)

WDO = Instrumento(
    codigo="WDO",
    nome="Mini Dólar Futuro",
    tick=0.5,
    valor_ponto=10.00,
    custo_operacao=2.00,
    slippage_ticks=1.0,
    margem_estimada=250.0,
)

INSTRUMENTOS = {"WIN": WIN, "WDO": WDO}


def resolver(ativo: str) -> Instrumento:
    """Aceita `WIN`, `WINQ26`, `WIN$N`, `win` — tudo mapeia para o mesmo instrumento.

    O coletor grava o código do contrato vigente, que muda a cada vencimento; o motor só
    precisa saber qual dos dois ativos é.
    """
    chave = ativo.strip().upper()
    for prefixo, instrumento in INSTRUMENTOS.items():
        if chave.startswith(prefixo):
            return instrumento
    raise ValueError(
        f"ativo fora do escopo: {ativo!r}. Este motor cobre apenas WIN e mini-dólar (WDO)."
    )
