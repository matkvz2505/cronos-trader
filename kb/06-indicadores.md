# Indicadores técnicos

Os cinco que a B3 lista como base para day trade, mais três que o motor usa internamente.
Implementação em `ai/trader_ai/indicadores.py`.

## Os cinco da B3

### 1. Média móvel
Ver [05-medias-moveis.md](05-medias-moveis.md) — tem arquivo próprio pela quantidade de
detalhe.

### 2. IFR / RSI — Índice de Força Relativa
Compara ganhos e perdas recentes numa escala de 0 a 100.

| Faixa | Leitura |
|---|---|
| acima de 70 | sobrecomprado |
| abaixo de 30 | sobrevendido |

**Cuidado que a leitura ingênua ignora:** em tendência forte o RSI *fica* acima de 70 por
dias. Vender só porque "está sobrecomprado" é a forma clássica de perder dinheiro contra a
tendência. O uso defensável é como **filtro contra**: um sinal de compra com RSI em 85 tem
menos espaço à frente.

Suavização de Wilder, período 14.

### 3. Bandas de Bollinger
Média móvel central com duas bandas a N desvios-padrão. As bandas **se afastam e se
aproximam conforme a volatilidade** — é isso que o indicador realmente mede.

- preço tocando a banda em mercado lateral → possível reversão
- bandas se estreitando (*squeeze*) → compressão de volatilidade, costuma preceder
  movimento forte, **sem dizer a direção**
- preço "andando na banda" em tendência → continuação, não reversão

Padrão: 20 períodos, 2 desvios.

### 4. Volume e VWAP
Volume confirma: um padrão de reversão com volume abaixo da média é suspeito — se o
mercado realmente mudou de mão, alguém negociou.

O motor usa como fator de confluência com três faixas:

| Volume do padrão vs média de 20 | Efeito |
|---|---|
| ≥ 1,5× | bônus |
| entre 0,6× e 1,5× | neutro |
| ≤ 0,6× | penalidade |

> Nota operacional: muitas corretoras devolvem `real_volume` zerado em WIN/WDO no MT5. O
> coletor usa `tick_volume`, senão o fator ficaria desligado sem que ninguém notasse.

**VWAP** é preço médio ponderado por volume, com reset diário. Entra como zona de
suporte/resistência de peso alto — é o benchmark de execução do institucional.

### 5. Fibonacci
Ver [../docs/ESTUDOS.md](../docs/ESTUDOS.md). Resumo do que foi **medido**, não do que se
repete:

- **WDO respeita 50%** (pico de 1,34× os vizinhos) — único nível com destaque real
- **WIN não respeita nenhum nível** em 5 minutos
- 38,2% e 61,8%, os mais citados na literatura, **não se destacam** em nenhum dos dois
- a faixa dos 30% é o *oposto* de suporte: é onde o preço menos para

O motor só dá bônus onde mediu.

---

## Os três que o motor usa internamente

### ATR — Average True Range
**O indicador mais importante do sistema**, e o que menos aparece na tela. É o denominador
de praticamente todo limiar: "corpo longo" é 0,8 ATR, "candle de força" é 1,2 ATR, folga
de stop é 0,25 ATR.

É o que permite o mesmo detector rodar em WIN (pontos) e WDO (reais), em 5 minutos e em 60,
sem reescrever nada. Suavização de Wilder, período 14.

### ADX — força de tendência
Mede **força**, não direção. Abaixo de 20 o contexto vira `LATERAL` e os padrões de
reversão perdem quase todo o peso — não há tendência para reverter.

Tem poder de veto sobre as outras evidências de propósito: EMA e estrutura de Dow sempre
apontam *alguma* direção, mesmo em lateralização, porque é geometria de ruído. O ADX é a
única das três que sabe dizer "não há tendência aqui".

### MACD, Estocástico e OBV
Disponíveis em `indicadores.py`, ainda não ligados à confluência — entram quando houver
estudo empírico que justifique o peso, no mesmo padrão do que foi feito com Fibonacci.

- **MACD** (12/26/9): o histograma muda de sinal antes do cruzamento das linhas, então
  mede aceleração e não só direção.
- **Estocástico** (14/3/3): onde o fechamento caiu dentro do range do período. Pode
  divergir do RSI, e a divergência costuma ser mais informativa que qualquer um sozinho.
- **OBV**: volume acumulado com o sinal da variação. Serve para divergência — preço
  fazendo máxima nova com OBV sem acompanhar significa alta com menos gente que a anterior.

---

## A regra que atravessa todos

Indicador **não gera sinal** neste motor. Indicador responde "o padrão aconteceu num lugar
e num momento que importavam?".

O ebook é explícito sobre padrões de candlestick isolados terem baixa confiabilidade, e a
medição em dados reais confirma. O edge, se existir, está na **exigência de confluência** —
e confluência inventada, dada a um fator que não se mediu, é pior que confluência nenhuma:
vira sinal ruim com aparência de bom.
