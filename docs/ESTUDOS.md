# Estudos — o que foi medido, e o que a medição derrubou

Este arquivo registra as medições que sustentam os pesos do motor. Existe porque a
alternativa é o motor pontuar por convenção, e convenção em análise técnica é
majoritariamente folclore repetido até virar verdade.

Toda medição aqui é reproduzível:

```powershell
cd ai
python scripts/estudo_fibonacci.py dados/WDO_M5_real.csv --ativo WDO --tf M5
python scripts/estudo_estrutura.py dados/WIN_M5_real.csv --ativo WIN --tf M5
python scripts/funil.py dados/WIN_M5_real.csv --ativo WIN --tf M5
```

---

## 1. Fibonacci — quais níveis WIN e WDO realmente respeitam

**Amostra:** 60.000 candles de M5 por ativo (jun/2024 a ago/2026, XP), ~2.400 correções
com virada clara em cada.

### O método, e por que o método comum engana

A pergunta parece simples: "das vezes que o preço chegou em 61,8%, quantas ele parou ali?".
Medida assim, a resposta é **sempre** que os níveis profundos funcionam melhor:

```
nível    parou antes do próximo    densidade
0.236              2.9%              0.45
0.300              6.4%              0.78
0.382             15.5%              1.31
0.500             21.6%              1.83
0.618             45.9%              2.73
0.786             84.8%              3.96
```

Isso parece uma descoberta e não é. A correção **precisa** terminar em algum lugar antes
de 100%, então a probabilidade condicional de terminar na próxima faixa cresce com a
profundidade quer Fibonacci signifique algo ou não. A rampa monotônica é o resultado
esperado do acaso.

**O teste correto é local.** Em bins uniformes de 2% de retração, calcula-se a taxa de
virada (hazard) e pergunta-se se o bin do nível se destaca dos **vizinhos imediatos**. Um
nível que o mercado enxerga produz **pico local**; um número sem significado produz curva
lisa.

### Resultado

| Nível | WDO | WIN |
|---|---|---|
| 0,236 | 1,05× | 0,32× *(vale)* |
| 0,300 | 0,79× *(vale)* | 0,74× *(vale)* |
| 0,382 | 0,89× | 0,85× |
| **0,500** | **1,34× — PICO** | 0,99× |
| 0,618 | 1,14× | 1,19× |
| 0,786 | 1,01× | 0,72× *(vale)* |

Corte de destaque: 1,25× a vizinhança.

### Conclusões

**O WDO respeita 50%.** Único nível com pico estatístico real, em 2.376 correções. É o
que o motor usa — e só ele.

**O WIN não respeita Fibonacci nenhum em 5 minutos.** Nem 61,8% (1,19×, abaixo do corte),
nem 38,2%. O motor **não dá bônus de Fibonacci ao WIN**.

**38,2% e 61,8% — os dois níveis mais citados na literatura — não se destacam em nenhum
dos dois ativos.** A crença é real; o efeito, nestes ativos e neste timeframe, não.

**A faixa dos 30% é o oposto de suporte.** 0,79× no WDO e 0,74× no WIN: é onde o preço
*menos* costuma parar. Operar contra essa medição é escolher o pior lugar do gráfico.

### Como entra no código

`fibonacci.NIVEIS_RESPEITADOS` guarda `{ativo: {nível: razão}}`, e
`fibonacci.relevancia()` escala o bônus. Nível não medido devolve zero — deixar de
pontuar onde não há evidência não é o motor ficando pior, é ele parando de inventar
confluência.

> Limite honesto: isto mede M5 em ~2 anos de um contrato contínuo. Não diz que Fibonacci
> não funciona em nenhum timeframe nem em nenhum mercado — diz que não funciona **aqui**,
> com estes dados. Rodar o estudo em M15 e M60 é trabalho pendente.

---

## 2. Onde os sinais morriam — o funil

O primeiro backtest sobre dados reais produziu **90 sinais em 777 dias**: um a cada 8
dias, o que não é day trade. O funil localizou a causa:

