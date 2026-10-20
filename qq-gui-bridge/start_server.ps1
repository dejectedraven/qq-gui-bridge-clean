$workspace = "C:\path\to\qq-workspace"
$opencode = "C:\Users\youruser\AppData\Roaming\npm\opencode.cmd"

if (-not (Test-Path -LiteralPath $workspace)) {
    throw "workspace not found: $workspace"
}
if (-not (Test-Path -LiteralPath $opencode)) {
    throw "opencode not found: $opencode"
}

Start-Process -FilePath $opencode -ArgumentList @("serve", "--port", "4100", "--hostname", "127.0.0.1") -WorkingDirectory $workspace -WindowStyle Hidden
Write-Output "OpenCode server starting on http://127.0.0.1:4100"
