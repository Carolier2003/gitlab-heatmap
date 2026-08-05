# GitLab Heatmap Sync

Windows helper for the weekday 10:00 scheduled task.

```powershell
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$logDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("sync-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

# Prefer real Python over WindowsApps stub
$python = @(
    "$env:LOCALAPPDATA\Python\bin\python.exe",
    "C:\Users\S703\AppData\Local\Python\bin\python.exe",
    "python"
) | Where-Object {
    if ($_ -eq "python") { return $true }
    Test-Path $_
} | Select-Object -First 1

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host $line
}

Write-Log "start python=$python root=$Root"

if (-not $env:GITLAB_TOKEN) {
    Write-Log "ERROR: GITLAB_TOKEN missing in process environment"
    exit 1
}

& $python (Join-Path $Root "sync_heatmap.py") *>> $log
$code = $LASTEXITCODE
Write-Log "exit=$code"
exit $code
