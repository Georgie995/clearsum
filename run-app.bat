@echo off
rem Starts ClearSum from this folder (used while the app is being built).
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m clearsum
