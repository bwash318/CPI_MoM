$ErrorActionPreference = "Stop"

$Processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*tasks.task2_kalshi_quote_snapshots*" -or
        $_.CommandLine -like "*run_kalshi_quote_collector.ps1*"
    }

foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force
    Write-Host "Stopped process $($Process.ProcessId): $($Process.Name)"
}

if (-not $Processes) {
    Write-Host "No Kalshi quote collector background process found."
}

