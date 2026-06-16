# start_asaf.ps1 — הפעלת אסף (Business Scout)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "║   אסף — Business Scout 🧭            ║" -ForegroundColor Yellow
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

if (-not $env:ANTHROPIC_API_KEY) {
    $env:ANTHROPIC_API_KEY = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY","User")
}
if (-not $env:ANTHROPIC_API_KEY) {
    $key = Read-Host "ANTHROPIC_API_KEY"
    $env:ANTHROPIC_API_KEY = $key.Trim()
}

Write-Host "🌐 Dashboard: http://localhost:5001" -ForegroundColor Cyan
Write-Host "מפעיל את אסף... (Ctrl+C לעצירה)" -ForegroundColor Green
Write-Host ""

Set-Location $ScriptDir
python -X utf8 asaf_web.py
