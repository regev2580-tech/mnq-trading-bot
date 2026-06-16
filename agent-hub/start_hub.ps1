# start_hub.ps1 — הפעלת Agent Hub (סטטוס כל הסוכנים + ישיבת צוות)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   🤖 Agent Hub                       ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "🌐 Hub:          http://localhost:5099" -ForegroundColor Cyan
Write-Host "🗣️  ישיבת צוות:  http://localhost:5099/meeting" -ForegroundColor Cyan
Write-Host ""

Set-Location $ScriptDir
python -X utf8 hub_server.py
