$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $RepoRoot "scripts\start_kalshi_quote_collector_background.ps1")
& (Join-Path $RepoRoot "scripts\start_predictor_collector_background.ps1")
& (Join-Path $RepoRoot "scripts\start_polymarket_quote_collector_background.ps1")

Write-Host "Started Kalshi, predictor, and Polymarket collectors in parallel."
