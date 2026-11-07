@echo off
cd /d "%~dp0"
title ThaiW3Console Studio
if exist .venv\Scripts\pythonw.exe (
  start "" ".venv\Scripts\pythonw.exe" -m studio
) else if exist .venv\Scripts\python.exe (
  start "" ".venv\Scripts\python.exe" -m studio
) else (
  start "" pythonw -m studio
)
