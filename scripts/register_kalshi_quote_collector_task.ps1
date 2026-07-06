$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$TaskName = "CPI_MoM - Kalshi Core CPI Quote Collector"
$RunnerPath = Join-Path $RepoRoot "scripts\run_kalshi_quote_collector.ps1"

$TaskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$RunnerPath`""

& schtasks.exe /Create /TN $TaskName /TR $TaskCommand /SC ONLOGON /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to register scheduled task: $TaskName"
}

& schtasks.exe /Run /TN $TaskName | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start scheduled task: $TaskName"
}

Write-Host "Registered and started scheduled task: $TaskName"
Write-Host "Collector interval: 30 seconds"
Write-Host "Output CSV: $(Join-Path $RepoRoot 'data\kalshi_core_cpi_quote_snapshots.csv')"
Write-Host "Log file: $(Join-Path $RepoRoot 'logs\kalshi_core_cpi_quote_collector.log')"
