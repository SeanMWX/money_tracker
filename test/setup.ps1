$ErrorActionPreference = "Stop"

$TestDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $TestDir ".venv"

if (-not (Test-Path $VenvDir)) {
    python -m venv $VenvDir
}

$PythonExe = Join-Path $VenvDir "Scripts\python.exe"

Write-Host ""
Write-Host "Environment ready."
Write-Host "Activate with:"
Write-Host "  $VenvDir\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Smoke test:"
Write-Host "  $PythonExe $TestDir\run_smoke.py"
Write-Host ""
Write-Host "Full CLI test suite:"
Write-Host "  $PythonExe $TestDir\run_cli_tests.py"
