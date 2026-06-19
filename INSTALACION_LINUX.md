# Instalación en Linux - INSEVIG

## Error: Driver ODBC no encontrado

Si ves este error:
```
Can't open lib 'SQL Server' : file not found
SQLDriverConnect error 01000
```

### Solución: Instalar Driver ODBC de Microsoft

#### 1. **Ubuntu 20.04 / 22.04 / 24.04**

```bash
# Agregar repositorio de Microsoft
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Actualizar e instalar
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Alternativamente (versión anterior)
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

#### 2. **Debian**

```bash
# Agregar repositorio de Microsoft
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/debian/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Instalar
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

#### 3. **Fedora / RHEL / CentOS**

```bash
sudo su
curl https://packages.microsoft.com/config/rhel/$(rpm -E %{rhel})/prod.repo > /etc/yum.repos.d/mssql-release.repo
exit

sudo ACCEPT_EULA=Y yum install -y msodbcsql18
```

### Verificar instalación

```bash
odbcinst -j
```

Debería mostrar:
```
DRIVERS............: /etc/odbcinst.ini
SYSTEM DSN.........: /etc/odbc.ini
FILE DSN...........: /etc/ODBCDataSources
USER DSN...........: ~/.odbc.ini
```

### Probar conexión a SQL Server

```bash
python3 << 'EOF'
import pyodbc

try:
    conexion = pyodbc.connect(
        'Driver={ODBC Driver 18 for SQL Server};'
        'Server=192.168.2.115;'
        'Database=insevig;'
        'UID=sa;'
        'PWD=puntosoft123*;'
        'TrustServerCertificate=yes'
    )
    print("✓ Conexión a SQL Server OK")
    conexion.close()
except Exception as e:
    print(f"✗ Error: {e}")
EOF
```

## Si el driver no se instala

### Alternativa: Usar Supabase

Si no puedes instalar el driver ODBC, puedes usar **Supabase como fuente de datos alternativa**.

Los módulos soportan selector:
- 📋 Roles de Pago → Supabase
- 👥 Gestión Empleados → Supabase
- 💰 Préstamos → Supabase (si está disponible)

## Solución rápida: Docker

Si tienes Docker, puedes ejecutar SQL Server en un contenedor:

```bash
docker run -e 'ACCEPT_EULA=Y' -e 'SA_PASSWORD=puntosoft123*' \
  -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2019-latest
```

Luego conecta a `localhost:1433` en lugar de `192.168.2.115:1433`.

## Soporte

Si los comandos no funcionan:
1. Verifica la versión de Ubuntu: `lsb_release -a`
2. Intenta `msodbcsql17` en lugar de `msodbcsql18`
3. Usa Supabase como fallback (selector en la interfaz)
