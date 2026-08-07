"""Catálogo de padrões de candlestick.

Importar este pacote é o que popula `CATALOGO`: os três módulos abaixo registram seus
detectores via decorator no momento do import. Por isso eles são importados aqui mesmo
sem uso aparente — remover essas linhas esvazia o catálogo silenciosamente.
"""

from . import continuacao, isolados, reversao  # noqa: F401 — efeito colateral: registram
from .base import (
    CALIBRACAO,
    CATALOGO,
    PRIOR_ALTA,
    PRIOR_BAIXA,
    PRIOR_INDECISAO,
    PRIOR_NEUTRO,
    EspecPadrao,
    catalogo_ordenado,
    confiabilidade_de,
    detectar_em,
    padrao,
    varrer,
)

__all__ = [
    "CALIBRACAO",
    "CATALOGO",
    "PRIOR_ALTA",
    "PRIOR_BAIXA",
    "PRIOR_INDECISAO",
    "PRIOR_NEUTRO",
    "EspecPadrao",
    "catalogo_ordenado",
    "confiabilidade_de",
    "detectar_em",
    "padrao",
    "varrer",
]
