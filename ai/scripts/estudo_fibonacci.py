"""Mede quais níveis de Fibonacci WIN e WDO **de fato** respeitam.

A literatura repete 38,2 / 50 / 61,8 para tudo. Isso é folclore herdado do mercado
americano de ações — não é medição em mini-índice e mini-dólar da B3, nos timeframes que
a gente opera. Este estudo troca a repetição por evidência.

    python scripts/estudo_fibonacci.py dados/WDO_M5_real.csv --ativo WDO --tf M5

## Método

Para cada perna confirmada (fundo→topo ou topo→fundo):

1. anda para frente a partir do fim da perna,
2. acompanha a **retração máxima** atingida,
3. para quando o preço retoma a direção da perna (a correção acabou), quando a retração
   passa de 100% (a perna foi invalidada) ou quando estoura a janela de observação,
4. registra em que fração da perna o preço **virou**.

O que sai é a distribuição real dos pontos de virada. Um nível "respeitado" é aquele onde
a virada acontece com frequência acima do acaso.

## Três métricas, e a terceira é a única que decide

**Distribuição das viradas** — onde as correções terminaram. Descritivo, e enganoso
sozinho: níveis profundos aparecem muito só porque as faixas entre eles são mais largas.

**Parou antes do próximo nível** — das vezes que o preço *chegou* ao nível, quantas ele
parou ali em vez de furar para o nível seguinte. Já é acionável: responde "se o WDO está
tocando 61,8%, qual a chance de ser ali que ele para?".

**Densidade** — a métrica acima dividida pela largura da faixa. É a que corrige o viés
que invalida as outras duas: as faixas de Fibonacci têm larguras muito diferentes
(0,236→0,300 tem 6,4 pontos percentuais; 0,786→1,000 tem 21,4). Uma faixa larga captura
mais viradas mesmo que o nível não signifique nada.

**Se a densidade for aproximadamente igual em todos os níveis, Fibonacci não está fazendo
nada** — as correções estariam terminando de forma uniforme, e os números bonitos das
outras duas métricas seriam só geometria das faixas. Um nível só "existe" se a densidade
dele se destacar da média.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from trader_ai.fontes.csv_loader import ler_arquivo
from trader_ai.indicadores import atr as calc_atr
from trader_ai.indicadores import swings_confirmados
from trader_ai.limiares import PADRAO
from trader_ai.tipos import Direcao, Serie, Timeframe

# Inclui 0.236 e 0.30 além dos clássicos. O 0.30 entrou por hipótese levantada na mesa —
# não é nível de Fibonacci, e o estudo existe justamente para aceitar ou descartar isso
# com número em vez de opinião.
NIVEIS = (0.236, 0.300, 0.382, 0.500, 0.618, 0.786, 1.000)

JANELA_MAXIMA = 120
"""Candles de observação depois da perna. Além disso a correção virou outra coisa."""

RETOMADA_MINIMA_ATR = 0.75
"""Quanto o preço precisa andar a favor da perna para a correção contar como encerrada.

