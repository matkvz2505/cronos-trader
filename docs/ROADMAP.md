# Roadmap

Ordem de execução. A regra que guia a sequência: **nada que dependa de corretora bloqueia o
que não depende.** Por isso o motor inteiro é construído e testado antes do primeiro tick real.

| Sprint | Entrega | Estado |
|---|---|---|
| **0** | Repo, docs, knowledge base destilada do ebook | ✅ entregue |
| **1** | Núcleo do motor: tipos, normalização, contexto, 60 detectores, testes | ✅ entregue |
| **2** | Indicadores, Fibonacci, S/R, confluência, decisão, multi-timeframe | ✅ entregue |
| **3** | Fontes de dados: adapter MT5, loader CSV, contrato, coletor, diagnóstico | ✅ entregue |
| **4** | Backtest + walk-forward → calibração das confiabilidades reais | ✅ entregue |
| **5** | Backend Node: auth, API REST, WebSocket de sinais ao vivo | ✅ entregue |
| **6** | Frontend: painel, gráfico, sinais ao vivo, catálogo, backtest | ✅ entregue |
| **7** | Agentes de IA + LiteLLM + Langfuse + RAG sobre `kb/` | pendente |
| **8** | Alertas (WhatsApp/Telegram), hardening, diário de operações | pendente |

**As sprints 0–6 estão entregues e a stack roda ponta a ponta.** O que falta para o
produto ter valor de verdade não é código: é **conta numa corretora com MT5** para o
walk-forward medir a confiabilidade real dos padrões em WIN/WDO. Até lá, o sistema roda
com dados sintéticos e todos os números vêm marcados como "amostra insuficiente".

---

## Sprint 0 — fundação
Estrutura do repositório, decisões de arquitetura registradas, ebook destilado em `kb/` com
uma página por família de padrão, errata documentada.

## Sprint 1 — o motor sabe ler um candle
`tipos.py`, `normalizacao.py`, `contexto.py`, `padroes/`. Todo detector com teste de candle
sintético: um caso que dispara e pelo menos um vizinho que **não** dispara — é o teste
negativo que impede um detector frouxo de passar.

**Pronto quando:** `pytest` verde e a CLI lista as detecções de um CSV de exemplo.

## Sprint 2 — o motor sabe montar um trade
Indicadores (EMA/SMA, ATR, RSI, ADX, VWAP, Bollinger), Fibonacci (retração e extensão),
suporte/resistência por pivôs, camada de confluência com pesos, motor de decisão com
entrada/stop/alvo/R:R/sizing e a lógica de veto. Multi-timeframe ligando 15/30/60m ao 5m.

**Pronto quando:** dado um CSV, a CLI emite sinais completos com preço, stop, alvo e score.

## Sprint 3 — dados reais
Adapter MT5 (`copy_rates_from_pos`, `copy_ticks_range`), resolução de contrato vigente
WIN/WDO e marcação da janela de rollover, loader de CSV/Parquet, esquema Timescale e o job
de ingestão contínua.

**Requer:** MT5 instalado e logado numa corretora B3. Passo manual — quem roda é o dono.

## Sprint 4 — os números viram evidência
Simulador candle a candle sem look-ahead, custos (spread, corretagem, slippage), walk-forward,
relatório de taxa de acerto por padrão × timeframe × horário × ativo, e a escrita de
`confiabilidade_medida` de volta no catálogo.

**Pronto quando:** existir a tabela que diz quais padrões apagar.

## Sprint 5 — backend
Node 20 + TypeScript + Express + Prisma, seguindo a convenção do Matriz-SA
(`<domínio>.routes.ts` → `.controller.ts` → `.service.ts`, Zod em toda mutation, `env.*` em
vez de `process.env`). Login e registro próprios — este produto não é multi-tenant e **não**
depende do `cronos-auth`. WebSocket para empurrar sinal ao vivo.

## Sprint 6 — frontend
React 19 + Vite + Tailwind + `lightweight-charts`. Front **novo**, sem herdar nada dos outros
produtos. Telas: gráfico ao vivo com padrões marcados, painel de sinais abertos, histórico com
resultado, e o placar de confiabilidade por padrão.

## Sprint 7 — IA
Agentes Analista, Crítico e Gestor de Risco atrás do LiteLLM, com Langfuse ligado e RAG sobre
`kb/`. Reaproveita o padrão de `cronos-go/ai/olivia_ai/llm.py` e `obs.py`: fallback em cadeia,
observabilidade que degrada para no-op sem quebrar o pipeline.

## Sprint 8 — operação
Alertas, diário de operações, monitoramento e hardening.

---

## Fora de escopo (decidido)

- **Envio automático de ordem.** Só sinal. A arquitetura comporta execução depois, mas isso
  exige kill-switch, limite de perda diária e conta demo obrigatória — outro projeto.
- **Outros ativos.** Só WIN e WDO.
- **Análise fundamentalista.** Não move o mini-índice em 5 minutos.
