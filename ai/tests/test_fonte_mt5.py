"""O campo `time` do MT5 é relógio de parede do servidor, não instante absoluto.

Este arquivo existe por causa de um bug que atravessou toda a construção da base
histórica: `datetime.fromtimestamp()` aplicava o fuso da máquina por cima de um valor que
já era horário local da corretora, e todo candle nascia 3 horas no passado.

O que tornou o bug caro foi ele não parecer bug. O pregão 09:00–18:25 virava 06:00–15:25 —
faixa plausível o bastante para ninguém desconfiar olhando a tela. O estrago não apareceu
em lugar nenhum óbvio: apareceu nos estudos por janela do pregão, que mediram a janela
certa com o nome errado.

Os epochs abaixo foram colhidos do terminal real em 07/08/2026, com o pregão aberto. Os
testes não importam o pacote `MetaTrader5` (Windows-only) — exercitam só a conversão, que
é pura.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from trader_ai.fontes import mt5 as mt5_mod
from trader_ai.fontes.mt5 import MetaTrader5Fonte, hora_do_servidor
from trader_ai.tipos import Timeframe

# Barra de M5 das 15:20 de 07/08/2026, lida do terminal enquanto o relógio marcava 15:20.
EPOCH_15H20 = 1786116000
# Primeira barra do mesmo pregão: 09:00, a abertura da B3.
EPOCH_ABERTURA = 1786093200


def test_devolve_o_relogio_do_servidor():
    """A conversão certa reproduz o relógio de parede que o terminal mostra.

    Numa máquina em UTC−3, `datetime.fromtimestamp()` devolveria 12:20 aqui — que é
    exatamente o bug. O valor esperado é o que o operador vê no gráfico.
    """
    assert hora_do_servidor(EPOCH_15H20) == datetime(2026, 8, 7, 15, 20)


def test_resultado_e_ingenuo():
    """`Candle.ts` é naive em todo o motor; um datetime aware quebraria as comparações."""
    assert hora_do_servidor(EPOCH_15H20).tzinfo is None


def test_abertura_cai_na_faixa_da_b3():
    """A checagem que teria pego o bug no dia em que ele nasceu.

    A B3 negocia mini-contratos das 9h às 18h25. Com a conversão errada a abertura cai às
    06:00 — fora da faixa, e este teste acusa sem depender do fuso da máquina de quem roda.
    """
    abertura = hora_do_servidor(EPOCH_ABERTURA)
    assert abertura == datetime(2026, 8, 7, 9, 0)
    assert 9 <= abertura.hour < 19, (
        f"abertura em {abertura:%H:%M}, fora do pregão da B3 — "
        "sinal clássico de conversão de fuso aplicada duas vezes."
    )


def test_intervalo_entre_barras_e_preservado():
    """Deslocamento constante não pode virar deslocamento variável.

    Se alguém trocar a conversão por algo sensível a horário de verão, a distância entre
    duas barras do mesmo pregão deixa de bater com o relógio.
    """
    delta = hora_do_servidor(EPOCH_15H20) - hora_do_servidor(EPOCH_ABERTURA)
    assert delta.total_seconds() == EPOCH_15H20 - EPOCH_ABERTURA


# ---------------------------------------------------------------------------
# As duas armadilhas do terminal, medidas em 07/08/2026 e travadas aqui.
# ---------------------------------------------------------------------------

M5 = 5 * 60


def _barras(quantas: int, fim_epoch: int):
    """Array estruturado no formato que o `copy_rates_*` devolve."""
    tipo = np.dtype(
        [
            ("time", "i8"),
            ("open", "f8"),
            ("high", "f8"),
            ("low", "f8"),
            ("close", "f8"),
            ("tick_volume", "f8"),
        ]
    )
    inicio = fim_epoch - (quantas - 1) * M5
    return np.array(
        [(inicio + i * M5, 100.0, 101.0, 99.0, 100.5, 10.0) for i in range(quantas)],
        dtype=tipo,
    )


class TerminalFalso:
    """Dublê do pacote MetaTrader5. Só o que o adapter chama."""

    # Os valores reais do pacote; o adapter os traduz em `_timeframe_mt5`.
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_D1 = 16408

    def __init__(self, series: dict[str, list]):
        # `series[simbolo]` é a lista de respostas sucessivas de `copy_rates_from_pos`.
        self.series = {k: list(v) for k, v in series.items()}
        self.ultima = {k: v[-1] for k, v in series.items()}
        self.chamadas: dict[str, int] = {}
        self.selecionados: list[str] = []

    def symbol_select(self, simbolo, _visivel=True):
        if simbolo not in self.series:
            return False
        self.selecionados.append(simbolo)
        return True

    def copy_rates_from_pos(self, simbolo, _tf, _de, quantidade):
        n = self.chamadas.get(simbolo, 0)
        self.chamadas[simbolo] = n + 1
        respostas = self.series[simbolo]
        barras = respostas[n] if n < len(respostas) else self.ultima[simbolo]
        if barras is None:
            return None
        return barras[-quantidade:] if quantidade < len(barras) else barras

    def last_error(self):
        return (0, "ok")

    def shutdown(self):
        pass


@pytest.fixture
def sem_espera(monkeypatch):
    """O adapter dorme entre tentativas; o teste não precisa."""
    monkeypatch.setattr(mt5_mod.time, "sleep", lambda _s: None)


def _ligar(monkeypatch, terminal) -> MetaTrader5Fonte:
    monkeypatch.setattr(mt5_mod, "_mt5", lambda: terminal)
    fonte = MetaTrader5Fonte()
    fonte._ligado = True
    return fonte


def test_espera_o_historico_assincrono_terminar_de_chegar(monkeypatch, sem_espera):
    """A primeira leitura veio curta; a série completa só apareceu na seguinte.

    É o bug que custou de 15:50 a 18:30 de 07/08: `symbol_select` devolveu `True`, a
    leitura devolveu barras sem erro nenhum, e a série simplesmente terminava cedo.
    """
    curta = _barras(60, EPOCH_15H20 - 40 * M5)
    completa = _barras(100, EPOCH_15H20)
    terminal = TerminalFalso({"WINQ26": [curta, completa, completa]})

    serie = _ligar(monkeypatch, terminal).ultimos("WIN", Timeframe.M5, 100)

    assert len(serie) == 100
    assert serie[-1].ts == hora_do_servidor(EPOCH_15H20)


def test_para_de_reler_quando_a_serie_estabiliza(monkeypatch, sem_espera):
    """Duas leituras iguais bastam: não pode custar uma rodada extra por ciclo."""
    completa = _barras(100, EPOCH_15H20)
    terminal = TerminalFalso({"WINQ26": [completa, completa, completa]})

    _ligar(monkeypatch, terminal).ultimos("WIN", Timeframe.M5, 100)

    assert terminal.chamadas["WINQ26"] == 2


def test_primeira_leitura_vazia_nao_e_erro(monkeypatch, sem_espera):
    """Símbolo recém-selecionado costuma devolver vazio antes de o histórico chegar."""
    completa = _barras(50, EPOCH_15H20)
    terminal = TerminalFalso({"WINQ26": [None, completa, completa]})

    serie = _ligar(monkeypatch, terminal).ultimos("WIN", Timeframe.M5, 50)

    assert len(serie) == 50


def test_troca_o_continuo_atrasado_pelo_contrato_vigente(monkeypatch, sem_espera):
    """`WIN$N` parou às 15:50 enquanto `WINQ26` tinha até 18:30. Trocar não é opcional.

    Uma série que termina cedo passa por completa — o modo de falha é dado sumindo em
    silêncio, que é o pior que um coletor pode fazer.
    """
    atrasado = _barras(80, EPOCH_15H20 - 60 * M5)
    em_dia = _barras(80, EPOCH_15H20)
    terminal = TerminalFalso({"WIN$N": [atrasado] * 3, "WINQ26": [em_dia] * 3})

    fonte = _ligar(monkeypatch, terminal)
    fonte.continuo = True
    serie = fonte.ultimos("WIN", Timeframe.M5, 80)

    assert serie[-1].ts == hora_do_servidor(EPOCH_15H20)
    assert fonte._trocados == {"WIN$N": "WINQ26"}


def test_continuo_em_dia_e_respeitado(monkeypatch, sem_espera):
    """Quem pediu o contínuo pediu a emenda entre contratos, não o contrato da vez."""
    iguais = _barras(80, EPOCH_15H20)
    terminal = TerminalFalso({"WIN$N": [iguais] * 3, "WINQ26": [iguais] * 3})

    fonte = _ligar(monkeypatch, terminal)
    fonte.continuo = True
    fonte.ultimos("WIN", Timeframe.M5, 80)

    assert fonte._trocados == {}


def test_a_comparacao_de_atraso_roda_uma_vez_por_sessao(monkeypatch, sem_espera):
    """Medir a cada ciclo dobraria as leituras sem mudar a resposta."""
    atrasado = _barras(80, EPOCH_15H20 - 60 * M5)
    em_dia = _barras(80, EPOCH_15H20)
    terminal = TerminalFalso({"WIN$N": [atrasado] * 3, "WINQ26": [em_dia] * 6})

    fonte = _ligar(monkeypatch, terminal)
    fonte.continuo = True
    fonte.ultimos("WIN", Timeframe.M5, 80)
    antes = terminal.chamadas["WIN$N"]
    fonte.ultimos("WIN", Timeframe.M5, 80)

    assert terminal.chamadas["WIN$N"] == antes


def test_desconectar_limpa_os_caches(monkeypatch, sem_espera):
    """Reconectar pode cair noutro terminal, com outro estado de histórico."""
    atrasado = _barras(80, EPOCH_15H20 - 60 * M5)
    em_dia = _barras(80, EPOCH_15H20)
    terminal = TerminalFalso({"WIN$N": [atrasado] * 9, "WINQ26": [em_dia] * 9})

    fonte = _ligar(monkeypatch, terminal)
    fonte.continuo = True
    fonte.ultimos("WIN", Timeframe.M5, 80)
    fonte.desconectar()

    assert fonte._trocados == {}
    assert fonte._seguros == set()
