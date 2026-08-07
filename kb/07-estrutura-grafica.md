# Estrutura gráfica: canais, pivôs, rompimentos e zonas

O desenho que um analista rabisca por cima do gráfico antes de decidir. Implementação em
`ai/trader_ai/estrutura.py`; o gráfico do produto renderiza tudo isto anotado.

## Pivô

Um topo ou fundo confirmado: um candle cuja máxima (ou mínima) supera as `N` de cada lado.

O detalhe que quase todo mundo erra: **um pivô só existe `N` candles depois de acontecer.**
No tempo real você não sabe que fez um topo enquanto o preço não se afastar dele. Usar um
pivô "recém-formado" para decidir é ler o futuro — foi um dos dois vazamentos que o motor
já teve e que hoje está travado por teste (`swings_confirmados` exige `índice + N ≤ i`).

## Canal

Duas retas aproximadamente paralelas contendo o movimento. Traçadas por **regressão linear
sobre os pivôs**, não ligando os extremos: ligar extremos deixa a reta refém de um único
candle de exagero, enquanto a regressão usa todos os toques e produz a linha que o mercado
de fato respeitou.

Três exigências para a figura contar como canal:

| Critério | Valor | Por quê |
|---|---|---|
| toques mínimos | 4 | duas retas passam por dois pontos quaisquer; só do terceiro toque de cada lado a figura deixa de ser desenho livre |
| paralelismo | inclinações divergindo ≤ 45% | acima disso é cunha ou triângulo, e chamar de canal daria alvos errados |
| largura | entre 1 e 12 ATR | estreito demais é ruído; largo demais deixou de ser canal e virou "o gráfico" |

**Classificação:** a inclinação é comparada ao ATR por candle, não medida em pontos. Em
ativo volátil, subir 10 pontos por candle é lateral; em ativo parado, é tendência.

- ascendente: inclinação > +0,06 ATR/candle
- descendente: inclinação < −0,06 ATR/candle
- lateral: entre os dois

### Dois critérios que R² sozinho não cobre

**Contenção ≥ 90% dos fechamentos.** Com poucos pivôs — 5 a 7 numa janela — até um passeio
aleatório produz regressão com R² de 0,90: qualquer punhado de pontos se alinha
razoavelmente por acaso. O que o aleatório **não** faz é ficar dentro das linhas entre os
pivôs. Medido na série sintética de controle: R² 0,91/0,75 mas contenção de 86,8% — é a
contenção que rejeita.

**R² degenera em dados horizontais.** Ele mede *quanta variância a reta explica*, e num
canal lateral perfeito não há variância a explicar: o R² despenca mesmo com ajuste
impecável. Por isso o ajuste é aceito por dois caminhos — R² alto **ou** resíduo abaixo de
0,35 ATR. Sem a segunda cláusula, a figura mais limpa que existe seria rejeitada.

### Canal é figura de timeframe maior

Medido em 2 anos de WIN da XP, varrendo janelas de 120 candles:

| Timeframe | Janelas com canal |
|---|---|
| 5 minutos | **3,6%** |
| 60 minutos | **31,4%** |

Em 5 minutos o preço é ruidoso demais para os pivôs se alinharem — 61% das rejeições são
por ajuste ruim, ou seja, os pontos simplesmente não formam reta. Em 60 minutos, quase um
terço do tempo há canal limpo.

Isso não é limitação do detector, é propriedade do mercado, e bate com a prática: ninguém
desenha canal em gráfico de 5 minutos. O produto diz isso na tela em vez de deixar o painel
vazio sem explicação.

## Rompimento

**Fechamento** além da borda, com folga mínima de 0,35 ATR.

Exigir fechamento e não pavio é o ponto: um pavio que fura a linha e volta é o canal sendo
**respeitado**, não rompido — é justamente o toque que valida a borda. E a folga mínima
existe porque rompimento raso é ruído de spread.

Rompimentos consecutivos na mesma direção são o mesmo evento; só o primeiro de cada
sequência conta.

## Zonas de oferta e demanda

Regiões onde o preço reagiu repetidamente. **Faixa, nunca linha.**

O preço não reage num tick exato, reage numa região. Desenhar linha dá a falsa precisão de
"o nível é 63.400" quando na verdade é "entre 63.350 e 63.450" — e o operador que coloca
stop confiando nessa precisão é estopado por 10 pontos de nada.

O agrupamento usa **ATR como raio**: em ativo volátil, "o mesmo preço" é uma faixa mais
larga. Um pivô isolado é acidente; três no mesmo preço é região com ordem.

- **oferta** — agrupamento de topos: onde apareceu vendedor
- **demanda** — agrupamento de fundos: onde apareceu comprador

## Linha de tendência

A que liga os fundos numa alta, os topos numa baixa. Escolhida pela inclinação absoluta
maior — é a que melhor descreve o movimento dominante.

Numa alta, os fundos ascendentes são a linha que **sustenta** o preço, e é essa que o
operador desenha.

## Como isso vira produto

O gráfico do Cronos Trader renderiza tudo anotado, no espírito das ideias publicadas no
TradingView:

- canal com as duas bordas traçadas e o tipo rotulado
- pivôs marcados
- rompimentos rotulados com a força em ATR
- zonas de oferta e demanda como faixas
- linha de tendência tracejada
- entrada, stop e alvo do sinal selecionado, com rótulo no eixo de preço

E alimenta a **tese**, que ganha frases como "rompeu o canal descendente" em vez de citar
só o padrão de candle.

## O que ainda não faz

- **Triângulos e cunhas** — hoje são simplesmente rejeitados pelo teste de paralelismo.
  Reconhecê-los explicitamente daria alvos diferentes (a altura da figura projetada do
  rompimento), e é trabalho pendente.
- **Ombro-cabeça-ombro, topos e fundos duplos** — figuras de reversão que os pivôs já
  tornam detectáveis; falta a regra e, principalmente, o estudo empírico que mostre se
  funcionam em WIN/WDO antes de virarem peso no score.
