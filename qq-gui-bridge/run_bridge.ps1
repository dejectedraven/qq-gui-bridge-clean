$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location $root
try {
    & "$root\.venv\Scripts\python.exe" -m bridge.main --config "$root\config.yaml" @args
}
finally {
    Pop-Location
}
