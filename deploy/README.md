# Despliegue — INSEVIG RRHH (Windows Server)

Runbook para poner la app en producción. Contexto: `docs/PLAN_IMPLEMENTACION.md` §D.

## Requisitos del servidor
- Windows Server 2019/2022, segmento interno con **línea de vista a `192.168.2.115`**
  (SQL Server). El SMB de préstamos ya NO se usa (se migra a Postgres una vez).
- ~2–4 vCPU / 8 GB RAM bastan para ~10 usuarios.
- Salida a Internet solo para: instalar/compilar, Supabase, correo. En operación
  diaria funciona sin Internet contra SQL Server local.

## Componentes
| Servicio | Qué | Puerto |
|---|---|---|
| `insevig-backend` | Reflex `--env prod --backend-only`, **1 proceso** | 8000 (localhost) |
| `insevig-caddy` | Proxy inverso HTTPS + sirve el frontend estático | 443 |
| PostgreSQL 16 | BD de la app (auth, auditoría, jobs, préstamos migrados) | 5432 (localhost) |
| Ollama (opcional) | IA de préstamos, offline | 11434 (localhost) |

## Pasos

### 1. Preparar el servidor
```powershell
# como Administrador
.\deploy\windows\setup.ps1     # guía paso a paso; instala prereqs a mano
```
Instalar: Python 3.12 x64, Node LTS, **ODBC Driver 17** (no el 18), PostgreSQL 16,
Caddy, NSSM. Crear la cuenta de servicio `svc_insevig` (mínimo privilegio, solo
control de `C:\insevig`).

### 2. Base de datos de la app
```sql
-- en psql
CREATE DATABASE insevig_app;
CREATE USER insevig_app WITH PASSWORD '...';
GRANT ALL PRIVILEGES ON DATABASE insevig_app TO insevig_app;
```

### 3. Logins de SQL Server (mínimo privilegio, NO usar `sa`)
```sql
CREATE LOGIN insevig_ro WITH PASSWORD = '...';
CREATE LOGIN insevig_rw WITH PASSWORD = '...';
USE insevig;
CREATE USER insevig_ro FOR LOGIN insevig_ro;  GRANT SELECT TO insevig_ro;
CREATE USER insevig_rw FOR LOGIN insevig_rw;  GRANT SELECT TO insevig_rw;
GRANT INSERT, UPDATE, DELETE ON dbo.RPEMPLEA   TO insevig_rw;
GRANT INSERT, UPDATE, DELETE ON dbo.RPEMPOBSERV TO insevig_rw;
GRANT INSERT                 ON dbo.RPINGDES   TO insevig_rw;
```

### 4. Código y configuración
```powershell
git clone <repo> C:\insevig\app
cd C:\insevig\app
python -m venv .venv
.\.venv\Scripts\pip install -e ".[web]" "psycopg[binary]"
copy deploy\.env.prod.example .env    # completar TODO
icacls .env /inheritance:r /grant "svc_insevig:R" "Administrators:F"
```

### 5. TLS 1.0 (si hace falta)
- **Preferido**: aplicar en `192.168.2.115` SQL Server 2008 R2 **SP3 + KB3144114**
  (soporte TLS 1.2). Después no hay que tocar el Windows Server.
- **Fallback**: `.\deploy\windows\enable-tls10.ps1` + reiniciar.

### 6. Verificar conectividad
```powershell
.\.venv\Scripts\python -m scripts.healthcheck    # debe decir "todo OK"
```

### 7. Migrar datos y sembrar
```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m insevig_web.seed --user admin --clave "<contraseña fuerte>"
# Historial de préstamos del SQLite legado (una vez):
.\.venv\Scripts\python -m core.migrations_legacy.sqlite_to_appdb "\\server\Respaldo 2017\Base\Saldo_prestamos_driver.db"
```

### 8. Compilar el frontend y arrancar servicios
```powershell
.\.venv\Scripts\reflex export --no-zip        # genera .web\build
copy deploy\Caddyfile C:\insevig\caddy\Caddyfile   # ajustar el hostname
.\deploy\windows\install-services.ps1
Start-Service insevig-backend, insevig-caddy
```
Añadir `insevig-rrhh.local` (o el nombre elegido) al DNS interno apuntando al servidor.

### 9. Backups
Programar `deploy\windows\backup.ps1` a diario en Task Scheduler. Probar restore
cada trimestre.

## Actualizar la app
```powershell
Stop-Service insevig-backend
cd C:\insevig\app; git pull
.\.venv\Scripts\pip install -e ".[web]"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\reflex export --no-zip
Start-Service insevig-backend
```

## Piloto y cutover (ver docs/PLAN_IMPLEMENTACION.md §D)
1. Correr web + Tkinter en paralelo 1–2 ciclos de nómina.
2. Reconciliar salidas (consolidado, roles, préstamos, observaciones) — cero
   diferencias inexplicadas.
3. Sign-off de RRHH → congelar los `.pyw`, retirar PyInstaller.
4. **Rotar** el JWT de Supabase y el password `sa` que están en git.

## Ruta Docker (opcional, Linux)
`deploy/docker/` tiene `Dockerfile` + `docker-compose.yml`. El enredo de TLS 1.0 +
red Windows hace más simple la instalación nativa; Docker queda como alternativa.