```
candles avaliados                     59.970
com ao menos uma detecção             19.477   (32,5%)
aprovados na confluência               2.714   (13,9%)
sobreviveram ao viés multi-timeframe   1.938   (71,4%)
viraram SINAL                            106   (5,5%)   ← aqui

MORTAS NA DECISÃO
  R:R abaixo de 1.5                    1.824   ← 94% das mortes
```

**Causa:** `decisao._alvo` adotava a zona de suporte/resistência assim que ela estivesse
do lado certo da entrada, sem checar se pagava o risco. Uma zona logo acima do rompimento
virava alvo minúsculo, o R:R nascia morto — e o motor **nunca tentava a opção seguinte**.

**Correção:** percorrer as zonas da mais próxima à mais distante e ficar na primeira que
rende ao menos `rr_minimo`; se nenhuma serve, projeção de Fibonacci; por último, 2R fixo.
É a regra que um operador usa: se o alvo mais próximo não paga, olhe o próximo.

**Efeito:** 106 → 948 sinais (1,2 por pregão). Travado por
`test_zona_que_nao_paga_o_risco_e_descartada_pela_seguinte`.

---

## 3. Janelas do pregão — o prior que a medição contradiz

Medido em WIN, 60.000 candles:

| Janela | n | Expectância | Resultado | Peso que eu dei |
|---|---|---|---|---|
| **abertura-eua** (14h–16h) | 115 | **+0,40R** | +R$ 5.905 | 1,15 |
| abertura (9h–10h) | 41 | +0,22R | +R$ 918 | 0,85 |
| almoço (12h–14h) | 55 | +0,01R | −R$ 500 | 0,60 |
| **tendência-manhã** (10h–12h) | 205 | **−0,28R** | **−R$ 11.948** | **1,15** |

Eu dei peso máximo à janela das 10h–12h supondo ser a de "tendência mais limpa". É a que
mais destrói capital na série inteira, e por larga margem.

**Não recalibrei os pesos.** Ajustá-los nesta mesma série e depois reportar melhora nela
é exatamente a memorização contra a qual o walk-forward existe. Recalibrar exige treinar
numa janela e medir na seguinte — trabalho pendente, e o produto avisa isso na tela.

---

## 4. Médias móveis — quatro papéis

| Média | Papel |
|---|---|
| EMA 9 | condução e stop móvel; rápida demais para filtrar |
| SMA 21 | viés direcional do dia; funciona como S/R |
| SMA 200 | a mais observada do mundo; perdê-la ou superá-la é gatilho |
| RMA 400 (Wilder) | regime de fundo |

Sobre a de Wilder: a suavização de Wilder com período N tem a inércia de uma EMA de
`2N-1` — a RMA(400) responde como uma EMA(799). Inútil para timing, e é exatamente isso
que a torna boa para regime: "de que lado do mercado estamos" não deveria mudar a cada
cinco minutos.

O que pontua **não é o valor das médias, é o alinhamento entre elas**. Quatro médias
empilhadas na ordem descrevem um mercado com estrutura; embaraçadas descrevem um sem
direção, onde padrão de reversão é ruído. Entrar contra estrutura definida penaliza mais
(0,35) do que entrar a favor bonifica (0,30) — errar contra a estrutura custa mais caro
do que acertar a favor rende.

Há também penalidade de **esticamento**: preço a mais de 2 ATR da SMA21 começa a ser
penalizado. Comprar 3 ATR acima da média de viés é comprar o fim do impulso — acerta a
direção e perde dinheiro.

---

## 5. Estrutura gráfica — medida, e reprovada para o score

O motor detecta canal, rompimento, zona de oferta/demanda, RSI e Bollinger. A pergunta era
se algo disso deveria **mexer no score**. Peso inventado é pior que peso nenhum: vira sinal
ruim com aparência de bom.

**Método:** rodar o motor sobre a série inteira, anotar o contexto estrutural de cada
operação acionada, e comparar a expectância **com** e **sem** cada condição. Um fator só
entra se tiver amostra ≥ 30 dos dois lados, diferença ≥ 0,15R, **e sinal consistente entre
WIN e WDO**.

