# Padrões de reversão

Fonte: ebook p.7–19. O grosso do catálogo.

Todo padrão aqui precisa de uma tendência anterior para reverter. **Em mercado lateral,
reversão não existe** — não há o que virar, e o motor veta esses sinais quando o ADX
indica ausência de tendência.

Priors: `0.70` = ebook diz "alta confiabilidade" · `0.50` = não qualificado ·
`0.35` = ebook diz "baixa confiabilidade".

---

## Harami de Alta
`harami_alta` · 2 candles · tendência de **baixa** · prior 0.35 · p.7

**Geometria** — corpo vermelho longo, seguido de corpo verde inteiramente dentro dele.

**Leitura** — "mulher grávida": mãe vermelha, bebê verde. A venda perdeu amplitude de um
candle para o outro. Não é reversão confirmada — é **perda de força**.

**Cuidado** — o ebook é explícito sobre a fragilidade: *"na prática você perceberá que
isso muitas vezes não acontece… não confie cegamente nele"*. E completa: muitas vezes a
tendência não reverte, apenas perde força e entra em consolidação.

## Harami de Baixa
`harami_baixa` · 2 candles · tendência de **alta** · prior 0.35 · p.7

Espelho: corpo verde longo, corpo vermelho dentro dele.

---

## Martelo
`martelo` · 1 candle · tendência de **baixa** · prior 0.35 · p.8

**Geometria** — corpo pequeno no topo do range, sombra inferior longa (≥ 2× o corpo),
pouca ou nenhuma sombra superior. **A cor do corpo é irrelevante** — o ebook insiste.

**Leitura** — o fundo foi testado e rejeitado. Apareceu comprador agressivo lá embaixo.

## Enforcado
`enforcado` · 1 candle · tendência de **alta** · prior 0.35 · p.8

**Mesma geometria do martelo.** O ebook: *"o candle é morfologicamente igual ao enforcado,
o que muda é a posição no gráfico"*.

**Leitura** — num topo, a mesma sombra significa outra coisa: houve venda forte durante o
período e ela foi absorvida. O alerta é ter aparecido vendedor agressivo no topo.

## Martelo Invertido
`martelo_invertido` · 1 candle · tendência de **baixa** · prior 0.35 · p.9

**Geometria** — corpo pequeno na base, sombra **superior** longa, pouca sombra inferior.

**Leitura** — apareceu comprador testando acima, mesmo dentro da queda.

## Estrela Cadente
`estrela_cadente` · 1 candle · tendência de **alta** · prior 0.35 · p.9

Mesma geometria do martelo invertido, no topo. O preço subiu e foi devolvido inteiro.

> ⚠️ O ebook chama esta formação de "enforcado" (ERRATA item 5). O nome correto é estrela
> cadente — o enforcado tem sombra **inferior**. A tabela completa:
>
> | Nome | Tendência | Sombra longa |
> |---|---|---|
> | Martelo | baixa | inferior |
> | Enforcado | alta | inferior |
> | Martelo invertido | baixa | superior |
> | Estrela cadente | alta | superior |

---

## Cinto de Segurança de Alta
`cinto_seguranca_alta` · 1 candle · tendência de **baixa** · prior 0.35 · p.9

**Geometria** — candle de alta com corpo grande cuja **abertura coincide com a mínima**
(sem sombra inferior); sombra superior pequena.

**Leitura** — não houve um único momento de venda: abriu no fundo e só subiu. O ebook
resume como *"basicamente um Marubozu verde no fim de uma tendência de baixa"*.

## Cinto de Segurança de Baixa
`cinto_seguranca_baixa` · 1 candle · tendência de **alta** · prior 0.35 · p.9

Abertura coincide com a máxima: vendeu do primeiro ao último negócio.

---

## Engolfo de Alta
`engolfo_alta` · 2 candles · tendência de **baixa** · prior 0.50 · p.9

**Geometria** — corpo verde cobrindo inteiramente o corpo vermelho anterior. O ebook:
*"o tamanho das sombras não é importante"* — o que conta é a cobertura dos corpos.

**Leitura** — toda a venda do período anterior foi recomprada, e ainda sobrou. Troca de
mão visível.

**Cuidado** — quanto maior a folga da cobertura, mais forte o sinal. Um engolfo que cobre
por 5% e outro que cobre por 300% não são o mesmo sinal; o motor mede isso na `forca`.

## Engolfo de Baixa
`engolfo_baixa` · 2 candles · tendência de **alta** · prior 0.50 · p.9

---

## Estrela da Manhã
`estrela_manha` · 3 candles · tendência de **baixa** · prior 0.50 · p.10

