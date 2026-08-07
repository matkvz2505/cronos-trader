# Errata do ebook — divergências entre a fonte e o código

O `Ebook-PADROES-DE-CANDLESTICK.pdf` é a fonte das regras geométricas do motor. Ao transcrever
os ~40 padrões para código, encontrei erros de copy-paste e ambiguidades no texto original.

Este arquivo existe porque **o código diverge do ebook em alguns pontos, de propósito**. Sem
este registro, a próxima pessoa que comparar os dois vai achar que o código está errado.

Cada detector em `ai/trader_ai/padroes/` referencia a página do ebook. Onde há divergência, o
docstring aponta para a entrada correspondente aqui.

---

## Erros claros (o código corrige)

### 1. Bebê Abandonado de baixa — primeiro candle com a cor errada
**Ebook p.17.** O texto do padrão de baixa diz:

> "Formado por 3 candles numa tendência de alta: Primeiro é um candle de força **vermelho**…"

Num topo, o primeiro candle é o último impulso de **alta** — tem que ser verde. O parágrafo
inteiro foi copiado da versão de alta e só o contexto de tendência foi trocado. O terceiro
candle ("de força vermelho") está certo.

**Código:** primeiro candle **verde** de força, doji com gap acima das máximas, terceiro
candle vermelho de força.

### 2. "3 corvos de baixa" descrito como três candles de alta
**Ebook p.18.** O bloco do padrão de baixa repete literalmente o texto dos 3 soldados:

> "Formado por 3 candles de **alta** consecutivos, com corpo grande e pouca ou nenhuma sombra."

