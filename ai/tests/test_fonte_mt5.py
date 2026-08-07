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

from trader_ai.fontes.mt5 import hora_do_servidor

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
