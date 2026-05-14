$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot
$Host.UI.RawUI.WindowTitle = "AshybulakStroy AI HUB - local server"

$venvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
$dotVenvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

$pythonExe = $null

if (Test-Path $dotVenvPython) {
    $pythonExe = $dotVenvPython
} elseif (Test-Path $venvPython) {
    $pythonExe = $venvPython
}

if (-not $pythonExe) {
    Write-Host "Virtual environment python was not found in .venv or venv." -ForegroundColor Red
    Write-Host "Create the virtual environment first, then run this script again." -ForegroundColor Yellow
    Read-Host "Press Enter to close this window"
    exit 1
}

Write-Host "Starting AshybulakStroy AI HUB local server..." -ForegroundColor Cyan
Write-Host "Project: $projectRoot"
Write-Host "Python:  $pythonExe"
Write-Host "URL:     http://127.0.0.1:8800"
Write-Host "Stop:    Ctrl+C"
Write-Host ""

try {
    & $pythonExe run.py
    $exitCode = $LASTEXITCODE
} finally {
    Write-Host ""
    Write-Host "Server session finished. Console output is left visible for review." -ForegroundColor Yellow
    Read-Host "Press Enter to close this window"
}

exit $exitCode
