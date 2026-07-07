$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $RepoRoot "scripts\stop_kalshi_quote_collector_background.ps1")
& (Join-Path $RepoRoot "scripts\stop_predictor_collector_background.ps1")
& (Join-Path $RepoRoot "scripts\stop_polymarket_quote_collector_background.ps1")

Write-Host "Stopped Kalshi, predictor, and Polymarket collectors."
