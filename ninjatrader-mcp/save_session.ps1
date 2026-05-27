# Saves timestamped snapshots of orderflow.json every 5 minutes
# Run at start of each trading session: .\save_session.ps1

$src     = "C:\Users\DELL\New folder\ninjatrader-mcp\data\orderflow.json"
$archive = "C:\Users\DELL\New folder\ninjatrader-mcp\data\archive"

Write-Host "Session recorder started. Press Ctrl+C to stop."

while ($true) {
    if (Test-Path $src) {
        $ts   = Get-Date -Format "yyyy-MM-dd_HH-mm"
        $dest = "$archive\orderflow_$ts.json"
        Copy-Item $src $dest -Force
        Write-Host "$(Get-Date -Format 'HH:mm:ss') Saved: $dest"
    }
    Start-Sleep -Seconds 300
}
