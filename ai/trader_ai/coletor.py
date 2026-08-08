"""Coletor: MetaTrader 5 → Postgres → motor.

Roda como processo **no host Windows**, não em container: precisa falar com o terminal
MT5, que não containeriza. É a única peça não portável do sistema.

    cd ai
    $env:DATABASE_URL = "postgresql://trader:trader@localhost:5460/cronos_trader"
    python -m trader_ai.coletor --ativos WIN WDO

A cada ciclo, para cada ativo e timeframe:

1. baixa as últimas N barras do MT5
2. faz upsert no Postgres (idempotente — o candle em formação é atualizado, não duplicado)
3. roda o motor nos candles recentes e persiste sinais novos
4. acompanha os sinais abertos contra os candles novos (alvo, stop, expiração)

Deixe rodando durante o pregão. Fora do horário ele continua vivo e apenas não encontra
nada novo — reiniciar a cada dia não é necessário.
"""

from __future__ import annotations

import argparse
import importlib.util
import signal
import sys
import time
from datetime import datetime, timedelta
from datetime import time as hora_do_dia

from . import padroes, persistencia
from .fontes.base import FonteIndisponivel
from .pipeline import analisar
from .tipos import Timeframe

TIMEFRAMES = (Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1)

ABERTURA = hora_do_dia(9, 0)
FECHAMENTO = hora_do_dia(18, 0)
"""Janela de coleta, horário de Brasília.

O coletor **não morre** fora dela: dorme e acorda. Um processo que termina às 18h precisa
de alguém para religá-lo às 9h — e "alguém" acaba sendo o operador lembrando de rodar um
comando, que é exatamente o que esta plataforma não pode exigir.
"""

ESPERA_FORA_DO_PREGAO = 60
"""Segundos entre checagens quando o mercado está fechado. Um minuto é folgado: o pior
atraso possível na reabertura é de 60 segundos."""

_parar = False


def dentro_do_pregao(momento: datetime | None = None) -> bool:
    """Pregão aberto: dia útil entre 9h e 18h.

    Feriados da B3 não são modelados. O custo de errar é baixo — o coletor tenta ler,
    não vem candle novo, e o ciclo seguinte tenta de novo.
    """
    agora = momento or datetime.now()
    if agora.weekday() >= 5:
        return False
    return ABERTURA <= agora.time() < FECHAMENTO


def _segundos_ate_abertura(agora: datetime) -> int:
    """Quanto falta para a próxima abertura, para o log dizer algo útil."""
    alvo = agora.replace(
        hour=ABERTURA.hour, minute=ABERTURA.minute, second=0, microsecond=0
    )
    # Se a abertura de hoje já passou, mira na de amanhã; depois pula o fim de semana.
    if alvo <= agora:
        alvo += timedelta(days=1)
    while alvo.weekday() >= 5:
        alvo += timedelta(days=1)
    return max(0, int((alvo - agora).total_seconds()))


def _sinal_de_parada(*_) -> None:
    global _parar
    _parar = True
    print("\nencerrando após o ciclo atual...")


