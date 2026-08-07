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

# Um .bat em vez de `cmd /c "..."`: o redirecionamento precisa de aspas no caminho do
# log, e essas aspas dentro do argumento já entre aspas do `/c` quebram o parser do cmd.
# O arquivo elimina o aninhamento — e ainda deixa o comando legível para depuração.
#
# `-u` é obrigatório: sem ele o Python bufferiza a saída redirecionada e o log fica vazio
# por minutos, justamente quando se precisa dele.
$bat = Join-Path $PSScriptRoot 'rodar-coletor.bat'
$conteudoBat = @"
@echo off
rem Gerado por instalar-coletor.ps1 - nao edite; rode o instalador de novo.
rem Arquivo em ASCII puro: .bat com acento vira mojibake no console do Windows.
cd /d "$Ai"
set "DATABASE_URL=$BancoUrl"
set "PYTHONPATH=$Ai"
"$python" -u -m trader_ai.coletor --ativos $($Ativos -join ' ') --capital $Capital --verboso >> "$LogArquivo" 2>&1
"@
Set-Content -Path $bat -Value $conteudoBat -Encoding ASCII

$acao = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $Ai

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

# A variável de ambiente precisa existir para o processo da tarefa. Gravada no usuário
# para sobreviver a reboot — o processo da tarefa não herda o ambiente deste terminal.
[Environment]::SetEnvironmentVariable('DATABASE_URL', $BancoUrl, 'User')

Escrever "`nTarefa '$Nome' registrada." 'Green'
Escrever "  ativos ..... $($Ativos -join ', ')"
Escrever "  gatilhos ... no logon + 08h55 de seg a sex"
Escrever "  reinicio ... automatico a cada 1 min se cair"
Escrever "  log ........ $LogArquivo"
Escrever "`nO coletor coleta das 9h as 18h e dorme fora disso." 'DarkGray'
Escrever "O MetaTrader 5 precisa estar aberto e logado numa corretora B3." 'Yellow'
Escrever "`nIniciar agora:  Start-ScheduledTask -TaskName $Nome" 'DarkGray'
