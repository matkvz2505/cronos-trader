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

## A coleta é automática — nunca peça comando ao operador

O coletor MT5 roda como **tarefa agendada do Windows** (`tools/instalar-coletor.ps1`),
com dois gatilhos: no logon e às 08h55 de segunda a sexta. Reinicia sozinho a cada minuto
se cair. Log em `logs/coletor.log`.

O processo é **consciente do pregão**: coleta das 9h às 18h em dias úteis, dorme fora
disso e reconecta quando o terminal MT5 volta. Ele não morre no fim do dia — um processo
que termina às 18h precisa de alguém para religá-lo, e "alguém" vira o operador lembrando
de rodar comando.

**Tarefa agendada e não serviço do Windows:** serviço roda na sessão 0, sem acesso à
sessão interativa — e o MetaTrader 5 conversa por IPC com um terminal que vive na sessão
do usuário. Serviço não enxergaria o terminal.

Consequência para a UI: **nenhuma tela pode instruir o operador a rodar `.\cronos.ps1
coletor`**. Quando falta dado, a causa é uma de duas, e a tela deve dizer qual: pregão
fechado, ou terminal MT5 não aberto.

Duas armadilhas na instalação, ambas já resolvidas e fáceis de reintroduzir:

- **`Get-Command python` devolve o stub da Microsoft Store**, que abre a loja em vez de
  executar. Pergunte ao próprio Python: `python -c "import sys; print(sys.executable)"`.
- **`cmd /c "... >> \"log\""` quebra** por aninhamento de aspas. Por isso o instalador
  gera um `.bat`. E o `-u` do Python é obrigatório: sem ele a saída redirecionada fica
  buferizada e o log some justamente quando é preciso.

## Tudo roda no relógio da B3 — host, containers e banco

O `ts` de um candle **não é um instante absoluto**: é o relógio de parede do pregão,
gravado em `timestamp without time zone`. Isso obriga três coisas a concordarem, e cada
uma já quebrou uma vez:

1. **O adapter do MT5.** O campo `time` é o relógio do servidor codificado *como se fosse*
   UTC. `datetime.fromtimestamp()` aplica o fuso da máquina por cima e enterra o candle 3
   horas no passado. Use `hora_do_servidor()` em `fontes/mt5.py`. Coberto por
   `tests/test_fonte_mt5.py`.
2. **Os containers.** `TZ: America/Sao_Paulo` via a âncora `x-fuso` do compose. Container
   em UTC calcula `now() - candle.ts` com dois relógios e a tela anuncia "dados parados há
   6 h" com candle de 3h20.
3. **A tela.** O Prisma serializa o timestamp naive como se fosse UTC — o candle das 15:30
   chega ao navegador como `...T15:30:00.000Z`. O `Z` mente. Formate com
   `timeZone: 'UTC'` (`frontend/src/lib/formato.ts`), que devolve o relógio do pregão.

**A checagem de 10 segundos, com o pregão aberto:** o último candle de M5 tem que estar a
menos de 5 minutos de agora. `.\cronos.ps1 status` mostra isso. Se der ~180 minutos, é o
item 1; se der ~360, é o item 1 somado ao 2.

O sintoma é traiçoeiro porque 09:00–18:25 deslocado vira 06:00–15:25, que ainda parece
pregão para quem olha de relance. Custou a base histórica inteira e a rotulagem de todo
estudo por janela — ver [docs/ESTUDOS.md](docs/ESTUDOS.md) seção 3.

> O Brasil não tem horário de verão desde 2019, então o offset é −3 fixo. Se voltar, a
> resposta certa é gravar o candle com fuso explícito, não desalinhar os relógios de novo.

## Os `.ps1` precisam de BOM UTF-8 — e sua ferramenta de edição o remove

**Todo `.ps1` deste repo tem que ser gravado em UTF-8 COM BOM.** Não é preferência de
estilo, é o que decide se o script roda.

O PowerShell 5.1 (que é o que está nesta máquina) assume **CP1252** para arquivo sem BOM.
Aí cada travessão `—` (UTF-8 `E2 80 94`) é lido como três caracteres — e o terceiro,
`0x94`, é `”` **U+201D**. O PowerShell aceita aspa curva como delimitador de string.
Dez travessões viram dez aspas fantasmas, o pareamento desloca, e o erro aparece **em
outro lugar**: o `cronos.ps1` acusou erro na linha 228, num bloco de sintaxe perfeita, por
causa de um travessão na linha 6.

O sintoma é traiçoeiro porque o arquivo parece certo em qualquer editor e o `git diff` sai
limpo. Para confirmar em vez de adivinhar:

```powershell
$e = $null; $t = $null
[System.Management.Automation.Language.Parser]::ParseFile($caminho, [ref]$t, [ref]$e) | Out-Null
$e | Select-Object -First 3
```

**Depois de qualquer edição num `.ps1`, recoloque o BOM.** As ferramentas de edição do
Claude Code gravam UTF-8 sem BOM, então isto reincide a cada mexida:

```powershell
$b = [System.IO.File]::ReadAllBytes($p)
if (-not ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)) {
    [System.IO.File]::WriteAllBytes($p, ([byte[]](0xEF,0xBB,0xBF) + $b))
}
```

A alternativa — escrever os scripts em ASCII puro — foi descartada: a copy é em pt-BR, e
trocar por copy sem acento resolveria o parser piorando o produto.

## Docker — o que costuma morder

- **`NODE_ENV=production` no container + `JWT_SECRET` de exemplo = boot recusado.** É o
  guard funcionando, não defeito. `cronos.ps1 up` gera um segredo aleatório real no `.env`
  no primeiro boot. Nunca troque isso por afrouxar a checagem.
- **`RandomNumberGenerator::Fill` não existe no PowerShell 5.1.** Ele falha em silêncio,
  o array fica zerado, e o "segredo" sai todo de zeros. Use `Create()` + `GetBytes()`.
- **Nunca chame de `$Args` um parâmetro de função no PowerShell.** É variável automática:
  declarar `param([string[]]$Args)` faz o splat `@Args` expandir para **vazio**. A função
  `Compose` do `cronos.ps1` caiu nisso e rodava `docker compose` sem comando nenhum — o
  Docker imprimia o help, saía com sucesso, e o `up` seguia esperando serviço que ninguém
  tinha mandado subir. O parâmetro se chama `$Argumentos`.
- **Prisma em Debian slim, não Alpine.** A combinação musl + OpenSSL é a fonte clássica de
  `Query engine binary not found`. `binaryTargets` declara `native` e `debian-openssl-3.0.x`.
- **O `migrate` é one-shot** e usa o estágio `build` do backend: o Prisma CLI e o `tsx` são
  devDependencies e não existem na imagem de runtime, de propósito.
- **O Langfuse demora no primeiro boot** — roda as próprias migrations. O `up` dá 180s.
- **O LiteLLM exige banco próprio.** Sem `database_url` a Admin UI devolve
  "Authentication Error, Not connected to DB!" no login. O banco `litellm` é criado pelo
  init do Postgres; em volume já existente:
  `docker compose exec postgres createdb -U trader litellm`.
- **Não use modelo de raciocínio no slot `rapido`.** O `qwen3-32b` gastava 183 tokens
  *pensando* para responder "OK" — com `max_tokens` apertado a resposta volta vazia.
  Tarefa mecânica pede modelo de resposta direta.
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
