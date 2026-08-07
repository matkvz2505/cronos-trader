"""Testes dos detectores de reversão.

Cada padrão tem duas metades:

- o caso **positivo**, montado exatamente como o ebook descreve;
- pelo menos um **vizinho negativo** — uma formação que quase é o padrão e não pode
  disparar.

O negativo é o teste que importa. Um detector frouxo passa em qualquer positivo; o que
o denuncia é ele aceitar a formação errada.
"""

from __future__ import annotations

from trader_ai.padroes import reversao as rev

from .conftest import (
    corpo_pequeno_alta,
    corpo_pequeno_baixa,
    doji,
    forca_alta,
    forca_baixa,
    martelo,
    martelo_invertido,
    marubozu_alta,
    marubozu_baixa,
    vela,
)

# ---------------------------------------------------------------------------
# Engolfo
# ---------------------------------------------------------------------------


def test_engolfo_alta_dispara(ctx_baixa, lim):
    anterior = vela(130_000, 130_050, 129_800, 129_850)
    atual = vela(129_800, 130_150, 129_780, 130_100)
    assert rev.engolfo_alta([anterior, atual], ctx_baixa, lim) is not None


def test_engolfo_alta_nao_dispara_sem_cobrir_o_corpo(ctx_baixa, lim):
    """Verde que sobe mas para dentro do corpo vermelho: não é engolfo."""
    anterior = vela(130_000, 130_050, 129_800, 129_850)
    atual = vela(129_870, 130_000, 129_860, 129_980)
    assert rev.engolfo_alta([anterior, atual], ctx_baixa, lim) is None


def test_engolfo_folgado_tem_forca_maior_que_engolfo_raspando(ctx_baixa, lim):
    """A força é contínua — é o ponto de devolver float em vez de booleano."""
    anterior = vela(130_000, 130_050, 129_900, 129_900)
    raspando = vela(129_895, 130_020, 129_880, 130_005)
    folgado = vela(129_700, 130_400, 129_690, 130_350)

    fraco = rev.engolfo_alta([anterior, raspando], ctx_baixa, lim)
    forte = rev.engolfo_alta([anterior, folgado], ctx_baixa, lim)
    assert fraco is not None and forte is not None
    assert forte > fraco


def test_engolfo_baixa_dispara(ctx_alta, lim):
    anterior = vela(129_850, 130_050, 129_800, 130_000)
    atual = vela(130_100, 130_150, 129_780, 129_800)
    assert rev.engolfo_baixa([anterior, atual], ctx_alta, lim) is not None


# ---------------------------------------------------------------------------
# Harami
# ---------------------------------------------------------------------------


def test_harami_alta_dispara(ctx_baixa, lim):
    mae = forca_baixa(130_000, tamanho=200)
    bebe = vela(129_850, 129_900, 129_830, 129_890)
    assert rev.harami_alta([mae, bebe], ctx_baixa, lim) is not None


def test_harami_alta_nao_dispara_com_bebe_fora_do_corpo(ctx_baixa, lim):
    mae = forca_baixa(130_000, tamanho=200)
    bebe = vela(129_850, 130_050, 129_830, 130_020)  # estoura o topo do corpo da mãe
    assert rev.harami_alta([mae, bebe], ctx_baixa, lim) is None


def test_harami_alta_nao_dispara_com_mae_curta(ctx_baixa, lim):
    """Mãe com corpo abaixo de 0.8 ATR não é 'corpo longo'."""
    mae = forca_baixa(130_000, tamanho=40)
    bebe = vela(129_985, 129_995, 129_975, 129_990)
    assert rev.harami_alta([mae, bebe], ctx_baixa, lim) is None


def test_pombo_correio_exige_bebe_da_mesma_cor(ctx_baixa, lim):
    mae = forca_baixa(130_000, tamanho=200)
    bebe_vermelho = vela(129_900, 129_910, 129_830, 129_850)
    bebe_verde = vela(129_850, 129_900, 129_830, 129_890)

    assert rev.pombo_correio([mae, bebe_vermelho], ctx_baixa, lim) is not None
    assert rev.pombo_correio([mae, bebe_verde], ctx_baixa, lim) is None


