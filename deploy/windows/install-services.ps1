<#
  Registra los servicios de Windows con NSSM.
  Ejecutar como Administrador. Requiere C:\insevig\tools\nssm.exe
  y la cuenta de servicio 'svc_insevig' ya creada.
#>
$ErrorActionPreference = 'Stop'
$Root   = 'C:\insevig'
$Nssm   = "$Root\tools\nssm.exe"
$Py     = "$Root\app\.venv\Scripts\python.exe"
$Svc    = 'svc_insevig'   # cambiar por '.\svc_insevig' (local) o 'DOMINIO\svc_insevig'

function New-Svc($name, $bin, $args, $dir, $extra = @{}) {
    & $Nssm install $name $bin $args
    & $Nssm set $name AppDirectory $dir
    & $Nssm set $name AppStdout "$Root\logs\$name.out.log"
    & $Nssm set $name AppStderr "$Root\logs\$name.err.log"
    & $Nssm set $name AppRotateFiles 1
    & $Nssm set $name AppRotateBytes 20971520
    & $Nssm set $name Start SERVICE_AUTO_START
    & $Nssm set $name AppExit Default Restart
    foreach ($k in $extra.Keys) { & $Nssm set $name $k $extra[$k] }
}

Write-Host "== Backend Reflex (1 proceso) ==" -ForegroundColor Cyan
New-Svc 'insevig-backend' $Py '-m reflex run --env prod --backend-only --backend-port 8000' "$Root\app" `
    @{ AppEnvironmentExtra = "REFLEX_ENV=prod" }

Write-Host "== Caddy (proxy inverso HTTPS) ==" -ForegroundColor Cyan
New-Svc 'insevig-caddy' "$Root\caddy\caddy.exe" "run --config $Root\caddy\Caddyfile" "$Root\caddy"

Write-Host "== Ollama (IA offline, opcional) ==" -ForegroundColor Cyan
Write-Host "   Si usas IA local: instala Ollama y deja su propio servicio; IA_PROVIDER=ollama." -ForegroundColor Yellow

Write-Host "== Cuenta de servicio ==" -ForegroundColor Cyan
Write-Host "   Asigna 'svc_insevig' a insevig-backend e insevig-caddy:" -ForegroundColor Yellow
Write-Host "   sc.exe config insevig-backend obj= `"$Svc`" password= `"<pwd>`"" -ForegroundColor Yellow
Write-Host "   sc.exe config insevig-caddy   obj= `"$Svc`" password= `"<pwd>`"" -ForegroundColor Yellow
Write-Host "   (PostgreSQL queda con su propio servicio de instalación.)" -ForegroundColor Yellow

Write-Host "== Arrancar ==" -ForegroundColor Cyan
Write-Host "   Start-Service insevig-backend, insevig-caddy" -ForegroundColor Yellow
Write-Host "   Verifica: https://insevig-rrhh.local  (login admin)" -ForegroundColor Yellow
