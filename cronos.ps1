<#
.SYNOPSIS
    Orquestrador do cronos-trader.

.DESCRIPTION
    A stack inteira roda em Docker — dez serviços numa rede só:

        postgres     :5460   candles, sinais, usuários
        redis        :6400   reservado
        adminer      :5461   inspeção do banco
        migrate       —      one-shot: prisma migrate deploy + seed
        motor        :1841   detecção, confluência, decisão, backtest (Python)
        backend      :1840   auth, API REST, WebSocket (Node)
        frontend     :5180   a tela (nginx servindo o build + proxy)
        langfuse-db   —      banco do Langfuse
        langfuse     :3010   observabilidade dos agentes
        litellm      :4010   gateway de LLM

    UMA peça não containeriza: o **coletor MT5**. O pacote MetaTrader5 é Windows-only e
    conversa com o terminal por IPC. Ele roda no host e escreve no Postgres publicado
    em :5460 — `.\cronos.ps1 coletor`.

.EXAMPLE
    .\cronos.ps1 up          # build + sobe tudo
    .\cronos.ps1 status      # estado dos containers e do MT5
    .\cronos.ps1 amostra     # dados sintéticos para ver o produto sem corretora
    .\cronos.ps1 coletor     # dados reais (precisa do MT5 logado)
    .\cronos.ps1 down
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('up', 'down', 'restart', 'build', 'status', 'logs', 'amostra', 'coletor',
                 'instalar-coletor', 'remover-coletor', 'diagnostico', 'testes', 'shell',
                 'nuke', 'dev')]
    [string]$Comando = 'status',

    [Parameter(Position = 1)]
    [string]$Alvo = ''
)

$ErrorActionPreference = 'Stop'
$Raiz = $PSScriptRoot
$BancoHost = 'postgresql://trader:trader@localhost:5460/cronos_trader'

function Escrever($Texto, $Cor = 'White') { Write-Host $Texto -ForegroundColor $Cor }
function Titulo($Texto) { Escrever "`n=== $Texto ===" 'Cyan' }

function ExigirDocker {
    docker info 2>&1 | Out-Null
    if (-not $?) {
        Escrever 'Docker não está rodando. Abra o Docker Desktop e tente de novo.' 'Red'
        exit 1
    }
}

function Compose { param([string[]]$Args) Push-Location $Raiz; try { docker compose @Args } finally { Pop-Location } }

function TestarPorta($Porta) {
    return Test-NetConnection -ComputerName localhost -Port $Porta -InformationLevel Quiet -WarningAction SilentlyContinue
}

# O backend recusa subir com o JWT_SECRET de exemplo quando NODE_ENV=production — e o
# container roda em production, porque é um build de produção. A resposta certa não é
# afrouxar a checagem: é gerar um segredo real. Cada máquina fica com o seu, e nunca
# existe um segredo conhecido publicamente valendo em lugar nenhum.
function GarantirSegredo {
    $envPath = Join-Path $Raiz '.env'
    if (-not (Test-Path $envPath)) {
        Copy-Item (Join-Path $Raiz '.env.example') $envPath
    }
    $conteudo = Get-Content $envPath -Raw
    if ($conteudo -notmatch 'JWT_SECRET=.*desenvolvimento') { return }

    # `RandomNumberGenerator::Fill` só existe no .NET Core — no Windows PowerShell 5.1
    # ele não é encontrado, o array fica ZERADO e o "segredo" sai todo de zeros, sem
    # erro visível. `Create()` + `GetBytes()` funciona nas duas edições.
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $bytes = [byte[]]::new(48)
        $rng.GetBytes($bytes)
    } finally { $rng.Dispose() }

    if (($bytes | Where-Object { $_ -ne 0 }).Count -eq 0) {
        Escrever 'Falha ao gerar entropia — abortando em vez de gravar um segredo previsível.' 'Red'
        exit 1
    }
    $segredo = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')

    ($conteudo -replace 'JWT_SECRET=.*', "JWT_SECRET=$segredo") |
        Set-Content $envPath -Encoding utf8 -NoNewline
    Escrever 'JWT_SECRET gerado (64 chars aleatórios) e gravado no .env' 'Green'
}

function EsperarSaude($Url, $Segundos = 120, $Nome = 'serviço') {
    for ($i = 0; $i -lt $Segundos; $i++) {
        try {
            Invoke-WebRequest $Url -TimeoutSec 3 -UseBasicParsing | Out-Null
            Escrever "  $Nome pronto (${i}s)" 'Green'
            return $true
        } catch { Start-Sleep -Seconds 1 }
    }
    Escrever "  $Nome não respondeu em ${Segundos}s — veja .\cronos.ps1 logs" 'Yellow'
    return $false
}

