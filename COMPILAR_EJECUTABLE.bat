@echo off
REM Script para compilar INSEVIG como EXE en Windows
REM Ejecuta este archivo en Windows para generar el ejecutable

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   COMPILADOR INSEVIG - Windows EXE
echo ============================================================
echo.

REM Verificar que Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no está instalado o no está en el PATH
    echo Descarga Python desde: https://www.python.org/downloads/
    echo Asegúrate de marcar "Add Python to PATH" durante la instalación
    pause
    exit /b 1
)

echo [1/4] Verificando dependencias...
pip install -q pyinstaller pyodbc pandas reportlab pillow pymupdf supabase >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas

echo.
echo [2/4] Compilando ejecutable...
echo (Esto puede tardar 2-3 minutos, por favor espera...)
echo.

PyInstaller ^
    --onedir ^
    --windowed ^
    --name INSEVIG ^
    --icon=icon.ico ^
    --hidden-import=pyodbc ^
    --hidden-import=pandas ^
    --hidden-import=reportlab ^
    --hidden-import=PIL ^
    --hidden-import=fitz ^
    --hidden-import=supabase ^
    --add-data "shared;shared" ^
    --add-data "roles;roles" ^
    --add-data "empleados;empleados" ^
    --add-data "prestamos;prestamos" ^
    --add-data "reportes;reportes" ^
    --add-data "observaciones;observaciones" ^
    --add-data "registrdor_vizulizador_egresosingresos;registrdor_vizulizador_egresosingresos" ^
    --add-data "envio_roles;envio_roles" ^
    --add-data "cuadrardor_modificardor;cuadrardor_modificardor" ^
    --add-data "config;config" ^
    Sistema_INSEVIG.pyw

if errorlevel 1 (
    echo.
    echo [ERROR] La compilación falló
    pause
    exit /b 1
)

echo.
echo [3/4] Creando archivos de configuración...

REM Crear script de inicio
(
    echo @echo off
    echo cd /d "%%~dp0"
    echo start "" "INSEVIG\INSEVIG.exe"
) > INSEVIG.bat

REM Crear README
(
    echo INSEVIG - Sistema de Nomina
    echo.
    echo INICIO RAPIDO
    echo =============
    echo 1. Doble clic en INSEVIG.bat
    echo 2. O ejecuta: INSEVIG\INSEVIG.exe
    echo.
    echo CREDENCIALES
    echo ============
    echo Usuario: admin
    echo Contraseña: admin
    echo.
    echo REQUISITOS
    echo ==========
    echo - Windows 7 o superior
    echo - Conexión a SQL Server 192.168.2.115
    echo - O Supabase como fallback
    echo.
) > README.txt

echo [OK] Archivos de configuración creados

echo.
echo [4/4] Finalizando...

REM Crear carpeta de distribución final
if not exist "INSEVIG_FINAL" mkdir INSEVIG_FINAL
if exist "INSEVIG_FINAL\*.*" del /q "INSEVIG_FINAL\*.*"
if exist "INSEVIG_FINAL\INSEVIG" rmdir /s /q "INSEVIG_FINAL\INSEVIG"

copy "dist\INSEVIG\*.*" "INSEVIG_FINAL\" >nul 2>&1
xcopy "dist\INSEVIG" "INSEVIG_FINAL\INSEVIG" /e /i /y >nul 2>&1

REM Copiar archivos importantes
copy INSEVIG.bat "INSEVIG_FINAL\" >nul 2>&1
copy README.txt "INSEVIG_FINAL\" >nul 2>&1

echo [OK] Aplicación empaquetada

echo.
echo ============================================================
echo   ✓ COMPILACION COMPLETADA EXITOSAMENTE
echo ============================================================
echo.
echo CARPETA DE DISTRIBUCION: INSEVIG_FINAL\
echo.
echo DENTRO ENCONTRARAS:
echo   - INSEVIG.bat          (Ejecutar este archivo)
echo   - INSEVIG\INSEVIG.exe  (El ejecutable principal)
echo   - README.txt           (Instrucciones)
echo.
echo COMO USAR
echo =========
echo 1. Ve a la carpeta INSEVIG_FINAL
echo 2. Doble clic en INSEVIG.bat
echo 3. O ejecuta INSEVIG\INSEVIG.exe directamente
echo 4. Inicia sesion con: admin / admin
echo.
echo DISTRIBUCION
echo =============
echo Puedes copiar la carpeta INSEVIG_FINAL a cualquier
echo computadora Windows y ejecutarla directamente.
echo NO requiere instalacion adicional.
echo.
echo IMPORTANTE
echo ===========
echo - No muevas los archivos de la carpeta
echo - Si algo se daña, copia nuevamente INSEVIG_FINAL
echo - Para actualizar, descarga nuevamente desde GitHub
echo.
echo ============================================================
echo.

pause
