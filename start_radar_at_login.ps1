$ErrorActionPreference = 'Stop'

$radarDir = $PSScriptRoot
$workspaceDir = Split-Path -Parent $radarDir
$pythonExe = Join-Path $workspaceDir '.venv\Scripts\python.exe'
$monitorScript = Join-Path $radarDir 'opportunity_monitor_24h.py'
$logDir = Join-Path $radarDir 'logs'
$profileDir = Join-Path $workspaceDir 'publish_v10_2\.radar_visible_chrome_profile'

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

$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$logFile = Join-Path $logDir "$stamp-local-daemon.log"
$errorLog = Join-Path $logDir "$stamp-local-daemon-error.log"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] startup task launched" | Out-File -FilePath $logFile -Encoding utf8
$process = Start-Process -FilePath $pythonExe -ArgumentList @($monitorScript, '--local-daemon') `
    -WorkingDirectory $radarDir -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput $logFile -RedirectStandardError $errorLog
exit $process.ExitCode