def ciclo(fonte, ativos: list[str], capital: float, barras: int, verboso: bool) -> None:
    for ativo in ativos:
        for tf in TIMEFRAMES:
            try:
                serie_mt5 = fonte.ultimos(ativo, tf, barras)
            except FonteIndisponivel as erro:
                print(f"  {ativo} {tf.rotulo}: {erro}")
                continue

            gravados = persistencia.gravar_candles(serie_mt5)

            # Relê do banco: a série do MT5 tem só as últimas `barras`, e o motor precisa
            # de histórico mais longo para ATR, tendência e pivôs terem sentido.
            serie = persistencia.ler_candles(ativo, tf, limite=5000)
            if len(serie) < 60:
                if verboso:
                    print(f"  {ativo} {tf.rotulo}: {len(serie)} candles, aquecendo")
                continue

            padroes.CALIBRACAO.update(persistencia.carregar_calibracao(ativo, tf))

            # Só o gatilho de 5min emite sinal. Os timeframes maiores existem no banco
            # para formar o viés e alimentar o gráfico — emitir sinal em todos eles
            # geraria quatro versões do mesmo trade.
            if tf is Timeframe.M5:
                analise = analisar(serie, capital=capital, ultimos=30)
                vies = analise.vies.descrever() if analise.vies else None
                novos = persistencia.gravar_sinais(analise.sinais, vies, analise.teses)
                persistencia.gravar_deteccoes(ativo, tf, analise.deteccoes, serie)
                mudancas = persistencia.atualizar_sinais_abertos(ativo, tf, serie)

                if novos or mudancas or verboso:
                    marca = datetime.now().strftime("%H:%M:%S")
                    partes = [f"{gravados} candles"]
                    if novos:
                        partes.append(f"{novos} SINAIS NOVOS")
                    if mudancas:
                        partes.append(", ".join(f"{k}={v}" for k, v in mudancas.items()))
                    print(f"  [{marca}] {ativo} {tf.rotulo}: {' · '.join(partes)}")

                for sinal in analise.sinais[-3:]:
                    print(f"      → {sinal.resumo()}")
            elif verboso:
                print(f"  {ativo} {tf.rotulo}: {gravados} candles")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ativos", nargs="+", default=["WIN"], choices=["WIN", "WDO"])
    parser.add_argument("--intervalo", type=int, default=30, help="segundos entre ciclos")
    parser.add_argument("--barras", type=int, default=500, help="barras lidas por ciclo")
    parser.add_argument("--capital", type=float, default=20_000.0)
    parser.add_argument(
        "--continuo",
        action="store_true",
        help="usa o símbolo contínuo (WIN$N) em vez do contrato vigente",
    )
    parser.add_argument("--uma-vez", action="store_true", help="roda um ciclo e sai")
    parser.add_argument("--verboso", action="store_true")
    args = parser.parse_args(argv)

    if not persistencia.disponivel():
        print(
            "DATABASE_URL não configurada (ou psycopg não instalado).\n"
            '  pip install -e ".[servico]"\n'
            '  $env:DATABASE_URL = "postgresql://trader:trader@localhost:5460/cronos_trader"',
            file=sys.stderr,
        )
        return 1

    # Banco fora do ar NÃO é motivo para desistir num processo que deve viver o dia
    # inteiro. O Docker sobe depois do logon, a máquina hiberna, o compose é recriado —
    # em todos esses casos o coletor acordaria antes do Postgres e morreria. Espera.
    if not args.uma_vez:
        _esperar_banco()
    else:
        ok, detalhe = persistencia.testar()
        if not ok:
            print(f"banco inacessível: {detalhe}", file=sys.stderr)
            return 1

    # Falha cedo e com mensagem útil se o pacote MT5 não existir — muito melhor que
    # descobrir isso no primeiro ciclo, dentro do laço de reconexão.
    if importlib.util.find_spec("MetaTrader5") is None:
        print(
            "pacote MetaTrader5 não instalado. Só funciona no Windows:\n"
            '  pip install -e ".[mt5]"',
            file=sys.stderr,
        )
        return 1

    _instalar_sinais()

    print(
        f"coletor: {', '.join(args.ativos)} · {len(TIMEFRAMES)} timeframes · "
        f"ciclo de {args.intervalo}s · capital R$ {args.capital:,.2f}\n"
        f"pregão {ABERTURA:%H:%M}–{FECHAMENTO:%H:%M} em dias úteis · "
        "coleta contínua, dorme fora do horário"
    )

    if args.uma_vez:
        return _ciclo_unico(args)

    return _laco_permanente(args)


def _interativo() -> bool:
    """Se este processo está numa janela com alguém olhando.

    Sob a tarefa agendada a saída vai para arquivo, então `isatty()` é falso — é
    exatamente a distinção de que `_instalar_sinais` precisa.
    """
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _instalar_sinais() -> None:
    """Ctrl+C encerra a janela interativa, mas NUNCA a tarefa agendada.

    O Windows entrega o evento de Ctrl+C a **todos os processos que compartilham o
    console**. A tarefa agendada roda na sessão interativa do usuário — ela precisa,
    porque o MetaTrader 5 conversa por IPC com um terminal que vive ali — e acaba
    dividindo console com o que mais estiver aberto. Resultado: um Ctrl+C em qualquer
    outro terminal derrubava a coleta, silenciosamente, no meio do pregão. Foi o que
    aconteceu em 07/08/2026 às 15:52, e o `^C` no meio do `logs/coletor.log` é a
    assinatura desse bug.

    `SIGTERM` continua honrado nos dois modos: é como `schtasks /End` e o desligamento do
    Windows pedem para parar, e ignorá-lo trocaria um bug por outro.
    """
    signal.signal(signal.SIGTERM, _sinal_de_parada)

    if _interativo():
        signal.signal(signal.SIGINT, _sinal_de_parada)
    else:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        print("modo desatendido: Ctrl+C de outro console será ignorado")


