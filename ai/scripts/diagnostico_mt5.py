"""Diagnóstico do MetaTrader 5 — descobre exatamente o que falta para o motor rodar.

    python scripts/diagnostico_mt5.py

Roda seis checagens em ordem e para na primeira que falhar, dizendo o que fazer. Não
altera nada no terminal além de tornar símbolos visíveis no Observador de Mercado.

As seis checagens, e por que cada uma existe:

1. **Pacote instalado** — `MetaTrader5` é Windows-only e não vem por padrão.
2. **Terminal acessível** — precisa estar aberto e logado; o pacote conversa por IPC.
3. **Conta é de corretora B3** — a demo da MetaQuotes conecta normalmente e **não tem**
   WIN nem WDO. É de longe a causa mais comum de "conectou mas não vem dado".
4. **Símbolos existem** — testa contrato vigente e série contínua, nas duas famílias.
5. **Candles chegam** — nos quatro timeframes do escopo.
6. **Tick ao vivo** — só funciona com o pregão aberto; fora do horário é esperado falhar.
"""

from __future__ import annotations

import sys
from datetime import datetime

VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
CINZA = "\033[90m"
FIM = "\033[0m"

# Heurística só para o aviso de "corretora não reconhecida" — nunca bloqueia nada.
# As cinco primeiras estão confirmadas oferecendo MT5 com B3; as demais aparecem em
# relatos e podem ter mudado. Uma corretora fora desta lista funciona normalmente se as
# checagens seguintes passarem, e é isso que de fato decide.
CORRETORAS_B3 = (
    "clear",
    "xp",
    "rico",
    "modal",
    "terra",
    "btg",
    "genial",
    "toro",
    "nova futura",
    "orama",
    "ativa",
    "guide",
)


def ok(msg: str) -> None:
    print(f"  {VERDE}[OK]{FIM} {msg}")


def falha(msg: str) -> None:
    print(f"  {VERMELHO}[FALHA]{FIM} {msg}")


def aviso(msg: str) -> None:
    print(f"  {AMARELO}[ATENÇÃO]{FIM} {msg}")


def info(msg: str) -> None:
    print(f"  {CINZA}{msg}{FIM}")


def como_resolver(titulo: str, passos: list[str]) -> None:
    print(f"\n{AMARELO}── COMO RESOLVER: {titulo} ──{FIM}")
    for i, passo in enumerate(passos, 1):
        print(f"  {i}. {passo}")
    print()


def etapa(numero: int, titulo: str) -> None:
    print(f"\n{numero}. {titulo}")


def main() -> int:
    print("=" * 74)
    print(" DIAGNÓSTICO DO METATRADER 5 — cronos-trader")
    print("=" * 74)

    # ------------------------------------------------------------------
    etapa(1, "Pacote MetaTrader5")
    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError:
        falha("pacote MetaTrader5 não está instalado")
        como_resolver(
            "instalar o pacote",
            [
                "cd ai",
                'pip install -e ".[mt5]"',
                "Só funciona no Windows. Em Linux/Mac não existe.",
            ],
        )
        return 1
    ok(f"instalado (versão {mt5.__version__})")

    # ------------------------------------------------------------------
    etapa(2, "Conexão com o terminal")
    if not mt5.initialize():
        falha(f"não conectou — erro {mt5.last_error()}")
        como_resolver(
            "conectar ao terminal",
            [
                "Abra o MetaTrader 5 e FAÇA LOGIN (o terminal precisa ficar aberto).",
                "Ferramentas → Opções → Consultores Especialistas:",
                "   marque 'Permitir negociação algorítmica'.",
                "Se tiver mais de um terminal instalado, aponte o caminho:",
                "   MetaTrader5Fonte(caminho_terminal=r'C:\\...\\terminal64.exe')",
                "Rode este script como o MESMO usuário que abriu o terminal.",
            ],
        )
        return 1
    ok("terminal respondendo")

    try:
        return _checar_conta(mt5)
    finally:
        mt5.shutdown()


