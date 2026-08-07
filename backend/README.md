# backend — API do cronos-trader

Node 20 · TypeScript strict · Express 4 · Prisma 5 · PostgreSQL 16 · WebSocket.

Responsabilidades: **login/registro, servir os dados ao frontend e conversar com o motor
de IA**. Nada mais. Toda regra de padrão, confluência e decisão vive em `../ai/` — o
backend não reimplementa nenhuma delas. Duas implementações da mesma regra divergem em
uma semana.

## Subir

```powershell
docker compose up -d          # Postgres :5460, Redis :6400, Adminer :5461
cp .env.example .env          # ajuste JWT_SECRET
npm install
npm run prisma:generate
npm run prisma:migrate -- --name init
npm run seed
npm run dev                   # http://localhost:1840/api/v1
```

Depois do seed: `matheus2aroldo@gmail.com` / `Trader@2026!` (admin).

## Rotas

Tudo sob `/api/v1`. Autenticação por `Authorization: Bearer <accessToken>`.

### auth
| | |
|---|---|
| `POST /auth/registro` | cria conta, devolve par de tokens |
| `POST /auth/login` | |
| `POST /auth/refresh` | rotaciona: a sessão antiga é revogada no mesmo ato |
| `POST /auth/sair` | revoga o refresh |
| `GET /auth/eu` · `PATCH /auth/eu` | perfil e capital |

### sinais
| | |
|---|---|
| `GET /sinais` | filtros: ativo, timeframe, status, direção, scoreMinimo, desde |
| `GET /sinais/abertos` | os que ainda estão vivos |
| `GET /sinais/resumo` | números do dashboard |
| `GET /sinais/desempenho` | placar por padrão, com flag de amostra suficiente |
| `GET /sinais/:id` | |
| `PATCH /sinais/:id/status` | marcar alvo/stop/expirado |
| `POST /sinais/:id/anotacao` | diário: operei ou não, e por quê |
| `POST /sinais/analisar` | dispara o motor sob demanda |

### mercado
| | |
|---|---|
| `GET /mercado/candles` | OHLC para o gráfico |
| `GET /mercado/deteccoes` | marcações do gráfico (inclui as que não viraram sinal) |
| `GET /mercado/padroes` | catálogo, vindo do motor |
| `GET /mercado/calibracoes` | confiabilidade medida pelo walk-forward |
| `GET /mercado/saude` | **pública** — estado de banco, motor, MT5 e candles |

### backtest
| | |
|---|---|
| `POST /backtest` | `walkforward` por padrão |
| `GET /backtest/execucoes` · `/:id` | histórico |

### WebSocket
`ws://localhost:1840/ws?token=<accessToken>` — mensagens `estado.inicial`,
`sinais.abertos`, `sinais.novos`.

Token vai por query param porque a API de WebSocket do navegador não permite cabeçalhos.
É de vida curta (15min) e a conexão é local.

## Convenções

- **Módulo**: `<domínio>.routes.ts` → `.service.ts` → Prisma. Controller separado só onde
  há tradução HTTP de verdade (`auth`); nos módulos de leitura o handler é de uma linha e
  um arquivo a mais só acrescenta indireção.
- **Zod em toda mutation**; `.strict()` em updates.
- **`env.*` de `src/config/env.ts`**, nunca `process.env` direto. Variável faltando
  derruba o processo no boot, com mensagem — não vira `undefined` que explode depois.
- **bcrypt rounds 12**; nunca desestruturar resultado do Prisma para "tirar" a senha —
  sempre `select` explícito.
- **Refresh opaco, guardado como sha256.** Vazamento do banco não pode virar sessão.
- **Decimal → number na borda de saída.** O banco guarda `Decimal` para não ter erro de
  ponto flutuante em preço; a API entrega `number`.

## Por que polling no WebSocket

O produtor de sinais é o processo Python, que escreve direto no Postgres. `LISTEN/NOTIFY`
funcionaria, mas acoplaria o Python ao protocolo de notificação. Com granularidade de 5
segundos num produto cujo candle mais rápido é de 5 minutos, um timer no servidor
transmitindo para todos os clientes é suficiente — e muito mais simples de operar.
