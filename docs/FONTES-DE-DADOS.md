# Fontes de dados — o que existe, o que é free, e o que escolhemos

Resumo da investigação. A conclusão curta: **não existe API pública e gratuita de tempo real
para futuros da B3.** WIN e WDO são dados de mercado licenciados; quem redistribui de graça
está fora do contrato com a B3. O único caminho legítimo e sem mensalidade é consumir o feed
que a **sua corretora** já tem direito de te entregar — e o MetaTrader 5 é a porta de entrada
programável desse feed.

## Decisão

**MetaTrader 5 + conta em corretora que opera B3.** O pacote Python `MetaTrader5` conversa com
o terminal MT5 instalado na máquina e devolve ticks e OHLC de qualquer timeframe.

```
Corretora (Clear / XP / Rico / Modal / BTG …)
        │  feed B3 já incluso na conta
        ▼
   Terminal MT5 (Windows, precisa estar aberto e logado)
        │  named pipe / IPC
        ▼
   Python: import MetaTrader5 as mt5
        mt5.copy_rates_from_pos("WINQ26", mt5.TIMEFRAME_M5, 0, 5000)
        mt5.copy_ticks_range(...)
```

**Por que ele venceu:** custo zero além da conta na corretora, tempo real de verdade
(não delayed), acesso a M1/M5/M15/M30/H1 na mesma chamada, histórico profundo de graça,
e roda nativamente no Windows — que é o ambiente desta máquina.

**O que ele cobra em troca:**

- Só funciona no **Windows** com o **terminal MT5 aberto e logado**. Não dá pra rodar num
  container Linux. O coletor é, por natureza, um processo no host.
- Uma conta de **demo da MetaQuotes não serve** — ela não tem os ativos da B3. Precisa ser
  demo ou real **de uma corretora brasileira**.
- Nem toda corretora oferece MT5. Confirme antes de abrir conta.

### Credencial: você não passa senha para o código

Este é o ponto que confunde quase todo mundo no começo. O pacote Python **não faz login** —
ele se **acopla a um terminal que já está logado**:

```
Você, uma vez, na interface do MT5:
    Arquivo → Login na conta de negociação → conta, senha, servidor

Depois disso, para sempre:
    mt5.initialize()        ← sem argumento nenhum
```

O `initialize()` encontra o terminal aberto e herda a sessão dele. Não há credencial no
código, nem no `.env`, nem no banco.

**A exceção**, para quando o coletor precisa sobreviver a um reboot sem alguém digitando
senha: se `MT5_LOGIN`, `MT5_SENHA` e `MT5_SERVIDOR` estiverem no ambiente, o adapter usa
as três para logar sozinho. São credenciais de conta de investimento — nunca em arquivo
versionado, e o `.gitignore` já cobre `.env`.

### Corretoras

Confirmadas oferecendo MT5 com acesso à B3: **Clear, XP, Rico, Modal, Terra**. Outras
aparecem em relatos (BTG, Genial, Toro, Ativa, Guide, Órama, Nova Futura) mas não
confirmei — pergunte antes de abrir conta.

Em várias delas o MT5 é um acesso que se **solicita à parte**, mesmo já tendo conta. Ao
abrir, peça explicitamente "acesso ao MetaTrader 5" e "mercado de derivativos".

### Consequência arquitetural

O coletor MT5 vira um **processo separado no host**, não um serviço do docker-compose. Ele
escreve nos candles do Postgres, e o resto da stack (que roda em container) lê dali. Isso
isola a única peça que não é portável.

Por isso `ai/trader_ai/fontes/` define um protocolo `FonteDados`, com duas implementações:
`mt5.py` (tempo real) e `csv_loader.py` (histórico exportado / backtest). O motor nunca
importa `MetaTrader5` diretamente — assim os testes e o backtest rodam em qualquer lugar.

## As outras opções, e por que não são a principal

| Fonte | Custo | Serve pra WIN/WDO? | Papel aqui |
|---|---|---|---|
| **MetaTrader 5** | free (com conta) | ✅ tempo real, todos os TFs | **fonte principal** |
| **Nelogica ProfitDLL** | pago (mensalidade) | ✅ tempo real, homologado | alternativa se o MT5 travar |
| **B3 UP2DATA / B3 for Developers** | pago (licença) | ✅ oficial | fora do orçamento inicial |
| **brapi.dev** | free 15k req/mês | ⚠️ futuros só EOD | complemento diário, não intraday |
| **yfinance** | free | ❌ não tem WIN/WDO | **contexto correlacionado** (abaixo) |
| **BCB SGS** | free, oficial | ❌ macro, não intraday | **contexto macro do WDO** |
| **investidor10** | free/pago | ❌ | **não serve** (veja abaixo) |

