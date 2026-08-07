# CLAUDE.md — cronos-trader

Guia para Claude Code (e humanos) trabalhando neste repositório.

## O que é

Motor de análise de padrões de candlestick e geração de sinais para **mini-índice (WIN)** e
**mini-dólar (WDO)** na B3. Produto novo, **independente** do resto do Matriz-SA — não
compartilha código, banco, auth nem frontend com os verticais Olivia.

Copy, comentários e nomes de identificadores em **pt-BR**. Mantenha ao editar.

## Escopo, e ele é fechado

| | |
|---|---|
| Ativos | **só WIN e WDO.** `instrumentos.resolver()` levanta `ValueError` em qualquer outro |
| Timeframes | viés em 15/30/60min, gatilho em 5min |
| Ação | **só sinal.** O motor não envia ordem e não deve ganhar essa capacidade sem decisão explícita |
| Dados | MetaTrader 5 + corretora B3 (ver [docs/FONTES-DE-DADOS.md](docs/FONTES-DE-DADOS.md)) |

## Layout

```
cronos-trader/
├─ docker-compose.yml  os 10 serviços — a raiz é o único compose do repo
├─ cronos.ps1          orquestrador: up / down / status / logs / amostra / coletor
├─ ai/                 motor em Python (:1841) + Dockerfile
│  ├─ trader_ai/       pacote: motor, pipeline, serviço FastAPI, coletor, persistência
│  ├─ tests/           pytest; roda sem corretora, sem banco e sem rede
│  ├─ scripts/         diagnóstico MT5, gerador sintético, importador de CSV
│  └─ dados/           CSVs (não versionados)
├─ backend/            Node 20 + TS + Express + Prisma (:1840) + Dockerfile
├─ frontend/           React 19 + Vite + Tailwind v4 (:5180) + Dockerfile + nginx.conf
├─ tools/litellm/      gateway de LLM (:4010) — config do Langfuse embutida
├─ kb/                 ebook destilado — RAG dos agentes (Sprint 7)
└─ docs/               arquitetura, roadmap, fontes de dados, errata
```

**Tudo roda em container, com uma exceção que não é negociável:** o **coletor MT5**. O
pacote `MetaTrader5` é Windows-only e conversa com o terminal por IPC. Ele roda no host e
escreve no Postgres publicado em `:5460`. Não tente containerizá-lo — não é falta de
Dockerfile, é o pacote não existir fora do Windows.

Consequência na tela: dentro do container o `/saude` **sempre** vai reportar MT5
indisponível. Por isso `_mt5_estado()` distingue esse caso (`emContainer: true`) e o painel
mostra a **idade do candle mais recente** como o sinal real de "os dados estão chegando".

### Quem é dono do quê

| Responsabilidade | Onde |
|---|---|
| Regras de padrão, confluência, decisão, backtest | **só** `ai/trader_ai/` |
| Schema do banco (Prisma) | **só** `backend/prisma/schema.prisma` |
| Autenticação, API REST, WebSocket | `backend/src/` |
| Tela | `frontend/src/` |

O backend **nunca** reimplementa regra do motor — duas implementações da mesma regra
divergem em uma semana. O Python **nunca** cria tabela — o Prisma é a fonte da verdade da
estrutura, e o Python lê/escreve nela via psycopg.

**Colunas do Prisma são camelCase e precisam de aspas no SQL cru**: é `sinais` (tabela,
via `@@map`) mas `"padraoId"` (coluna). Sem aspas o Postgres normaliza para minúsculo e a
coluna "não existe". `id` é gerado pelo cliente (`@default(uuid())` roda no Node), então
quem insere do Python precisa gerar o UUID.

## Princípio que governa o design

> **O motor decide, a IA narra.**

Padrões são detectados por código determinístico e testável — **nunca por LLM**. O backtest
mede a taxa de acerto real. Só então os agentes leem os números e escrevem a leitura em
português. Se o LLM cair, o motor continua produzindo sinais.

Ao adicionar qualquer coisa: se ela precisa de um modelo de linguagem para decidir se um
padrão existe, está na camada errada.

## As sete camadas

`normalizacao` → `contexto` → `padroes` → `confluencia` → `decisao` → `multitimeframe` →
`backtest`. Detalhe em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Regras que não são negociáveis

**1. Nenhum limiar em pontos.** Tudo é fração da amplitude do candle ou múltiplo de ATR, e
mora em `limiares.py`. Um número mágico solto num detector quebra entre WIN e WDO e não
pode ser calibrado pelo backtest.

**2. Nenhum look-ahead.** Já custou duas correções reais:
- pivôs precisam de `swings_confirmados()` (exige `indice + lookback <= i`), nunca de
  `swings()` filtrado por `indice <= i`;
- viés multi-timeframe usa `indice_fechado_em()`, nunca `indice_em()` — o candle de 60min
  em formação contém futuro.

O teste `test_pipeline_inteira_nao_olha_para_o_futuro` é o que sustenta a decisão de passar
a série inteira no laço do backtest em vez de fatiar. **Se ele quebrar, pare tudo**: os
números do backtest viram ficção.

