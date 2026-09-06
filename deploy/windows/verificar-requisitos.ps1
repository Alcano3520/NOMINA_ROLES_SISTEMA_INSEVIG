<#
  Verifica en el NAS (192.168.2.181) qué requisitos están y cuáles faltan
  para correr el servicio Reflex de INSEVIG. No instala nada: solo informa.
  Ejecutar como Administrador:  .\deploy\windows\verificar-requisitos.ps1
#>
$ErrorActionPreference = 'Continue'
$proyecto = 'E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG'
$ok = $true

function Chk($nombre, $cond, $comoInstalar) {
    if ($cond) {
        Write-Host ("  OK    {0}" -f $nombre) -ForegroundColor Green
    } else {
        $script:ok = $false
        Write-Host ("  FALTA {0}" -f $nombre) -ForegroundColor Red
        Write-Host ("        -> {0}" -f $comoInstalar) -ForegroundColor Yellow
    }
}

Write-Host "== Requisitos del servidor INSEVIG Reflex ==" -ForegroundColor Cyan

# Python 3.12+
$py = try { (& python --version) 2>&1 } catch { '' }
$pyOk = $py -match 'Python 3\.(1[2-9]|[2-9]\d)'
Chk "Python 3.12+  ($py)" $pyOk "winget install -e --id Python.Python.3.12  (per-machine, Add to PATH)"

# Node LTS (recomendado; Reflex baja Bun solo, pero Node ayuda a compilar)
$node = try { (& node --version) 2>&1 } catch { '' }
Chk "Node.js LTS  ($node)" ($node -match '^v(1[89]|2\d)\.') "winget install -e --id OpenJS.NodeJS.LTS"

# ODBC Driver 17 (NO el 18)
$odbc = try { (Get-OdbcDriver -Name 'ODBC Driver 17 for SQL Server' -ErrorAction Stop) } catch { $null }
Chk "ODBC Driver 17 for SQL Server" ($null -ne $odbc) "Descargar 'msodbcsql17' de Microsoft (NO instalar el 18)"

# PostgreSQL 16
$pg = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue
Chk "PostgreSQL (servicio)" ($null -ne $pg) "winget install -e --id PostgreSQL.PostgreSQL.16  (crear BD 'insevig_app')"

# NSSM (para el servicio Windows)
$nssm = (Test-Path 'C:\insevig\tools\nssm.exe') -or ($null -ne (Get-Command nssm -ErrorAction SilentlyContinue))
Chk "NSSM (nssm.exe)" $nssm "Descargar de nssm.cc y dejar en C:\insevig\tools\nssm.exe"

# Código del proyecto en el share de desarrollo
Chk "Proyecto en $proyecto" (Test-Path (Join-Path $proyecto 'insevig_web')) "git clone del repo dentro de E:\Sistemas_Dev\"

# venv ya creado
Chk "venv (.venv\Scripts\reflex.exe)" (Test-Path (Join-Path $proyecto '.venv\Scripts\reflex.exe')) "Lo crea deploy\windows\deploy-nas.ps1"

# .env de producción
Chk ".env de producción" (Test-Path (Join-Path $proyecto '.env')) "copy deploy\.env.prod.example .env  y completar credenciales"

# Regla de firewall para el puerto 3000
$fw = Get-NetFirewallRule -DisplayName 'INSEVIG Web 3000' -ErrorAction SilentlyContinue
Chk "Firewall entrante TCP 3000" ($null -ne $fw) "Lo crea deploy\windows\deploy-nas.ps1"

# Línea de vista a SQL Server
$sql = Test-NetConnection -ComputerName 192.168.2.115 -Port 1433 -WarningAction SilentlyContinue
Chk "Alcanza SQL Server 192.168.2.115:1433" ($sql.TcpTestSucceeded) "Revisar red/VLAN y firewall del SQL Server"

Write-Host ""
if ($ok) {
    Write-Host "TODO LISTO. Siguiente: .\deploy\windows\deploy-nas.ps1" -ForegroundColor Green
} else {
    Write-Host "Instala/verifica lo marcado FALTA y vuelve a correr este script." -ForegroundColor Yellow
}
