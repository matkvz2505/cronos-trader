# tools — gateway de LLM e observabilidade

Duas peças que só passam a ser usadas na **Sprint 7**, quando os agentes existirem. Sobem
junto com a stack desde já para que a infraestrutura esteja pronta e testada antes de
haver o que observar.

| Serviço | Porta | Para quê |
|---|---|---|
| **LiteLLM** | 4010 | Endpoint OpenAI-compatível na frente de OpenRouter e Anthropic |
| **Langfuse** | 3010 | Um trace por execução de agente: input, output, tokens, latência, custo |

## LiteLLM

Os agentes chamam **este proxy**, nunca o provedor direto. Trocar de modelo passa a ser
editar [litellm/config.yaml](litellm/config.yaml) em vez de mexer em código.

A cadeia de fallback é a mesma já usada em `cronos-go/tools/litellm`:

```
free-primary  ──429/5xx──▶  paid-fallback  ──falha──▶  claude-haiku-4-5
(OpenRouter :free)          (gpt-4o-mini)              (Anthropic)
```

O modelo principal é **gratuito**. O nome `free-primary` é neutro de propósito: os
modelos `:free` do OpenRouter rotacionam e esgotam capacidade, e trocar qual deles está
por trás não pode exigir mexer no código dos agentes.

**Sobe sem chave nenhuma.** `/health` responde, e só as chamadas de modelo falhariam — que
é exatamente o comportamento correto enquanto não há agente para chamar. Para ativar,
preencha no `.env` da raiz:

```
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_API_KEY=sk-ant-...      # opcional; o fallback pago já roda pelo OpenRouter
```

### Duas decisões que valem explicação

**Cache semântico desligado.** Com um system prompt grande — e o do Analista carrega a
knowledge base do ebook inteira — o embedding é dominado pelo prompt, e perguntas
diferentes colidem acima do limiar de similaridade. O agente passa a responder sempre a
mesma coisa, em silêncio. Com o modelo principal custando zero, o cache não compensa
esse risco.

**`cache_control_injection_points` nos modelos Anthropic.** Marca o system prompt como
prefixo estável, e a leitura sai por cerca de 10% do custo de input. Importa justamente
porque o system prompt é grande.

## Langfuse

Chega **pré-configurado**: organização, projeto, usuário e chaves de API já criados no
primeiro boot via `LANGFUSE_INIT_*`. Sem isso seria preciso abrir a UI e copiar chaves à
mão antes de qualquer agente conseguir logar um trace.

- UI: http://localhost:3010
- Login: `admin@cronos.trader` / `cronos-dev-123`
- Chaves: `pk-lf-cronos-trader-dev` / `sk-lf-cronos-trader-dev`

O LiteLLM já aponta para ele (`success_callback: ["langfuse"]`), então toda chamada que
passar pelo gateway vira trace automaticamente — inclusive as que você fizer à mão para
testar.

> O primeiro boot roda as migrations do Langfuse e demora mais que os outros serviços.
> É esperado; o `cronos.ps1 up` dá 180 segundos para ele.

## Como os agentes vão usar (Sprint 7)

O padrão já existe em `cronos-go/ai/olivia_ai/` e vai ser reaproveitado:

- `llm.py` — chama o proxy via SDK OpenAI, com o gateway resolvendo fallback e retry
- `obs.py` — **degrada para no-op** sem `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` no ambiente

Essa segunda parte é a que importa operacionalmente: observabilidade nunca pode derrubar
o produto. Se o Langfuse cair, o agente continua respondendo — perde-se o trace, não a
análise.

E a regra que atravessa tudo: **a IA narra, não decide**. Os agentes leem o dossiê de
números que o motor produziu e escrevem a leitura em português. Se o LLM inteiro cair, o
motor continua emitindo sinal.
