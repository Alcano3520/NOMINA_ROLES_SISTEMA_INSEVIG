# INSEVIG - Guía de Instalación y Uso

## 📥 Instalación Rápida

### Opción 1: Ejecutable Empaquetado (Recomendado)

1. **Descargar**:
   - Ve a: https://github.com/tuusuario/INSEVIG/releases
   - Descarga `INSEVIG-v1.0.zip`

2. **Extraer**:
   ```bash
   unzip INSEVIG-v1.0.zip
   cd INSEVIG
   ```

3. **Ejecutar**:
   - **Windows**: Doble clic en `INSEVIG.bat` o `INSEVIG.exe`
   - **Linux/Mac**: `./INSEVIG.sh` o `./INSEVIG`

### Opción 2: Desde Código Fuente

1. **Clonar repositorio**:
   ```bash
   git clone https://github.com/tuusuario/INSEVIG.git
   cd INSEVIG
   ```

2. **Instalar dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ejecutar**:
   ```bash
   python3 Sistema_INSEVIG.pyw
   ```

## 🔑 Credenciales por Defecto

| Campo | Valor |
|-------|-------|
| **Usuario** | admin |
| **Contraseña** | admin |

## 🗄️ Configuración de Base de Datos

### SQL Server
El sistema intenta conectarse a:
- **Servidor**: 192.168.2.115
- **Base de datos**: insevig
- **Usuario**: sa
- **Contraseña**: puntosoft123*

### Supabase (Fallback)
Si SQL Server no está disponible, el sistema usa automáticamente Supabase para lectura de datos.

## 📋 Módulos Disponibles

### 1. 📋 Roles de Pago
- Generador de roles en PDF
- Visualizador de nóminas
- Búsqueda por código, nombre o cédula
- Exportación en Excel

### 2. 👥 Gestión de Empleados
- Registro y actualización de empleados
- Búsqueda avanzada
- Visualización de datos personales
- Historial de cambios

### 3. 💰 Préstamos
- Administración de préstamos de empresa
- Historial de pagos
- Búsqueda por empleado
- Cálculo automático de saldos

### 4. 📊 Reportes
- Reportes de nómina
- Análisis comparativo (SQL Server vs Supabase)
- Exportación de datos
- Gráficos estadísticos

### 5. 📝 Observaciones
- Registro de observaciones al personal
- Búsqueda y filtrado
- Estadísticas por empleado

### 6. 📥 Registrador de Movimientos
- Registro de egresos e ingresos
- Gestión de préstamos unificada
- Cálculo automático

## 🔧 Requisitos del Sistema

### Windows
- Windows 7 o superior
- No requiere instalación
- Driver ODBC 17 for SQL Server (opcional, automático)

### Linux
```bash
# Instalar driver ODBC
sudo apt-get install odbcinst unixodbc
sudo apt-get install odbc-mssql
```

### macOS
```bash
# Instalar con Homebrew
brew install unixodbc
brew install freetds --with-odbc
```

## 🚀 Inicio Rápido

1. **Ejecuta el programa**
2. **Inicia sesión**: admin / admin
3. **Selecciona un módulo** del menú lateral
4. **Busca un empleado** o accede a los reportes

## ⚙️ Configuración Avanzada

### Cambiar Base de Datos
El programa detecta automáticamente si está disponible:
1. SQL Server (prioritario)
2. Supabase (fallback)

Para forzar una fuente específica, edita la línea en `Sistema_INSEVIG.pyw`:
```python
self.db_disponible = 'SQL Server'  # o 'Supabase'
```

### Agregar Nuevos Usuarios
Edita la función `_login()` en `Sistema_INSEVIG.pyw`:
```python
if usuario == "admin" and password == "admin":
    # Agregar más condiciones aquí
elif usuario == "nuevo_usuario" and password == "contraseña":
```

## 🐛 Solución de Problemas

### Error: "Could not connect to the database"
- Verifica que SQL Server está accesible en 192.168.2.115
- El programa automáticamente fallback a Supabase
- Revisa la conexión de red

### Error: "Module not found: obtener_datos"
- Asegúrate de que la carpeta `shared` existe
- No muevas los archivos de su directorio original

### Error: "SSL Provider: unsupported protocol"
- Linux: Instala `odbc-mssql`
- Windows: El programa lo maneja automáticamente
- Fallback a Supabase disponible

### Interfaz se ve lenta o congelada
- El programa carga datos en background
- Espera a que aparezca el mensaje "✅" en la consola
- Aumenta el timeout en `obtener_datos.py` si es necesario

## 📦 Estructura del Proyecto

```
INSEVIG/
├── Sistema_INSEVIG.pyw          # Aplicación principal
├── shared/                        # Módulos compartidos
│   ├── obtener_datos.py          # Queries a BD
│   ├── detect_db.py              # Detección automática
│   └── ...
├── roles/                         # Módulo de Roles
├── empleados/                     # Módulo de Empleados
├── prestamos/                     # Módulo de Préstamos
├── reportes/                      # Módulo de Reportes
├── config/                        # Configuración
└── dist/                          # Ejecutable (si se compiló)
```

## 🔄 Actualizaciones

Para obtener las últimas versiones:
```bash
git pull origin main
```

O descarga el ejecutable más reciente desde Releases.

## 📞 Soporte

- **Email**: daniel3520@gmail.com
- **GitHub Issues**: https://github.com/tuusuario/INSEVIG/issues
- **Documentación**: Ver README.md

## 📄 Licencia

Todos los derechos reservados © 2026

---

**Última actualización**: 2026-07-15
**Versión**: 1.0
