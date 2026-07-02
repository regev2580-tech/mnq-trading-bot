# position_monitor.ps1
# מנהל פוזיציה פתוחה אוטונומית — כל 5 שניות
# מופעל אוטומטית כשנשלח BUY/SHORT signal

param(
    [string]$DataPath = "C:\Users\regev\New folder\ninjatrader-mcp\data"
)

$configFile   = "$DataPath\monitor_config.json"
$posFile      = "$DataPath\position.json"
$signalFile   = "$DataPath\trade_signal.json"
$logFile      = "$DataPath\monitor_log.txt"

function Write-Log($msg) {
    $ts = (Get-Date).ToString("HH:mm:ss")
    "$ts $msg" | Add-Content $logFile
    Write-Host "$ts $msg"
}

# קרא config
if (-not (Test-Path $configFile)) {
    Write-Log "ERROR: monitor_config.json not found — exiting"
    exit 1
}

$cfg = Get-Content $configFile | ConvertFrom-Json
$entry      = [double]$cfg.entry
$sl         = [double]$cfg.sl
$tp         = [double]$cfg.tp
$beTrigger  = [double]$cfg.be_trigger   # מחיר שבו מזיזים SL לכניסה
$direction  = $cfg.direction            # "LONG" or "SHORT"
$beReached  = $false

Write-Log "=== Position Monitor started | $direction entry=$entry SL=$sl TP=$tp BE=$beTrigger ==="

while ($true) {
    Start-Sleep -Seconds 5

    try {
        $pos  = Get-Content $posFile  -ErrorAction Stop | ConvertFrom-Json
        $flow = Get-Content "$DataPath\orderflow.json" -ErrorAction Stop | ConvertFrom-Json
    } catch {
        Write-Log "READ ERROR: $_"
        continue
    }

    # פוזיציה נסגרה — סיים
    if ($pos.status -ne "open") {
        Write-Log "Position closed (status=$($pos.status)) — monitor exiting"
        exit 0
    }

    $price = [double]$pos.price
    $upnl  = [double]$pos.unrealized_pnl

    # ── LONG management ──────────────────────────────────────────────
    if ($direction -eq "LONG") {

        # BE: כשמחיר מגיע ל-beTrigger → עדכן SL ל-entry
        if (-not $beReached -and $price -ge $beTrigger) {
            $beReached = $true
            $sl = $entry
            Write-Log "BE REACHED @ $price — SL moved to entry $entry"
        }

        # SL hit
        if ($price -le $sl) {
            Write-Log "SL HIT @ $price (sl=$sl) uPnL=$upnl — sending SELL"
            $ts  = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
            $reason = if ($beReached) { "BE stop hit | price=$price" } else { "SL hit | price=$price sl=$sl" }
            $json = "{`"status`":`"pending`",`"action`":`"SELL`",`"price`":$price,`"sl`":0,`"tp`":0,`"qty`":1,`"reason`":`"$reason`",`"timestamp`":`"$ts`"}"
            [System.IO.File]::WriteAllText($signalFile, $json, [System.Text.UTF8Encoding]::new($false))
            Write-Log "SELL signal written — waiting for NT8 execution"
            Start-Sleep -Seconds 10
            exit 0
        }

        # TP hit
        if ($price -ge $tp) {
            Write-Log "TP HIT @ $price (tp=$tp) uPnL=$upnl — sending SELL"
            $ts   = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
            $json = "{`"status`":`"pending`",`"action`":`"SELL`",`"price`":$price,`"sl`":0,`"tp`":0,`"qty`":1,`"reason`":`"TP hit $tp | price=$price`",`"timestamp`":`"$ts`"}"
            [System.IO.File]::WriteAllText($signalFile, $json, [System.Text.UTF8Encoding]::new($false))
            Write-Log "SELL signal written at TP — exiting"
            Start-Sleep -Seconds 10
            exit 0
        }
    }

    # ── SHORT management ─────────────────────────────────────────────
    if ($direction -eq "SHORT") {

        if (-not $beReached -and $price -le $beTrigger) {
            $beReached = $true
            $sl = $entry
            Write-Log "BE REACHED @ $price — SL moved to entry $entry"
        }

        if ($price -ge $sl) {
            Write-Log "SL HIT @ $price (sl=$sl) — sending BUY to cover SHORT"
            $ts  = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
            $json = "{`"status`":`"pending`",`"action`":`"BUY`",`"price`":$price,`"sl`":0,`"tp`":0,`"qty`":1,`"reason`":`"SHORT SL hit | price=$price sl=$sl`",`"timestamp`":`"$ts`"}"
            [System.IO.File]::WriteAllText($signalFile, $json, [System.Text.UTF8Encoding]::new($false))
            Write-Log "BUY signal written — exiting"
            Start-Sleep -Seconds 10
            exit 0
        }

        if ($price -le $tp) {
            Write-Log "TP HIT @ $price — sending BUY to close SHORT"
            $ts   = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
            $json = "{`"status`":`"pending`",`"action`":`"BUY`",`"price`":$price,`"sl`":0,`"tp`":0,`"qty`":1,`"reason`":`"SHORT TP hit $tp`",`"timestamp`":`"$ts`"}"
            [System.IO.File]::WriteAllText($signalFile, $json, [System.Text.UTF8Encoding]::new($false))
            Write-Log "BUY signal written at TP — exiting"
            Start-Sleep -Seconds 10
            exit 0
        }
    }

    Write-Log "OK | price=$price uPnL=$upnl SL=$sl BE=$beReached"
}
