# Especificações de WIN e WDO

Fontes: Genial Investimentos (cálculo dos minicontratos) e leitura direta do MT5 da XP
(`symbol_info.trade_tick_size` e `trade_tick_value`). As duas batem.

Implementação em `ai/trader_ai/instrumentos.py`.

## As duas fichas

| | **WIN** — mini-índice | **WDO** — mini-dólar |
|---|---|---|
| Referência | Ibovespa futuro | Dólar futuro |
| Tamanho do contrato | 1 ponto = R$ 0,20 | US$ 10.000 |
| **Valor do ponto** | **R$ 0,20** | **R$ 10,00** |
| Tick mínimo | 5 pontos | 0,5 ponto |
| **Valor do tick** | **R$ 1,00** | **R$ 5,00** |
| Cotação | pontos inteiros | 3 casas decimais |
| Vencimento | meses **pares** (fev, abr, jun, ago, out, dez) | **mensal** |
| Data | quarta-feira mais próxima do dia 15 | primeiro dia útil do mês |

**Fórmulas:**

```
resultado WIN = nº de contratos × diferença de pontos × 0,20
resultado WDO = nº de contratos × diferença de pontos × 10,00
```

## O erro de 50×

**Um ponto de WDO vale cinquenta vezes um ponto de WIN.**

É a armadilha mais cara do produto. A mesma "distância de 100 pontos" custa R$ 20 num e
R$ 1.000 no outro. Um dimensionamento que trate os dois igual erra por ordem de grandeza —
e erra justamente no trade em que a conta não fecha.

Por isso `instrumentos.resolver()` levanta erro em qualquer ativo fora de WIN e WDO, em
vez de assumir um default. Aceitar um ativo desconhecido em silêncio produziria sizing
errado sem nenhum aviso.

## `point` não é `tick`

Confusão que já custou uma correção neste repositório. No MT5:

| Campo | WIN | WDO | O que é |
|---|---|---|---|
| `point` | 1,0 | 0,001 | menor unidade de **cotação** |
| `trade_tick_size` | **5,0** | **0,5** | menor passo de **negociação** |
| `trade_tick_value` | R$ 1,00 | R$ 5,00 | quanto vale esse passo |

O que importa para arredondar entrada, stop e alvo é o `trade_tick_size`. Um stop
calculado fora do tick é rejeitado ou arredondado pela corretora — **para o lado que ela
quiser**.

O `scripts/diagnostico_mt5.py` confere as specs da sua corretora contra as do código e
avisa se divergirem.

## Rollover — corrupção silenciosa de backtest

Contratos vencem. Se a série misturar `WINQ26` e `WINV26` sem tratar a virada, aparece um
salto artificial de centenas de pontos e **todo padrão de gap detectado ali é falso**. Não
gera erro nenhum: só estatística errada com cara de certa.

- **Backtest** → símbolo contínuo ajustado (`WIN$N`, `WDO$N`)
- **Tempo real** → contrato cheio, onde está a liquidez
- **Sempre** → descartar a janela de ±3 dias do vencimento (`em_rollover()`)

## Custos

Estimativas conservadoras em `instrumentos.py`, usadas no backtest:

| | WIN | WDO |
|---|---|---|
| Corretagem + emolumentos (ida e volta) | R$ 1,50 | R$ 2,00 |
| Slippage estimado | 1 tick por ponta | 1 tick por ponta |

Custo total por contrato = corretagem + (slippage × valor do tick × 2 pontas).

Isso entra em **toda** simulação. Uma estratégia de 5 minutos com 55% de acerto pode
perder dinheiro depois dos custos, e é muito melhor descobrir isso no backtest do que no
extrato.

## Horário

Pregão das 9h às 18h (horário de Brasília), com variações por leilão e por horário de
verão americano. O motor trata as janelas do dia como fator de confluência — ver
[04-contexto-win-wdo.md](04-contexto-win-wdo.md).

> Margem de garantia varia por corretora e é ajustada livremente por ela. O valor em
> `instrumentos.py` é estimativa para limitar o sizing; confirme com a sua antes de operar.
