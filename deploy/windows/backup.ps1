<#
  Backup diario de la BD de la app + las salidas de jobs.
  Programar en Task Scheduler (diario, como svc_insevig o SYSTEM).
  El SQL Server 192.168.2.115 lo respalda su propio DBA.
#>
$ErrorActionPreference = 'Stop'
$Dest      = 'C:\insevig\backups'
$PgDump    = 'C:\Program Files\PostgreSQL\16\bin\pg_dump.exe'
$Db        = 'insevig_app'
$RetainDays = 30
$Stamp     = Get-Date -Format 'yyyyMMdd_HHmmss'

New-Item -ItemType Directory -Force -Path $Dest | Out-Null

# 1. Volcado de la BD (usa PGPASSWORD o .pgpass del entorno de la tarea)
& $PgDump -Fc -f "$Dest\insevig_app_$Stamp.dump" $Db
Write-Host "BD -> $Dest\insevig_app_$Stamp.dump"

# 2. Salidas de jobs (Excel/PDF/ZIP generados)
$storage = 'C:\insevig\var\storage'
if (Test-Path $storage) {
    Compress-Archive -Path "$storage\*" -DestinationPath "$Dest\storage_$Stamp.zip" -Force
    Write-Host "storage -> $Dest\storage_$Stamp.zip"
}

# 3. Retención
Get-ChildItem $Dest -File |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetainDays) } |
    Remove-Item -Force

Write-Host "Backup completo ($Stamp). Retención: $RetainDays días." -ForegroundColor Green
Write-Host "PROBAR RESTORE cada trimestre:  pg_restore -d insevig_app_test <dump>" -ForegroundColor Yellow