# ---------------------------------------------------------------------------
# Martelo / Enforcado / Estrela Cadente — mesma geometria, nomes diferentes
# ---------------------------------------------------------------------------


def test_martelo_e_enforcado_compartilham_geometria(ctx_baixa, ctx_alta, lim):
    """O ebook: 'morfologicamente igual, o que muda é a posição no gráfico'.

    O detector não separa os dois — quem separa é `tendencia_requerida` no catálogo.
    """
    c = martelo(130_000)
    assert rev.martelo([c], ctx_baixa, lim) is not None
    assert rev.enforcado([c], ctx_alta, lim) is not None


def test_martelo_nao_dispara_com_sombra_superior_grande(ctx_baixa, lim):
    c = vela(130_000, 130_120, 129_940, 130_010)
    assert rev.martelo([c], ctx_baixa, lim) is None


def test_martelo_invertido_e_estrela_cadente_compartilham_geometria(ctx_baixa, ctx_alta, lim):
    c = martelo_invertido(130_000)
    assert rev.martelo_invertido([c], ctx_baixa, lim) is not None
    assert rev.estrela_cadente([c], ctx_alta, lim) is not None


def test_martelo_e_martelo_invertido_sao_mutuamente_exclusivos(ctx_baixa, lim):
    assert rev.martelo_invertido([martelo(130_000)], ctx_baixa, lim) is None
    assert rev.martelo([martelo_invertido(130_000)], ctx_baixa, lim) is None


# ---------------------------------------------------------------------------
# Linha de Perfuração / Nuvem Negra — os dois "de alta confiabilidade"
# ---------------------------------------------------------------------------


def test_linha_perfuracao_dispara(ctx_baixa, lim):
    c1 = forca_baixa(130_000, tamanho=200)  # 130000 -> 129800, mínima 129795
    c2 = vela(129_760, 129_960, 129_755, 129_940)  # abre abaixo da mínima, fecha acima do meio
    assert rev.linha_perfuracao([c1, c2], ctx_baixa, lim) is not None


def test_linha_perfuracao_nao_dispara_sem_perfurar_a_metade(ctx_baixa, lim):
    """Fecha abaixo da metade do corpo anterior: não 'perfurou'."""
    c1 = forca_baixa(130_000, tamanho=200)
    c2 = vela(129_760, 129_890, 129_755, 129_870)  # meio do corpo de c1 = 129900
    assert rev.linha_perfuracao([c1, c2], ctx_baixa, lim) is None


def test_linha_perfuracao_nao_dispara_se_engolfa(ctx_baixa, lim):
    """Fechando acima da abertura do primeiro já é engolfo, não perfuração."""
    c1 = forca_baixa(130_000, tamanho=200)
    c2 = vela(129_760, 130_100, 129_755, 130_050)
    assert rev.linha_perfuracao([c1, c2], ctx_baixa, lim) is None


def test_nuvem_negra_dispara(ctx_alta, lim):
    c1 = forca_alta(129_800, tamanho=200)  # 129800 -> 130000, máxima 130005
    c2 = vela(130_040, 130_045, 129_850, 129_860)
    assert rev.nuvem_negra([c1, c2], ctx_alta, lim) is not None


# ---------------------------------------------------------------------------
# Estrela da Manhã / da Noite
# ---------------------------------------------------------------------------


def test_estrela_manha_dispara(ctx_baixa, lim):
    c1 = forca_baixa(130_000, tamanho=200)  # corpo 130000 -> 129800, meio = 129900
    c2 = corpo_pequeno_baixa(129_700, tamanho=20)  # corpo 129700 -> 129680
    c3 = forca_alta(129_720, tamanho=250)  # fecha em 129970 > 129900
    assert rev.estrela_manha([c1, c2, c3], ctx_baixa, lim) is not None


def test_estrela_manha_nao_dispara_sem_retomar_a_metade(ctx_baixa, lim):
    c1 = forca_baixa(130_000, tamanho=200)
    c2 = corpo_pequeno_baixa(129_700, tamanho=20)
    c3 = forca_alta(129_720, tamanho=100)  # fecha em 129820 < 129900
    assert rev.estrela_manha([c1, c2, c3], ctx_baixa, lim) is None