Três corvos são, por definição, três candles de **baixa** consecutivos com fechamentos
descendentes. As duas conclusões que seguem no ebook ("se numa tendência de baixa, sugerem
continuidade") só fazem sentido com candles vermelhos.

**Código:** três candles vermelhos consecutivos, corpo grande, fechamentos descendentes.

### 3. Escada de Baixa — tendência e sequência invertidas
**Ebook p.15.** Duas falhas no mesmo bloco:

> "Escada Baixa: É composto por 5 candles numa tendência de **baixa**: Os 3 primeiros são
> candles de força **verdes**, com aberturas e fechamentos cada vez **menores**…"

Uma escada de baixa é a reversão de uma tendência de **alta**, e três candles verdes de força
formam uma escada **ascendente** — aberturas e fechamentos cada vez **maiores**. O "menores"
veio da versão de alta.

**Código:** tendência de alta, três verdes ascendentes, quarto candle martelo invertido, quinto
vermelho de força fechando abaixo da abertura do terceiro.

### 4. Gap Tasuki de baixa — terceiro candle não foi espelhado
**Ebook p.20.** O padrão de baixa repete a redação do de alta:

> "O terceiro candle é verde, fechando **abaixo da abertura do segundo**, mas não chega a
> fechar o gap (fica **acima do fechamento do primeiro** candle)."

No Tasuki de baixa o gap é para baixo, então o terceiro candle (verde, a correção) fecha
**acima da abertura do segundo** e permanece **abaixo do fechamento do primeiro** — é isso
que caracteriza o gap não preenchido.

**Código:** espelho correto do Tasuki de alta.

### 5. "Martelo Invertido / Enforcado" — o segundo nome está trocado
**Ebook p.9.** A seção descreve corpo pequeno com **sombra superior longa** e o próprio texto
admite: *"O candlé é morfologicamente igual à estrela cadente."* Exato — mas então o título
deveria ser **"Martelo Invertido / Estrela Cadente"**. O *enforcado* tem sombra **inferior**
longa e já foi coberto na p.8.

A família completa, para não restar dúvida:

| Nome | Tendência anterior | Sombra longa | Sinal |
|---|---|---|---|
| Martelo | baixa | inferior | reversão de alta |
| Enforcado | alta | inferior | reversão de baixa |
| Martelo invertido | baixa | superior | reversão de alta |
| Estrela cadente | alta | superior | reversão de baixa |

**Código:** os quatro nomes existem separadamente, cada um com sua tendência exigida.

### 6. Blocos duplicados de "tendência de alta / de baixa"
**Ebook p.9.** O mesmo parágrafo de geometria aparece duas vezes, uma sob "tendência de alta"
e outra sob "tendência de baixa", sem diferença no texto. Resolvido pela tabela do item 5.

### 7. "Morubozu"
**Ebook p.9**, duas ocorrências. Grafia correta: **Marubozu**. Cosmético, mas o identificador
no código é `marubozu`.

---

## Ambiguidades (o código escolhe uma leitura e documenta)

### 8. Linhas brancas lado a lado — onde medir o gap
**Ebook p.22.** A versão de baixa diz que o segundo candle é verde e *"seu fechamento fica
abaixo da mínima do primeiro (gap)"*. Medir gap pelo **fechamento** é incomum e conflita com a
versão de alta, que mede pela **abertura/mínima**.

**Código:** o gap é sempre medido na **abertura** do segundo candle contra o extremo do
primeiro, nas duas direções. Consistente com o resto do catálogo.

### 9. Padrões descritos em uma direção só
O ebook detalha apenas um lado destes; o espelho foi implementado por simetria e está marcado
com `derivado_por_simetria=True` no catálogo:

- **Sanduíche de Graveto** — só a versão de alta (p.12)
- **3 Rios** — só "3 Rios de Alta" (p.14)
- **3 por fora** — só "3 por fora de alta" (p.18)
- **Falcão Descendente / Pombo-correio** — só a versão em tendência de baixa (p.11)

### 10. "Gap" em intraday de 5 minutos praticamente não existe
Não é erro do ebook — é uma limitação de aplicá-lo ao nosso caso. O ebook foi escrito pensando
em gráfico diário, onde o pregão fecha e reabre. No WIN/WDO em 5 minutos, dentro do pregão, o
preço é contínuo: **gap estrito quase nunca ocorre**, e todo padrão que exige gap (Bebê
Abandonado, Chute, Tasuki, Estrela Tripla, Linhas Brancas, Interrupção) nunca dispararia.

**Código:** `Limiares.tolerancia_gap` permite que um "gap" seja satisfeito por uma
quase-sobreposição — a diferença entre os extremos precisa ser maior que `-tolerancia * ATR`
em vez de estritamente positiva. Padrão: estrito no diário, tolerante no intraday. Este é o
parâmetro mais sensível do motor e o backtest deve calibrá-lo por timeframe.

### 11. Alinhamento na alta — coincidência medida na abertura, não no fechamento
**Ebook p.11–12.** As duas metades do par não são espelhos uma da outra:

> Alinhamento na **baixa**: "Ambos vermelhos com corpos longos; **Fechamento** dos dois deve
> coincidir. Preferencialmente os dois sem sombra inferior."
>
> Alinhamento na **alta**: "Ambos verdes com corpos longos; **Abertura** dos dois deve
> coincidir. Preferencialmente os dois sem sombra superior."

A lógica do padrão é um **nível testado duas vezes e rejeitado**. Num candle vermelho sem
sombra inferior, esse nível é o fechamento. Num candle verde sem sombra superior, o nível é
igualmente o **fechamento** — a abertura fica na base do corpo, longe do topo que está sendo
testado. Exigir coincidência de abertura marcaria dois candles que *começaram* juntos, o que
não diz nada sobre resistência.

**Código:** coincidência de **fechamento** nas duas direções.

---

## O ebook é honesto sobre confiabilidade — e isso é usado

Vale registrar o que o ebook **acerta** e que o motor aproveita: ele classifica explicitamente
vários padrões como pouco confiáveis, em vez de vender todos como infalíveis.

> *"Na teoria é um padrão de reversão de tendência. Mas na prática você perceberá que isso
> muitas vezes não acontece. Portanto, não confie cegamente nele e tente analisar o contexto."*
> — sobre o Harami, p.7

Esses julgamentos viram o campo `confiabilidade_ebook` do catálogo, usado como **peso inicial**
(prior). Assim que houver histórico suficiente, o backtest substitui esse prior pela taxa de
acerto medida em WIN/WDO — `confiabilidade_medida`. O prior nunca é o número mostrado na tela
como se fosse evidência.

| Classificação do ebook | Prior | Padrões |
|---|---|---|
| "alta confiabilidade" | 0.70 | Linha de Perfuração, Nuvem Negra, Bebê Abandonado, Bebê Engolido |
| não qualificado | 0.50 | Engolfo, Estrela da manhã/noite, 3 por dentro, 3 por fora, 3 soldados/corvos, Tasuki, … |
| "baixa confiabilidade" | 0.35 | Martelo/Enforcado, Martelo Invertido, Cinto de Segurança, Harami, Alinhamento, Chute, Linha de Separação, Strike |
| "indecisão", isolados | 0.25 | Doji, Spinning Top, Marubozu isolado |
