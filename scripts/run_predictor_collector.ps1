$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot "logs"
$LogPath = Join-Path $LogDir "predictor_collector.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $RepoRoot

python -m tasks.task3_predictor_snapshots --interval-seconds 60 2>&1 |
    Tee-Object -FilePath $LogPath -Append

