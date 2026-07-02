# install_autostart.ps1
# מתקין את ג'ימי כ-Task Scheduler שמתחיל אוטומטית עם Windows
# הרץ פעם אחת כ-Administrator

$ErrorActionPreference = "Stop"
$JimmyDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = (python -c "import sys; print(sys.executable)").Trim()
$ScriptPath = "$JimmyDir\jimmy_server.py"
$ApiKey    = $env:ANTHROPIC_API_KEY

if (-not $ApiKey) {
    $ApiKey = Read-Host "הכנס ANTHROPIC_API_KEY (יישמר ב-Task Scheduler)"
}

Write-Host ""
Write-Host "מתקין ג'ימי 24/7..." -ForegroundColor Cyan
Write-Host "Python: $PythonExe"
Write-Host "Script: $ScriptPath"
Write-Host ""

# הגדר Task Scheduler
$TaskName    = "Jimmy-TradingAgent"
$Description = "ג'ימי - סוכן מסחר אוטונומי 24/7"

# מחק task ישן אם קיים
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Action: הפעל python עם jimmy_server.py
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $ScriptPath `
    -WorkingDirectory $JimmyDir

# Trigger: כניסת משתמש (לא רק boot — כי צריך API Key בenv)
$Triggers = @(
    $(New-ScheduledTaskTrigger -AtLogOn),
    $(New-ScheduledTaskTrigger -AtStartup)
)

# Settings: הפעל מחדש אם נכשל
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew

# Environment: API Key
$EnvVar = [System.Environment]::SetEnvironmentVariable(
    "ANTHROPIC_API_KEY", $ApiKey,
    [System.EnvironmentVariableTarget]::User
)

# צור Task
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName   $TaskName `
    -Action     $Action `
    -Trigger    $Triggers `
    -Settings   $Settings `
    -Principal  $Principal `
    -Description $Description `
    -Force

Write-Host ""
Write-Host "✅ ג'ימי מותקן!" -ForegroundColor Green
Write-Host ""
Write-Host "ג'ימי יתחיל אוטומטית:" -ForegroundColor Cyan
Write-Host "  • כשנכנסים ל-Windows"
Write-Host "  • אחרי restart"
Write-Host "  • אם קרסה התוכנית — מפעיל מחדש עצמאית"
Write-Host ""
Write-Host "Dashboard: http://localhost:5000" -ForegroundColor Yellow
Write-Host ""

# הפעל עכשיו
$run = Read-Host "להפעיל את ג'ימי עכשיו? (y/n)"
if ($run -eq 'y') {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "✅ ג'ימי רץ! פתח: http://localhost:5000" -ForegroundColor Green
}
