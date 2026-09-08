<#
  Instala el "self-hosted runner" de GitHub Actions en el NAS como SERVICIO
  de Windows. Con esto, cada push a main despliega solo (workflow
  .github/workflows/deploy-nas.yml).

  Ejecutar UNA vez, como Administrador, en el NAS.

    # 1. Sacar un token en:
    #    https://github.com/Alcano3520/NOMINA_ROLES_SISTEMA_INSEVIG/settings/actions/runners/new
    #    (boton "New self-hosted runner" -> copiar el token que aparece en "Configure")
    # 2. Correr:
    powershell -ExecutionPolicy Bypass -File deploy\windows\instalar-runner.ps1 -Token "AXXXX..."

  El runner queda con las etiquetas [self-hosted, windows, insevig-nas] que
  espera el workflow. Corre como servicio con arranque automatico.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Token,
    [string]$RepoUrl  = 'https://github.com/Alcano3520/NOMINA_ROLES_SISTEMA_INSEVIG',
    [string]$RunnerDir = 'C:\insevig\actions-runner',
    [string]$Version  = '2.319.1',   # actualizar si GitHub pide una mas nueva
    [string]$Labels   = 'insevig-nas',
    [string]$SvcUser  = ''            # cuenta con permiso de Restart-Service; vacio = NT AUTHORITY\SYSTEM
)
$ErrorActionPreference = 'Stop'

# ── 1. Descargar y descomprimir ─────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $RunnerDir | Out-Null
Set-Location $RunnerDir
$zip = "actions-runner-win-x64-$Version.zip"
if (-not (Test-Path $zip)) {
    Write-Host "Descargando runner $Version..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v$Version/$zip" -OutFile $zip
}
Expand-Archive -Path $zip -DestinationPath $RunnerDir -Force

# ── 2. Configurar (registrar en el repo) ────────────────────────────────────
Write-Host "Registrando el runner en $RepoUrl ..." -ForegroundColor Cyan
$cfgArgs = @(
    '--url', $RepoUrl,
    '--token', $Token,
    '--name', "nas-$(hostname)",
    '--labels', $Labels,
    '--work', '_work',
    '--unattended',
    '--replace'
)
& "$RunnerDir\config.cmd" @cfgArgs

# ── 3. Instalar como servicio ──────────────────────────────────────────────
Write-Host "Instalando como servicio de Windows..." -ForegroundColor Cyan
if ($SvcUser) {
    $pwd = Read-Host "Password de $SvcUser" -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($pwd))
    & "$RunnerDir\svc.cmd" install $SvcUser $plain
} else {
    & "$RunnerDir\svc.cmd" install       # corre como NT AUTHORITY\SYSTEM (puede Restart-Service)
}
& "$RunnerDir\svc.cmd" start

Write-Host ""
Write-Host "OK. El runner esta corriendo como servicio." -ForegroundColor Green
Write-Host "Verifica en: $RepoUrl/settings/actions/runners  (debe figurar 'Idle')" -ForegroundColor Green
Write-Host "Desde ahora, cada push a main despliega solo (~1-2 min)." -ForegroundColor Green
Write-Host ""
Write-Host "Si el runner NO corre como SYSTEM y falla 'Restart-Service insevig-web'," -ForegroundColor Yellow
Write-Host "dale permiso a su cuenta sobre ese servicio con:" -ForegroundColor Yellow
Write-Host '  sc.exe sdset insevig-web "D:(A;;RPWPCR;;;<SID-de-la-cuenta>)(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)"' -ForegroundColor Yellow
