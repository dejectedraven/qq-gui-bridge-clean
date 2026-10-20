param(
    [int]$IntervalSec = 10,
    [int]$StartupGraceSec = 25
)

$root = 'C:\path\to\qq-gui-bridge'
$log = Join-Path $root 'logs\watchdog.log'

$mutex = New-Object System.Threading.Mutex($false, 'Local\qq_gui_bridge_watchdog')
if (-not $mutex.WaitOne(0)) {
    exit 0
}

function Write-Log([string]$message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message" | Add-Content -LiteralPath $log -Encoding utf8
}

function Get-BridgeProcesses {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*-m bridge.main*' }
}

Write-Log "watchdog started (interval=${IntervalSec}s)"

while ($true) {
    try {
        $bridge = Get-BridgeProcesses
        if (-not $bridge) {
            Write-Log 'bridge not running; starting'
            Start-Process -FilePath 'powershell.exe' `
                -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$root\run_bridge.ps1") `
                -WorkingDirectory $root -WindowStyle Hidden
            Start-Sleep -Seconds $StartupGraceSec
            $bridge = Get-BridgeProcesses
            if ($bridge) {
                Write-Log "bridge started pids=$($bridge.ProcessId -join ',')"
            } else {
                Write-Log 'bridge start failed; will retry next cycle'
            }
        }
    } catch {
        Write-Log "watchdog error: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds $IntervalSec
}
