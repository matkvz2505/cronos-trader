"""Limiares do motor — todo número mágico do sistema mora aqui.

Dois motivos para centralizar:

1. **Calibração.** O backtest (Sprint 4) precisa varrer combinações de limiares. Se eles
   estivessem espalhados pelos detectores, não haveria o que varrer.
2. **Auditoria.** Quando um sinal parecer errado, a pergunta é sempre "com que limiar isso
   disparou?". Aqui a resposta está num arquivo só.

Nenhum valor está em pontos ou reais. Tudo é fração da amplitude do candle ou múltiplo de
ATR — ver docs/ARQUITETURA.md, camada 1.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .tipos import Timeframe


@dataclass(frozen=True, slots=True)
class Limiares:
    # ------------------------------------------------------------------
    # Geometria do candle isolado
    # ------------------------------------------------------------------

    doji_corpo_pct_max: float = 0.10
    """Corpo <= 10% da amplitude = doji. O ebook diz 'pouco ou nenhum corpo' (p.5)."""

    corpo_pequeno_pct_max: float = 0.30
    """'Corpo pequeno' do martelo, estrela e spinning top."""

    corpo_longo_atr_min: float = 0.80
    """'Corpo longo' — corpo >= 0.8 ATR. Distingue candle relevante de ruído."""

    marubozu_sombra_pct_max: float = 0.05
    """Marubozu 'não tem sombra'. O ebook admite (p.5): 'na prática podem ter sombra
    mínima'. 5% da amplitude de cada lado é essa prática."""

    marubozu_corpo_pct_min: float = 0.90

    sombra_longa_ratio: float = 2.0
    """Sombra 'longa' = pelo menos 2x o corpo. O ebook cita esse número no spinning top
    (p.6) e ressalva que não é obrigatório — por isso é limiar, não dogma."""

    sombra_curta_pct_max: float = 0.15
    """'Pouca ou nenhuma sombra' — até 15% da amplitude."""

    candle_forca_atr_min: float = 1.20
    """'Candle de força': amplitude >= 1.2 ATR…"""

    candle_forca_corpo_pct_min: float = 0.60
    """…e corpo ocupando pelo menos 60% dela. As duas condições juntas — amplitude
    grande com corpo pequeno é indecisão volátil, não força."""

    # ------------------------------------------------------------------
    # Gaps e coincidências
    # ------------------------------------------------------------------

    tolerancia_gap_atr: float = 0.05
    """Folga para considerar que houve gap, em ATR.

    O parâmetro mais sensível do motor. Dentro do pregão o preço é contínuo e gap
    estrito quase não existe; sem folga, ~8 padrões do ebook nunca disparariam.
    Com folga demais, qualquer sobreposição vira 'gap' e eles disparam sempre.
    O backtest deve calibrar isto por timeframe antes de qualquer outra coisa.
    Ver docs/ERRATA-EBOOK.md item 10.
    """

    coincidencia_atr: float = 0.10
    """Dois preços 'coincidem' se distam menos que 0.1 ATR.

    Necessário para Alinhamento na baixa/alta e Linhas de Reunião, que no texto exigem
    fechamentos iguais. Igualdade exata em float, com tick de 5 pontos no WIN, seria
    um detector que nunca dispara.
    """

    # ------------------------------------------------------------------
    # Contexto
    # ------------------------------------------------------------------

    adx_periodo: int = 14
    adx_lateral_max: float = 20.0
    """ADX abaixo disto = LATERAL. Padrões de reversão perdem peso: não há tendência
    para reverter."""

    adx_forte_min: float = 25.0

    atr_periodo: int = 14
    ema_rapida: int = 9
    ema_lenta: int = 21
    swing_lookback: int = 5
    """Candles de cada lado para confirmar um topo/fundo pivô."""

    tendencia_min_candles: int = 30
    """Histórico mínimo antes de afirmar qualquer tendência."""

    # ------------------------------------------------------------------
    # Confluência — multiplicadores aplicados ao score bruto
    # ------------------------------------------------------------------

    bonus_fibonacci: float = 0.35
    """Padrão numa retração **medida como relevante naquele ativo**.

    Escalado por `fibonacci.relevancia()`, que só reconhece níveis com pico local
    comprovado. Hoje: WDO em 50%; o WIN não ganha bônus de Fibonacci nenhum.
    """

    bonus_media: float = 0.25
    bonus_suporte_resistencia: float = 0.30
    bonus_volume: float = 0.20
    penalidade_volume_fraco: float = 0.15
    bonus_correlacao: float = 0.10
    penalidade_correlacao_contra: float = 0.20
    bonus_zona_quente: float = 0.25
    """Bônus extra quando Fibonacci, média e S/R apontam para o MESMO preço. É o sinal
    mais forte que o motor produz: três leituras independentes concordando é onde há
    ordem de verdade no book."""

    tolerancia_zona_atr: float = 0.25
    """Distância máxima, em ATR, para o padrão 'estar' numa zona."""

    penalidade_volatilidade_baixa: float = 0.30
    atr_minimo_operavel: float = 0.60
    """ATR abaixo de 60% da média: o movimento não paga spread + corretagem."""

    # ------------------------------------------------------------------
    # Regime de médias (9 / 21 / 200 / 400-Wilder)
    # ------------------------------------------------------------------

    bonus_regime_medias: float = 0.30
    """Médias empilhadas a favor do sinal."""

    penalidade_regime_contra: float = 0.35
    """Médias empilhadas contra. Maior que o bônus de propósito: entrar contra estrutura
    definida erra mais do que entrar a favor acerta."""

    esticamento_maximo_atr: float = 2.0
    """Distância do preço à SMA21 a partir da qual a entrada começa a ser penalizada."""

    penalidade_esticamento: float = 0.18
    """Por ATR de excesso além do limite. Comprar 3 ATR acima da média de viés é comprar
    o fim do impulso — acerta a direção e perde dinheiro."""

    # ------------------------------------------------------------------
    # Multi-timeframe
    # ------------------------------------------------------------------

    bonus_mtf_alinhado: float = 0.30
    """15/30/60min todos concordando com o gatilho de 5min."""

    score_minimo_contra_vies: float = 0.85
    """Contra o viés dos timeframes maiores, só passa sinal quase perfeito.
    Na prática, quase nada passa — e é essa a intenção."""

    usar_peso_horario: bool = True
    """Aplica o peso da janela do pregão no score.

    **Os pesos atuais são suspeitos.** Foram calibrados sobre a base que estava 3 horas
    deslocada, então cada peso ficou preso à janela errada — o 1,15 que eu dei à
    "tendência da manhã" foi medido sobre operações que aconteceram no meio da tarde.
    Desligar é a forma de perguntar se eles ajudam ou atrapalham, em vez de assumir."""

    vetar_contra_vizinho: bool = False
    """Viés neutro POR DISCORDÂNCIA veta se o timeframe vizinho contraria a entrada.

    **Desligado porque a medição o reprovou.** A ideia era boa e o caso que a motivou era
    real — em 10/08/2026 o motor vendeu WDO com o 15min em alta, e o trade foi estopado.
    Mas no walk-forward a regra piora os DOIS ativos: WDO −0,036R, WIN −0,015R. Consistente
    nos dois, que é exatamente o critério para acreditar num efeito — e aqui o efeito é
    negativo.

    A leitura provável: o 15min contrariar o gatilho é comum em pullback, e pullback é
    onde entrada de reversão nasce. O veto matava o setup junto com o erro.

    Fica no código, desligado, porque a hipótese é razoável e pode voltar a ser testada
    com outra definição de "vizinho contrário" — força mínima, por exemplo."""

    confiabilidade_sem_medicao: float | None = None
    """Confiabilidade de padrão que ainda não foi medido NESTE ativo.

    Antes o motor caía no prior do ebook — 0,70 para a Nuvem Negra, por exemplo — e esse
    número entrava no score como se fosse evidência, além de aparecer na tela escrito
    "confiabilidade do padrão em WDO: 70%". Não havia uma única medição de Nuvem Negra em
    WDO. Meio a meio é o que se sabe de um padrão não medido; o prior do ebook continua
    no catálogo como referência de leitura, não como peso.

    **`None` (usar o prior do ebook) é o padrão, porque a medição mandou.** Achatar para
    0,50 custou −0,076R no WDO, e o mecanismo aparece no número de sinais: 254 → 382. A
    regra não filtrou, **re-ranqueou**. Vários padrões disparam no mesmo candle e
    `confluencia.melhor()` escolhe um; com todas as confiabilidades iguais, o desempate
    passa a ser feito pelos outros fatores e o padrão escolhido muda — para pior.

    Isso separa duas coisas que eu tinha juntado:

    - **Usar o prior como peso** é uma escolha de modelagem, e a medição diz que ela
      seleciona melhor do que não ter informação nenhuma. Fica.
    - **Chamar o prior de "confiabilidade medida em WDO" na tela** era mentira, e
      continua sendo. Isso se conserta na apresentação, não no score — ver
      `foi_medida()`, que é o que a tela deve consultar antes de escrever "medido".

    O valor numérico (0,50) segue disponível para quem quiser re-testar a hipótese junto
    de uma mudança no critério de desempate do `melhor()`, que é o que realmente
    quebrou."""

    vetar_expectancia_negativa: bool = True
    """Padrão com expectância medida negativa e amostra suficiente não emite.

    Hoje a medição só entrava via taxa de acerto no score, onde os outros fatores a
    diluíam: o `tres_por_dentro_baixa` do WDO mede −0,300R e saiu com score 0,61."""

    # ------------------------------------------------------------------
    # Decisão e risco
    # ------------------------------------------------------------------

    folga_stop_atr: float = 0.25
    """Folga além do extremo do padrão, para não ser estopado por spread/ruído."""

    rr_minimo: float = 1.5
    """Abaixo disso o sinal é descartado por melhor que seja o padrão. Um padrão ótimo
    com alvo ruim continua sendo um trade ruim."""

    score_minimo_sinal: float = 0.45
    risco_por_trade_pct: float = 1.0
    perda_diaria_maxima_pct: float = 3.0
    max_trades_dia: int = 6
    """Limite contra over-trading — a causa mais comum de ruína em day trade."""

    minutos_veto_noticia: int = 15
    """Janela de ±15min em torno de evento econômico: não abrir posição nova."""

    # ------------------------------------------------------------------
    # Backtest
    # ------------------------------------------------------------------

    amostra_minima_confiabilidade: int = 30
    """Abaixo de 30 ocorrências, mantém o prior do ebook e marca 'insuficiente'.
    Taxa de acerto sobre 4 trades não é evidência."""

    def para_timeframe(self, tf: Timeframe) -> Limiares:
        """Ajusta os limiares sensíveis ao timeframe.

        No diário há fechamento de pregão entre os candles, então gap é gap: tolerância
        zero. No intraday o preço é contínuo e a tolerância é obrigatória.
        """
        if not tf.e_intraday:
            return replace(self, tolerancia_gap_atr=0.0)
        # Quanto menor o timeframe, mais contínuo o preço e maior a folga necessária.
        folga = {5: 0.08, 15: 0.06, 30: 0.05, 60: 0.04}.get(tf.value, 0.05)
        return replace(self, tolerancia_gap_atr=folga)


PADRAO = Limiares()
"""Instância default. Detectores aceitam `limiares=None` e caem nesta."""
