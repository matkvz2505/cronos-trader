# Anatomia de um candle

Fonte: ebook p.3–4.

Um candle resume um período com quatro números: **abertura, máxima, mínima e fechamento**.
Toda a análise nasce da proporção entre eles.

```
        ┌─ máxima
        │
        │   ← sombra superior
      ┌─┴─┐ ← topo do corpo
      │   │
      │   │  corpo
      │   │
      └─┬─┘ ← base do corpo
        │   ← sombra inferior
        │
        └─ mínima
```

## As três leituras que importam

**1. Tamanho do corpo = força do movimento direcional.**
Corpo grande com sombra pequena significa que uma das mãos dominou do início ao fim do
período. O ebook: *"quanto maior o corpo e menor a sombra, mais força o movimento tem e,
portanto, provavelmente seguirá na mesma direção"*.

**2. Sombras = rejeição de preço.**
A sombra é a marca do lado que perdeu. Uma sombra inferior longa quer dizer que o preço
caiu até ali e foi recomprado — aquele nível foi **rejeitado**. Quanto mais longa, mais
difícil ultrapassar.

Muitos candles seguidos com sombras longas significam mercado indeciso, brigando. Acontece
em consolidação.

**3. Posição do fechamento dentro da amplitude.**
É a informação mais direta de todas:

| Fechamento perto da | Significa |
|---|---|
| máxima | compradores dominando |
| mínima | vendedores dominando |
| meio | neutralidade, indecisão |

## Por que o motor mede tudo em proporção

Um corpo de 200 pontos no WIN é enorme às 12h e banal às 9h05. Um limiar absoluto quebra
entre ativos — WIN anda em pontos, WDO em reais — e entre regimes de volatilidade.

Por isso todo limiar do motor é ou **fração da amplitude do próprio candle**, ou
**múltiplo do ATR(14)**:

```
corpo_pct     = |fechamento - abertura| / (máxima - mínima)
amplitude_atr = (máxima - mínima) / ATR(14)
```

É o que permite o mesmo detector rodar em WIN de 5 minutos e WDO de 60 minutos sem
reescrever nada. Implementação: `ai/trader_ai/normalizacao.py`.

## O contexto vem antes da geometria

Praticamente toda descrição do ebook começa com *"numa tendência de baixa…"*. Isso não é
enfeite de texto — é requisito.

Um engolfo de alta no meio de uma alta não é reversão: é continuação de ruído. Um martelo
sem queda anterior não rejeitou nada. **Detectar geometria sem contexto é a causa número
um de sinal falso**, e é por isso que o motor decide a tendência antes de rodar qualquer
detector (`ai/trader_ai/contexto.py`).

## A honestidade do ebook

Vale registrar, porque muda como os agentes devem falar: o ebook **não** vende os padrões
como infalíveis. Ele classifica vários como de baixa confiabilidade e avisa, sobre o
Harami:

> *"Na teoria é um padrão de reversão de tendência. Mas na prática você perceberá que isso
> muitas vezes não acontece. Portanto, não confie cegamente nele e tente analisar o
> contexto."*

Um agente que apresentar qualquer padrão como certeza está contradizendo a própria fonte.
