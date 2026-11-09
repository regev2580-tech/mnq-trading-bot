# Registers the bridge watchdog to start (hidden) every time Regev logs on to Windows.
# Run once: powershell -ExecutionPolicy Bypass -File install-bridge-autostart.ps1
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $dir 'start-bridge.ps1'
$taskName = 'WhatsApp-Agents-Bridge'

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description 'WhatsApp agents bridge (Roni + Yaniv) watchdog' | Out-Null
Write-Host "Registered $taskName"
