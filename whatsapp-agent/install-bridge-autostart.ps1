# Registers the bridge check to run at Windows logon and then every minute, with no visible
# window (conhost --headless). Run once: powershell -ExecutionPolicy Bypass -File install-bridge-autostart.ps1
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $dir 'start-bridge.ps1'
$taskName = 'WhatsApp-Agents-Bridge'

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute 'conhost.exe' `
    -Argument "--headless powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $dir
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$atLogon.Delay = 'PT20S'
$everyMinute = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($atLogon, $everyMinute) -Settings $settings `
    -Principal $principal -Description 'WhatsApp agents bridge (Roni + Yaniv): start it if not running' | Out-Null
Write-Host "Registered $taskName"
