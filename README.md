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
| [ai/](ai/) | Motor: 60 detectores, confluência, decisão, backtest, serviço HTTP e coletor MT5 | **funcionando** |
| [backend/](backend/) | API Node + TypeScript: auth, sinais, candles, backtest, WebSocket | **funcionando** |
| [frontend/](frontend/) | 6 telas: painel, gráfico ao vivo, sinais, catálogo, backtest | **funcionando** |
| [kb/](kb/) | Knowledge base destilada do ebook — consumida pelos agentes via RAG | pronta |
| [docs/](docs/) | Arquitetura, roadmap, fontes de dados, errata do ebook | pronta |
| [tools/](tools/) | LiteLLM (gateway) + Langfuse (observabilidade de IA) | planejado (Sprint 7) |

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

### Ligar dados reais

```powershell
.\cronos.ps1 diagnostico    # 6 checagens do MetaTrader 5, parando na primeira que falhar
.\cronos.ps1 coletor        # MT5 → Postgres → motor, em ciclo, no host
```

### Desenvolvimento com hot reload

```powershell
.\cronos.ps1 dev            # infra em docker, app no host
```

## Por onde começar

1. [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — as sete camadas do motor e por que existem
2. [docs/FONTES-DE-DADOS.md](docs/FONTES-DE-DADOS.md) — o que é free, o que não é, e por que MT5
3. [docs/ROADMAP.md](docs/ROADMAP.md) — as sprints em ordem de execução
4. [docs/ERRATA-EBOOK.md](docs/ERRATA-EBOOK.md) — os erros do ebook que o código corrige

## Portas

| Serviço | Porta |
|---|---|
| frontend | 5180 |
| backend | 1840 |
| motor (IA) | 1841 |
| Postgres | 5460 |
| Redis | 6400 |
| Adminer | 5461 |

## Aviso

Isto é uma ferramenta de **apoio à decisão**, não uma recomendação de investimento. Mini-índice
e mini-dólar são contratos alavancados: a perda pode superar o capital depositado. Nenhuma taxa
de acerto histórica garante resultado futuro. Opere em conta demo até ter estatística própria
suficiente.
