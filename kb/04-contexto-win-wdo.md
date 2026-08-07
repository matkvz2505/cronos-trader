# Contexto operacional de WIN e WDO

Este arquivo cobre o que **o ebook não cobre**. Ele ensina a ler candles; não ensina a
operar mini-índice e mini-dólar. A diferença entre as duas coisas é onde a conta ganha ou
perde dinheiro.

---

## Os dois contratos

| | WIN (mini-índice) | WDO (mini-dólar) |
|---|---|---|
| Referência | Ibovespa futuro | Dólar futuro, US$ 10.000 |
| Tick mínimo | 5 pontos | 0,5 ponto |
| **Valor do ponto** | **R$ 0,20** | **R$ 10,00** |
| Valor do tick | R$ 1,00 | R$ 5,00 |
| Vencimento | meses **pares** (G J M Q V Z) | **mensal** (todos os meses) |
| Data de vencimento | quarta-feira mais próxima do dia 15 | primeiro dia útil do mês |

**Um ponto de WDO vale cinquenta vezes um ponto de WIN.** É o erro de dimensionamento mais
caro possível: a mesma "distância de 100 pontos" custa R$ 20 num e R$ 1.000 no outro.

> Confira margem e valor do ponto na B3 antes de operar valendo — contratos mudam.

## Rollover — a armadilha silenciosa

Contratos vencem. Se a série misturar `WINQ26` e `WINV26` sem tratar a virada, aparece um
salto artificial de centenas de pontos, e **todo padrão de gap detectado ali é falso**.
Isso corrompe estatística sem gerar erro nenhum.

- **Backtest** → símbolo contínuo ajustado (`WIN$N`, `WDO$N`)
- **Tempo real** → contrato cheio, onde está a liquidez
- **Sempre** → descartar a janela de ±3 dias do vencimento

---

## O horário é praticamente um indicador

WIN e WDO mudam tanto de caráter ao longo do dia que a hora do sinal carrega informação
comparável à do próprio padrão.

| Janela (Brasília) | Caráter | Como operar |
|---|---|---|
| 09:00–10:00 | abertura: volatilidade alta, muito ruído, stops caçados | exigir padrão mais forte |
| 10:00–12:00 | tendência mais limpa, direção definida | **janela preferida** |
| 12:00–14:00 | liquidez cai, lateraliza, spread abre | evitar; alvo não paga custo |
| 14:00–16:00 | abertura dos EUA traz direção | **janela preferida** |
| 16:00–17:30 | movimento final, ajuste de posição | normal |
| após 17:30 | ajuste e fechamento | **não abrir posição nova** |

Horário de verão americano desloca a janela das 14h em uma hora. Leilões e vencimento de
opções (terceira sexta-feira) distorcem o dia inteiro.

## WIN e WDO não se movem sozinhos

| Ativo | Correlação dominante | Efeito |
|---|---|---|
| WIN | futuro do **S&P 500** (`ES=F`) | segue quase tick a tick no intraday |
| WIN | peso de PETR e VALE | petróleo e minério puxam o índice |
| WDO | **índice do dólar** (DXY) | DXY subindo empurra WDO |
| WDO | Selic vs. juros americanos | define o regime de médio prazo |

Um sinal de compra em WIN contra um S&P despencando é um sinal pior. No motor isso entra
como **penalidade de confluência, nunca como veto** — correlação intraday quebra, e vetar
por ela transformaria uma dica em camisa de força.

## Agenda econômica invalida padrão gráfico

Payroll, CPI americano, decisão do Copom e do Fed produzem picos de volatilidade em que
nenhuma leitura de candle sobrevive. A regra é simples: **não abrir posição nova na janela
de ±15 minutos do evento.**

Não é conservadorismo — é reconhecer que naquele instante o preço responde a uma
informação que não está no gráfico.

---

## O que o ebook não diz e o motor precisa saber

**Gap quase não existe em intraday.** O ebook pensa em gráfico diário, onde o pregão fecha
e reabre. Dentro do pregão o preço é contínuo, e os oito padrões que exigem gap (Bebê
Abandonado, Chute, Tasuki, Estrela Tripla, Linhas Brancas, Interrupção) praticamente não
aparecem em 5 minutos. Ver ERRATA item 10.

**Custo mata estratégia de alvo curto.** Corretagem, emolumento e slippage nas duas pontas.
Uma estratégia de 5 minutos com 55% de acerto pode perder dinheiro depois dos custos — e
isso precisa aparecer no backtest, não na corretora.

**Padrão sozinho não basta, e o ebook concorda.** Ele classifica boa parte dos padrões como
de baixa confiabilidade. O edge não está em detectar a formação; está em exigir que ela
aconteça **num lugar que já importava** — retração de Fibonacci, média móvel relevante,
suporte/resistência, máxima do dia anterior. Quando três dessas leituras apontam para o
mesmo preço, existe ordem grande no book, e aí o padrão vira informação.

**O tamanho da posição importa mais que a entrada.** Risco fixo por operação, limite de
perda diária, teto de trades por dia. Over-trading é a causa mais comum de ruína em day
trade, e nenhum score alto justifica o sétimo trade do dia.

---

## Como um agente deve falar sobre um sinal

- Cite a **confiabilidade medida** pelo backtest, não o prior do ebook. Se não houver
  amostra suficiente, diga que não há.
- Nomeie a **invalidação**: em que preço a leitura estará errada. É o stop, e é a parte
  mais útil da análise.
- Diga o **contexto**, não só o padrão: qual tendência, qual janela do pregão, o que os
  timeframes maiores estão dizendo.
- Nunca prometa resultado. Mini-índice e mini-dólar são alavancados e a perda pode superar
  o capital depositado.