def _esperar_banco(tentativa_max_s: float = 60.0) -> None:
    """Bloqueia até o Postgres responder, com backoff limitado.

    Sem teto o intervalo cresceria até horas e a coleta perderia o pregão inteiro por
    causa de uma indisponibilidade de trinta segundos.
    """
    espera = 2.0
    avisou = False
    while not _parar:
        ok, detalhe = persistencia.testar()
        if ok:
            if avisou:
                print("banco de volta — retomando a coleta")
            return
        if not avisou:
            print(f"banco inacessível ({detalhe.splitlines()[0]}) — aguardando", file=sys.stderr)
            avisou = True
        time.sleep(espera)
        espera = min(tentativa_max_s, espera * 2)


def _ciclo_unico(args) -> int:
    """Um ciclo e sai. Usado por scripts e para depuração."""
    from .fontes.mt5 import MetaTrader5Fonte

    try:
        with MetaTrader5Fonte(continuo=args.continuo) as fonte:
            ciclo(fonte, args.ativos, args.capital, args.barras, args.verboso)
    except FonteIndisponivel as erro:
        print(f"MT5 indisponível: {erro}", file=sys.stderr)
        return 1
    return 0


def _laco_permanente(args) -> int:
    """Roda para sempre: coleta durante o pregão, dorme fora dele, reconecta se cair.

    Três decisões que fazem a diferença entre um script e um serviço:

    **Não morre fora do pregão.** Dorme e acorda. Um processo que termina às 18h precisa
    de alguém para religá-lo — e "alguém" vira o operador lembrando de rodar um comando.

    **Reconecta sozinho.** O terminal MT5 fecha, a máquina hiberna, a corretora derruba a
    sessão. Nada disso pode exigir intervenção: o laço espera e tenta de novo.

    **Só conecta ao MT5 quando precisa.** Fora do pregão a conexão é solta, o que evita
    segurar o terminal a noite inteira e permite atualizá-lo sem conflito.
    """
    from .fontes.mt5 import MetaTrader5Fonte

    espera_reconexao = 30

    while not _parar:
        agora = datetime.now()

        if not dentro_do_pregao(agora):
            faltam = _segundos_ate_abertura(agora)
            horas = faltam / 3600
            print(
                f"[{agora:%d/%m %H:%M}] fora do pregão — próxima abertura em "
                f"{horas:.1f} h. Dormindo."
            )
            _dormir(min(faltam, ESPERA_FORA_DO_PREGAO * 10) or ESPERA_FORA_DO_PREGAO)
            continue

        try:
            with MetaTrader5Fonte(continuo=args.continuo) as fonte:
                print(
                    f"[{datetime.now():%d/%m %H:%M}] MT5 conectado · "
                    f"símbolo {fonte.resolver_simbolo(args.ativos[0])} · coletando"
                )
                espera_reconexao = 30

                while not _parar and dentro_do_pregao():
                    ciclo(fonte, args.ativos, args.capital, args.barras, args.verboso)
                    _dormir(args.intervalo)

                if not _parar:
                    print(f"[{datetime.now():%d/%m %H:%M}] pregão encerrado — soltando o MT5")

        except FonteIndisponivel as erro:
            print(
                f"[{datetime.now():%d/%m %H:%M}] MT5 indisponível: {erro}\n"
                f"  nova tentativa em {espera_reconexao}s "
                "(o terminal precisa estar aberto e logado)",
                file=sys.stderr,
            )
            _dormir(espera_reconexao)
            # Backoff até 5 minutos: se o terminal está fechado há horas, insistir a
            # cada 30 segundos só enche o log.
            espera_reconexao = min(300, espera_reconexao * 2)
        except Exception as erro:  # noqa: BLE001 — o serviço não pode morrer por um ciclo
            print(f"[{datetime.now():%d/%m %H:%M}] erro no ciclo: {erro}", file=sys.stderr)
            _dormir(espera_reconexao)

    print("coletor encerrado.")
    return 0


def _dormir(segundos: float) -> None:
    """Sono fatiado, para que Ctrl+C e SIGTERM respondam em 1 segundo.

    Um `time.sleep(3600)` deixaria o serviço surdo por uma hora — o Windows mataria o
    processo à força no shutdown, sem chance de fechar a conexão com o MT5.
    """
    for _ in range(max(1, int(segundos))):
        if _parar:
            return
        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