**3. Detector devolve `float | None`, não booleano.** `None` = não é o padrão; float em
0..1 = quão limpa foi a formação. Use `combinar()` para juntar condições — média harmônica,
para que a condição mais fraca domine.

**4. Contexto é obrigatório.** Quase todo padrão do ebook exige tendência. Detectar
geometria sem contexto é a causa número um de sinal falso.

**5. Divergência do ebook vai para a errata.** O ebook tem erros reais de copy-paste. Onde
o código diverge, registre em [docs/ERRATA-EBOOK.md](docs/ERRATA-EBOOK.md) e cite o item no
`observacao` do padrão. Sem isso, a próxima pessoa vai "consertar" o código de volta para o
errado.

**6. Score não é probabilidade.** `Avaliacao.score` é nota de ranqueamento. A estimativa
honesta de acerto é `confiabilidade`, e ela só vira número medido depois do backtest, com
amostra ≥ 30. Nunca apresente prior do ebook como evidência.

## Comandos

O dono roda os comandos. Claude edita código e documenta o comando.

```powershell
# --- stack inteira (docker) ---
.\cronos.ps1 up           # build + sobe os 10 serviços e espera cada um responder
.\cronos.ps1 status       # containers, endpoints, candles no banco e o MT5
.\cronos.ps1 logs motor   # logs de um serviço
.\cronos.ps1 amostra      # dados sintéticos — ver o produto sem corretora
.\cronos.ps1 coletor      # MT5 → Postgres → motor, no host
.\cronos.ps1 diagnostico  # os 6 pontos do MetaTrader 5
.\cronos.ps1 testes       # pytest + ruff + typecheck dos dois TS
.\cronos.ps1 dev          # infra em docker, app no host com hot reload
.\cronos.ps1 down

# --- motor ---
cd ai
pip install -e ".[dev,servico,mt5]"
pytest -o addopts=                                       # 320 testes, sem rede
ruff check trader_ai tests scripts
python scripts/gerar_amostra.py --ativo WIN --dias 60    # dados sintéticos
python scripts/importar_csv.py dados/WIN_M5.csv --ativo WIN --tf M5 --analisar
python -m trader_ai.cli walkforward dados/WIN_M5.csv --ativo WIN --janelas 4
python -m trader_ai.servico                              # :1841

# --- backend ---
cd backend
npm run prisma:migrate -- --name <nome>
npm run seed
npm run dev                                              # :1840
npm run typecheck

# --- frontend ---
cd frontend
npm run dev                                              # :5180
npm run build
```

## Portas reservadas (sem colidir com o resto do workspace)

frontend 5180 · backend 1840 · motor 1841 · Postgres 5460 · Adminer 5461 ·
Redis 6400 · LiteLLM 4010 · Langfuse 3010

## Docker — o que costuma morder

- **`NODE_ENV=production` no container + `JWT_SECRET` de exemplo = boot recusado.** É o
  guard funcionando, não defeito. `cronos.ps1 up` gera um segredo aleatório real no `.env`
  no primeiro boot. Nunca troque isso por afrouxar a checagem.
- **`RandomNumberGenerator::Fill` não existe no PowerShell 5.1.** Ele falha em silêncio,
  o array fica zerado, e o "segredo" sai todo de zeros. Use `Create()` + `GetBytes()`.
- **Prisma em Debian slim, não Alpine.** A combinação musl + OpenSSL é a fonte clássica de
  `Query engine binary not found`. `binaryTargets` declara `native` e `debian-openssl-3.0.x`.
- **O `migrate` é one-shot** e usa o estágio `build` do backend: o Prisma CLI e o `tsx` são
  devDependencies e não existem na imagem de runtime, de propósito.
- **O Langfuse demora no primeiro boot** — roda as próprias migrations. O `up` dá 180s.
- **Timeouts do nginx** estão em 300s para `/api` (backtest longo) e 3600s para `/ws`
  (conexão ociosa entre candles). Os defaults de 60s cortariam os dois.

## Gotchas

- **`ai/dados/` não é versionado.** Gere com `scripts/gerar_amostra.py` ou baixe do MT5.
- **Dado sintético não valida estratégia.** Serve para exercitar a pipeline. Expectância
  medida sobre random walk não significa nada — e o gerador avisa isso ao rodar.
- **MT5 é Windows-only e exige terminal aberto e logado numa corretora B3.** Demo da
  MetaQuotes não tem ativos da B3. Por isso o coletor roda no host, não em container, e
  `import MetaTrader5` acontece dentro de funções, nunca no topo de módulo.
- **Rollover de contrato corrompe backtest em silêncio.** Use símbolo contínuo (`WIN$N`)
  para histórico e descarte a janela de virada.
- **`tolerancia_gap_atr` é o limiar mais sensível do motor.** Zero mata 8 padrões em
  intraday; alto demais faz todos dispararem sempre. Calibrar por timeframe antes de
  qualquer outra coisa.
- Não existe git na raiz `Matriz-SA/` — e este repo ainda não foi inicializado.
