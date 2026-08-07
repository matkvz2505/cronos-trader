# Padrões isolados

Fonte: ebook p.5–6.

> *"Tem confiabilidade baixa, como todos os padrões de candlestick isolados."* — ebook, p.6
>
> *"São mais importantes quando formam padrões de 2 ou mais candlesticks."* — ebook, p.5

Todos entram no motor com prior **0.25**. Existem no catálogo por dois motivos: são blocos
de construção dos padrões compostos, e marcá-los no gráfico é informação visual legítima
para quem opera olhando a tela. **Nenhum deles deveria gerar sinal sozinho.**

---

## Doji
`doji` · isolado · neutra · 1 candle · qualquer contexto · prior 0.25 · p.5

**Geometria** — corpo desprezível: abertura e fechamento praticamente no mesmo preço
(corpo ≤ 10% da amplitude).

**Leitura** — empate. Compradores e vendedores se anularam no período. Não diz para onde
o preço vai; diz que ninguém sabe.

**Cuidado** — dojis são muito comuns, principalmente em baixa liquidez. Um doji no
meio-dia do WIN é falta de gente negociando, não indecisão informativa.

---

## Doji Libélula
`doji_libelula` · isolado · alta · 1 candle · **tendência de baixa** · prior 0.25 · p.5

**Geometria** — abertura, fechamento e máxima praticamente iguais; sombra inferior longa.

**Leitura** — o preço afundou durante o período e voltou inteiro. Rejeição forte do nível
mais baixo. O ebook: *"pode representar uma reversão após longa tendência de baixa"*.

**Cuidado** — precisa da tendência de baixa anterior. Uma libélula em lateralização é só
um teste de fundo de range.

---

## Doji Lápide
`doji_lapide` · isolado · baixa · 1 candle · **tendência de alta** · prior 0.25 · p.5

**Geometria** — espelho da libélula: corpo colado na mínima, sombra superior longa.

**Leitura** — o preço subiu e foi devolvido inteiro. O ebook: *"tem mais relevância se
surgir no final de uma tendência de alta"*.

---

## Marubozu de Alta
`marubozu_alta` · isolado · alta · 1 candle · qualquer contexto · prior 0.25 · p.5

**Geometria** — corpo grande ocupando quase toda a amplitude, praticamente sem sombras. O
ebook admite que *"na prática podem ter sombra mínima"*.

**Leitura** — os compradores mandaram do primeiro ao último negócio. Não houve um momento
de dúvida no período.

**Duas situações onde importa**, e elas são opostas:
- em tendência de **alta** → a tendência tem força e deve se manter (continuação)
- depois de um movimento longo de **baixa** → força compradora surgindo, possível reversão

Quem resolve qual das duas é a camada de confluência do motor, não o detector.

---

## Marubozu de Baixa
`marubozu_baixa` · isolado · baixa · 1 candle · qualquer contexto · prior 0.25 · p.6

**Geometria** — espelho do anterior: corpo vermelho grande, sem sombras.

**Leitura** — mesma lógica invertida. Em tendência de baixa, continuação; depois de alta
longa, possível reversão.

---

## Spinning Top
`spinning_top` · isolado · neutra · 1 candle · qualquer contexto · prior 0.25 · p.6

**Geometria** — corpo pequeno espremido entre duas sombras longas (cada sombra ≥ 2× o
corpo). O ebook ressalva que a proporção de 2× *"não é característica obrigatória"* — por
isso no motor é limiar calibrável, não regra.

**Leitura** — briga sem vencedor. O preço subiu bastante, caiu bastante, e terminou onde
começou. Indecisão com volatilidade — diferente do doji, aqui houve movimento de verdade.

**Cuidado** — o ebook é direto: *"significam indecisão e são pouco confiáveis"*.

---

## Candle de Rejeição
`martelo_isolado` · isolado · neutra · 1 candle · qualquer contexto · prior 0.25 · p.4

**Não é um padrão nomeado no ebook.** Foi acrescentado ao catálogo para marcar qualquer
candle com uma sombra desproporcional, que a p.4 define como o núcleo da leitura:

> *"As sombras representam a força do lado oposto, ou a rejeição do preço naquele nível."*

**Uso** — marcação visual no gráfico e insumo para o mapa de suporte/resistência: onde
houve rejeição forte, provavelmente há ordem no book.
