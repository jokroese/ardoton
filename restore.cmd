@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\windows.ps1" restore
if errorlevel 1 pause
