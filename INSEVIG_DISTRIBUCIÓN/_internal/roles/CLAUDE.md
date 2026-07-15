# Módulo: ROLES DE PAGO

## Descripción
Módulo de visualización y generación de roles de pago en PDF para INSEVIG.

## Archivos principales
- `Roles_Principal.pyw` - Aplicación principal con selector SQL Server/Supabase
- Otros: Versiones anteriores y visualizadores

## Funcionalidad
1. **Visualizador**: Busca empleados (por código, nombre, apellido, cédula) y muestra rol de pago
2. **Generador**: Crea PDF en batch de múltiples empleados
3. **Selector dual**: Permite buscar desde SQL Server o Supabase

## Dependencias
- `shared/obtener_datos.py` - Métodos de búsqueda y consolidación
- `tkinter`, `pandas`, `pyodbc`, `supabase`

## Rutas críticas (NO ROMPER)
- `_buscar_bd()` - Dispatcher entre SQL Server y Supabase
- `_vis_cargar()` - Carga datos del período seleccionado
- `_vis_mostrar_lista()` - Interfaz de selección de empleado
- `GeneradorRolesPagoINSEVIG` - Generador de PDF

## Integración
- Se abre desde `Sistema_INSEVIG.pyw` con parámetro `fuente`
- El selector cambia entre SQL Server y Supabase en tiempo real

## Últimas mejoras
- Búsqueda dual (SQL Server + Supabase)
- Mejor manejo de errores en threads
- Interfaz más responsiva con buttons Cancel/OK
