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
import sys
import time
from datetime import UTC, datetime

from ..tipos import Candle, Serie, Timeframe
from .base import FonteIndisponivel
from .contratos import codigo_vigente, em_rollover, simbolo_continuo, vencimento

# Leituras até a série parar de crescer. Três é o suficiente na prática: a segunda já
# costuma vir completa, e a terceira confirma. Mais que isso só atrasaria o ciclo do
# coletor quando o símbolo genuinamente não tem mais dado.
TENTATIVAS_HISTORICO = 3
ESPERA_HISTORICO_S = 0.6

# Atraso do símbolo contínuo que justifica trocar pelo contrato vigente. Dez minutos são
# dois candles de M5 — abaixo disso pode ser só a defasagem normal da emenda; acima, é
# dado faltando.
ATRASO_MAXIMO_MIN = 10.0


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
        """`True` usa o símbolo contínuo ajustado (`WIN$N`) — o correto para backtest,
        onde a emenda entre contratos importa. `False` usa o contrato vigente, que é onde
        está a liquidez no tempo real.

        Mesmo com `True`, `ultimos()` troca para o contrato vigente se o contínuo estiver
        atrasado: ver `_simbolo_para_leitura`."""
        self._ligado = False

        # Símbolos já selecionados nesta sessão. `symbol_select` é idempotente, mas
        # chamá-lo a cada leitura custa uma ida ao terminal por timeframe por ciclo.
        self._seguros: set[str] = set()

        # Contínuos que já se provaram atrasados, e por qual contrato foram trocados.
        # Medir uma vez por sessão basta: um símbolo que atrasa não volta ao normal no
        # meio do pregão, e refazer a comparação a cada ciclo dobraria as leituras.
        self._trocados: dict[str, str] = {}

        # Ativos cujo aviso de rollover já foi dado. Sem isto o log ganharia uma linha
        # a cada timeframe de cada ciclo — 8 por 30 segundos — e o aviso viraria ruído.
        self._avisou_rollover: set[str] = set()

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
        # Os caches valem por sessão do terminal: reconectar pode cair noutro terminal,
        # com outros símbolos visíveis e outro estado de download de histórico.
        self._seguros.clear()
        self._trocados.clear()

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
        if simbolo in self._seguros:
            return
        if not mt5.symbol_select(simbolo, True):
            raise FonteIndisponivel(
                f"símbolo {simbolo} indisponível no terminal ({mt5.last_error()}). "
                "Sua corretora dá acesso a esse contrato?"
            )
        self._seguros.add(simbolo)

    # -- leitura ------------------------------------------------------------

    def _ultima_barra(self, simbolo: str, timeframe: Timeframe) -> datetime | None:
        """O `ts` da barra mais recente que o terminal tem para o símbolo, ou `None`."""
        barras = _mt5().copy_rates_from_pos(simbolo, _timeframe_mt5(timeframe), 0, 1)
        if barras is None or len(barras) == 0:
            return None
        return hora_do_servidor(int(barras[-1]["time"]))

    def _ler_barras(self, simbolo: str, timeframe: Timeframe, quantidade: int):
        """`copy_rates_from_pos` esperando o histórico assíncrono terminar de chegar.

        **O MT5 baixa histórico em segundo plano**, e `symbol_select` devolver `True` não
        significa que ele chegou. A mesma chamada que devolveu barras até 15:50 devolveu
        até 18:30 alguns segundos depois — sem erro nenhum, sem aviso. Num backfill de uma
        tacada isso vira dado faltando que ninguém percebe, porque a série *parece*
        completa: ela só termina cedo.

        O critério de "chegou" é a série parar de crescer entre duas leituras. Comparar
        com o relógio não serviria: fora do pregão a última barra é legitimamente antiga,
        e a espera nunca terminaria.
        """
        mt5 = _mt5()
        codigo = _timeframe_mt5(timeframe)

        anterior = None
        for tentativa in range(TENTATIVAS_HISTORICO):
            barras = mt5.copy_rates_from_pos(simbolo, codigo, 0, quantidade)
            if barras is None or len(barras) == 0:
                # Recém-selecionado costuma devolver vazio na primeira leitura; só é
                # erro de verdade se continuar vazio depois de esperar.
                if tentativa == TENTATIVAS_HISTORICO - 1:
                    return barras
                time.sleep(ESPERA_HISTORICO_S)
                continue

            fim = (len(barras), int(barras[-1]["time"]))
            if fim == anterior:
                return barras
            anterior = fim
            time.sleep(ESPERA_HISTORICO_S)

        return barras

    def ultimos(self, ativo: str, timeframe: Timeframe, quantidade: int) -> Serie:
        self._garantir_conexao()
        mt5 = _mt5()
        simbolo = self._simbolo_para_leitura(ativo, timeframe)
        self.selecionar(simbolo)

        barras = self._ler_barras(simbolo, timeframe, quantidade)
        if barras is None or len(barras) == 0:
            raise FonteIndisponivel(
                f"sem dados para {simbolo} {timeframe.rotulo}: {mt5.last_error()}"
            )
        return Serie(ativo.strip().upper()[:3], timeframe, _converter(barras))

    def _simbolo_para_leitura(self, ativo: str, timeframe: Timeframe) -> str:
        """O símbolo a usar, trocando o contínuo pelo vigente se ele estiver mesmo atrás.

        **Rede de segurança, não regra.** Em 07/08/2026 `WIN$N` e `WDO$N` apareceram
        parados às 15:50 enquanto `WINQ26` e `WDOU26` tinham o pregão até 18:30, e a
        leitura óbvia foi "o contínuo atrasa nesta corretora". **Não atrasa.** A tentativa
        de reproduzir mostrou que aquelas leituras eram do download assíncrono de
        histórico — o mesmo defeito que `_ler_barras` resolve. Com a espera no lugar, o
        contínuo devolve exatamente o que o contrato vigente devolve, e esta função nunca
        troca nada.

        O que sobra é um guarda contra dado velho de qualquer origem, e ele vale porque o
        modo de falha é o pior possível: uma série que termina cedo passa por completa.
        Quando dispara, avisa alto — se algum dia isso aparecer no log, é sinal de que
        existe um segundo fenômeno, e aí sim ele terá sido medido.

        `periodo()` não passa por aqui: em histórico longo a emenda entre contratos é
        justamente o motivo de pedir o contínuo.
        """
        base = ativo.strip().upper()[:3]
        hoje = datetime.now().date()
        pediu_base = ativo.strip().upper() in ("WIN", "WDO")

        # --- virada de contrato -------------------------------------------
        # `codigo_vigente` pula para o contrato SEGUINTE assim que a janela de rollover
        # abre, e está certo: o volume já migrou, e operar o que vence é operar book
        # vazio. Só que o contrato seguinte negocia noutro nível de preço — em
        # 10/08/2026 o WINV26 estava 3.500 pontos acima do WINQ26, puro custo de carrego.
        #
        # Gravar isso na mesma série `WIN` emenda dois papéis e inventa um gap que o
        # mercado nunca fez. ATR, tendência, pivôs e médias passam a ser calculados sobre
        # um salto de 2% que não existiu — e o pior é que tudo continua parecendo normal.
        #
        # Durante a janela a série continua no símbolo contínuo, que é o que preserva a
        # história. Quem decide não operar aí é o coletor, que suprime sinal enquanto
        # `em_rollover` for verdadeiro.
        if pediu_base and em_rollover(base, hoje):
            continuo = simbolo_continuo(base)
            if base not in self._avisou_rollover:
                self._avisou_rollover.add(base)
                print(
                    f"  {base} em rollover (vence {vencimento(base, hoje.year, hoje.month):%d/%m}) "
                    f"— série segue em {continuo}, sinais suspensos",
                    file=sys.stderr,
                )
            self.selecionar(continuo)
            return continuo

        simbolo = self.resolver_simbolo(ativo)
        if not self.continuo:
            return simbolo

        vigente = codigo_vigente(base, hoje)
        if vigente == simbolo or simbolo in self._trocados:
            return self._trocados.get(simbolo, simbolo)

        self.selecionar(simbolo)
        try:
            self.selecionar(vigente)
        except FonteIndisponivel:
            return simbolo  # sem contrato vigente no terminal, o contínuo é o que há

        fim_continuo = self._ultima_barra(simbolo, timeframe)
        fim_vigente = self._ultima_barra(vigente, timeframe)
        if fim_continuo is None or fim_vigente is None:
            return simbolo

        atraso = (fim_vigente - fim_continuo).total_seconds() / 60
        if atraso < ATRASO_MAXIMO_MIN:
            return simbolo

        # Alto de propósito: dado faltando em silêncio é o pior modo de falha do coletor.
        print(
            f"  {simbolo} está {atraso:.0f} min atrás de {vigente} "
            f"({fim_continuo:%d/%m %H:%M} vs {fim_vigente:%d/%m %H:%M}) — "
            f"usando {vigente}",
            file=sys.stderr,
        )
        self._trocados[simbolo] = vigente
        return vigente

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