### Sobre o investidor10

Você levantou o [investidor10.com.br](https://investidor10.com.br/) como candidato. Vale ser
direto: ele é um site de **análise fundamentalista de ações, FIIs e BDRs** — P/L, dividend
yield, balanço, ranking. Isso não tem interseção útil com day trade de WIN/WDO em 5 minutos.
Não há dado intraday de futuros lá, e fundamento de empresa não move o mini-índice numa janela
de minutos. **Recomendo não integrar.**

### O que de fato ajuda além do preço

Estas duas são gratuitas, oficiais ou estáveis, e agregam sinal real:

**1. Correlação externa (via `yfinance`, free).** WIN e WDO não se movem sozinhos:

| Ticker | O que é | Por que importa |
|---|---|---|
| `ES=F` | Futuro do S&P 500 | WIN segue o S&P quase tick a tick no intraday |
| `DX-Y.NYB` | Índice do dólar (DXY) | WDO é dólar; DXY subindo empurra WDO |
| `CL=F` / `^BVSP` | Petróleo / Ibovespa à vista | peso de PETR/VALE no índice |

Um sinal de compra em WIN contra um S&P despencando é um sinal pior — e o motor precisa
saber disso. Entra como **penalidade de confluência**, não como bloqueio.

**2. Agenda econômica.** Payroll, CPI americano, decisão do Copom e do Fed viram picos de
volatilidade que invalidam padrão gráfico. A regra prática é **não abrir posição nova na
janela de ±15 minutos do evento**. Implementado como filtro de veto no motor. A agenda vem
do calendário do BCB (free) para eventos locais; eventos americanos entram por lista
configurada.

**3. BCB SGS (free, oficial)** — `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json`
Séries úteis: `1` (dólar PTAX venda), `11` (Selic), `433` (IPCA). Contexto de regime para o
WDO, atualizado diariamente. Limite: consultas restritas a janelas de 10 anos.

## Rollover de contrato — a armadilha silenciosa

WIN e WDO **vencem**. Se o coletor gravar `WINQ26` e depois `WINV26` na mesma série sem
tratar a virada, o gráfico ganha um salto artificial de centenas de pontos e **todo padrão
de gap detectado ali é falso**. Isso corrompe o backtest inteiro sem dar erro nenhum.

| | WIN (mini-índice) | WDO (mini-dólar) |
|---|---|---|
| Vencimento | meses **pares** (fev, abr, jun, ago, out, dez) | **mensal** |
| Códigos de mês | G · J · M · Q · V · Z | F G H J K M N Q U V X Z |
| Exemplo | `WINQ26` = ago/2026 | `WDOU26` = set/2026 |

A maioria das corretoras expõe no MT5 um símbolo contínuo (`WIN$`/`WIN$N`, `WDO$`/`WDO$N`)
já ajustado. **Use o contínuo para backtest** e o contrato cheio para o tempo real.
`fontes/contratos.py` resolve o código vigente e marca a data de virada, para que o backtest
possa descartar a janela de rollover.

> As datas exatas de vencimento devem ser conferidas no calendário oficial da B3 antes de
> rodar o backtest em produção — as regras acima são o padrão, mas feriados deslocam datas.

## Horário de pregão (implementado em `contexto.py`)

O comportamento do WIN/WDO muda tanto ao longo do dia que horário é praticamente um
indicador. Regime padrão (horário de Brasília):

| Janela | Caráter | Tratamento no motor |
|---|---|---|
| 09:00–10:00 | abertura, volatilidade alta, muito ruído | padrões exigem score maior |
| 10:00–12:00 | tendência mais limpa | **janela preferida** |
| 12:00–14:00 | liquidez baixa, lateralização | penalidade forte |
| 14:00–16:00 | abertura dos EUA, direção | **janela preferida** |
| 16:00–17:30 | movimento final | normal |
| após 17:30 | ajuste e fechamento | não abrir posição nova |

Os horários mudam com o horário de verão americano e com leilões — são configuráveis em
`Limiares`, não hard-coded.
