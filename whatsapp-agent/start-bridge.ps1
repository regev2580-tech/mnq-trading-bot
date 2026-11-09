# Watchdog for the WhatsApp bridge. Runs hidden at Windows logon (scheduled task
# "WhatsApp-Agents-Bridge", installed by install-bridge-autostart.ps1).
# Every 60 seconds: if no bridge.js is running, start one. Never starts a second one,
# because two bridges would compete over the same inbox.
$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'bridge.log'

function Test-BridgeRunning {
    $procs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue
    return [bool]($procs | Where-Object { $_.CommandLine -like '*bridge.js*' -and $_.CommandLine -notlike '*--test*' -and $_.CommandLine -notlike '*--brief*' })
}

# Give the network a moment after logon
Start-Sleep -Seconds 20

while ($true) {
    if (-not (Test-BridgeRunning)) {
        $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        Add-Content -Path $log -Value "$stamp watchdog: bridge not running, starting it" -Encoding utf8
        Start-Process -FilePath 'node' -ArgumentList 'bridge.js' -WorkingDirectory $dir -WindowStyle Hidden
    }
    Start-Sleep -Seconds 60
}