| Condição | WIN M5 | WDO M5 | Veredito |
|---|---|---|---|
| na zona certa (compra na demanda / venda na oferta) | +0,05R (n=71) | **−0,32R** (n=59) | **sinais opostos** |
| canal existe | −0,49R (n=4) | +0,01R (n=14) | sem amostra |
| a favor da borda do canal | −1,00R (n=3) | +0,17R (n=9) | sem amostra |
| fora da banda de Bollinger | −0,49R (n=5) | +0,29R (n=4) | sem amostra |
| rompimento recente a favor | n=0 | n=0 | nunca ocorreu |
| RSI extremo contra | n=0 | n=0 | nunca ocorreu |

**Nenhuma condição entra na confluência.** Três razões distintas:

**As de canal não têm amostra em 5 minutos** — consequência direta de canal ser figura de
timeframe maior (3,6% das janelas em M5 contra 31,4% em H1). Com 3 a 14 ocorrências em dois
anos, não há o que medir.

**"Na zona certa" tem sinal oposto nos dois ativos.** É a única com amostra decente, e
justamente por isso o critério de consistência importa: +0,05R no WIN e −0,32R no WDO não
é um fator, é ruído que encontrou um ativo. Ligá-la olhando só o WIN seria overfitting com
cara de descoberta.

**"RSI extremo contra" nunca ocorre, e isso é lógico.** Sinais de compra nascem de padrões
de reversão em tendência de baixa, onde o RSI está baixo — não em 70+. A condição estava
correta e é vazia por construção.

A estrutura continua fazendo o trabalho dela: **desenhar o gráfico e sustentar a tese**.
Não pontua.

---

## 6. Multi-timeframe — o gatilho se auto-vetava em 60min

Encontrado ao rodar o estudo acima em H1: **1 operação em 5.314 candles**. O funil mostrou
onde:

```
aprovados na confluência                 89
sobreviveram ao viés multi-timeframe     25   (28%)  ← 64 mortos aqui
viraram SINAL                             3
```

**Causa:** `montar_conjunto` incluía a própria série de gatilho no conjunto de viés. Com
H1 como gatilho, o viés passava a ser o próprio H1 — e um padrão de **reversão** tem, por
definição, direção oposta à tendência em que nasce. Todo sinal de reversão se auto-vetava.

Em 5 minutos o defeito era invisível: ali o viés vem de 15/30/60, timeframes diferentes do
gatilho. Só apareceu ao operar o motor no topo da escala.

**Correção:** o conjunto de viés passa a conter **apenas timeframes estritamente maiores**
que o do gatilho. Conjunto vazio significa *sem viés*, e a avaliação passa intacta —
ausência de informação não é informação contrária.

| | antes | depois |
|---|---|---|
| sobrevivência no MTF (H1) | 28% | **100%** |
| sinais (WIN H1, 2 anos) | 3 | **35** |
| WIN M5 | 208 acionadas | 208 acionadas *(inalterado)* |

M5 não muda porque o viés nunca consultava M5 — a correção é cirúrgica. Travado por
`test_conjunto_de_vies_nao_inclui_o_proprio_gatilho` e
`test_sem_vies_a_avaliacao_passa_intacta`.

---

## 7. Estado atual do edge

Medido em WIN M5, walk-forward de 5 janelas, depois de todas as correções acima:

```
expectância média fora da amostra:  +0,04R por operação
sinais:                             293 em 777 dias
```

Positiva, mas perto de zero — **não há edge comprovado**. O que existe são dois indícios
com amostra:

- **Engolfo de Alta**: n=143, 47,6% de acerto, +0,18R
- **janela da abertura americana**: n=115, 58,3%, +0,40R

Ambos precisam de validação fora da amostra antes de virarem regra. O produto mostra tudo
isso marcado como "amostra insuficiente" onde couber, e a convicção de cada sinal é
rebaixada quando a confiabilidade medida do padrão é baixa — mesmo que o score de
confluência seja alto.

