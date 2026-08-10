"""A camada de IA — o que ela faz, e o que ela deliberadamente não faz.

Até 10/08/2026 este arquivo não existia, e o painel de Request Logs do LiteLLM mostrava
**zero requisições**. O gateway, os seis modelos e a `kb/` inteira tinham sido construídos
e nunca conectados a nada. Este módulo é a conexão.

## A divisão de trabalho, e por que ela é assim

> **O motor decide. A IA audita e narra.**

O LLM **não** detecta padrão, não escolhe direção, não define entrada, stop ou alvo. Três
razões, e nenhuma é ideológica:

1. **Não dá para fazer backtest de um LLM.** A confiabilidade de cada padrão vem de rodar
   o detector sobre 60.000 candles. Um modelo que responde diferente para o mesmo prompt
   não tem taxa de acerto mensurável — e sem medição, o número que aparece na tela vira
   opinião com cara de estatística. É exatamente o erro que custou caro em `nuvem_negra`.
2. **Geometria é aritmética.** "O corpo engolfa o anterior" é uma comparação de floats.
   Terceirizar isso para um transformador é trocar uma resposta exata por uma provável.
3. **Se o LLM cair, o pregão continua.** O motor precisa emitir sinal com o gateway fora,
   com a chave vencida, com a OpenRouter instável.

## O que ela faz, então — e por que isso vale

O que o motor **não** sabe fazer é o mais difícil de codificar: pegar dezenas de números
espalhados (funil, calibração medida, viés por timeframe, estrutura, Fibonacci, médias,
custo) e responder *"o que tudo isso, junto, quer dizer?"*. Em particular:

- **Contra-argumento.** O caso mais forte CONTRA a operação, montado a partir dos próprios
  fatores que puxaram o score para baixo. Um dossiê que só lista o que favorece não é
  análise, é propaganda.
- **Auditoria de coerência.** A tese contradiz o que foi medido? Em 10/08 uma venda de WDO
  saiu com "confiabilidade 70%" de um padrão sem uma única medição no ativo — o tipo de
  incoerência que salta aos olhos quando alguém lê tudo junto, e passa batido em código.
- **Contexto do dia** que o motor não tem: o que a estrutura maior está fazendo, se o preço
  está num lugar historicamente relevante, o que invalida a leitura.

Nada disso muda entrada, stop ou alvo. Muda o que o operador entende antes de clicar.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# O gateway fala o protocolo da OpenAI. `urllib` em vez de um SDK: uma dependência a menos
# num pacote que precisa importar em Linux sem MT5 e rodar dentro de container enxuto.
URL_PADRAO = os.environ.get("LITELLM_URL", "http://litellm:4000")
CHAVE = os.environ.get("LITELLM_MASTER_KEY", "sk-cronos-trader-dev")

# Timeout curto de propósito: isto é enfeite sobre um sinal que já existe. Uma tela que
# trava 30s esperando narrativa é pior do que uma tela sem narrativa.
TIMEOUT_S = 25.0

RAIZ_KB = Path(__file__).resolve().parents[2] / "kb"


@dataclass(frozen=True, slots=True)
class Narrativa:
    """O que a IA acrescenta a um dossiê que já está completo sem ela."""

    leitura: str
    """O que está acontecendo, em português, para quem não vai ler 40 números."""

    contra: list[str] = field(default_factory=list)
    """O caso mais forte CONTRA a operação."""

    incoerencias: list[str] = field(default_factory=list)
    """Onde a tese não bate com o que foi medido. Vazio é o resultado esperado."""

    atencao: list[str] = field(default_factory=list)
    """O que vigiar nos próximos candles."""

    modelo: str = ""
    tokens: int = 0

    def para_dict(self) -> dict:
        return {
            "leitura": self.leitura,
            "contra": self.contra,
            "incoerencias": self.incoerencias,
            "atencao": self.atencao,
            "modelo": self.modelo,
            "tokens": self.tokens,
        }


class IAIndisponivel(RuntimeError):
    """Gateway fora, chave inválida, modelo sem crédito. Nunca sobe para o motor."""


def _kb(*nomes: str) -> str:
    """Trechos da base de conhecimento para dar vocabulário ao modelo.

    A `kb/` é o ebook destilado mais o que foi medido em WIN/WDO. Sem ela o modelo
    responde com o folclore genérico da internet sobre candlestick, que é justamente o
    que este produto existe para substituir.
    """
    partes = []
    for nome in nomes:
        caminho = RAIZ_KB / nome
        if caminho.exists():
            partes.append(caminho.read_text(encoding="utf-8")[:6000])
    return "\n\n---\n\n".join(partes)


SISTEMA = """Você é o analista sênior de uma mesa de day trade em mini-índice (WIN) e
mini-dólar (WDO) na B3. Escreve em português do Brasil, direto, sem jargão de guru.

