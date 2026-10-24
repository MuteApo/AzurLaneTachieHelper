@echo off
chcp 65001 >nul
cd /d "%~dp0"
uv run --locked tachie
if errorlevel 1 pause
