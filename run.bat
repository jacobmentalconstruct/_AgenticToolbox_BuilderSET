@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [run] Launching AgenticToolboxBuilder UI
"%PYTHON_EXE%" src/app.py ui
exit /b %errorlevel%
