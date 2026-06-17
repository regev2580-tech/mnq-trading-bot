# start_sean.ps1 — הפעלת שון, מפקח BeautyAI (פורט 5002)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# טעינת משתני סביבה מ-.env של BeautyAI
$envFile = Join-Path (Split-Path $ScriptDir -Parent) "beautyai\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.+)$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

# מפתח Anthropic מה-User env (עדיפות על ה-.env)
$userKey = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
if ($userKey) { $env:ANTHROPIC_API_KEY = $userKey }

Write-Host ""
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║   💄 שון — BeautyAI Manager          ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "🌐 Dashboard: http://localhost:5002" -ForegroundColor Cyan
Write-Host ""

Set-Location $ScriptDir
python -X utf8 sean_web.py
