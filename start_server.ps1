$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot "venv\Scripts\python.exe"
$dotVenvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    & $venvPython run.py
    exit $LASTEXITCODE
}

if (Test-Path $dotVenvPython) {
    & $dotVenvPython run.py
    exit $LASTEXITCODE
}

Write-Host "Virtual environment python was not found in venv or .venv." -ForegroundColor Red
Write-Host "Run .\\venv\\Scripts\\python.exe run.py or create the virtual environment first." -ForegroundColor Yellow
exit 1
