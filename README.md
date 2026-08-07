# Cronos Trader — motor de decisão para WIN e WDO

Plataforma de análise de padrões de candlestick e geração de sinais para os dois únicos
ativos do escopo: **mini-índice (WIN)** e **mini-dólar (WDO)** na B3.

O produto responde uma pergunta só, com número em cima: **"tem entrada agora, em que preço,
com que stop, com que alvo, e qual a chance histórica disso dar certo?"**

## Princípio central

> **O motor decide, a IA narra.**

Os padrões são detectados por código determinístico e testável — nunca por LLM. O backtest
mede a taxa de acerto **real** de cada padrão em WIN/WDO, por timeframe e por horário do
pregão. Só depois os agentes de IA leem esse dossiê de números e escrevem a leitura em
português, com a tese e a invalidação. Isso mantém o sinal auditável: todo número na tela
tem uma função Python por trás que você pode rodar de novo.

O ebook `Ebook-PADROES-DE-CANDLESTICK.pdf` é a **fonte das regras geométricas**, não da
confiabilidade. O ebook dá um palpite inicial de peso; o backtest sobre WIN/WDO substitui
esse palpite por evidência.

## Escopo

| | |
|---|---|
| Ativos | **WIN e WDO apenas.** Nada de ações, cripto ou forex. |
| Timeframes | Viés em **15m / 30m / 60m**, gatilho em **5m** |
| Ação | **Só sinal.** O sistema não envia ordem. Você aperta o botão na corretora. |
| Fonte de dados | **MetaTrader 5** + conta em corretora B3 (ver [docs/FONTES-DE-DADOS.md](docs/FONTES-DE-DADOS.md)) |

## Mapa do repositório

| Pasta | O que é | Estado |
|---|---|---|
| [ai/](ai/) | Motor: 60 detectores, confluência, decisão, estrutura, backtest, serviço HTTP e coletor MT5 | **funcionando** |
| [backend/](backend/) | API Node + TypeScript: auth, sinais, candles, diário, WebSocket de alertas | **funcionando** |
| [frontend/](frontend/) | Mesa, Alertas, Sala por ativo, Gráfico, Diário, Histórico, Conhecimento | **funcionando** |
| [kb/](kb/) | Knowledge base: ebook destilado + médias, indicadores, estrutura, contratos | pronta |
| [docs/](docs/) | Arquitetura, produto, estudos medidos, fontes de dados, errata | pronta |
| [tools/](tools/) | LiteLLM (:4010) + Langfuse (:3010) + instalador do coletor | **funcionando** |

## As telas

| Rota | O que responde |
|---|---|
| `/` **Mesa** | Para onde eu olho agora? Os dois ativos lado a lado. |
| `/alertas` | O que aconteceu enquanto eu não olhava. Push por WebSocket. |
| `/sala/win` · `/sala/wdo` | **O agente ao vivo.** Tem entrada? Se não, por quê? Qual a conta? |
| `/grafico` | Candles anotados: canal, pivôs, rompimentos, zonas, níveis do sinal. |
| `/diario` | Fechamento de dia/semana/mês + preparação do próximo pregão. |
| `/historico` | Sinais passados com o resultado de cada um. |
| `/conhecimento` | Auditoria do motor: padrões, medições, validação fora da amostra. |

A tela central é a **Sala**, e o que ela faz de diferente é mostrar **as recusas**. Em 60
mil candles, 33.751 detecções viraram 293 sinais — 99,1% recusadas. Um produto que esconde
isso parece um oráculo; um que mostra vira ferramenta de estudo. Ver
[docs/PRODUTO.md](docs/PRODUTO.md).

## Arquitetura

Dez serviços em Docker, numa rede só (`cronos-net`). Uma peça fica de fora — e não por
falta de vontade.

```
 ┌─ HOST (Windows) ───────────────┐
 │  MetaTrader 5 ◀── IPC ── coletor.py
 └────────────────────────────────┼──────────────────────────────────┐
                                  │ escreve candles                  │
 ┌─ DOCKER (cronos-net) ──────────▼──────────────────────────────────┴───┐
 │                                                                       │
 │   postgres :5460 ◀────────────┬──────────────────┐                    │
 │        ▲                      │                  │                    │
 │        │                 motor :1841        backend :1840             │
 │   migrate (one-shot)     ┌──────────────┐   ┌──────────────┐          │
 │                          │ normalização │◀──│ auth JWT     │          │
 │   adminer :5461          │ contexto     │   │ API /api/v1  │          │
 │   redis   :6400          │ 60 padrões   │   │ WebSocket    │          │
 │                          │ confluência  │   └──────┬───────┘          │
 │   litellm  :4010         │ decisão      │          │                  │
 │   langfuse :3010         │ backtest     │          ▼                  │
 │   langfuse-db            └──────────────┘   frontend :5180 (nginx)    │
 └───────────────────────────────────────────────────────────────────────┘
```

