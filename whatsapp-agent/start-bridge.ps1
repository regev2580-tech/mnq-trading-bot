# One-shot check for the WhatsApp bridge. The scheduled task "WhatsApp-Agents-Bridge"
# (installed by install-bridge-autostart.ps1) runs this at logon and then every minute.
# If no bridge.js is running, start one. Never starts a second one, because two bridges
# would compete over the same inbox. (A long-running watchdog loop died with
# 0xC000013A on 2026-11-09, so the scheduler does the repeating instead.)
$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'bridge.log'

$procs = Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue
$running = $procs | Where-Object { $_.CommandLine -like '*bridge.js*' -and $_.CommandLine -notlike '*--test*' -and $_.CommandLine -notlike '*--brief*' }

if (-not $running) {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
    Add-Content -Path $log -Value "$stamp watchdog: bridge not running, starting it" -Encoding utf8
    Start-Process -FilePath 'node' -ArgumentList 'bridge.js' -WorkingDirectory $dir -WindowStyle Hidden
}