**Geometria** — (1) vermelho de corpo longo; (2) corpo pequeno **abaixo dos corpos dos
dois vizinhos**, cor irrelevante; (3) verde fechando **acima da metade do corpo do
primeiro**.

**Leitura** — a estrela do meio é o instante em que a venda parou de conseguir empurrar.
O terceiro candle é a confirmação: sem ele retomar mais da metade, não há padrão.

## Estrela da Noite
`estrela_noite` · 3 candles · tendência de **alta** · prior 0.50 · p.10

Espelho: verde longo, estrela isolada acima, vermelho fechando abaixo da metade.

---

## Pombo-correio
`pombo_correio` · 2 candles · tendência de **baixa** · prior 0.35 · p.11

**Geometria** — Harami com os dois candles **da mesma cor** (dois vermelhos).

**Leitura** — a queda continuou, mas com muito menos amplitude. O ebook comenta que muitos
autores chamam tudo de Harami, *"no mínimo sensato, afinal a interpretação é a mesma"*. No
motor ficam separados para o backtest poder medir se a cor do bebê muda algo na prática.

## Falcão Descendente
`falcao_descendente` · 2 candles · tendência de **alta** · prior 0.35 · p.11 · *espelhado*

Dois verdes no topo, o segundo dentro do primeiro. O ebook descreve só a versão de baixa;
este é o espelho inferido (ERRATA item 9).

---

## Alinhamento na Baixa
`alinhamento_baixa` · 2 candles · tendência de **baixa** · prior 0.35 · p.11

**Geometria** — dois vermelhos de corpo longo com **fechamentos coincidentes**.
Preferencialmente sem sombra inferior, mas o ebook diz que é raro e nem todos os autores
exigem.

**Leitura** — duas tentativas de furar o mesmo nível, duas falhas. Um piso que o vendedor
não conseguiu romper.

**Cuidado** — o ebook manda aguardar um terceiro candle: *"muitas vezes a tendência
continua. Ou seja, é um padrão de baixa confiabilidade"*.

## Alinhamento na Alta
`alinhamento_alta` · 2 candles · tendência de **alta** · prior 0.35 · p.12

Dois verdes longos fechando no mesmo preço: um teto testado duas vezes.

> ⚠️ O ebook pede coincidência de **abertura** nesta metade do par, e de fechamento na
> outra (ERRATA item 11). O motor usa fechamento nas duas — com candles verdes sem sombra
> superior, é o fechamento que marca o teto testado.

---

## Linha de Reunião de Alta
`linha_reuniao_alta` · 2 candles · tendência de **baixa** · prior 0.35 · p.12

**Geometria** — vermelho longo e verde longo terminando **no mesmo preço**.

**Leitura** — diferente do engolfo: aqui o verde não cobre o vermelho, apenas o encontra.
Por isso o ebook manda aguardar o terceiro candle antes de confirmar.

## Linha de Reunião de Baixa
`linha_reuniao_baixa` · 2 candles · tendência de **alta** · prior 0.35 · p.12

---

## Sanduíche de Graveto de Alta
`sanduiche_graveto_alta` · 3 candles · tendência de **baixa** · prior 0.50 · p.12

**Geometria** — (1) vermelho de força; (2) verde fechando acima do fechamento anterior,
com a mínima não ultrapassando esse fechamento; (3) vermelho de força engolfando o segundo
e fechando **no mesmo nível do primeiro**.

**Leitura** — o mercado voltou duas vezes exatamente ao mesmo preço e parou. O ebook lê o
nível repetido como *"um suporte importante"* — e é essa a informação aproveitável, mais
que a reversão em si.

## Sanduíche de Graveto de Baixa
`sanduiche_graveto_baixa` · 3 candles · tendência de **alta** · prior 0.50 · *espelhado*

---

## 3 Estrelas do Sul
`tres_estrelas_sul` · 3 candles · tendência de **baixa** · prior 0.50 · p.13

**Geometria** — três vermelhos com corpos **estritamente decrescentes**: (1) com sombra
inferior longa; (2) abrindo abaixo da abertura anterior mas com mínima acima da mínima
anterior; (3) marubozu vermelho de corpo pequeno, dentro do segundo.

**Leitura** — a queda continua, mas cada vez com menos convicção. O ebook: *"os corpos
estão ficando menores, indicando perda de momentum da força vendedora"*. É exaustão, não
virada — a reversão ainda precisa de confirmação.

## Bloqueio Avançado
`bloqueio_avancado` · 3 candles · tendência de **alta** · prior 0.50 · p.13