switch ($Comando) {

    'up' {
        ExigirDocker
        Titulo 'Subindo a stack'
        GarantirSegredo
        Compose @('up', '-d', '--build')

        Titulo 'Aguardando'
        EsperarSaude 'http://localhost:1841/saude'          90  'motor'    | Out-Null
        EsperarSaude 'http://localhost:1840/api/v1'         90  'backend'  | Out-Null
        EsperarSaude 'http://localhost:5180'                60  'frontend' | Out-Null
        # Langfuse roda migrations do Prisma no primeiro boot e demora bem mais.
        EsperarSaude 'http://localhost:3010/api/public/health' 180 'langfuse' | Out-Null
        EsperarSaude 'http://localhost:4010/health/liveliness' 90  'litellm'  | Out-Null

        Escrever "`nNo ar:" 'Green'
        Escrever '  produto    http://localhost:5180    (matheus2aroldo@gmail.com / Trader@2026!)'
        Escrever '  API        http://localhost:1840/api/v1'
        Escrever '  motor      http://localhost:1841/saude'
        Escrever '  adminer    http://localhost:5461'
        Escrever '  langfuse   http://localhost:3010     (admin@cronos.trader / cronos-dev-123)'
        Escrever '  litellm    http://localhost:4010'
        Escrever "`nSem candles ainda. Escolha:" 'Yellow'
        Escrever '  .\cronos.ps1 amostra    dados sintéticos, para ver o produto agora'
        Escrever '  .\cronos.ps1 coletor    dados reais (precisa do MT5 logado numa corretora)'
    }

    'build'   { ExigirDocker; Compose @('build', '--no-cache') }
    'down'    { ExigirDocker; Compose @('down'); Escrever 'Stack derrubada. Dados preservados.' 'Green' }
    'restart' {
        ExigirDocker
        if ($Alvo) { Compose @('restart', $Alvo) } else { Compose @('restart') }
    }

    'logs' {
        ExigirDocker
        if ($Alvo) { Compose @('logs', '-f', '--tail', '120', $Alvo) }
        else { Compose @('logs', '-f', '--tail', '60') }
    }

    'shell' {
        ExigirDocker
        if (-not $Alvo) { Escrever 'Informe o serviço: .\cronos.ps1 shell backend' 'Yellow'; break }
        Compose @('exec', $Alvo, 'sh')
    }

    'status' {
        ExigirDocker
        Titulo 'Containers'
        Compose @('ps', '--format', 'table {{.Service}}\t{{.Status}}\t{{.Ports}}')

        Titulo 'Endpoints'
        $alvos = @(
            @{ Nome = 'produto';  Porta = 5180 }
            @{ Nome = 'backend';  Porta = 1840 }
            @{ Nome = 'motor';    Porta = 1841 }
            @{ Nome = 'postgres'; Porta = 5460 }
            @{ Nome = 'adminer';  Porta = 5461 }
            @{ Nome = 'langfuse'; Porta = 3010 }
            @{ Nome = 'litellm';  Porta = 4010 }
            @{ Nome = 'redis';    Porta = 6400 }
        )
        foreach ($a in $alvos) {
            $ok = TestarPorta $a.Porta
            Escrever ("  {0,-10} :{1,-6} {2}" -f $a.Nome, $a.Porta, $(if ($ok) { 'no ar' } else { 'fora' })) `
                     $(if ($ok) { 'Green' } else { 'DarkGray' })
        }

        Titulo 'Dados'
        try {
            $s = Invoke-RestMethod 'http://localhost:1840/api/v1/mercado/saude' -TimeoutSec 5
            if ($s.candles -and $s.candles.Count -gt 0) {
                foreach ($c in $s.candles) {
                    Escrever ("  {0} {1,-5} {2,8} candles   último {3}" -f $c.ativo, $c.timeframe, $c.total, $c.ultimo)
                }
            } else {
                Escrever '  nenhum candle — rode .\cronos.ps1 amostra ou .\cronos.ps1 coletor' 'Yellow'
            }
        } catch { Escrever '  backend fora do ar' 'DarkGray' }

        Titulo 'MetaTrader 5 (host)'
        if (Get-Process terminal64 -ErrorAction SilentlyContinue) {
            Escrever '  terminal aberto — confirme login com .\cronos.ps1 diagnostico' 'Green'
        } else {
            Escrever '  terminal fechado. O coletor precisa dele aberto e logado.' 'Yellow'
        }
    }

    'amostra' {
        Titulo 'Dados sintéticos'
        Escrever 'Serve para exercitar a pipeline inteira sem corretora.' 'DarkGray'
        Escrever 'NÃO valida estratégia: é random walk.' 'Yellow'
        Push-Location (Join-Path $Raiz 'ai')
        try {
            $env:DATABASE_URL = $BancoHost
            python -m pip install --quiet --disable-pip-version-check "psycopg[binary]>=3.2" numpy
            python scripts/gerar_amostra.py --ativo WIN --dias 60
            python scripts/importar_csv.py dados/WIN_M5.csv --ativo WIN --tf M5 --analisar
        } finally { Pop-Location }
        Escrever "`nAbra http://localhost:5180" 'Green'
    }

    'instalar-coletor' {
        Titulo 'Instalando o coletor como tarefa automática'
        & (Join-Path $Raiz 'tools\instalar-coletor.ps1')
        Start-ScheduledTask -TaskName 'CronosTrader-Coletor' -ErrorAction SilentlyContinue
        Escrever 'Tarefa iniciada. A partir de agora ela sobe sozinha no logon.' 'Green'
    }

    'remover-coletor' {
        & (Join-Path $Raiz 'tools\instalar-coletor.ps1') -Remover
    }

    'coletor' {
        Titulo 'Coletor MT5 (host, em janela)'
        Escrever 'Requer o terminal MetaTrader 5 aberto e logado numa corretora B3.' 'Yellow'
        Escrever 'Esta peça não containeriza: o pacote MetaTrader5 é Windows-only.' 'DarkGray'
        Start-Process powershell -ArgumentList @(
            '-NoExit', '-Command',
            "`$host.UI.RawUI.WindowTitle='cronos-coletor';" +
            "Set-Location '$(Join-Path $Raiz 'ai')';" +
            "`$env:DATABASE_URL='$BancoHost';" +
            'python -m trader_ai.coletor --ativos WIN WDO --verboso'
        )
    }

    'diagnostico' {
        Push-Location (Join-Path $Raiz 'ai')
        try { python scripts/diagnostico_mt5.py } finally { Pop-Location }
    }

    'testes' {
        Titulo 'Motor'
        Push-Location (Join-Path $Raiz 'ai')
        try {
            python -m pytest tests -o addopts= --no-header -q
            python -m ruff check trader_ai tests scripts
        } finally { Pop-Location }

        Titulo 'Typecheck'
        Push-Location (Join-Path $Raiz 'backend');  npm run typecheck; Pop-Location
        Push-Location (Join-Path $Raiz 'frontend'); npm run typecheck; Pop-Location
    }

    'dev' {
        # Modo desenvolvimento: infra em docker, app no host com hot reload.
        ExigirDocker
        Titulo 'Modo dev (infra em docker, app no host)'
        Compose @('up', '-d', 'postgres', 'redis', 'adminer', 'migrate')

        $janelas = @(
            @{ T = 'cronos-motor';    D = 'ai';       C = "`$env:DATABASE_URL='$BancoHost'; python -m trader_ai.servico" }
            @{ T = 'cronos-backend';  D = 'backend';  C = 'npm run dev' }
            @{ T = 'cronos-frontend'; D = 'frontend'; C = 'npm run dev' }
        )
        foreach ($j in $janelas) {
            Start-Process powershell -ArgumentList @(
                '-NoExit', '-Command',
                "`$host.UI.RawUI.WindowTitle='$($j.T)'; Set-Location '$(Join-Path $Raiz $j.D)'; $($j.C)"
            )
            Start-Sleep -Seconds 2
        }
        Escrever "`nHot reload ativo. Frontend em http://localhost:5180" 'Green'
        Escrever 'Lembre-se: neste modo o backend usa backend\.env, não o .env da raiz.' 'DarkGray'
    }

    'nuke' {
        ExigirDocker
        Escrever 'Isto APAGA os bancos (candles, sinais, usuários, traces do Langfuse).' 'Red'
        if ((Read-Host 'Digite APAGAR para confirmar') -ne 'APAGAR') {
            Escrever 'Cancelado.' 'Yellow'; break
        }
        Compose @('down', '-v')
        Escrever 'Volumes removidos. Rode .\cronos.ps1 up para recomeçar.' 'Green'
    }
}
