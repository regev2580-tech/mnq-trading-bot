# start_jimmy.ps1 — הפעלת ג'ימי v2.0

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    ג'ימי v2.0 — Trading Agent 🤖     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# API Key
if (-not $env:ANTHROPIC_API_KEY) {
    $key = Read-Host "ANTHROPIC_API_KEY"
    $env:ANTHROPIC_API_KEY = $key.Trim()
}

# Python check
try {
    $pyVer = python --version 2>&1
    Write-Host "✅ $pyVer" -ForegroundColor Green
} catch {
    Write-Host "❌ Python לא נמצא!" -ForegroundColor Red
    exit 1
}

# Packages check
$missing = @()
foreach ($pkg in @("anthropic", "flask", "websocket", "mss")) {
    python -c "import $pkg" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { $missing += $pkg }
}
if ($missing.Count -gt 0) {
    Write-Host "מתקין: $($missing -join ', ')..." -ForegroundColor Yellow
    pip install @($missing -replace "websocket","websocket-client")
}

# session_bias.json
Write-Host ""
Write-Host "─── session_bias.json ───────────────────" -ForegroundColor Yellow
$biasFile = "$ScriptDir\data\session_bias.json"
if (Test-Path $biasFile) {
    $bias = Get-Content $biasFile | ConvertFrom-Json
    Write-Host "HTF Bias: $($bias.htf_bias)" -ForegroundColor $(if ($bias.htf_bias -eq 'BULLISH') {'Green'} elseif ($bias.htf_bias -eq 'BEARISH') {'Red'} else {'White'})
    Write-Host "Set at:   $($bias.set_at)"
} else {
    Write-Host "לא נמצא — ג'ימי יעבוד בלי HTF bias" -ForegroundColor Yellow
}
Write-Host "─────────────────────────────────────────" -ForegroundColor Yellow
Write-Host ""

# NT8 check
$ofFile = "$ScriptDir\data\orderflow.json"
if (Test-Path $ofFile) {
    $of = Get-Content $ofFile | ConvertFrom-Json
    $age = ((Get-Date) - [datetime]$of.timestamp).TotalSeconds
    if ($age -lt 30) {
        Write-Host "✅ NT8 מחובר | price=$($of.price) | age=$([int]$age)s" -ForegroundColor Green
    } else {
        Write-Host "⚠️  NT8: orderflow.json ישן $([int]$age)s — פתח NT8 עם ClaudeOrderFlow" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  NT8: orderflow.json לא נמצא — פתח NT8!" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "🌐 Dashboard: http://localhost:5000" -ForegroundColor Cyan
Write-Host "📊 הפעל ג'ימי מהדפדפן לניטור בזמן אמת" -ForegroundColor Cyan
Write-Host ""
Write-Host "מפעיל ג'ימי... (Ctrl+C לעצירה)" -ForegroundColor Green
Write-Host ""

# הפעל
Set-Location $ScriptDir
python jimmy.py