def test_estrela_manha_nao_dispara_com_estrela_dentro_do_corpo(ctx_baixa, lim):
    """A estrela precisa estar isolada ABAIXO dos corpos vizinhos."""
    c1 = forca_baixa(130_000, tamanho=200)
    c2 = corpo_pequeno_baixa(129_900, tamanho=20)  # dentro do corpo de c1
    c3 = forca_alta(129_880, tamanho=250)
    assert rev.estrela_manha([c1, c2, c3], ctx_baixa, lim) is None


def test_estrela_noite_dispara(ctx_alta, lim):
    c1 = forca_alta(129_800, tamanho=200)  # corpo 129800 -> 130000, meio = 129900
    c2 = corpo_pequeno_alta(130_100, tamanho=20)  # corpo 130100 -> 130120
    c3 = forca_baixa(130_080, tamanho=250)  # fecha em 129830 < 129900
    assert rev.estrela_noite([c1, c2, c3], ctx_alta, lim) is not None


# ---------------------------------------------------------------------------
# Bebê Abandonado — ERRATA item 1
# ---------------------------------------------------------------------------


def test_bebe_abandonado_alta_dispara(ctx_baixa, lim):
    c1 = forca_baixa(130_000, tamanho=200)  # mínima 129795
    c2 = doji(129_700, sombra=30)  # range 129670..129730, abaixo de tudo
    c3 = forca_alta(129_760, tamanho=200)  # mínima 129755 > 129730
    assert rev.bebe_abandonado_alta([c1, c2, c3], ctx_baixa, lim) is not None


def test_bebe_abandonado_alta_nao_dispara_sem_gap(ctx_baixa, lim):
    """Doji encostando no candle anterior deixa de ser 'abandonado'."""
    c1 = forca_baixa(130_000, tamanho=200)
    c2 = doji(129_800, sombra=30)  # sobrepõe o range de c1
    c3 = forca_alta(129_790, tamanho=200)
    assert rev.bebe_abandonado_alta([c1, c2, c3], ctx_baixa, lim) is None


def test_bebe_abandonado_baixa_exige_primeiro_candle_verde(ctx_alta, lim):
    """ERRATA item 1 — o ebook diz 'vermelho', copiando o texto da versão de alta.

    Num topo, o primeiro candle é o último impulso comprador.
    """
    c1_verde = forca_alta(129_800, tamanho=200)  # máxima 130005
    c2 = doji(130_100, sombra=30)  # range 130070..130130
    c3 = forca_baixa(130_040, tamanho=200)  # máxima 130045 < 130070

    assert rev.bebe_abandonado_baixa([c1_verde, c2, c3], ctx_alta, lim) is not None

    c1_vermelho = forca_baixa(130_005, tamanho=200)
    assert rev.bebe_abandonado_baixa([c1_vermelho, c2, c3], ctx_alta, lim) is None


# ---------------------------------------------------------------------------
# 3 Soldados / 3 Corvos — ERRATA item 2
# ---------------------------------------------------------------------------


def test_tres_soldados_dispara(ctx_alta, lim):
    janela = [
        forca_alta(129_000, tamanho=150, i=0),
        forca_alta(129_150, tamanho=150, i=1),
        forca_alta(129_300, tamanho=150, i=2),
    ]
    assert rev.tres_soldados(janela, ctx_alta, lim) is not None


def test_tres_corvos_exige_candles_vermelhos(ctx_baixa, lim):
    """ERRATA item 2 — o ebook descreve 3 corvos como 'três candles de ALTA'."""
    corvos = [
        forca_baixa(130_000, tamanho=150, i=0),
        forca_baixa(129_850, tamanho=150, i=1),
        forca_baixa(129_700, tamanho=150, i=2),
    ]
    soldados = [
        forca_alta(129_000, tamanho=150, i=0),
        forca_alta(129_150, tamanho=150, i=1),
        forca_alta(129_300, tamanho=150, i=2),
    ]
    assert rev.tres_corvos(corvos, ctx_baixa, lim) is not None
    assert rev.tres_corvos(soldados, ctx_baixa, lim) is None


