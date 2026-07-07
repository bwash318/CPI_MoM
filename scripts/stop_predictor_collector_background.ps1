$ErrorActionPreference = "Stop"

$Processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -like "*tasks.task3_predictor_snapshots*" -or
        $_.CommandLine -like "*run_predictor_collector.ps1*"
    }

foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force
    Write-Host "Stopped process $($Process.ProcessId): $($Process.Name)"
}

if (-not $Processes) {
    Write-Host "No predictor collector background process found."
}

