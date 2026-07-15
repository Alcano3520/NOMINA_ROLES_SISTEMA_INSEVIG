# Módulo: REPORTES

## Descripción
Herramientas de reportes y análisis de nómina desde SQL Server y Supabase.

## Archivos principales
- `reporte_nomina_GUI.pyw` - Interfaz unificada de reportes
- `reporte_nomina_SQL_SERVER.pyw` - Queries directas a SQL Server
- `reporte_nomina_SUPABASE.pyw` - Queries directas a Supabase
- `reporte_nomina_COMPARADOR_SUPABASE_vs_SQL.pyw` - Comparador de sincronización

## Funcionalidad
1. **Reportes unificados**: Genera reportes desde una interfaz única
2. **Comparador**: Verifica que Supabase esté sincronizado con SQL Server
3. **Análisis**: Extrae datos de movimientos, ingresos, egresos

## Dependencias
- `shared/obtener_datos.py`
- `tkinter`, `pandas`, `pyodbc`, `supabase`

## Rutas críticas (NO ROMPER)
- Paginación en Supabase: Usar cursor-based (WHERE id > last_id) para tablas grandes
- Filtro CODEMP='10' CODSUC='10' para SQL Server
- Consolidación de conceptos desde clase (100=SUELDO, 102=BONIFICACION, etc.)

## Datos
- RPHISTOR: ~2.5M filas (solo lectura desde SQL Server)
- rphistor_temp en Supabase: Espejo histórico
- rpingdesres: Período abierto actual

## Últimas mejoras
- Soporte dual SQL Server/Supabase
- Paginación eficiente para tablas grandes
- Manejo de timeout en queries largas
