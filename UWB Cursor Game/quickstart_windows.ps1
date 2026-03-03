param(
  [string]$ProjectPath = "",
  [int]$Tag1 = 1,
  [int]$Tag2 = 2,
  [int]$UdpPort = 9000,
  [int]$WsPort = 8765,
  [int]$WebPort = 8000,
  [double]$TrackerXMin = 0.0,
  [double]$TrackerXMax = 3.2,
  [double]$TrackerZMin = 0.0,
  [double]$TrackerZMax = 1.8288,
  [double]$BridgeEmaAlpha = 0.35,
  [string]$Entry = "game_menu.html",
  [switch]$NoOpen,
  [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
  $ProjectPath = $PSScriptRoot
}

if (-not (Test-Path -LiteralPath $ProjectPath)) {
  throw "Project path not found: $ProjectPath"
}

$Entry = $Entry.Trim()
$Entry = $Entry.TrimStart('\','/')
$entryPath = Join-Path $ProjectPath $Entry
if (-not (Test-Path -LiteralPath $entryPath)) {
  $files = Get-ChildItem -Path $ProjectPath -Filter "*.html" | Select-Object -ExpandProperty Name
  $available = if ($files) { $files -join ", " } else { "(no html files found)" }
  throw "Entry file not found: $Entry. Available: $available"
}

if ($TrackerXMax -le $TrackerXMin) {
  throw "Invalid X bounds: max must be greater than min."
}
if ($TrackerZMax -le $TrackerZMin) {
  throw "Invalid Z bounds: max must be greater than min."
}
if ($BridgeEmaAlpha -lt 0 -or $BridgeEmaAlpha -gt 1) {
  throw "Invalid BridgeEmaAlpha: must be in range [0,1]."
}

$bridgeXScale = 4.0 / ($TrackerXMax - $TrackerXMin)
$bridgeYScale = 3.0 / ($TrackerZMax - $TrackerZMin)
$bridgeXOffset = -$TrackerXMin * $bridgeXScale
$bridgeYOffset = -$TrackerZMin * $bridgeYScale

$outputDir = Join-Path $ProjectPath "output"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$bridgeLog = Join-Path $outputDir "quickstart_bridge.log"
$bridgeErrLog = Join-Path $outputDir "quickstart_bridge.err.log"
$webLog = Join-Path $outputDir "quickstart_web.log"
$webErrLog = Join-Path $outputDir "quickstart_web.err.log"
$pidFile = Join-Path $outputDir "quickstart_pids.json"

if (Test-Path $pidFile) {
  try {
    $old = Get-Content $pidFile | ConvertFrom-Json
    if ($old.bridge_pid) { Stop-Process -Id $old.bridge_pid -ErrorAction SilentlyContinue }
    if ($old.web_pid) { Stop-Process -Id $old.web_pid -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 250
  } catch {}
}

if (Test-Path $bridgeLog) { Remove-Item $bridgeLog -Force }
if (Test-Path $bridgeErrLog) { Remove-Item $bridgeErrLog -Force }
if (Test-Path $webLog) { Remove-Item $webLog -Force }
if (Test-Path $webErrLog) { Remove-Item $webErrLog -Force }
if (Test-Path $pidFile) { Remove-Item $pidFile -Force }

if (-not $SkipDeps) {
  Write-Host "[quickstart] checking Python bridge dependency (websockets)..."
  & py -c "import websockets" *> $null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "[quickstart] installing websockets..."
    py -m pip install websockets | Out-Null
    & py -c "import websockets" *> $null
    if ($LASTEXITCODE -ne 0) {
      throw "websockets install failed. Run: py -m pip install websockets"
    }
  }
}

$bridgeArgs = @(
  ".\bridge.py",
  "--udp-port", "$UdpPort",
  "--ws-port", "$WsPort",
  "--csv-3-mode", "xyz",
  "--default-tag-id", "$Tag1",
  "--x-scale", "$bridgeXScale",
  "--y-scale", "$bridgeYScale",
  "--x-offset", "$bridgeXOffset",
  "--y-offset", "$bridgeYOffset",
  "--x-min", "0",
  "--x-max", "4",
  "--y-min", "0",
  "--y-max", "3",
  "--ema-alpha", "$BridgeEmaAlpha"
)

$webArgs = @(
  "-m", "http.server", "$WebPort",
  "--bind", "127.0.0.1",
  "--directory", "."
)

Write-Host "[quickstart] starting bridge..."
$bridgeProc = Start-Process `
  -FilePath "py" `
  -ArgumentList $bridgeArgs `
  -WorkingDirectory $ProjectPath `
  -RedirectStandardOutput $bridgeLog `
  -RedirectStandardError $bridgeErrLog `
  -PassThru

Start-Sleep -Milliseconds 450

Write-Host "[quickstart] starting web server..."
$webProc = Start-Process `
  -FilePath "py" `
  -ArgumentList $webArgs `
  -WorkingDirectory $ProjectPath `
  -RedirectStandardOutput $webLog `
  -RedirectStandardError $webErrLog `
  -PassThru

Start-Sleep -Milliseconds 700
$bridgeProc.Refresh()
$webProc.Refresh()

if ($bridgeProc.HasExited) {
  Write-Host "[quickstart] bridge exited early with code $($bridgeProc.ExitCode)" -ForegroundColor Red
  if (Test-Path $bridgeErrLog) {
    Write-Host "---- bridge err (tail) ----"
    Get-Content $bridgeErrLog -Tail 40
  }
  throw "Bridge failed to start."
}

if ($webProc.HasExited) {
  Write-Host "[quickstart] web server exited early with code $($webProc.ExitCode)" -ForegroundColor Red
  if (Test-Path $webErrLog) {
    Write-Host "---- web err (tail) ----"
    Get-Content $webErrLog -Tail 40
  }
  throw "Web server failed to start."
}

$query = "tag1=$Tag1&tag2=$Tag2&ws=ws://127.0.0.1:$WsPort"
if ($Entry -eq "cursor_game.html") {
  $url = "http://127.0.0.1:$WebPort/$($Entry)?input=tag&$query"
} else {
  $url = "http://127.0.0.1:$WebPort/$($Entry)?$query"
}

Write-Host ""
Write-Host "[quickstart] ready"
Write-Host "  URL:         $url"
Write-Host "  Bridge PID:  $($bridgeProc.Id)"
Write-Host "  Web PID:     $($webProc.Id)"
Write-Host "  Bridge log:  $bridgeLog"
Write-Host "  Bridge err:  $bridgeErrLog"
Write-Host "  Web log:     $webLog"
Write-Host "  Web err:     $webErrLog"
Write-Host ""
Write-Host "Axis mapping: x<-packet.x, y<-packet.z (packet.y is depth/out-of-screen)"
Write-Host ("Transform: x=(x*{0:N6})+{1:N6}, y=(z*{2:N6})+{3:N6}" -f $bridgeXScale, $bridgeXOffset, $bridgeYScale, $bridgeYOffset)
Write-Host ("Smoothing: bridge ema-alpha={0:N2}" -f $BridgeEmaAlpha)
Write-Host ""
Write-Host "Stop with:"
Write-Host "  Stop-Process -Id $($bridgeProc.Id),$($webProc.Id)"

@{
  bridge_pid = $bridgeProc.Id
  web_pid = $webProc.Id
  bridge_log = $bridgeLog
  bridge_err = $bridgeErrLog
  web_log = $webLog
  web_err = $webErrLog
} | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8
Write-Host "PID file: $pidFile"

$healthUrl = "http://127.0.0.1:$WebPort/$Entry"
$healthy = $false
for ($i = 0; $i -lt 12; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 1
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
      $healthy = $true
      break
    }
  } catch {}
  Start-Sleep -Milliseconds 250
}
if (-not $healthy) {
  Write-Host "[quickstart] warning: local health check failed for $healthUrl" -ForegroundColor Yellow
  Write-Host "Check logs:"
  Write-Host "  $webErrLog"
  Write-Host "  $bridgeErrLog"
}

if (-not $NoOpen) {
  Start-Process $url | Out-Null
}
