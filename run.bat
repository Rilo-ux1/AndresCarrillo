@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

"%PYTHON%" "ReconocimientoFacial\Main.py"
if errorlevel 1 (
    echo.
    echo El programa termino con errores. Revise app.log.
    pause
)
endlocal
