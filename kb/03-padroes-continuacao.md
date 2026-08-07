# Padrões de continuação

Fonte: ebook p.19–21.

Família menor e mais delicada de operar. O sinal aqui é "a tendência que já existe vai
seguir", então a entrada é sempre **a favor** do movimento — e o risco é entrar tarde,
perto da exaustão. Todos exigem tendência definida; nenhum vale em mercado lateral.

---

## Linha de Separação de Alta
`linha_separacao_alta` · 2 candles · tendência de **alta** · prior 0.35 · p.19

**Geometria** — dois candles de força com **aberturas coincidentes** (ou quase): o
primeiro vermelho, o segundo verde.

**Leitura** — o ebook: *"resposta rápida da força compradora à tentativa dos ursos de
reverter o mercado"*. Os vendedores conseguiram um candle inteiro, e no seguinte o preço
abriu exatamente onde eles tinham começado — como se a queda não tivesse acontecido.

**Cuidado** — baixa confiabilidade.

## Linha de Separação de Baixa
`linha_separacao_baixa` · 2 candles · tendência de **baixa** · prior 0.35 · p.19

Verde de força e vermelho de força abrindo no mesmo preço.

---

## Strike de Alta
`strike_alta` · 4 candles · tendência de **alta** · prior 0.35 · p.19

**Geometria** — três verdes com aberturas e fechamentos ascendentes; o quarto abre acima
do fechamento anterior, despenca e fecha **abaixo da abertura do primeiro**.

**Leitura** — parece reversão e o ebook classifica como continuação. A leitura é de
**realização de lucro**: quem comprou embaixo vendeu, o aumento de oferta derrubou o
preço, e ele voltou a ficar atrativo para compra.

**Cuidado** — prior baixo de propósito. Distinguir realização de virada real, no
intraday, é exatamente o problema difícil. O ebook avisa: *"não é muito confiável. Não
duvide da força vendedora após um candle desse tamanho. O famoso 'medo de perder' pode se
transformar em pânico em massa."*

## Strike de Baixa
`strike_baixa` · 4 candles · tendência de **baixa** · prior 0.35 · p.20

**Geometria** — três vermelhos, cada um abrindo dentro do corpo do anterior e fechando
mais embaixo; o quarto é verde e **engolfa os corpos dos três**.

**Leitura** — o preço caiu bastante, ficou atrativo, quem estava vendido realizou lucro.
O ebook espera que os operadores usem a subida para vender de novo.

---

## Gap Tasuki de Alta
`gap_tasuki_alta` · 3 candles · tendência de **alta** · prior 0.50 · p.20 · *exige gap*

**Geometria** — dois verdes de força com **gap entre si**; o terceiro é vermelho, fecha
abaixo da abertura do segundo, mas **não chega a fechar o gap** (permanece acima do
fechamento do primeiro).

**Leitura** — o padrão inteiro é sobre a **falha**. O ebook chama de *"derrota da força
vendedora ao tentar fechar o gap"*. Se o vermelho fechasse o gap, não haveria sinal nenhum
— por isso a condição de não-fechamento é obrigatória, não decorativa. Pode ser lido
também como correção antes da continuação.

## Gap Tasuki de Baixa
`gap_tasuki_baixa` · 3 candles · tendência de **baixa** · prior 0.50 · p.20 · *exige gap*

Dois vermelhos de força com gap; o terceiro verde fecha **acima da abertura do segundo** e
permanece **abaixo do fechamento do primeiro**.

> ⚠️ O ebook repete literalmente a redação da versão de alta para o terceiro candle
> (ERRATA item 4). O motor implementa o espelho correto.

---

## Linhas Brancas Lado a Lado (Alta)
`linhas_brancas_alta` · 3 candles · tendência de **alta** · prior 0.50 · p.21 · *exige gap*

**Geometria** — (1) verde; (2) verde abrindo em gap de alta, com pouca sombra e mínima
acima da máxima do primeiro; (3) verde semelhante ao segundo, com aberturas e fechamentos
muito próximos.

**Cuidado** — o ebook classifica como *"incidência rara"*.

## Linhas Brancas Lado a Lado (Baixa)
`linhas_brancas_baixa` · 3 candles · tendência de **baixa** · prior 0.50 · p.21 · *exige gap*

**Geometria** — (1) vermelho; (2) verde abrindo em gap de **baixa**; (3) verde semelhante
ao segundo.

**Leitura — a mais estranha do catálogo, e o ebook sabe disso**: *"isso mesmo, parece
estranho, mas os dois candles são verdes (ou brancos, daí o nome), e é teoricamente
descrito como padrão de continuação"*.

A explicação: os dois verdes acontecem inteiramente **dentro do gap de baixa**. É repique
dentro da queda, não retomada — o preço subiu e nem assim voltou ao nível anterior.

> ⚠️ O ebook mede o gap pelo **fechamento** do segundo candle nesta versão e pela
> abertura/mínima na de alta (ERRATA item 8). O motor usa a abertura nas duas.

---

## Nota sobre gaps em intraday

Seis dos oito padrões desta família exigem gap, e o ebook foi escrito pensando em gráfico
**diário**, onde o pregão fecha e reabre. No WIN/WDO em 5 minutos, dentro do pregão, o
preço é contínuo: **gap estrito quase nunca ocorre**.

Por isso o motor tem `Limiares.tolerancia_gap_atr`, que permite tratar uma
quase-sobreposição como gap. É o parâmetro mais sensível do sistema:

- **tolerância de menos** → estes padrões nunca disparam
- **tolerância de mais** → qualquer sobreposição vira "gap" e eles disparam sempre

Calibrar isso por timeframe é a primeira coisa que o backtest deve fazer. Ver
[docs/ERRATA-EBOOK.md](../docs/ERRATA-EBOOK.md) item 10.