def test_tres_soldados_nao_dispara_sem_fechamentos_ascendentes(ctx_alta, lim):
    janela = [
        forca_alta(129_000, tamanho=150, i=0),
        forca_alta(128_900, tamanho=150, i=1),  # fecha abaixo do anterior
        forca_alta(129_300, tamanho=150, i=2),
    ]
    assert rev.tres_soldados(janela, ctx_alta, lim) is None


# ---------------------------------------------------------------------------
# Escada — ERRATA item 3
# ---------------------------------------------------------------------------


def test_escada_baixa_exige_tres_verdes_ascendentes_em_tendencia_de_alta(ctx_alta, lim):
    """ERRATA item 3 — o ebook diz 'tendência de baixa' e 'cada vez menores'."""
    janela = [
        forca_alta(129_000, tamanho=150, i=0),
        forca_alta(129_100, tamanho=150, i=1),
        forca_alta(129_200, tamanho=150, i=2),
        martelo_invertido(129_400, i=3),
        forca_baixa(129_380, tamanho=250, i=4),  # fecha em 129130 < abertura de c3
    ]
    assert rev.escada_baixa(janela, ctx_alta, lim) is not None


def test_escada_alta_dispara(ctx_baixa, lim):
    janela = [
        forca_baixa(130_000, tamanho=150, i=0),
        forca_baixa(129_900, tamanho=150, i=1),
        forca_baixa(129_800, tamanho=150, i=2),
        martelo_invertido(129_600, i=3),
        forca_alta(129_620, tamanho=250, i=4),  # fecha em 129870 > abertura de c3
    ]
    assert rev.escada_alta(janela, ctx_baixa, lim) is not None


# ---------------------------------------------------------------------------
# Alinhamento — ERRATA item 11
# ---------------------------------------------------------------------------


def test_alinhamento_baixa_exige_fechamentos_coincidentes(ctx_baixa, lim):
    c1 = forca_baixa(130_100, tamanho=200)  # fecha 129900
    c2 = vela(130_050, 130_060, 129_895, 129_903)  # fecha 129903, dentro de 10 pontos
    assert rev.alinhamento_baixa([c1, c2], ctx_baixa, lim) is not None

    c2_longe = vela(130_050, 130_060, 129_700, 129_750)  # fecha 150 pontos abaixo
    assert rev.alinhamento_baixa([c1, c2_longe], ctx_baixa, lim) is None


def test_alinhamento_alta_usa_fechamento_e_nao_abertura(ctx_alta, lim):
    """ERRATA item 11 — o ebook pede coincidência de abertura nesta metade do par."""
    c1 = forca_alta(129_800, tamanho=200)  # fecha 130000
    c2 = vela(129_850, 130_010, 129_845, 130_004)  # fecha 130004: coincide
    assert rev.alinhamento_alta([c1, c2], ctx_alta, lim) is not None

    # Mesma abertura, fechamento distante: não é o padrão.
    c2_mesma_abertura = vela(129_800, 130_300, 129_795, 130_280)
    assert rev.alinhamento_alta([c1, c2_mesma_abertura], ctx_alta, lim) is None


# ---------------------------------------------------------------------------
# 3 Por Dentro / 3 Por Fora
# ---------------------------------------------------------------------------


def test_tres_por_dentro_alta_exige_rompimento_no_terceiro(ctx_baixa, lim):
    mae = forca_baixa(130_000, tamanho=200)  # máxima 130005
    bebe = vela(129_850, 129_900, 129_830, 129_890)
    rompe = vela(129_890, 130_120, 129_880, 130_100)  # fecha acima da máxima dos dois
    nao_rompe = vela(129_890, 129_990, 129_880, 129_960)

    assert rev.tres_por_dentro_alta([mae, bebe, rompe], ctx_baixa, lim) is not None
    assert rev.tres_por_dentro_alta([mae, bebe, nao_rompe], ctx_baixa, lim) is None


def test_tres_por_fora_alta_dispara(ctx_baixa, lim):
    c1 = vela(130_000, 130_050, 129_800, 129_850)
    c2 = vela(129_800, 130_150, 129_780, 130_100)
    c3 = vela(130_100, 130_300, 130_080, 130_250)
    assert rev.tres_por_fora_alta([c1, c2, c3], ctx_baixa, lim) is not None


