# Médias móveis

Fontes: Portal do Trader (médias mais usadas), B3 Bora Investir (5 indicadores para day
trade). Implementação em `ai/trader_ai/medias.py` e `ai/trader_ai/indicadores.py`.

## Os quatro tipos, e o que cada um faz de diferente

| Tipo | Como calcula | Comportamento |
|---|---|---|
| **SMA** (simples) | média aritmética do período | acompanha o movimento dos candles; a mais "lenta" |
| **EMA** (exponencial) | peso maior nos preços recentes | cola mais nos candles, principalmente em períodos longos |
| **WWMA / RMA** (Welles Wilder) | "exponencial ao quadrado" | cola ainda mais; usada com períodos altos, tipicamente **400** |
| **VWAP** | ponderada pelo volume financeiro | dá peso a quem move dinheiro grande, não a quem move tempo |

A de Wilder merece a nota técnica: uma RMA de período N tem a inércia de uma EMA de
`2N-1`. A **RMA(400) responde como uma EMA(799)**. Isso a torna inútil para timing — e é
exatamente o que a torna boa para **regime**: a pergunta "de que lado do mercado estamos"
não deveria mudar a cada cinco minutos.

O VWAP tem uma propriedade que as outras não têm: **reseta a cada pregão**. VWAP acumulado
desde o início da base não significa nada para day trade — o que os operadores olham, e
contra o que o preço reage, é o preço médio ponderado *do dia*.

## Períodos por horizonte

| Horizonte | Períodos | Uso |
|---|---|---|
| Curtíssimo (day trade) | 3, 8, 9 | condução, stop móvel |
| Médio (swing) | 20–80 | viés direcional |
| Longo | 200+ | regime, gatilho estrutural |

## O conjunto que o motor usa

Quatro médias, quatro papéis — não quatro versões da mesma coisa:

| Média | Papel | Por que não serve para o papel das outras |
|---|---|---|
| **EMA 9** | condução do trade, stop móvel | reage rápido demais para filtrar: vira e desvira |
| **SMA 21** | viés direcional do dia, suporte/resistência | lenta demais para conduzir, rápida demais para regime |
| **SMA 200** | gatilho estrutural | não serve de timing: quando ela vira, o movimento já andou |
| **RMA 400** | regime de fundo | quase não se move — e é isso que a torna confiável para regime |

## O que de fato pontua: alinhamento, não valor

O motor **não** dá bônus por "o preço está acima da média X". Dá por **empilhamento**:

```
preço > EMA9 > SMA21 > SMA200 > RMA400     →  estrutura de alta, alinhamento 1.0
preço < EMA9 < SMA21 < SMA200 < RMA400     →  estrutura de baixa, alinhamento 1.0
qualquer outra ordem                        →  médias embaraçadas
```

Quatro médias na ordem descrevem um mercado com estrutura. Embaraçadas descrevem um sem
direção — e é justamente aí que padrão de reversão mais engana, porque não há tendência
para reverter.

**Assimetria proposital:** entrar contra estrutura definida penaliza 0,35; a favor
bonifica 0,30. Errar contra a estrutura custa mais caro do que acertar a favor rende.

## Esticamento

Preço a mais de **2 ATR** da SMA21 começa a ser penalizado. Comprar 3 ATR acima da média
de viés é comprar o fim do impulso: a reversão à média passa a puxar contra a posição
antes mesmo de o alvo chegar. É uma das formas mais comuns de **acertar a direção e perder
dinheiro**.

## Cruzamentos conhecidos

**9 × 21** — EMA9 cruzando a SMA21. O motor detecta e registra na tese
(`medias.cruzamento_recente`), porque cruzamento é **evento**, não estado: marca o instante
em que o viés virou, e um padrão que aparece logo depois pega o movimento no começo em vez
do fim.

**Agulhada do Didi** — três SMAs (3, 8, 20). Alerta quando a de 3 cruza a de 8;
confirmação quando cruza a de 20. Não implementado; candidato natural a estudo empírico
nos moldes do que foi feito com Fibonacci.

**Larry Williams** — EMA 9 com leitura de curvatura e de cruzamento com os candles.
