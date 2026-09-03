<#
  Prepara un Windows Server 2019/2022 para INSEVIG.
  Ejecutar como Administrador una sola vez. Revisa cada paso antes de correr.
#>
$ErrorActionPreference = 'Stop'
$Root = 'C:\insevig'

Write-Host "== 1. Estructura de carpetas ==" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$Root\app", "$Root\var\storage", "$Root\logs", "$Root\caddy", "$Root\tools" | Out-Null

Write-Host "== 2. Cuenta de servicio (mínimo privilegio) ==" -ForegroundColor Cyan
Write-Host "   Crea manualmente 'svc_insevig' (local o de dominio) y dale:" -ForegroundColor Yellow
Write-Host "   - 'Log on as a service'" -ForegroundColor Yellow
Write-Host "   - Control total SOLO sobre C:\insevig" -ForegroundColor Yellow
# icacls "$Root" /grant "svc_insevig:(OI)(CI)F" /T

Write-Host "== 3. Software base ==" -ForegroundColor Cyan
Write-Host "   Instala manualmente (o con winget):" -ForegroundColor Yellow
Write-Host "   - Python 3.12 x64 (python.org, per-machine, Add to PATH)" -ForegroundColor Yellow
Write-Host "   - Node.js LTS (para que Reflex compile el frontend)" -ForegroundColor Yellow
Write-Host "   - Microsoft ODBC Driver 17 for SQL Server (msodbcsql17) -- NO el 18" -ForegroundColor Yellow
Write-Host "   - PostgreSQL 16 (crea BD 'insevig_app' y usuario 'insevig_app')" -ForegroundColor Yellow
Write-Host "   - Caddy (caddyserver.com) en C:\insevig\caddy\caddy.exe" -ForegroundColor Yellow
Write-Host "   - NSSM (nssm.cc) en C:\insevig\tools\nssm.exe" -ForegroundColor Yellow
# winget install -e --id Python.Python.3.12
# winget install -e --id OpenJS.NodeJS.LTS
# winget install -e --id PostgreSQL.PostgreSQL.16

Write-Host "== 4. App ==" -ForegroundColor Cyan
Write-Host "   git clone <repo> C:\insevig\app   (o copiar el código)" -ForegroundColor Yellow
Write-Host "   cd C:\insevig\app" -ForegroundColor Yellow
Write-Host "   python -m venv .venv" -ForegroundColor Yellow
Write-Host "   .\.venv\Scripts\pip install -e '.[web]' psycopg[binary]" -ForegroundColor Yellow
Write-Host "   copy deploy\.env.prod.example .env   (y completar)" -ForegroundColor Yellow
Write-Host "   .\.venv\Scripts\python -m scripts.healthcheck   (debe dar 'todo OK')" -ForegroundColor Yellow
Write-Host "   .\.venv\Scripts\alembic upgrade head" -ForegroundColor Yellow
Write-Host "   .\.venv\Scripts\python -m insevig_web.seed --user admin --clave <fuerte>" -ForegroundColor Yellow
Write-Host "   .\.venv\Scripts\reflex export --no-zip   (compila el frontend a .web\build)" -ForegroundColor Yellow

Write-Host "== 5. TLS 1.0 (solo si SQL Server 2008 R2 no negocia TLS 1.2) ==" -ForegroundColor Cyan
Write-Host "   Preferido: parchear la BD (SP3 + KB3144114)." -ForegroundColor Yellow
Write-Host "   Fallback:  .\deploy\windows\enable-tls10.ps1" -ForegroundColor Yellow

Write-Host "== 6. Servicios ==" -ForegroundColor Cyan
Write-Host "   .\deploy\windows\install-services.ps1" -ForegroundColor Yellow

Write-Host "== 7. Backups ==" -ForegroundColor Cyan
Write-Host "   Programar deploy\windows\backup.ps1 a diario (Task Scheduler)." -ForegroundColor Yellow

Write-Host "Listo. Revisa deploy\README.md para el detalle." -ForegroundColor Green