# ---------------------------------------------------------------------------
# Bebê Engolido
# ---------------------------------------------------------------------------


def test_bebe_engolido_alta_dispara(ctx_baixa, lim):
    c1 = marubozu_baixa(130_000, tamanho=150, i=0)  # 130000 -> 129850
    c2 = marubozu_baixa(129_850, tamanho=150, i=1)  # 129850 -> 129700
    c3 = martelo_invertido(129_600, corpo=10, cauda=60, i=2)  # range 129587..129660
    c4 = marubozu_baixa(129_700, tamanho=150, i=3)  # corpo 129550..129700 cobre c3
    assert rev.bebe_engolido_alta([c1, c2, c3, c4], ctx_baixa, lim) is not None


def test_bebe_engolido_alta_nao_dispara_sem_engolir_o_bebe(ctx_baixa, lim):
    c1 = marubozu_baixa(130_000, tamanho=150, i=0)
    c2 = marubozu_baixa(129_850, tamanho=150, i=1)
    c3 = martelo_invertido(129_600, corpo=10, cauda=60, i=2)
    c4 = marubozu_baixa(129_700, tamanho=60, i=3)  # corpo 129640..129700: não cobre
    assert rev.bebe_engolido_alta([c1, c2, c3, c4], ctx_baixa, lim) is None


# ---------------------------------------------------------------------------
# Cinto de Segurança
# ---------------------------------------------------------------------------


def test_cinto_seguranca_alta_exige_abertura_na_minima(ctx_baixa, lim):
    com_cinto = vela(129_800, 130_010, 129_800, 130_000)  # abertura == mínima
    sem_cinto = vela(129_800, 130_010, 129_700, 130_000)  # sombra inferior grande
    assert rev.cinto_seguranca_alta([com_cinto], ctx_baixa, lim) is not None
    assert rev.cinto_seguranca_alta([sem_cinto], ctx_baixa, lim) is None


# ---------------------------------------------------------------------------
# Bloqueio Avançado
# ---------------------------------------------------------------------------


def test_bloqueio_avancado_exige_corpos_encolhendo_e_sombras_crescendo(ctx_alta, lim):
    janela = [
        vela(129_000, 129_210, 128_990, 129_200, i=0),  # corpo 200, sombra sup 10
        vela(129_200, 129_360, 129_190, 129_330, i=1),  # corpo 130, sombra sup 30
        vela(129_330, 129_450, 129_320, 129_400, i=2),  # corpo  70, sombra sup 50
    ]
    assert rev.bloqueio_avancado(janela, ctx_alta, lim) is not None

    # Corpos crescendo em vez de encolhendo: é força, não bloqueio.
    forte = [
        vela(129_000, 129_110, 128_990, 129_100, i=0),
        vela(129_100, 129_260, 129_090, 129_250, i=1),
        vela(129_250, 129_460, 129_240, 129_450, i=2),
    ]
    assert rev.bloqueio_avancado(forte, ctx_alta, lim) is None


# ---------------------------------------------------------------------------
# Chute — sem tendência requerida
# ---------------------------------------------------------------------------


def test_chute_alta_dispara_em_qualquer_tendencia(ctx_baixa, ctx_alta, lim):
    """O ebook: 'a tendência anterior à sua formação não é importante'."""
    c1 = marubozu_baixa(130_000, tamanho=150, i=0)  # fecha 129850
    c2 = marubozu_alta(130_050, tamanho=150, i=1)  # abre acima do corpo de c1
    assert rev.chute_alta([c1, c2], ctx_baixa, lim) is not None
    assert rev.chute_alta([c1, c2], ctx_alta, lim) is not None


def test_chute_alta_nao_dispara_sem_gap(ctx_baixa, lim):
    c1 = marubozu_baixa(130_000, tamanho=150, i=0)
    c2 = marubozu_alta(129_900, tamanho=150, i=1)  # abre dentro do corpo de c1
    assert rev.chute_alta([c1, c2], ctx_baixa, lim) is None
