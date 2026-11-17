$ErrorActionPreference = 'Stop'

$radarDir = 'E:\赚钱监控平台\radar_runtime_clean'
$pythonExe = 'E:\赚钱监控平台\.venv\Scripts\python.exe'
$monitorScript = Join-Path $radarDir 'opportunity_monitor_24h.py'
$logDir = Join-Path $radarDir 'logs'
$profileDir = 'E:\赚钱监控平台\publish_v10_2\.radar_visible_chrome_profile'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python environment not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $monitorScript)) {
    throw "Monitor script not found: $monitorScript"
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$env:LOCAL_BROWSER_PROFILE = $profileDir
$env:RADAR_CHROME_PORT = '9337'
$env:PYTHONUNBUFFERED = '1'
Set-Location -LiteralPath $radarDir

$logFile = Join-Path $logDir (Get-Date -Format 'yyyy-MM-dd')
$logFile = "$logFile-local-daemon.log"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] startup task launched" | Out-File -FilePath $logFile -Append -Encoding utf8
& $pythonExe $monitorScript --local-daemon *>> $logFile
