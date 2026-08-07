# Arquitetura — as sete camadas do motor

O motor é uma pipeline de sete camadas. Cada uma recebe a saída da anterior e é testável
isoladamente. Nenhuma delas chama LLM — a IA entra **depois**, lendo o resultado.

```
OHLCV bruto
   │
   ├─ 1. NORMALIZAÇÃO      corpo, sombras, amplitude — tudo relativo ao ATR
   ├─ 2. CONTEXTO          tendência, swings, regime de volatilidade, janela do pregão
   ├─ 3. DETECTORES        ~40 padrões do ebook → Deteccao(forca 0..1)
   ├─ 4. CONFLUÊNCIA       Fibonacci + médias + S/R + volume + horário + correlação
   ├─ 5. DECISÃO           entrada, stop, alvo, R:R, tamanho, veto
   ├─ 6. MULTI-TIMEFRAME   viés em 15/30/60m governa o gatilho em 5m
   └─ 7. BACKTEST          mede o resultado real e recalibra os pesos de volta na 4
                                                              │
                                          agentes de IA ◀─────┘ (narram, não decidem)
```

---

## 1. Normalização — por que nada é medido em pontos

Um corpo de 200 pontos no WIN é enorme às 12h e banal às 9h05. Um limiar absoluto quebra
entre ativos (WIN anda em pontos, WDO em reais) e entre regimes de volatilidade.

**Regra:** todo limiar do motor é expresso ou como **fração da amplitude do próprio candle**,
ou como **múltiplo do ATR(14)** da série. Nunca em pontos.

```
corpo_pct    = |close - open| / (high - low)      → "corpo pequeno" = corpo_pct <= 0.30
sombra_sup   = high - max(open, close)
sombra_inf   = min(open, close) - low
amplitude_atr = (high - low) / atr14              → "candle de força" = amplitude_atr >= 1.2
```

Isso é o que permite o mesmo detector rodar em WIN 5m e WDO 60m sem reescrever nada.

## 2. Contexto — quase todo padrão do ebook exige tendência

Repare que o ebook abre praticamente toda descrição com *"numa tendência de baixa…"*. Um
engolfo de alta no meio de uma alta não é um engolfo de alta — é ruído. Detectar geometria
sem contexto é o erro mais comum e a causa número um de sinal falso.

A tendência é decidida por três evidências combinadas, não por uma:

| Evidência | Como | Peso |
|---|---|---|
| Inclinação da EMA | EMA(9) vs EMA(21), normalizada por ATR | direção |
| Estrutura de Dow | sequência de topos/fundos ascendentes ou descendentes | confirmação |
| ADX(14) | força da tendência; `< 20` = lateral | veto |

Se ADX indica lateralidade, o contexto retorna `LATERAL` e os padrões de reversão perdem a
maior parte do peso — não há tendência para reverter.

O contexto também classifica **regime de volatilidade** (ATR atual vs média do ATR) e a
**janela do pregão** (ver tabela em [FONTES-DE-DADOS.md](FONTES-DE-DADOS.md)).

## 3. Detectores

Cada padrão é uma função pura: `(janela_de_candles, contexto, limiares) → Deteccao | None`.

Duas escolhas de design importantes:

**Retornam força, não booleano.** Um engolfo que cobre o candle anterior por 5% e outro que
cobre por 300% não são o mesmo sinal. Cada condição devolve uma margem contínua, e a `forca`
final é a média harmônica das margens — assim uma condição mal satisfeita puxa o conjunto
para baixo, em vez de ser mascarada pelas outras.

**Não conhecem preço nem ordem.** Um detector não sabe o que é stop. Ele só afirma "esta
geometria ocorreu aqui, com esta força". Quem transforma isso em trade é a camada 5.

Registro em `padroes/__init__.py` via decorator, para que o catálogo seja iterável e o
backtest possa varrer todos automaticamente.

## 4. Confluência — onde mora o edge

O ebook diz, várias vezes, que os padrões sozinhos têm baixa confiabilidade. Ele está certo, e
é por isso que um produto que só detecta padrão não vale nada. **O valor está em exigir que o
padrão aconteça num lugar que já importava.**

O score final é o prior do padrão, ajustado por fatores multiplicativos:

| Fator | O que checa | Efeito |
|---|---|---|
| **Fibonacci** | padrão caiu em retração 38.2 / 50 / 61.8 do último swing | ×1.0 → ×1.35 |
| **Médias** | preço reagiu na SMA/EMA 9, 21, 50 ou 200 | ×1.0 → ×1.25 |
| **Suporte/Resistência** | pivôs, VWAP, máx/mín do dia anterior, abertura | ×1.0 → ×1.30 |
| **Volume** | volume do padrão vs média de 20 períodos | ×0.85 → ×1.20 |
| **Horário** | janela do pregão | ×0.60 → ×1.15 |
| **Correlação** | S&P (WIN) / DXY (WDO) a favor ou contra | ×0.80 → ×1.10 |
| **Volatilidade** | ATR muito baixo = movimento não paga o custo | ×0.70 → ×1.05 |

