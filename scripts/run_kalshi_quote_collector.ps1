$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$LogPath = Join-Path $LogDir "kalshi_core_cpi_quote_collector.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $RepoRoot

# Native stderr is collector diagnostic output. PowerShell 5 wraps it as an
# ErrorRecord, so a Stop policy here would kill the supervisor while logging a
# recoverable Python traceback.
$ErrorActionPreference = "Continue"

while ($true) {
    python -u -m tasks.task1_kalshi_quote_snapshots --interval-seconds 60 2>&1 |
        Tee-Object -FilePath $LogPath -Append
    $ExitCode = $LASTEXITCODE
    $Message = "$(Get-Date -Format o) collector exited with code $ExitCode; restarting in 15 seconds"
    $Message | Tee-Object -FilePath $LogPath -Append
    Start-Sleep -Seconds 15
}
