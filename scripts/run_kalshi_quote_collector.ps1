$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$LogPath = Join-Path $LogDir "kalshi_core_cpi_quote_collector.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $RepoRoot

python -m tasks.task2_kalshi_quote_snapshots --interval-seconds 60 2>&1 |
    Tee-Object -FilePath $LogPath -Append
