# Módulo: GESTIÓN DE EMPLEADOS

## Descripción
Módulo de gestión integral de empleados desde SQL Server con soporte a Supabase.

## Archivos principales
- `SISTEMA_GESTION_EMPLEADOS_10.pyw` - Aplicación principal
- `historial_empleado_GUI.pyw` - Visor de historial de empleado

## Funcionalidad
1. **Búsqueda**: Por nombre, cédula, código
2. **CRUD**: Create, Read, Update, Delete de empleados
3. **Catálogos**: Cargos, departamentos, secciones, etc.
4. **Dark mode**: Interfaz oscura profesional
5. **Selector dual**: SQL Server o Supabase

## Dependencias
- `shared/obtener_datos.py` - Métodos de datos
- `tkinter`, `pandas`, `pyodbc`, `supabase`

## Rutas críticas (NO ROMPER)
- `__init__()` - Inicialización con parámetro `fuente`
- `_conectar_bd()` - Elige SQL Server o Supabase
- `_cargar_catalogos()` - Carga catálogos (8 tipos: CAR, SEC, DPT, SEX, ECS, TTR, FPA, BCO)
- `_cargar_lista()` - Carga lista de empleados
- Dark mode: `_configurar_estilo()` con paleta COL_*

## Integración
- Se abre desde `Sistema_INSEVIG.pyw` como ventana Toplevel
- Selector de fuente integrado en barra superior
- Tablas en Supabase: rpemplea, dbtablas

## Últimas mejoras
- Selector SQL Server/Supabase en header
- Métodos _conectar_supabase() y _cargar_catalogos_supabase()
- Dark mode completo con option_add() global
