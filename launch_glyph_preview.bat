@echo off
cd /d "%~dp0"
title ThaiW3Console Glyph Preview
if exist .venv\Scripts\python.exe (
  ".venv\Scripts\python.exe" devtools\preview_glyphs.py %*
) else (
  python devtools\preview_glyphs.py %*
)