def _checar_conta(mt5) -> int:
    from trader_ai.fontes.contratos import codigo_vigente, simbolo_continuo
    from trader_ai.instrumentos import resolver

    # ------------------------------------------------------------------
    etapa(3, "Conta conectada")
    conta = mt5.account_info()
    if conta is None:
        falha("terminal aberto mas sem conta logada")
        como_resolver(
            "logar",
            ["No terminal: Arquivo → Login na conta de negociação."],
        )
        return 1

    corretora = (conta.company or "").strip()
    e_demo = conta.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
    tipo = "DEMO" if e_demo else "REAL"
    ok(f"conta {conta.login} ({tipo}) · corretora: {corretora}")
    info(f"servidor: {conta.server} · moeda: {conta.currency} · saldo: {conta.balance}")

    if not e_demo:
        aviso("esta é uma conta REAL")
        info("    Este sistema só LÊ cotação e emite sinal — nunca envia ordem.")
        info("    Ainda assim, para estudar o motor uma conta demo é a escolha certa:")
        info("    dado idêntico, zero chance de um clique errado virar posição.")

    e_b3 = any(nome in corretora.lower() for nome in CORRETORAS_B3)
    if "metaquotes" in corretora.lower():
        falha("esta é a conta demo padrão da MetaQuotes — ela NÃO tem ativos da B3")
        como_resolver(
            "conseguir acesso a WIN e WDO",
            [
                "Abra conta numa corretora brasileira que ofereça MT5 — DEMO JÁ SERVE.",
                "   Confirmadas: Clear · XP · Rico · Modal · Terra",
                "   Outras podem oferecer; pergunte antes de abrir conta.",
                "Peça 'acesso ao MetaTrader 5' — em algumas é preciso solicitar à parte.",
                "A corretora envia três coisas: número da conta, senha de negociação",
                "   e o nome do SERVIDOR (algo como 'ClearCorretora-DEMO').",
                "No terminal: Arquivo → Login na conta de negociação →",
                "   digite os três e entre. Você faz isso UMA vez.",
                "Deixe o terminal aberto e rode este diagnóstico de novo.",
            ],
        )
        print(
            f"{AMARELO}Este é o passo que falta na maioria dos casos. O terminal conecta,"
            f" tudo parece certo, e simplesmente não existe WIN no Observador.{FIM}\n"
        )
        return 1
    if not e_b3:
        aviso(f"'{corretora}' não está na lista de corretoras B3 conhecidas")
        info("Pode funcionar mesmo assim — as checagens seguintes vão dizer.")

    # ------------------------------------------------------------------
    etapa(4, "Símbolos WIN e WDO")
    hoje = datetime.now().date()
    candidatos: list[tuple[str, str]] = []
    for base in ("WIN", "WDO"):
        try:
            candidatos.append((base, codigo_vigente(base, hoje)))
        except ValueError:
            pass
        candidatos.append((base, simbolo_continuo(base)))

    disponiveis: list[tuple[str, str]] = []
    divergencias: list[str] = []

    for base, simbolo in candidatos:
        if not mt5.symbol_select(simbolo, True):
            falha(f"{simbolo:<8} indisponível")
            continue
        infos = mt5.symbol_info(simbolo)
        if infos is None:
            falha(f"{simbolo:<8} indisponível")
            continue

        ok(f"{simbolo:<8} disponível")
        disponiveis.append((base, simbolo))

        # Confere as specs da corretora contra as que o motor usa para arredondar preço e
        # dimensionar posição. Divergência aqui é séria: um stop calculado fora do tick é
        # rejeitado ou arredondado pela corretora — para o lado que ela quiser —, e um
        # valor de tick errado erra o número de contratos.
        #
        # Atenção ao campo: `point` é a menor unidade de cotação (1.0 no WIN), NÃO o
        # passo mínimo de negociação (5.0). Confundir os dois é o erro clássico.
        esperado = resolver(base)
        real_tick = float(infos.trade_tick_size)
        real_valor = float(infos.trade_tick_value)
        casa_tick = abs(real_tick - esperado.tick) < 1e-9
        casa_valor = abs(real_valor - esperado.valor_tick) < 1e-6

        detalhe = (
            f"tick {real_tick:g} (R$ {real_valor:.2f})"
            f" · ponto de cotação {infos.point:g} · {infos.digits} dígitos"
        )
        if casa_tick and casa_valor:
            info(f"         {detalhe} — confere com instrumentos.py")
        else:
            info(f"         {detalhe}")
            divergencias.append(
                f"{simbolo}: corretora diz tick={real_tick:g}/R$ {real_valor:.2f}, "
                f"o motor usa tick={esperado.tick:g}/R$ {esperado.valor_tick:.2f}"
            )

    if divergencias:
        aviso("especificação de contrato divergente")
        for d in divergencias:
            info(f"    {d}")
        como_resolver(
            "alinhar as specs",
            [
                "Ajuste ai/trader_ai/instrumentos.py com os valores que a corretora informa.",
                "Isso afeta arredondamento de entrada/stop/alvo e número de contratos —",
                "   um stop fora do tick é rejeitado ou arredondado pela corretora.",
            ],
        )

    if not disponiveis:
        como_resolver(
            "liberar os símbolos",
            [
                "No terminal: Ver → Observador de Mercado (Ctrl+M).",
                "Clique com o botão direito → Símbolos (ou Ctrl+U).",
                "Procure por 'WIN' e 'WDO' e marque os contratos.",
                "Se não aparecerem, sua conta não tem direito ao mercado de",
                "   derivativos da B3 — peça liberação à corretora.",
                "Nomes variam entre corretoras: algumas usam 'WIN$' em vez de 'WIN$N'.",
                "   Rode: python scripts/diagnostico_mt5.py --listar",
            ],
        )
        return 1

    # ------------------------------------------------------------------
    etapa(5, "Leitura de candles")
    timeframes = [
        ("M5", mt5.TIMEFRAME_M5),
        ("M15", mt5.TIMEFRAME_M15),
        ("M30", mt5.TIMEFRAME_M30),
        ("H1", mt5.TIMEFRAME_H1),
    ]
    algum_dado = False
    for _, simbolo in disponiveis:
        for rotulo, tf in timeframes:
            barras = mt5.copy_rates_from_pos(simbolo, tf, 0, 100)
            if barras is None or len(barras) == 0:
                falha(f"{simbolo:<8} {rotulo:<4} sem dados ({mt5.last_error()})")
                continue
            primeira = datetime.fromtimestamp(int(barras[0]["time"]))
            ultima = datetime.fromtimestamp(int(barras[-1]["time"]))
            ok(f"{simbolo:<8} {rotulo:<4} {len(barras):>4} barras · até {ultima:%d/%m %H:%M}")
            info(f"         primeira {primeira:%d/%m/%Y %H:%M} · fech. {barras[-1]['close']}")
            algum_dado = True

    if not algum_dado:
        como_resolver(
            "obter histórico",
            [
                "No terminal, abra o gráfico do ativo e role para trás —",
                "   o MT5 baixa o histórico sob demanda.",
                "Ferramentas → Opções → Gráficos → 'Máx. barras no histórico':",
                "   coloque um valor alto (ex.: 100000000).",
                "Espere o download terminar e rode este diagnóstico de novo.",
            ],
        )
        return 1

    # ------------------------------------------------------------------
    etapa(6, "Tick ao vivo")
    agora = datetime.now()
    pregao_aberto = agora.weekday() < 5 and 9 <= agora.hour < 18
    for _, simbolo in disponiveis[:2]:
        tick = mt5.symbol_info_tick(simbolo)
        if tick is None or (tick.last == 0 and tick.bid == 0):
            if pregao_aberto:
                falha(f"{simbolo:<8} sem tick com o pregão aberto")
            else:
                aviso(f"{simbolo:<8} sem tick — esperado, o pregão está fechado")
        else:
            momento = datetime.fromtimestamp(tick.time)
            ok(f"{simbolo:<8} último {tick.last or tick.bid} às {momento:%H:%M:%S}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 74)
    print(f" {VERDE}TUDO PRONTO.{FIM} Próximos passos:")
    print("=" * 74)
    principal = next((s for b, s in disponiveis if b == "WIN"), disponiveis[0][1])
    print(f"""
  Baixar histórico para backtest (use a série contínua, sem salto de contrato):
    python -m trader_ai.cli baixar WIN --tf M5 --n 50000 --continuo

  Medir a confiabilidade real dos padrões:
    python -m trader_ai.cli walkforward dados/WIN_M5.csv --ativo WIN --janelas 5

  Alimentar o banco continuamente (deixe rodando durante o pregão):
    python -m trader_ai.coletor --ativos WIN WDO

  Símbolo detectado nesta conta: {principal}
""")
    return 0


def listar_simbolos() -> int:
    """`--listar`: mostra todos os símbolos com WIN/WDO/IND/DOL no nome.

    Serve para descobrir a nomenclatura exata da sua corretora quando o nome padrão
    não aparece.
    """
    try:
        import MetaTrader5 as mt5  # noqa: N813
    except ImportError:
        print("pacote MetaTrader5 não instalado")
        return 1
    if not mt5.initialize():
        print(f"não conectou: {mt5.last_error()}")
        return 1
    try:
        todos = mt5.symbols_get()
        alvo = [
            s.name
            for s in (todos or [])
            if any(p in s.name.upper() for p in ("WIN", "WDO", "IND", "DOL"))
        ]
        print(f"{len(alvo)} símbolos de índice/dólar encontrados:\n")
        for nome in sorted(alvo):
            print(f"  {nome}")
        if not alvo:
            print("  nenhum — sua conta provavelmente não tem acesso a derivativos da B3")
    finally:
        mt5.shutdown()
    return 0


if __name__ == "__main__":
    if "--listar" in sys.argv:
        raise SystemExit(listar_simbolos())
    raise SystemExit(main())
