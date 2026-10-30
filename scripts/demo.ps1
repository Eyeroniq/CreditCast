# CreditCast demo launcher (Windows PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1          # start (sets up only what's missing)
#   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -Rebuild # retrain models + rebuild the dashboard
#
# Then open http://localhost:8000. Stop with Ctrl+C.
# Needs Python 3.11+ and Node 24 on PATH. The AI Copilot stays hidden unless the
# dashboard is built with $env:NEXT_PUBLIC_SHOW_COPILOT = "1" (and the server has GROQ_API_KEY).
param(
    [switch]$Rebuild,
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = "1"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# 1. Python environment
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Step "Creating the Python environment (first run only, a few minutes)"
    python -m venv .venv
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
}

# 2. Models and reports (generate data -> train -> validate -> governance -> monitor -> lifetime -> stress -> gates)
$artifacts = Join-Path $root "creditcast\artifacts"
$needModels = $Rebuild -or -not (Test-Path (Join-Path $artifacts "stress_report.json")) `
    -or -not (Test-Path (Join-Path $artifacts "lifetime_report.json"))
if ($needModels) {
    Step "Training the models and building every report (about 2 minutes)"
    & $python -m creditcast.cli all
    if ($LASTEXITCODE -ne 0) { throw "The pipeline or its quality gates failed - see the output above." }
}

# 3. Dashboard (static build served by the API)
$dash = Join-Path $root "app\dashboard"
if ($Rebuild -or -not (Test-Path (Join-Path $dash "out\index.html"))) {
    Step "Building the dashboard (about 1 minute)"
    Push-Location $dash
    if (-not (Test-Path "node_modules")) { npm ci --no-audit --no-fund }
    npm run build
    if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Dashboard build failed." }
    Pop-Location
}

# 4. Serve API + dashboard on one port
$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) { throw "Port $Port is already in use. Close the other program or run with -Port 8010." }
$env:STATIC_DIR = Join-Path $dash "out"
Step "CreditCast is starting: open http://localhost:$Port  (Ctrl+C to stop)"
& $python -m uvicorn app.api.main:app --host 127.0.0.1 --port $Port
