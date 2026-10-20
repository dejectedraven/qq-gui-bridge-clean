@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0qq-bridge-toggle.ps1" %*
if "%~1"=="" pause
