$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = (Get-Command python -ErrorAction Stop).Source }

& $python -m pip install pyinstaller
& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "ImmoPortfolio" `
    --distpath $root `
    --workpath (Join-Path $root "build\portfolio-exe") `
    --specpath (Join-Path $root "build\portfolio-exe") `
    (Join-Path $root "tools\portfolio_launcher.py")

Write-Host "Erstellt: $(Join-Path $root 'ImmoPortfolio.exe')"