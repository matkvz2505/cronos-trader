# Knowledge base — o ebook destilado para consumo dos agentes

Base de conhecimento que os agentes de IA (Sprint 7) consultam via RAG para fundamentar a
leitura de um sinal. **Não é código e não gera sinal** — quem detecta e pontua é o motor
em [`ai/trader_ai/`](../ai/trader_ai/). Isto aqui é o material que permite ao Analista
escrever *por que* aquele padrão significa alguma coisa, em vez de inventar.

## Formato

Uma entrada por padrão, sempre com os mesmos campos, para que o chunking do RAG não corte
no meio de uma ideia:

```
## Nome do Padrão
- id · família · direção · nº de candles · contexto exigido · confiabilidade · página
- **Geometria** — o que precisa acontecer no gráfico
- **Leitura** — o que isso diz sobre a briga entre compradores e vendedores
- **Cuidado** — quando o padrão falha
```

O campo `id` casa exatamente com o `padrao_id` do catálogo em `ai/trader_ai/padroes/`.
É o que liga uma detecção do motor ao texto que a explica.

## Arquivos

**Candlestick** — do ebook, com a errata aplicada:

| Arquivo | Conteúdo |
|---|---|
| [00-anatomia-do-candle.md](00-anatomia-do-candle.md) | O que um candle diz. Base de tudo. |
| [01-padroes-isolados.md](01-padroes-isolados.md) | Doji, Marubozu, Spinning Top |
| [02-padroes-reversao.md](02-padroes-reversao.md) | O grosso do catálogo |
| [03-padroes-continuacao.md](03-padroes-continuacao.md) | Separação, Strike, Tasuki, Linhas Brancas |

**Além do ebook** — o que ele não cobre e o produto precisa:

| Arquivo | Conteúdo |
|---|---|
| [04-contexto-win-wdo.md](04-contexto-win-wdo.md) | Como WIN e WDO se comportam: horário, correlação, agenda |
| [05-medias-moveis.md](05-medias-moveis.md) | SMA, EMA, Wilder 400, VWAP; alinhamento e esticamento |
| [06-indicadores.md](06-indicadores.md) | Os 5 da B3 + ATR, ADX, MACD, Estocástico, OBV |
| [07-estrutura-grafica.md](07-estrutura-grafica.md) | Canais, pivôs, rompimentos, zonas de oferta e demanda |
| [08-contratos-e-custos.md](08-contratos-e-custos.md) | Specs de WIN e WDO, rollover, custos operacionais |

Medições que sustentam os pesos do motor: [../docs/ESTUDOS.md](../docs/ESTUDOS.md).

## Regra editorial

O ebook é a fonte das regras geométricas. Onde ele erra, o texto aqui segue **o código**,
não o ebook, e diz isso explicitamente — as divergências estão catalogadas em
[docs/ERRATA-EBOOK.md](../docs/ERRATA-EBOOK.md).

E a regra que atravessa tudo: **confiabilidade declarada aqui é o prior do ebook, não
evidência.** Quando o backtest tiver medido o padrão em WIN/WDO, o número que vale é o
dele. Um agente que citar "alta confiabilidade" sem checar a medição está repetindo
folclore.
