# frontend — a tela do Cronos Trader

React 19 · Vite 6 · TypeScript strict · Tailwind v4 · lightweight-charts.

**Novo, sem herdar nada dos outros produtos do workspace.** Design próprio, escuro,
orientado a quem passa o pregão olhando gráfico.

```powershell
npm install
npm run dev      # http://localhost:5180
```

O Vite faz proxy de `/api` e `/ws` para o backend em :1840 — o navegador fala só com
:5180, então não há CORS nem URL diferente entre dev e produção.

## Telas

| Rota | O que faz |
|---|---|
| `/entrar` | Login, **com o estado da stack visível antes de tentar** (banco, motor, MT5, candles) |
| `/registrar` | Conta nova, com o capital que dimensiona a posição |
| `/` | Painel: métricas, sinais ao vivo por WebSocket, placar por padrão, infraestrutura |
| `/grafico` | Candles + marcações de padrão + linhas de entrada/stop/alvo do sinal selecionado |
| `/sinais` | Histórico com filtros e a explicação do score de cada sinal |
| `/padroes` | Os 60 detectores: prior do ebook × confiabilidade medida |
| `/backtest` | Dispara walk-forward e mostra o resultado fora da amostra |

## Decisões de design

**Escuro por padrão, não por moda.** Quem opera passa horas olhando gráfico, e o
contraste alto de fundo claro cansa.

**As cores direcionais são as únicas saturadas.** Se tudo brilha, nada chama atenção — e
o que precisa chamar atenção aqui é o sinal.

**Alta é ciano-esverdeado, baixa é rosa-avermelhado**, não verde/vermelho puro. Cerca de
8% dos homens têm deficiência de visão para vermelho-verde; essa dupla continua
distinguível por matiz **e** por luminosidade. Direção também sempre aparece escrita
(`▲ COMPRA`), nunca só por cor.

**Números em fonte tabular.** Sem isso, preço e score dançam na vertical a cada
atualização e comparar linhas fica desconfortável.

**Entrada, stop e alvo têm hierarquia acima de tudo no cartão de sinal.** É o que a
pessoa precisa ler em dois segundos para digitar na corretora. Score, padrão e
confluência são a justificativa — vêm depois.

**"Amostra insuficiente" é exibido, não escondido.** Taxa de acerto sobre 4 operações não
é evidência, e a tela precisa dizer isso em vez de mostrar "75%" com a mesma confiança de
um número medido sobre 300 trades.

**Zero sinais tem texto próprio**, explicando que é o resultado esperado. Um motor que
aprova tudo o que detecta é um motor que perde dinheiro — a tela não pode fazer parecer
que algo quebrou.

## Estrutura

```
src/
├─ lib/
│  ├─ api.ts             cliente HTTP com renovação de sessão serializada
│  ├─ auth.tsx           contexto de autenticação
│  ├─ useSinaisAoVivo.ts WebSocket com backoff exponencial limitado
│  ├─ formato.ts         pt-BR: preço por ativo, R$, %, R, datas
│  └─ tipos.ts           contratos da API
├─ components/
│  ├─ Layout.tsx         casca, navegação, indicador de conexão
│  ├─ CartaoSinal.tsx    o elemento central do produto
│  └─ ui.tsx             primitivas
└─ paginas/              uma por rota
```

## Detalhes que costumam morder

**A renovação de sessão é serializada.** A tela dispara várias chamadas em paralelo; sem
uma promise única, cinco delas tentariam renovar ao mesmo tempo, a primeira rotacionaria o
refresh e as outras quatro receberiam 401 com um token recém-revogado.

**O gráfico é imperativo.** `lightweight-charts` não reage a props: a integração cria o
gráfico uma vez e atualiza por efeito. Recriar a cada render perderia o zoom e o
posicionamento do usuário a cada atualização — inaceitável em algo que a pessoa fica
olhando.

**Marcações de padrão são limitadas às 120 mais recentes.** Acima disso o gráfico vira
uma sopa de setas e nenhuma delas comunica nada.
