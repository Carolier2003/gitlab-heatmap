$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$logDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("sync-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

$pythonCandidates = @(
    "$env:LOCALAPPDATA\Python\bin\python.exe",
    "C:\Users\S703\AppData\Local\Python\bin\python.exe"
)
$python = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    $python = "python"
}

function Write-Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host $line
}

Write-Log "start python=$python root=$Root"

# Scheduled tasks sometimes miss User env; reload explicitly
if (-not $env:GITLAB_TOKEN) {
    $env:GITLAB_TOKEN = [Environment]::GetEnvironmentVariable("GITLAB_TOKEN", "User")
}
if (-not $env:GITLAB_URL) {
    $env:GITLAB_URL = [Environment]::GetEnvironmentVariable("GITLAB_URL", "User")
}
if (-not $env:GITLAB_USER_ID) {
    $env:GITLAB_USER_ID = [Environment]::GetEnvironmentVariable("GITLAB_USER_ID", "User")
}
if (-not $env:GITLAB_USERNAME) {
    $env:GITLAB_USERNAME = [Environment]::GetEnvironmentVariable("GITLAB_USERNAME", "User")
}

if (-not $env:GITLAB_TOKEN) {
    Write-Log "ERROR: GITLAB_TOKEN missing in process/user environment"
    exit 1
}

& $python (Join-Path $Root "sync_heatmap.py") *>> $log
$code = $LASTEXITCODE
Write-Log "exit=$code"
exit $code
