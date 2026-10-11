@echo off
rem Starts Delivery Desk from this folder (used while the app is being built).
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m delivery_desk_app
