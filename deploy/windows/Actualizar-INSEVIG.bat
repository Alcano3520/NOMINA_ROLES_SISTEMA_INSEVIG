@echo off
REM ============================================================================
REM  Actualizar INSEVIG Web  -  doble clic para poner la ultima version en linea
REM ----------------------------------------------------------------------------
REM  Corre el script de despliegue (-SoloActualizar): git pull + dependencias +
REM  migraciones + reinicio del servicio 'insevig-web' + prueba de que responde.
REM  Tarda ~1 minuto (mas la primera vez que recompila el frontend).
REM
REM  Instalar: copiar este .bat al Escritorio del NAS  (o usar
REM  deploy\windows\crear-acceso-directo.ps1 que crea el acceso directo).
REM ============================================================================

setlocal
set "PROYECTO=E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG"
set "SCRIPT=%PROYECTO%\deploy\windows\deploy-nas.ps1"

title Actualizar INSEVIG Web
echo.
echo   Actualizando INSEVIG Web desde  %PROYECTO%
echo   ------------------------------------------------------------
echo.

REM  Relanzarse como Administrador si no lo es
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo   Se necesitan permisos de Administrador. Pidiendo elevacion...
    powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

if not exist "%SCRIPT%" (
    echo   [ERROR] No se encontro:  %SCRIPT%
    echo   Revisa que la ruta PROYECTO de este .bat sea la correcta.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -SoloActualizar
set "RC=%errorlevel%"

echo.
if "%RC%"=="0" (
    echo   ============================================================
    echo    LISTO. La app quedo actualizada:  http://192.168.2.181:3000
    echo    Los usuarios solo tienen que apretar F5.
    echo   ============================================================
) else (
    echo   ============================================================
    echo    HUBO UN PROBLEMA (codigo %RC%). Revisa el texto de arriba y
    echo    el log:  C:\insevig\logs\insevig-web.err.log
    echo   ============================================================
)
echo.
pause
endlocal
