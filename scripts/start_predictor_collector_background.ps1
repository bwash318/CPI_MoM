$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunnerPath = Join-Path $RepoRoot "scripts\run_predictor_collector.ps1"

$Process = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $RunnerPath) `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -PassThru

Write-Host "Started predictor collector background process."
Write-Host "Process ID: $($Process.Id)"
Write-Host "Collector interval: 60 seconds, aligned to top of minute"
Write-Host "Output CSV: $(Join-Path $RepoRoot 'data\predictor_snapshots.csv')"
Write-Host "State file: $(Join-Path $RepoRoot 'data\predictor_latest_hashes.json')"
Write-Host "Log file: $(Join-Path $RepoRoot 'logs\predictor_collector.log')"
