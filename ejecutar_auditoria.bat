@echo off
setlocal
chcp 65001 >nul

rem Carpeta del proyecto
set "PROYECTO=%~dp0"
cd /d "%PROYECTO%"

rem Python disponible en esta sesion
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py"

if not defined PY (
    echo [ERROR] No se encontro Python en el PATH. >> "%PROYECTO%logs\auditoria.log"
    exit /b 1
)

if not exist "%PROYECTO%logs" mkdir "%PROYECTO%logs"

echo. >> "%PROYECTO%logs\auditoria.log"
echo ===== Inicio: %date% %time% ===== >> "%PROYECTO%logs\auditoria.log"

%PY% "%PROYECTO%auditor_web.py" >> "%PROYECTO%logs\auditoria.log" 2>&1
set "RC=%ERRORLEVEL%"

echo ===== Fin: %date% %time% - codigo %RC% ===== >> "%PROYECTO%logs\auditoria.log"

exit /b %RC%