**Geometria** — três verdes com máximas e mínimas mais altas, **porém** corpos cada vez
menores e sombras superiores cada vez maiores.

**Leitura** — na tela parece força: o preço segue fazendo máximas mais altas. O que
denuncia a fraqueza é a proporção — cada candle sobe menos e é rejeitado mais no topo.
*"Lembre-se: sombras longas representam rejeição do preço."*

---

## Estrela Tripla de Fundo
`estrela_tripla_fundo` · 3 candles · tendência de **baixa** · prior 0.50 · p.13 · *exige gap*

**Geometria** — três dojis consecutivos, o do meio isolado **abaixo** das mínimas dos
outros dois, formando gap dos dois lados.

**Cuidado** — o ebook classifica como *"pouco comum"*. Em intraday, mais raro ainda: gap
estrito quase não existe dentro do pregão.

## Estrela Tripla de Topo
`estrela_tripla_topo` · 3 candles · tendência de **alta** · prior 0.50 · p.13 · *exige gap*

---

## 3 Rios de Alta
`tres_rios_alta` · 3 candles · tendência de **baixa** · prior 0.50 · p.14

**Geometria** — (1) vermelho de corpo longo; (2) martelo; (3) verde com corpo abaixo do
corpo do martelo, sem furar as mínimas anteriores.

**Cuidado** — o ebook classifica como *"padrão raro"*.

## 3 Rios de Baixa
`tres_rios_baixa` · 3 candles · tendência de **alta** · prior 0.50 · *espelhado*

---

## 2 Corvos
`dois_corvos` · 3 candles · tendência de **alta** · prior 0.50 · p.14 · *exige gap*

**Geometria** — (1) verde; (2) vermelho de corpo pequeno abrindo em gap de alta;
(3) vermelho cuja máxima não supera a abertura do segundo e que fecha **abaixo do
fechamento do primeiro**.

**Leitura** — o gap de alta é a euforia; os dois vermelhos são a devolução. Fechar abaixo
do fechamento do primeiro candle apaga toda a alta anterior.

---

## Interrupção de Alta
`interrupcao_alta` · 5 candles · tendência de **baixa** · prior 0.50 · p.14 · *exige gap*

**Geometria** — quatro candles afundando em gap, e um quinto verde longo que abre acima da
abertura anterior, fecha acima da abertura do segundo, **mas não fecha o gap**.

**Cuidado** — o ebook chama de *"raríssimos"*. Ficam no catálogo porque o custo de um
detector a mais é nulo e o backtest precisa **contar** a raridade em vez de assumi-la.

## Interrupção de Baixa
`interrupcao_baixa` · 5 candles · tendência de **alta** · prior 0.50 · p.14 · *exige gap*

---

## Escada de Alta
`escada_alta` · 5 candles · tendência de **baixa** · prior 0.50 · p.15

**Geometria** — três vermelhos de força descendo em degraus, um martelo invertido, e um
verde de força fechando acima da abertura do terceiro.

**Atalho prático** que o próprio ebook dá: *"preste atenção no fato de ser um martelo
invertido/enforcado seguido de um importante candle de força"*. É essa a assinatura; o
resto é enquadramento.

## Escada de Baixa
`escada_baixa` · 5 candles · tendência de **alta** · prior 0.50 · p.15

Três verdes de força **subindo** em degraus, martelo invertido, vermelho de força fechando
abaixo da abertura do terceiro.

> ⚠️ O ebook diz "tendência de baixa" e "aberturas e fechamentos cada vez menores" para os
> três candles verdes — incoerente (ERRATA item 3). O motor implementa o espelho correto.

---

## Linha de Perfuração
`linha_perfuracao` · 2 candles · tendência de **baixa** · **prior 0.70** · p.16

**Geometria** — (1) vermelho de corpo longo; (2) verde grande que **abre abaixo da mínima
anterior** e fecha **acima da metade do corpo** do primeiro, sem chegar a engolfá-lo.

**Leitura** — o verde abre no pior lugar possível e ainda assim devolve mais de metade da
queda. É a definição de comprador agressivo.

**Por que importa aqui** — o ebook chama de *"simples e de alta confiabilidade"*, e é dos
poucos padrões robustos em intraday: o gap é medido só na **abertura**, não no range
inteiro, então funciona mesmo com preço contínuo.

## Nuvem Negra
`nuvem_negra` · 2 candles · tendência de **alta** · **prior 0.70** · p.16

Espelho: verde longo, vermelho abrindo acima da máxima e fechando abaixo da metade.

---

## Chute de Alta
`chute_alta` · 2 candles · **qualquer tendência** · prior 0.35 · p.16 · *exige gap*

