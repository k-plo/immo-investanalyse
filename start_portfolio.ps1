$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8000
$url = "http://127.0.0.1:$port/"

function Test-PortfolioServer {
    try {
        $response = Invoke-WebRequest -Uri "$url`api/health" -UseBasicParsing -TimeoutSec 1
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-PortfolioServer)) {
    $python = Get-Command python3 -ErrorAction Stop
    $arguments = @("tools\local_server.py", "$port")
    Start-Process -FilePath $python.Source -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 200
        if (Test-PortfolioServer) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        throw "Der lokale Portfolio-Server wurde nicht rechtzeitig gestartet."
    }
}

$chromePath = $null
$chromeCommand = Get-Command chrome.exe -ErrorAction SilentlyContinue
if ($chromeCommand) {
    $chromePath = $chromeCommand.Source
} else {
    $chromeCandidates = @(
        (Join-Path ${env:ProgramFiles} "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe"),
        (Join-Path ${env:LOCALAPPDATA} "Google\Chrome\Application\chrome.exe")
    )
    $chromePath = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $chromePath) {
    throw "Google Chrome wurde nicht gefunden. Bitte Chrome installieren oder chrome.exe zum PATH hinzufügen."
}

Start-Process -FilePath $chromePath -ArgumentList @("--new-window", $url)
