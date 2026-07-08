$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunnerPath = Join-Path $RepoRoot "scripts\run_polymarket_quote_collector.ps1"

$Process = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $RunnerPath) `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -PassThru

Write-Host "Started Polymarket CPI quote collector background process."
Write-Host "Process ID: $($Process.Id)"
Write-Host "Collector interval: 60 seconds, aligned to top of minute"
Write-Host "Output Parquet dir: $(Join-Path $RepoRoot 'data\polymarket_cpi_quote_snapshots')"
Write-Host "Log file: $(Join-Path $RepoRoot 'logs\polymarket_cpi_quote_collector.log')"