Confluência de zona é o fator mais forte de todos: quando Fibonacci, uma média e um S/R
apontam para o **mesmo preço**, isso é uma zona de decisão real, onde há ordem de gente grande.
Um martelo ali vale muito mais que um martelo no meio do nada. O motor detecta essa
coincidência explicitamente (`confluencia.zona_quente`) e dá um bônus adicional.

Todos os multiplicadores vivem em `Limiares` e são calibráveis pelo backtest — os valores
acima são o ponto de partida, não verdade revelada.

## 5. Decisão

Converte `(padrão + score)` em um trade concreto:

- **Entrada** — rompimento do extremo do padrão na direção do sinal (não no fechamento do
  candle: exige confirmação)
- **Stop** — extremo oposto do padrão, com folga de `0.25 × ATR` para não ser estopado por
  ruído de spread
- **Alvo** — o primeiro entre: próxima zona de S/R, extensão de Fibonacci 1.618, ou múltiplo
  fixo de R
- **R:R** — sinais abaixo de `1.5` são descartados, por melhor que seja o padrão. Um padrão
  ótimo com alvo ruim continua sendo um trade ruim.
- **Tamanho** — número de contratos por risco fixo em % do capital, arredondado para baixo

**Vetos** (matam o sinal independentemente do score): ADX lateral em padrão de reversão, janela
de notícia econômica, fora do horário operacional, limite de perda diária atingido, número
máximo de trades no dia.

## 6. Multi-timeframe

Foi o que você pediu: **15/30/60m avaliam, 5m dispara.**

```
60m ─┐
30m ─┼─▶ VIÉS   (alta / baixa / neutro, com força)
15m ─┘            │
                  ▼
 5m ────────▶ GATILHO ── só é aceito se concordar com o viés
```

Um padrão de compra em 5m contra um viés de baixa em 30m e 60m é rejeitado — é exatamente o
trade que parece bom na tela e perde. Quando os três timeframes altos concordam entre si, o
sinal ganha bônus; quando divergem, o viés é `neutro` e só padrões de score muito alto passam.

## 7. Backtest — o que torna os números honestos

O backtest não existe para provar que a estratégia funciona. Existe para **descobrir quais
padrões realmente funcionam em WIN e WDO**, e apagar os que não funcionam.

Ele varre o histórico, aplica o motor exatamente como no tempo real (sem olhar candle futuro),
simula entrada/stop/alvo candle a candle e registra o resultado. A saída é a métrica que
interessa:

```
taxa de acerto por padrão × timeframe × janela do pregão × ativo
```

Essa tabela realimenta `confiabilidade_medida` no catálogo. Padrões com amostra pequena
(`n < 30`) ficam marcados como *insuficiente* e mantêm o prior do ebook — sem inventar
confiança que os dados não sustentam.

**Contra o overfitting:** validação *walk-forward* — calibra numa janela, testa na seguinte,
anda para frente. Uma taxa de acerto medida no mesmo período em que os pesos foram ajustados
não é evidência, é memorização.

Custos entram na simulação: **spread, corretagem e slippage**. Uma estratégia de 5 minutos com
taxa de acerto de 55% pode perder dinheiro depois dos custos, e é melhor descobrir isso aqui.

---

## Onde a IA entra

Depois de tudo isso — e só lendo o resultado.

| Agente | Papel |
|---|---|
| **Analista** | lê o dossiê de números e escreve a tese em pt-BR: por que este trade existe |
| **Crítico** | argumenta contra: qual a leitura alternativa, o que invalida a tese |
| **Gestor de Risco** | tamanho, exposição acumulada, veto por limite diário |

Os agentes consultam `kb/` (o ebook destilado) via RAG para fundamentar a leitura. Rodam
atrás do gateway **LiteLLM** com modelo free como principal e fallback pago, e são observados
pelo **Langfuse** — mesmo padrão já usado em `cronos-go/tools/`.

**A IA nunca altera o score nem cria sinal.** Se o LLM cair, o motor continua produzindo
sinais — perde-se a narrativa, não a decisão.

## Stack

| Camada | Escolha | Por quê |
|---|---|---|
| Motor / IA | **Python 3.11+** — numpy, pandas, scipy, pandas-ta | ecossistema numérico; MT5 só tem binding Python |
| Backend | **Node 20 + TypeScript** — Express, Prisma, Postgres | auth, API, WebSocket; convenção do Matriz-SA |
| Banco | **Postgres 16 + TimescaleDB** | candles são série temporal; hypertable resolve volume |
| Frontend | **React 19 + Vite + lightweight-charts** | biblioteca de gráfico da TradingView, free |
| Gateway LLM | **LiteLLM** | free-primary + fallback pago |
| Observabilidade | **Langfuse** | trace por execução de agente |

### Portas (sem colidir com o resto do workspace)

| Serviço | Porta |
|---|---|
| backend (dev / prod) | 1840 / 2540 |
| serviço de IA | 1841 |
| frontend (dev) | 5180 |
| Postgres | 5460 |
| Redis | 6400 |
| LiteLLM | 4010 |
| Langfuse | 3010 |