**Geometria** — dois marubozu longos, o primeiro vermelho e o segundo verde, abrindo em
gap de alta acima do corpo do anterior.

**Único par do catálogo sem tendência exigida.** O ebook: *"a tendência anterior à sua
formação não é importante… pode ser um padrão de reversão ou de continuação"*.

**Cuidado** — baixa confiabilidade, e em intraday depende inteiramente da tolerância de
gap configurada. É um bom canário para calibração.

## Chute de Baixa
`chute_baixa` · 2 candles · **qualquer tendência** · prior 0.35 · p.17 · *exige gap*

---

## Bebê Abandonado de Alta
`bebe_abandonado_alta` · 3 candles · tendência de **baixa** · **prior 0.70** · p.17 · *exige gap*

**Geometria** — (1) vermelho de força; (2) doji isolado por gap **abaixo das mínimas** dos
dois vizinhos; (3) verde de força.

**Leitura** — o doji não encosta em nenhum vizinho, daí "abandonado". Capitulação seguida
de retomada imediata.

**Cuidado** — raro e de alta confiabilidade segundo o ebook. É o padrão onde a tolerância
de gap mais importa: com folga demais, deixa de ser abandonado e vira outra coisa.

## Bebê Abandonado de Baixa
`bebe_abandonado_baixa` · 3 candles · tendência de **alta** · **prior 0.70** · p.17

Verde de força, doji isolado acima das máximas, vermelho de força.

> ⚠️ O ebook diz que o primeiro candle é **vermelho**, copiando o texto da versão de alta
> (ERRATA item 1). Num topo, o primeiro candle é o último impulso comprador — tem que ser
> verde.

---

## 3 Por Dentro de Alta
`tres_por_dentro_alta` · 3 candles · tendência de **baixa** · prior 0.50 · p.16

**Geometria** — Harami de alta seguido de um verde de corpo grande fechando **acima da
máxima dos dois anteriores**.

**Leitura** — o ebook nota o óbvio e o importante: *"obviamente tem maior confiabilidade
do que o Harami, afinal existe um terceiro candle reforçando a possibilidade de reversão"*.

## 3 Por Dentro de Baixa
`tres_por_dentro_baixa` · 3 candles · tendência de **alta** · prior 0.50 · p.16

## 3 Por Fora de Alta
`tres_por_fora_alta` · 3 candles · tendência de **baixa** · prior 0.50 · p.18

Engolfo de alta confirmado por um terceiro candle de alta. Mesma lógica: mais confiável
que o engolfo sozinho.

## 3 Por Fora de Baixa
`tres_por_fora_baixa` · 3 candles · tendência de **alta** · prior 0.50 · *espelhado*

---

## 3 Soldados de Alta
`tres_soldados` · 3 candles · **qualquer tendência** · prior 0.50 · p.18

**Geometria** — três candles de alta consecutivos, corpo grande, pouca ou nenhuma sombra,
fechamentos ascendentes.

**Leitura** — o ebook: *"o preço deve seguir na mesma direção dos 3 candles, independente
da tendência anterior"*. Portanto:
- em tendência de **alta** → continuidade
- em tendência de **baixa** → reversão

Quem resolve o significado é a confluência, não o detector.

## 3 Corvos de Baixa
`tres_corvos` · 3 candles · **qualquer tendência** · prior 0.50 · p.18

Três candles de **baixa** consecutivos, corpo grande, fechamentos descendentes.

> ⚠️ O ebook descreve este padrão como *"formado por 3 candles de ALTA consecutivos"*,
> repetindo o texto dos 3 Soldados (ERRATA item 2). Três corvos são, por definição, três
> candles de baixa.

---

## Bebê Engolido de Alta
`bebe_engolido_alta` · 4 candles · tendência de **baixa** · **prior 0.70** · p.19 · *exige gap*

**Geometria** — (1) e (2) marubozu vermelhos; (3) martelo invertido abrindo em gap de
baixa; (4) marubozu vermelho **engolfando completamente** o martelo invertido.

**Leitura — contraintuitiva e vale ler com atenção.** O último candle é vermelho e o sinal
é de **alta**. O ebook explica: o martelo invertido abriu em gap de baixa e subiu quase
até a máxima anterior; então o quarto candle abre num **forte gap de alta**. A força
compradora está nos gaps, não na cor dos corpos. Espera-se um quinto candle verde.

## Bebê Engolido de Baixa
`bebe_engolido_baixa` · 4 candles · tendência de **alta** · **prior 0.70** · p.19 · *exige gap*

Dois marubozu verdes, um enforcado, e um quarto verde engolfando-o. Mesmo raciocínio
invertido.
