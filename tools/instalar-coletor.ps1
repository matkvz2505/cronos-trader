<#
.SYNOPSIS
    Registra o coletor MT5 como tarefa automática do Windows.

.DESCRIPTION
    Depois disto o operador nunca mais roda comando para coletar. A tarefa:

      - sobe no LOGON do usuário e também às 08h55 de todo dia útil
      - reinicia sozinha se o processo cair
      - roda com a sessão do usuário (o MT5 precisa da sessão interativa)

    O coletor em si é consciente do pregão: coleta das 9h às 18h, dorme fora disso e
    reconecta quando o terminal volta. A tarefa só garante que ele *exista*; quem decide
    quando trabalhar é ele.

    Por que tarefa agendada e não serviço do Windows: um serviço roda na sessão 0, sem
    acesso à sessão interativa — e o MetaTrader 5 conversa por IPC com um terminal que
    vive na SUA sessão. Serviço não enxergaria o terminal.

.EXAMPLE
    .\tools\instalar-coletor.ps1
    .\tools\instalar-coletor.ps1 -Remover
#>

param(
    [switch]$Remover,
    [string[]]$Ativos = @('WIN', 'WDO'),
    [double]$Capital = 20000
)

$ErrorActionPreference = 'Stop'
$Nome = 'CronosTrader-Coletor'
$Raiz = Split-Path -Parent $PSScriptRoot
$Ai = Join-Path $Raiz 'ai'
$BancoUrl = 'postgresql://trader:trader@localhost:5460/cronos_trader'

function Escrever($t, $c = 'White') { Write-Host $t -ForegroundColor $c }

if ($Remover) {
    if (Get-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
        Escrever "Tarefa '$Nome' removida." 'Green'
    } else {
        Escrever "Tarefa '$Nome' não existe." 'Yellow'
    }
    return
}

# `Get-Command python` no Windows costuma devolver o STUB da Microsoft Store
# (`...\WindowsApps\python.exe`), que não é o interpretador — ele abre a loja. Perguntar
# ao próprio Python onde ele está resolve isso e funciona com venv, pyenv e instalação
# normal.
$python = (& python -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
if (-not $python -or -not (Test-Path $python)) {
    Escrever 'Python não encontrado. Instale-o ou ajuste o PATH.' 'Red'
    exit 1
}
Escrever "Python: $python" 'DarkGray'

# O log vai para arquivo porque a tarefa roda sem janela — sem isso, uma falha de
# conexão com o MT5 seria invisível.
$Logs = Join-Path $Raiz 'logs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$LogArquivo = Join-Path $Logs 'coletor.log'

# Python DIRETO, sem `.bat` e sem `cmd /c`. Não é simplificação estética: o `cmd.exe` do
# wrapper interceptava o Ctrl+C do console — que a tarefa agendada compartilha com a
# sessão interativa do usuário —, perguntava "Terminate batch job (Y/N)?", lia EOF do
# stdin nulo e encerrava com código 1, levando a coleta junto no meio do pregão.
# Ignorar SIGINT no Python não resolvia: quem morria era o processo pai.
#
# Sem o `.bat` some também o aninhamento de aspas do redirecionamento, que já tinha
# quebrado este instalador uma vez. Quem escreve o log agora é o próprio coletor
# (`--log`), o que ainda corrige o mojibake do codepage do console.
#
# `-u` continua obrigatório: sem ele a saída fica buferizada e o log some justamente
# quando é preciso.
$argumentos = @(
    '-u', '-m', 'trader_ai.coletor',
    '--ativos') + $Ativos + @(
    '--capital', $Capital,
    '--log', $LogArquivo,
    '--verboso'
)

$acao = New-ScheduledTaskAction -Execute $python -Argument ($argumentos -join ' ') -WorkingDirectory $Ai

$gatilhos = @(
    # No logon: se a máquina ligou depois das 9h, o coletor já sobe coletando.
    (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME),
    # 08h55 de segunda a sexta: cinco minutos de folga antes da abertura.
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At '08:55')
)

$config = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $Nome `
    -Action $acao `
    -Trigger $gatilhos `
    -Settings $config `
    -Principal $principal `
    -Description 'Coleta MT5 -> Postgres do Cronos Trader. Opera das 9h as 18h; dorme fora disso.' | Out-Null

# As variáveis precisam existir para o processo da tarefa. Gravadas no usuário para
# sobreviver a reboot — o processo da tarefa não herda o ambiente deste terminal.
[Environment]::SetEnvironmentVariable('DATABASE_URL', $BancoUrl, 'User')
# `python -m` já põe o diretório de trabalho no `sys.path`, mas o `PYTHONPATH` explícito
# torna a tarefa imune a alguém mexer no `-WorkingDirectory`.
[Environment]::SetEnvironmentVariable('PYTHONPATH', $Ai, 'User')

# O wrapper antigo não é mais usado — deixá-lo no disco convida alguém a rodá-lo e
# reencontrar o bug do Ctrl+C.
$batAntigo = Join-Path $PSScriptRoot 'rodar-coletor.bat'
if (Test-Path $batAntigo) {
    Remove-Item $batAntigo -Force
    Escrever '  removido o rodar-coletor.bat antigo (o cmd.exe dele matava a coleta no Ctrl+C)' 'DarkGray'
}

Escrever "`nTarefa '$Nome' registrada." 'Green'
Escrever "  ativos ..... $($Ativos -join ', ')"
Escrever "  gatilhos ... no logon + 08h55 de seg a sex"
Escrever "  reinicio ... automatico a cada 1 min se cair"
Escrever "  log ........ $LogArquivo"
Escrever "`nO coletor coleta das 9h as 18h e dorme fora disso." 'DarkGray'
Escrever "O MetaTrader 5 precisa estar aberto e logado numa corretora B3." 'Yellow'
Escrever "`nIniciar agora:  Start-ScheduledTask -TaskName $Nome" 'DarkGray'
