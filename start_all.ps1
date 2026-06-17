# start_all.ps1 — מפעיל את כל הסוכנים + Hub
$Root = "C:\Users\DELL\New folder"
$Key  = [System.Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")

$envVars = @{}
Get-Content "$Root\beautyai\.env" | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.+)$') { $envVars[$matches[1].Trim()] = $matches[2].Trim() }
}
$SbUrl = $envVars["SUPABASE_URL"]
$SbKey = $envVars["SUPABASE_ANON_KEY"]

function Start-Agent {
    param($Name, $Port, $Dir, $Script, [hashtable]$Env = @{})
    $running = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host "  ✅ $Name כבר רץ (פורט $Port)" -ForegroundColor Green
        return
    }
    Write-Host "  ▶  מפעיל $Name..." -ForegroundColor Yellow
    $envStr = "`$env:ANTHROPIC_API_KEY='$Key'"
    foreach ($k in $Env.Keys) { $envStr += "; `$env:$k='$($Env[$k])'" }
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "$envStr; cd '$Dir'; python -X utf8 $Script"
    Start-Sleep 2
    Write-Host "  ✅ $Name הופעל" -ForegroundColor Green
}

Write-Host ""
Write-Host "  =============================" -ForegroundColor Cyan
Write-Host "   Agent Hub — הפעלה מלאה" -ForegroundColor Cyan
Write-Host "  =============================" -ForegroundColor Cyan
Write-Host ""

Start-Agent "ג'ימי (מסחר)"    5000 "$Root\ninjatrader-mcp" "jimmy_server.py"
Start-Agent "מקס (עסקים)"     5001 "$Root\business-scout"  "max_web.py"
Start-Agent "שון (BeautyAI)"  5002 "$Root\sean"             "sean_web.py" @{ SUPABASE_URL=$SbUrl; SUPABASE_ANON_KEY=$SbKey }
Start-Agent "Agent Hub"       5100 "$Root\agent-hub"        "hub_server.py"

Start-Sleep 3
Write-Host ""
Write-Host "  =============================" -ForegroundColor Cyan
Write-Host "   http://127.0.0.1:5100" -ForegroundColor White
Write-Host "  =============================" -ForegroundColor Cyan
Write-Host ""
Start-Process "http://127.0.0.1:5100"
