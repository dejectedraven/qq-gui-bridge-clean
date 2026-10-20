param(
    [ValidateSet('on', 'off', 'status', 'toggle')]
    [string]$Action = 'toggle'
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$watchdogScript = Join-Path $root 'watchdog.ps1'
$serverPort = 41873
$healthUrl = "http://127.0.0.1:$serverPort/global/health"

function Get-BridgeProcesses {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*-m bridge.main*' }
}

function Get-WatchdogProcesses {
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.CommandLine -like "*$root\watchdog.ps1*" -or $_.CommandLine -like "*$root\run_bridge.ps1*" }
}

function Get-ServerProcesses {
    Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -like "*serve --port $serverPort*" }
}

function Test-ServerHealthy {
    try {
        Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Show-BridgeStatus {
    $bridge = @(Get-BridgeProcesses)
    $watchdog = @(Get-WatchdogProcesses)
    $server = @(Get-ServerProcesses)
    if ($bridge) {
        Write-Host "桥接: 运行中 (PID $($bridge.ProcessId -join ','))" -ForegroundColor Green
    }
    else {
        Write-Host '桥接: 已停止' -ForegroundColor Yellow
    }
    if ($watchdog) {
        Write-Host '看护: 运行中'
    }
    else {
        Write-Host '看护: 已停止'
    }
    if ($server) {
        $health = if (Test-ServerHealthy) { '正常' } else { '异常' }
        Write-Host "服务: 运行中 (PID $($server.ProcessId -join ','), 端口 $serverPort, 健康 $health)"
    }
    else {
        Write-Host "服务: 已停止 (端口 $serverPort)"
    }
    return ($bridge.Count -gt 0)
}

function Start-QQBridge {
    if (Get-BridgeProcesses) {
        Write-Host '桥接已在运行'
        Show-BridgeStatus | Out-Null
        return
    }
    if (-not (Get-WatchdogProcesses)) {
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $watchdogScript) -WorkingDirectory $root -WindowStyle Hidden
    }
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Get-BridgeProcesses) {
            if (Test-ServerHealthy) { break }
        }
    }
    if (Get-BridgeProcesses) {
        Write-Host 'QQ 桥接已开启'
    }
    else {
        Write-Host '启动失败，查看 logs\watchdog.log 和 logs\bridge.log'
    }
    Show-BridgeStatus | Out-Null
}

function Stop-QQBridge {
    $watchdogs = @(Get-WatchdogProcesses)
    $bridges = @(Get-BridgeProcesses)
    $servers = @(Get-ServerProcesses)
    foreach ($p in $watchdogs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($p in $bridges) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($p in $servers) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
    Write-Host 'QQ 桥接已关闭'
    Show-BridgeStatus | Out-Null
}

switch ($Action) {
    'on' { Start-QQBridge }
    'off' { Stop-QQBridge }
    'status' { Show-BridgeStatus | Out-Null }
    default {
        if (Get-BridgeProcesses) { Stop-QQBridge } else { Start-QQBridge }
    }
}
