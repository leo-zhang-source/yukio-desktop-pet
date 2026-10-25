@echo off
cd /d "%~dp0"
py -3 -B launcher.py --collect
if errorlevel 1 pause
