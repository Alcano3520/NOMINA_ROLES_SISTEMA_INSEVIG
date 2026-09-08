<#
  Crea en el Escritorio (de todos los usuarios) un acceso directo a
  "Actualizar INSEVIG Web" que corre deploy\windows\Actualizar-INSEVIG.bat.
  Ejecutar UNA vez, como Administrador, en el NAS.

    powershell -ExecutionPolicy Bypass -File deploy\windows\crear-acceso-directo.ps1
#>
[CmdletBinding()]
param(
    [string]$Proyecto = 'E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG'
)
$ErrorActionPreference = 'Stop'

$bat = Join-Path $Proyecto 'deploy\windows\Actualizar-INSEVIG.bat'
if (-not (Test-Path $bat)) { throw "No existe $bat" }

$escritorio = [Environment]::GetFolderPath('CommonDesktopDirectory')  # C:\Users\Public\Desktop
$lnk = Join-Path $escritorio 'Actualizar INSEVIG Web.lnk'

$w = New-Object -ComObject WScript.Shell
$s = $w.CreateShortcut($lnk)
$s.TargetPath       = $bat
$s.WorkingDirectory = Split-Path $bat
$s.IconLocation     = "$env:SystemRoot\System32\shell32.dll,238"   # icono de "actualizar"
$s.Description       = 'Pone la ultima version de INSEVIG Web en linea (git pull + reinicio del servicio)'
$s.Save()

Write-Host "OK -> acceso directo creado:  $lnk" -ForegroundColor Green
Write-Host "     Doble clic para desplegar. Pide elevacion de Administrador solo." -ForegroundColor Green
