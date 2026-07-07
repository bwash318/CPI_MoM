$ErrorActionPreference = "Stop"

$Processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*tasks.task4_polymarket_cpi_quote_snapshots*" -or
        $_.CommandLine -like "*run_polymarket_quote_collector.ps1*"
    }

foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force
    Write-Host "Stopped process $($Process.ProcessId): $($Process.Name)"
}

if (-not $Processes) {
    Write-Host "No Polymarket quote collector background process found."
}