O QUE VOCÊ NÃO FAZ — e isto é absoluto:
- não inventa padrão, preço, entrada, stop ou alvo. Esses números já foram calculados por
  um motor determinístico e testado. Você os LÊ.
- não estima probabilidade de acerto. Se um número não veio no dossiê, ele não existe.
- não usa "provavelmente vai subir/cair". Você descreve condição, não faz previsão.

O QUE VOCÊ FAZ:
- explica o que os números, JUNTOS, querem dizer
- monta o caso mais forte CONTRA a operação, a partir dos fatores que pesaram contra
- aponta incoerência entre a tese e o que foi MEDIDO (ex.: tese cita confiabilidade alta
  de um padrão que o dossiê marca como "sem medição neste ativo")
- diz o que vigiar nos próximos candles

REGRA DE HONESTIDADE, a mais importante:
Distinga sempre MEDIDO de ESTIMADO. O dossiê marca cada número. Um prior de ebook nunca
pode ser apresentado como evidência — se a amostra é pequena ou inexistente, diga isso.
Amostra abaixo de 30 operações não sustenta conclusão.

Responda SOMENTE com JSON válido, sem cercas de código:
{"leitura": "2 a 4 frases", "contra": ["..."], "incoerencias": ["..."], "atencao": ["..."]}
Listas vazias são respostas válidas e preferíveis a encher linguiça."""


def _chamar(mensagens: list[dict], modelo: str, max_tokens: int) -> tuple[str, str, int]:
    corpo = json.dumps(
        {
            "model": modelo,
            "messages": mensagens,
            "max_tokens": max_tokens,
            # Baixa, não zero: queremos consistência, e zero em alguns modelos degrada a
            # qualidade da prosa sem ganhar determinismo real.
            "temperature": 0.2,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{URL_PADRAO}/v1/chat/completions",
        data=corpo,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {CHAVE}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise IAIndisponivel(f"gateway de IA inacessível: {erro}") from erro
    except json.JSONDecodeError as erro:
        raise IAIndisponivel(f"resposta ilegível do gateway: {erro}") from erro

    try:
        texto = dados["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as erro:
        raise IAIndisponivel(f"resposta sem conteúdo: {str(dados)[:200]}") from erro

    return texto, dados.get("model", modelo), int(dados.get("usage", {}).get("total_tokens", 0))


def _extrair_json(texto: str) -> dict:
    """Modelo instruído a devolver JSON puro às vezes devolve JSON dentro de cerca.

    Tratar isso aqui é mais barato que brigar com o prompt: a falha é frequente o
    bastante para não valer uma retentativa, e rara o bastante para não valer um parser.
    """
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = limpo.split("```")[1] if "```" in limpo[3:] else limpo[3:]
        limpo = limpo.removeprefix("json").strip()
    inicio, fim = limpo.find("{"), limpo.rfind("}")
    if inicio == -1 or fim == -1:
        raise IAIndisponivel(f"modelo não devolveu JSON: {texto[:200]}")
    return json.loads(limpo[inicio : fim + 1])


def narrar(dossie: dict, modelo: str = "principal") -> Narrativa:
    """Lê o dossiê do motor e devolve a leitura, o contra-argumento e as incoerências.

    Levanta `IAIndisponivel` em qualquer falha. **Quem chama trata e segue** — nenhuma
    decisão do motor pode depender disto.
    """
    contexto = _kb("04-contexto-win-wdo.md", "08-contratos-e-custos.md")

    mensagens = [
        {"role": "system", "content": SISTEMA},
        {
            "role": "user",
            "content": (
                f"Base de conhecimento da mesa (use o vocabulário dela):\n{contexto}\n\n"
                f"=== DOSSIÊ DO MOTOR (todos os números já calculados) ===\n"
                f"{json.dumps(dossie, ensure_ascii=False, indent=1, default=str)[:12000]}"
            ),
        },
    ]

    texto, modelo_real, tokens = _chamar(mensagens, modelo, max_tokens=900)
    dados = _extrair_json(texto)

    def lista(chave: str) -> list[str]:
        valor = dados.get(chave) or []
        if isinstance(valor, str):
            return [valor]
        return [str(v) for v in valor][:6]

    return Narrativa(
        leitura=str(dados.get("leitura", "")).strip(),
        contra=lista("contra"),
        incoerencias=lista("incoerencias"),
        atencao=lista("atencao"),
        modelo=modelo_real,
        tokens=tokens,
    )


def disponivel() -> bool:
    """Ping barato para a tela saber se pode oferecer a narrativa."""
    try:
        req = urllib.request.Request(
            f"{URL_PADRAO}/health/liveliness",
            headers={"Authorization": f"Bearer {CHAVE}"},
        )
        with urllib.request.urlopen(req, timeout=4.0) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