**Por que o coletor não containeriza:** o pacote `MetaTrader5` é Windows-only e conversa
com o terminal por IPC. Ele roda no host e escreve no Postgres publicado em `:5460`.
Todo o resto é container.

O backtest fecha o ciclo: mede o resultado real e recalibra a confiabilidade de cada padrão.

## Subir tudo

```powershell
.\cronos.ps1 up         # build + sobe os 10 serviços, espera cada um responder
.\cronos.ps1 status     # containers, endpoints, candles no banco e o MT5
.\cronos.ps1 logs motor # logs de um serviço
.\cronos.ps1 down
```

| | |
|---|---|
| Produto | http://localhost:5180 — `matheus2aroldo@gmail.com` / `Trader@2026!` |
| Langfuse | http://localhost:3010 — `admin@cronos.trader` / `cronos-dev-123` |
| Adminer | http://localhost:5461 |

### Ver o produto sem ter conta em corretora

```powershell
.\cronos.ps1 amostra
```

Gera 60 pregões sintéticos, importa e roda o motor. Exercita a pipeline inteira — gráfico,
sinais, placar, backtest. **Não valida estratégia**: é random walk, e o gerador avisa isso
ao rodar.

### Ligar dados reais — uma vez, e nunca mais

```powershell
.\cronos.ps1 diagnostico        # 6 checagens do MetaTrader 5, parando na primeira que falhar
.\cronos.ps1 instalar-coletor   # registra a coleta como tarefa automática do Windows
```

Depois disso **você não roda mais nada**. A coleta:

- sobe no logon e às **08h55** de segunda a sexta
- coleta das **9h às 18h**, dorme fora do horário e reconecta sozinha
- reinicia a cada minuto se cair · log em `logs/coletor.log`

A única exigência diária é **deixar o MetaTrader 5 aberto e logado**. O pacote é
Windows-only e conversa com o terminal por IPC — é a razão de a coleta rodar no host e não
em container.

> Tarefa agendada e não serviço do Windows: serviço roda na sessão 0, sem acesso à sessão
> interativa, e não enxergaria o terminal MT5.

### Desenvolvimento com hot reload

```powershell
.\cronos.ps1 dev            # infra em docker, app no host
```

## Estado do edge — leia antes de operar

Medido em 60 mil candles reais de WIN (jun/2024 a ago/2026, XP), walk-forward de 5 janelas:

```
expectância fora da amostra:  +0,04R por operação
sinais:                       293 em 777 dias
```

Positiva, mas perto demais de zero para chamar de vantagem. **Não há edge comprovado.** O
que existe são dois indícios com amostra, ambos pendentes de validação:

- **Engolfo de Alta** — n=143, 47,6% de acerto, **+0,18R**
- **Janela da abertura americana** (14h–16h) — n=115, 58,3%, **+0,40R**

E um achado que contradiz a intuição: a janela das **10h–12h**, que parecia a de "tendência
mais limpa", mede **−0,28R** em 205 operações. Detalhes em [docs/ESTUDOS.md](docs/ESTUDOS.md).

## Por onde começar

1. [docs/PRODUTO.md](docs/PRODUTO.md) — o que é, contra quem, e por quê
2. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — as sete camadas do motor e por que existem
3. [docs/ESTUDOS.md](docs/ESTUDOS.md) — o que foi medido, e o que a medição derrubou
4. [docs/FONTES-DE-DADOS.md](docs/FONTES-DE-DADOS.md) — o que é free, o que não é, e por que MT5
5. [docs/ERRATA-EBOOK.md](docs/ERRATA-EBOOK.md) — os erros do ebook que o código corrige
6. [docs/ROADMAP.md](docs/ROADMAP.md) — as sprints em ordem de execução

## Portas

| Serviço | Porta | Acesso |
|---|---|---|
| frontend | 5180 | `matheus2aroldo@gmail.com` / `Trader@2026!` |
| backend | 1840 | `/api/v1` |
| motor (IA) | 1841 | `/saude` |
| Langfuse | 3010 | `admin@cronos.trader` / `cronos-dev-123` |
| LiteLLM | 4010 | Admin UI com `LITELLM_MASTER_KEY` |
| Adminer | 5461 | |
| Postgres | 5460 | `trader` / `trader` |
| Redis | 6400 | reservado |

## Aviso

Isto é uma ferramenta de **apoio à decisão**, não uma recomendação de investimento. Mini-índice
e mini-dólar são contratos alavancados: a perda pode superar o capital depositado. Nenhuma taxa
de acerto histórica garante resultado futuro. Opere em conta demo até ter estatística própria
suficiente.
