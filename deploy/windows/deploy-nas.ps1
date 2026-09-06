<#
  Despliega / actualiza el servicio Reflex de INSEVIG en el NAS 192.168.2.181.
  Corre desde el propio NAS, como Administrador, dentro del proyecto:
      cd E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG
      .\deploy\windows\deploy-nas.ps1

  Deja la app en  http://192.168.2.181:3000  (servicio Windows 'insevig-web',
  arranque automatico, reinicio si falla).
#>
[CmdletBinding()]
param(
    [string]$Proyecto = 'E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG',
    [int]$Puerto = 3000,
    [string]$Nssm = 'C:\insevig\tools\nssm.exe',
    [string]$Servicio = 'insevig-web',
    [switch]$SoloActualizar   # salta creacion de venv/servicio; solo git pull + deps + restart
)
$ErrorActionPreference = 'Stop'
Set-Location $Proyecto

$py  = Join-Path $Proyecto '.venv\Scripts\python.exe'
$rfx = Join-Path $Proyecto '.venv\Scripts\reflex.exe'

Write-Host "== 1. Actualizar codigo ==" -ForegroundColor Cyan
if (Test-Path (Join-Path $Proyecto '.git')) { git pull --ff-only }
else { Write-Host "   (no es repo git; se asume copia manual actualizada)" -ForegroundColor Yellow }

Write-Host "== 2. Entorno virtual + dependencias ==" -ForegroundColor Cyan
if (-not (Test-Path $py)) { python -m venv .venv }
& $py -m pip install --upgrade pip
& $py -m pip install -e ".[web]"

Write-Host "== 3. .env ==" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $Proyecto '.env'))) {
    Copy-Item 'deploy\.env.prod.example' '.env'
    Write-Host "   Se creo .env desde la plantilla. COMPLETA las credenciales y vuelve a correr." -ForegroundColor Red
    exit 1
}
icacls .env /inheritance:r /grant "Administrators:F" "SYSTEM:F" | Out-Null

Write-Host "== 4. Conectividad (SQL Server / Supabase / BD app) ==" -ForegroundColor Cyan
& $py -m scripts.healthcheck
if ($LASTEXITCODE -ne 0) { Write-Host "   Hay fallos de conectividad; revisa .env" -ForegroundColor Red; exit 1 }

Write-Host "== 5. Migraciones + usuario admin ==" -ForegroundColor Cyan
& $py -m alembic upgrade head
& $py -m insevig_web.seed

Write-Host "== 6. Frontend ==" -ForegroundColor Cyan
Write-Host "   'reflex run --env prod' compila el frontend al arrancar (1a vez ~1-2 min)." -ForegroundColor Yellow

if (-not $SoloActualizar) {
    Write-Host "== 7. Firewall TCP $Puerto ==" -ForegroundColor Cyan
    if (-not (Get-NetFirewallRule -DisplayName "INSEVIG Web $Puerto" -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName "INSEVIG Web $Puerto" -Direction Inbound `
            -Protocol TCP -LocalPort $Puerto -Action Allow -Profile Any | Out-Null
    }

    Write-Host "== 8. Servicio Windows '$Servicio' (NSSM) ==" -ForegroundColor Cyan
    if (-not (Test-Path $Nssm)) { throw "No existe $Nssm  (descargar de nssm.cc)" }
    if (Get-Service $Servicio -ErrorAction SilentlyContinue) { & $Nssm stop $Servicio; & $Nssm remove $Servicio confirm }
    & $Nssm install $Servicio $rfx "run --env prod --single-port --frontend-port $Puerto"
    & $Nssm set $Servicio AppDirectory $Proyecto
    & $Nssm set $Servicio AppStdout 'C:\insevig\logs\insevig-web.out.log'
    & $Nssm set $Servicio AppStderr 'C:\insevig\logs\insevig-web.err.log'
    & $Nssm set $Servicio AppRotateFiles 1
    & $Nssm set $Servicio AppRotateBytes 20971520
    & $Nssm set $Servicio Start SERVICE_AUTO_START
    & $Nssm set $Servicio AppExit Default Restart
}

Write-Host "== 9. (Re)arrancar ==" -ForegroundColor Cyan
if (Get-Service $Servicio -ErrorAction SilentlyContinue) { Restart-Service $Servicio }
else { Start-Service $Servicio }
Start-Sleep 5
try {
    (Invoke-WebRequest "http://localhost:$Puerto/" -UseBasicParsing -TimeoutSec 10) | Out-Null
    Write-Host "OK -> http://192.168.2.181:$Puerto  (login admin / admin, cambiar clave)" -ForegroundColor Green
} catch {
    Write-Host "El servicio arranco pero aun no responde; revisa C:\insevig\logs\insevig-web.err.log" -ForegroundColor Yellow
}