Sem esse piso, qualquer oscilação de um tick marcaria uma "virada" e a distribuição
viraria ruído.
"""


def _pernas(serie: Serie, lookback: int) -> list[tuple[int, int, float, float, Direcao]]:
    """Pernas confirmadas: `(i_inicio, i_fim, preco_inicio, preco_fim, direcao)`."""
    topos, fundos = swings_confirmados(serie, len(serie) - 1, lookback)
    pivos = sorted(
        [(i, p, Direcao.ALTA) for i, p in topos] + [(i, p, Direcao.BAIXA) for i, p in fundos]
    )

    pernas = []
    for (i0, p0, t0), (i1, p1, t1) in zip(pivos, pivos[1:], strict=False):
        # Só interessa fundo→topo ou topo→fundo. Dois topos seguidos não formam perna.
        if t0 is t1 or i1 <= i0:
            continue
        direcao = Direcao.ALTA if p1 > p0 else Direcao.BAIXA
        pernas.append((i0, i1, p0, p1, direcao))
    return pernas


def estudar(serie: Serie, lookback: int) -> tuple[Counter, dict[float, list[int]], int]:
    """`(viradas_por_nivel, {nivel: [chegadas, reacoes]}, total_de_pernas)`."""
    atr_arr = calc_atr(serie, PADRAO.atr_periodo)
    viradas: Counter = Counter()
    alcance: dict[float, list[int]] = {n: [0, 0] for n in NIVEIS}
    analisadas = 0

    for _i0, i1, p0, p1, direcao in _pernas(serie, lookback):
        amplitude = abs(p1 - p0)
        if amplitude <= 0 or i1 + 2 >= len(serie):
            continue
        atr_local = float(atr_arr[i1]) if atr_arr[i1] == atr_arr[i1] else 0.0
        if atr_local <= 0 or amplitude < atr_local:
            continue  # perna menor que um ATR é ruído, não movimento

        analisadas += 1
        profundidade_max = 0.0
        virou_em: float | None = None

        for j in range(i1 + 1, min(i1 + 1 + JANELA_MAXIMA, len(serie))):
            c = serie[j]
            # Retração medida no extremo adverso do candle: é o pior ponto alcançado.
            if direcao is Direcao.ALTA:
                extremo_adverso = c.minima
                profundidade = (p1 - extremo_adverso) / amplitude
                retomou = c.maxima >= p1 + RETOMADA_MINIMA_ATR * atr_local
            else:
                extremo_adverso = c.maxima
                profundidade = (extremo_adverso - p1) / amplitude
                retomou = c.minima <= p1 - RETOMADA_MINIMA_ATR * atr_local

            profundidade_max = max(profundidade_max, profundidade)

            if profundidade_max > 1.0:
                break  # perna invalidada: não foi correção, foi reversão
            if retomou:
                virou_em = profundidade_max
                break

        if virou_em is None:
            continue

        # Em qual faixa a virada caiu — o nível mais próximo abaixo do ponto de virada.
        alvo = max((n for n in NIVEIS if n <= virou_em + 0.03), default=None)
        if alvo is not None:
            viradas[alvo] += 1

        # Chegou ao nível e parou ANTES do próximo? Contar assim — e não "virou perto do
        # nível" — remove o viés de que níveis profundos têm menos espaço à frente.
        for nivel, proximo in zip(NIVEIS, NIVEIS[1:], strict=False):
            if profundidade_max >= nivel - 0.02:
                alcance[nivel][0] += 1
                if virou_em < proximo - 0.02:
                    alcance[nivel][1] += 1

    return viradas, alcance, analisadas


LARGURA_BIN = 0.02
"""Bins de 2% de retração — fino o bastante para um nível aparecer, grosso o bastante
para ter amostra."""


def _teste_do_pico(serie: Serie, lookback: int) -> None:
    """O teste que de fato decide se Fibonacci existe neste ativo.

    As métricas por faixa larga sofrem de um viés que não some: a correção **precisa**
    terminar em algum lugar antes de 100%, então a probabilidade condicional de terminar
    na próxima faixa cresce com a profundidade, quer Fibonacci signifique algo ou não.
    Uma rampa monotônica é o resultado esperado do acaso, não uma descoberta.

    O teste correto é local: em bins finos e uniformes, calcular a **taxa de virada**
    (hazard) — dos que chegaram ao bin, quantos pararam ali — e perguntar se o bin do
    nível de Fibonacci se destaca dos **vizinhos imediatos**. Um nível real produz um
    pico local; ruído produz uma curva lisa.
    """
    atr_arr = calc_atr(serie, PADRAO.atr_periodo)
    n_bins = int(1.0 / LARGURA_BIN)
    chegou = [0] * n_bins
    parou = [0] * n_bins

    for _i0, i1, p0, p1, direcao in _pernas(serie, lookback):
        amplitude = abs(p1 - p0)
        if amplitude <= 0 or i1 + 2 >= len(serie):
            continue
        atr_local = float(atr_arr[i1]) if atr_arr[i1] == atr_arr[i1] else 0.0
        if atr_local <= 0 or amplitude < atr_local:
            continue

        profundidade_max = 0.0
        virou_em: float | None = None
        for j in range(i1 + 1, min(i1 + 1 + JANELA_MAXIMA, len(serie))):
            c = serie[j]
            if direcao is Direcao.ALTA:
                profundidade = (p1 - c.minima) / amplitude
                retomou = c.maxima >= p1 + RETOMADA_MINIMA_ATR * atr_local
            else:
                profundidade = (c.maxima - p1) / amplitude
                retomou = c.minima <= p1 - RETOMADA_MINIMA_ATR * atr_local
            profundidade_max = max(profundidade_max, profundidade)
            if profundidade_max > 1.0:
                break
            if retomou:
                virou_em = profundidade_max
                break

        if virou_em is None:
            continue
        bin_virada = min(n_bins - 1, int(virou_em / LARGURA_BIN))
        for b in range(bin_virada + 1):
            chegou[b] += 1
        parou[bin_virada] += 1

    hazard = [parou[b] / chegou[b] if chegou[b] >= 40 else None for b in range(n_bins)]

    print("\nTESTE DO PICO — o nível se destaca dos vizinhos?")
    print(f"  {'nível':<8} {'hazard':>8} {'vizinhos':>10} {'razão':>8}   veredito")

    houve_pico = False
    for nivel in (0.236, 0.300, 0.382, 0.500, 0.618, 0.786):
        b = int(nivel / LARGURA_BIN)
        if hazard[b] is None:
            continue
        # Vizinhos: dois bins de cada lado, pulando o próprio e os colados nele.
        vizinhos = [
            hazard[k]
            for k in (b - 3, b - 2, b + 2, b + 3)
            if 0 <= k < n_bins and hazard[k] is not None
        ]
        if not vizinhos:
            continue
        base = sum(vizinhos) / len(vizinhos)
        razao = hazard[b] / base if base > 0 else 0.0
        # 1.25 é um destaque modesto e ainda assim exigente: 25% acima da vizinhança
        # imediata, num histograma com milhares de correções.
        pico = razao >= 1.25
        houve_pico = houve_pico or pico
        veredito = "PICO" if pico else ("—" if razao >= 0.85 else "vale")
        print(
            f"  {nivel:<8.3f} {hazard[b]:>7.1%} {base:>9.1%} {razao:>7.2f}x   {veredito}"
        )

    if not houve_pico:
        print(
            "\n  Nenhum nível produz pico local. A subida da taxa de virada com a\n"
            "  profundidade é uma propriedade da correção ter que acabar em algum lugar —\n"
            "  não evidência de que o mercado enxerga Fibonacci neste ativo/timeframe."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arquivo")
    parser.add_argument("--ativo", default="WDO", choices=["WIN", "WDO"])
    parser.add_argument("--tf", default="M5", choices=[tf.name for tf in Timeframe])
    parser.add_argument("--lookback", type=int, default=PADRAO.swing_lookback)
    args = parser.parse_args(argv)

    tf = Timeframe[args.tf]
    serie = ler_arquivo(Path(args.arquivo), args.ativo, tf)
    viradas, alcance, analisadas = estudar(serie, args.lookback)

    total_viradas = sum(viradas.values())
    print(
        f"\n{args.ativo} {tf.rotulo} · {len(serie):,} candles · "
        f"{serie[0].ts:%d/%m/%Y} a {serie[-1].ts:%d/%m/%Y}".replace(",", ".")
    )
    print(f"{analisadas} pernas analisadas · {total_viradas} correções com virada clara\n")

    if total_viradas == 0:
        print("Amostra vazia — série curta demais ou lookback alto demais.")
        return 1

    print("ONDE AS CORREÇÕES TERMINARAM")
    print(f"  {'nível':<10} {'viradas':>8} {'%':>7}")
    for nivel in NIVEIS:
        n = viradas.get(nivel, 0)
        pct = n / total_viradas
        barra = "█" * int(pct * 46)
        print(f"  {nivel:<10.3f} {n:>8} {pct:>6.1%}  {barra}")

    _teste_do_pico(serie, args.lookback)

    print("\nPAROU ANTES DO PRÓXIMO NÍVEL · densidade corrige a largura da faixa")
    print(
        f"  {'nível':<8} {'faixa':>14} {'chegadas':>9} "
        f"{'parou':>7} {'taxa':>7} {'densidade':>10}"
    )
    linhas = []
    for nivel, proximo in zip(NIVEIS, NIVEIS[1:], strict=False):
        chegadas, paradas = alcance[nivel]
        if chegadas < 30:
            continue
        largura = proximo - nivel
        taxa = paradas / chegadas
        densidade = taxa / largura
        linhas.append((nivel, chegadas, paradas, taxa, densidade))
        print(
            f"  {nivel:<8.3f} {f'{nivel:.3f}–{proximo:.3f}':>14} {chegadas:>9} "
            f"{paradas:>7} {taxa:>6.1%} {densidade:>10.2f}"
        )

    if not linhas:
        return 0

    media_dens = sum(d for *_, d in linhas) / len(linhas)
    print(f"\n  Densidade média: {media_dens:.2f}")
    print("  (se todas as faixas tivessem densidade parecida, Fibonacci não estaria fazendo nada)")

    destaques = [(n, d) for n, _, _, _, d in linhas if d > media_dens * 1.15]
    fracos = [(n, d) for n, _, _, _, d in linhas if d < media_dens * 0.85]

    for nivel, dens in sorted(destaques, key=lambda x: -x[1]):
        rel = dens / media_dens
        print(f"    {nivel:.3f}  densidade {dens:.2f}  →  {rel:.0%} da média  RESPEITADO")
    for nivel, dens in sorted(fracos, key=lambda x: x[1]):
        print(f"    {nivel:.3f}  densidade {dens:.2f}  →  {dens / media_dens:.0%} da média  fraco")

    if not destaques:
        print("    Nenhum nível se destaca — neste ativo/timeframe, Fibonacci é ruído.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
