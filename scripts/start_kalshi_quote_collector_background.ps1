$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunnerPath = Join-Path $RepoRoot "scripts\run_kalshi_quote_collector.ps1"

$Process = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $RunnerPath) `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -PassThru

Write-Host "Started Kalshi quote collector background process."
Write-Host "Process ID: $($Process.Id)"
Write-Host "Collector interval: 30 seconds"
Write-Host "Output CSV: $(Join-Path $RepoRoot 'data\kalshi_core_cpi_quote_snapshots.csv')"
Write-Host "Log file: $(Join-Path $RepoRoot 'logs\kalshi_core_cpi_quote_collector.log')"

