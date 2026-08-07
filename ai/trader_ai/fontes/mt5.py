"""Adapter do MetaTrader 5 — a única fonte gratuita de tempo real para WIN/WDO.

**Pré-requisitos operacionais** (não dá para contornar por código):

1. Windows, com o terminal **MT5 instalado, aberto e logado**
2. Conta — demo ou real — numa **corretora brasileira** que ofereça MT5
   (Clear, XP, Rico, Modal, BTG). Demo da MetaQuotes **não** tem ativos da B3.
3. `pip install MetaTrader5` (Windows-only)
4. O símbolo precisa estar visível no *Observador de Mercado* do terminal — o
   `selecionar()` abaixo faz isso, mas o terminal precisa ter direito ao ativo.

Por isso o coletor roda como processo no **host**, não em container. É a única peça não
portável do sistema, e está isolada aqui de propósito: `import MetaTrader5` acontece
dentro das funções, nunca no topo do módulo. Importar `trader_ai.fontes.mt5` em Linux
não quebra — só falha ao usar.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from ..tipos import Candle, Serie, Timeframe
from .base import FonteIndisponivel
from .contratos import codigo_vigente, simbolo_continuo


def _credenciais_do_ambiente() -> tuple[int, str, str] | None:
    """`(login, senha, servidor)` se as três variáveis estiverem definidas.

    Exige as três juntas: logar exige conta, senha e servidor, e aceitar duas de três
    produziria uma falha confusa em vez de dizer o que falta.
    """
    login = os.environ.get("MT5_LOGIN", "").strip()
    senha = os.environ.get("MT5_SENHA", "")
    servidor = os.environ.get("MT5_SERVIDOR", "").strip()
    if not (login and senha and servidor):
        return None
    try:
        return int(login), senha, servidor
    except ValueError as erro:
        raise FonteIndisponivel(
            f"MT5_LOGIN precisa ser o número da conta, recebi {login!r}"
        ) from erro


def _explicar_falha(codigo: int, mensagem: str, tinha_credenciais: bool) -> str:
    """Traduz o código do MT5 para o que fazer a respeito.

    Os códigos do terminal são secos demais para ajudar: `-6 Authorization failed` não
    diz que o problema é não haver conta logada, e é justamente esse o caso mais comum.
    """
    base = f"MT5 recusou a conexão ({codigo}: {mensagem}). "

    if codigo == -6:
        if tinha_credenciais:
            return base + (
                "Credenciais rejeitadas. Confira MT5_LOGIN (número da conta), MT5_SENHA e "
                "MT5_SERVIDOR — o nome do servidor precisa ser exatamente o que a "
                "corretora informou, e a senha é a de negociação, não a do site."
            )
        return base + (
            "Não há conta logada no terminal. Abra o MetaTrader 5 e faça login numa "
            "corretora que dê acesso à B3 (Clear, XP, Rico, Modal, Terra) — demo serve. "
            "A demo padrão da MetaQuotes conecta mas NÃO tem WIN nem WDO."
        )
    if codigo == -10003:
        return base + "Caminho do terminal inválido. Ajuste MT5_CAMINHO."
    if codigo in (-10004, -10005):
        return base + "Terminal não está aberto. Abra o MetaTrader 5 e deixe-o rodando."
    return base + "Rode `python scripts/diagnostico_mt5.py` para o passo a passo."


def _mt5():
    """Importa o pacote sob demanda e traduz a ausência num erro compreensível."""
    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError as erro:
        raise FonteIndisponivel(
            "pacote MetaTrader5 não instalado. Este é o caminho de tempo real e só "
            "funciona no Windows: pip install 'trader-ai[mt5]'"
        ) from erro
    return mt5


def _timeframe_mt5(tf: Timeframe):
    mt5 = _mt5()
    mapa = {
        Timeframe.M5: mt5.TIMEFRAME_M5,
        Timeframe.M15: mt5.TIMEFRAME_M15,
        Timeframe.M30: mt5.TIMEFRAME_M30,
        Timeframe.H1: mt5.TIMEFRAME_H1,
        Timeframe.D1: mt5.TIMEFRAME_D1,
    }
    if tf not in mapa:
        raise ValueError(f"timeframe não suportado pelo adapter: {tf}")
    return mapa[tf]


def hora_do_servidor(epoch: int) -> datetime:
    """Converte o campo `time` do MT5 no relógio do servidor da corretora.

    **Tem que ser `UTC`, e isso não é detalhe.** O MT5 não entrega um instante absoluto:
    ele pega o relógio de parede do servidor e o codifica *como se fosse* UTC. Ler esse
    número com `datetime.fromtimestamp()` aplica o fuso da máquina por cima — e no Brasil
    (UTC−3) isso enterra todo candle 3 horas no passado.

    O erro é silencioso da pior forma possível, porque o resultado continua parecendo um
    pregão: 09:00–18:25 vira 06:00–15:25, que é horário plausível para quem olha de
    relance. Custou uma base inteira deslocada — inclusive os CSVs exportados por este
    mesmo caminho — e, com ela, a rotulagem errada de todo estudo por janela do pregão.

    Como conferir em 10 segundos, com o pregão aberto: o último candle de M5 tem que ficar
    a menos de 5 minutos de `datetime.now()`. Se der ~180 minutos, é este bug de volta.

    A corretora B3 roda o servidor no horário de Brasília, então o relógio do servidor já
    é o horário local — e o Brasil não tem mais horário de verão desde 2019, o que faz o
    deslocamento ser constante e não sazonal.
    """
    return datetime.fromtimestamp(epoch, UTC).replace(tzinfo=None)


def _converter(barras) -> list[Candle]:
    """Converte o array estruturado do MT5 em `Candle`.

    Usa `tick_volume` e não `real_volume`: no WIN/WDO muitas corretoras devolvem
    `real_volume` zerado, e o fator de volume da confluência ficaria sempre desligado
    sem que ninguém notasse.
    """
    return [
        Candle(
            ts=hora_do_servidor(int(b["time"])),
            abertura=float(b["open"]),
            maxima=float(b["high"]),
            minima=float(b["low"]),
            fechamento=float(b["close"]),
            volume=float(b["tick_volume"]),
        )
        for b in barras
    ]


class MetaTrader5Fonte:
    """Implementa `FonteDados` sobre o terminal MT5 local.

    Use como context manager para garantir o `shutdown()`:

        with MetaTrader5Fonte() as fonte:
            serie = fonte.ultimos("WIN", Timeframe.M5, 2000)
    """

    def __init__(self, caminho_terminal: str | None = None, continuo: bool = False):
        self.caminho_terminal = caminho_terminal or os.environ.get("MT5_CAMINHO") or None
        self.continuo = continuo
        """`True` usa o símbolo contínuo ajustado (`WIN$N`) — o correto para backtest.
        `False` usa o contrato vigente, que é onde está a liquidez no tempo real."""
        self._ligado = False

    # -- ciclo de vida ------------------------------------------------------

    def conectar(self) -> None:
        """Acopla-se ao terminal MT5.

        **O caminho normal não usa credencial nenhuma.** `initialize()` sem argumentos
        encontra o terminal aberto e usa a conta que já está logada nele — você faz login
        uma vez, pela interface, e o Python herda a sessão.

        O login programático existe só para o coletor sobreviver a um reboot sem alguém
        digitando senha: se `MT5_LOGIN`, `MT5_SENHA` e `MT5_SERVIDOR` estiverem no
        ambiente, eles são usados. Nunca coloque essas variáveis em arquivo versionado —
        são credenciais de conta de investimento.
        """
        mt5 = _mt5()
        credenciais = _credenciais_do_ambiente()

        if credenciais:
            login, senha, servidor = credenciais
            ok = mt5.initialize(
                *( [self.caminho_terminal] if self.caminho_terminal else [] ),
                login=login,
                password=senha,
                server=servidor,
            )
        elif self.caminho_terminal:
            ok = mt5.initialize(self.caminho_terminal)
        else:
            ok = mt5.initialize()

        if not ok:
            codigo, mensagem = mt5.last_error()
            raise FonteIndisponivel(_explicar_falha(codigo, mensagem, bool(credenciais)))
        self._ligado = True

    def desconectar(self) -> None:
        if self._ligado:
            _mt5().shutdown()
            self._ligado = False

    def __enter__(self) -> MetaTrader5Fonte:
        self.conectar()
        return self

    def __exit__(self, *_) -> None:
        self.desconectar()

    def _garantir_conexao(self) -> None:
        if not self._ligado:
            self.conectar()

    # -- símbolos -----------------------------------------------------------

    def resolver_simbolo(self, ativo: str, dia: datetime | None = None) -> str:
        """Nome do símbolo no terminal para `ativo` (`WIN` ou `WDO`)."""
        base = ativo.strip().upper()
        if len(base) > 3 and not base.endswith("$N"):
            return base  # já veio um código específico, respeita
        if self.continuo:
            return simbolo_continuo(base)
        return codigo_vigente(base, (dia or datetime.now()).date())

    def selecionar(self, simbolo: str) -> None:
        """Torna o símbolo visível no Observador de Mercado.

        Sem isto, `copy_rates_*` devolve `None` mesmo com o símbolo existindo — é o
        erro mais comum de quem começa com a API.
        """
        mt5 = _mt5()
        if not mt5.symbol_select(simbolo, True):
            raise FonteIndisponivel(
                f"símbolo {simbolo} indisponível no terminal ({mt5.last_error()}). "
                "Sua corretora dá acesso a esse contrato?"
            )

    # -- leitura ------------------------------------------------------------

    def ultimos(self, ativo: str, timeframe: Timeframe, quantidade: int) -> Serie:
        self._garantir_conexao()
        mt5 = _mt5()
        simbolo = self.resolver_simbolo(ativo)
        self.selecionar(simbolo)

        barras = mt5.copy_rates_from_pos(simbolo, _timeframe_mt5(timeframe), 0, quantidade)
        if barras is None or len(barras) == 0:
            raise FonteIndisponivel(
                f"sem dados para {simbolo} {timeframe.rotulo}: {mt5.last_error()}"
            )
        return Serie(ativo.strip().upper()[:3], timeframe, _converter(barras))

    def periodo(
        self, ativo: str, timeframe: Timeframe, inicio: datetime, fim: datetime
    ) -> Serie:
        self._garantir_conexao()
        mt5 = _mt5()
        simbolo = self.resolver_simbolo(ativo, inicio)
        self.selecionar(simbolo)

        barras = mt5.copy_rates_range(simbolo, _timeframe_mt5(timeframe), inicio, fim)
        if barras is None or len(barras) == 0:
            raise FonteIndisponivel(
                f"sem dados para {simbolo} entre {inicio} e {fim}: {mt5.last_error()}"
            )
        return Serie(ativo.strip().upper()[:3], timeframe, _converter(barras))

    def ultimo_preco(self, ativo: str) -> float:
        """Último preço negociado — para acompanhar posição entre fechamentos de candle."""
        self._garantir_conexao()
        mt5 = _mt5()
        simbolo = self.resolver_simbolo(ativo)
        self.selecionar(simbolo)
        tick = mt5.symbol_info_tick(simbolo)
        if tick is None:
            raise FonteIndisponivel(f"sem tick para {simbolo}: {mt5.last_error()}")
        return float(tick.last or tick.bid)
