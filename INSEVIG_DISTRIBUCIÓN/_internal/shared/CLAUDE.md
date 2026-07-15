# Módulo: CÓDIGO COMPARTIDO

## Descripción
Utilidades y métodos compartidos por todos los módulos.

## Archivos principales
- `obtener_datos.py` - Métodos de búsqueda y consolidación de datos
- `DEBUG_DATOS.py` - Herramientas de debug

## Funciones críticas en obtener_datos.py

### `class ObtenerDatos`
```python
obtener_datos_empleado_rapido(periodo, cedula_o_nombre)
    # Búsqueda rápida desde SQL Server
    # Retorna: pandas.Series con datos consolidados

obtener_datos_empleado_supabase(periodo, cedula_o_nombre)
    # Búsqueda desde Supabase (solo lectura)
    # Busca por: código empleado → nombres → apellidos → cédula
    # Retorna: pandas.Series con estructura idéntica a SQL Server
```

## Mapeo de conceptos (NO CAMBIAR)
```python
100: 'SUELDO'
102: 'BONIFICACION'
104: 'FONDO_RESERVA'
107: 'DECIMO_TERCERA'
108: 'DECIMO_CUARTA'
200: 'APORT_IESS'
202: 'ANTICIPO_SUELDO'
203: 'MULTAS'
205: 'PRESTAMOS_COMPANIA'
...
```

## Conexiones
- **SQL Server**: pyodbc con drivers fallback (17→18→13→11→Native)
- **Supabase**: Cliente thread-safe singleton en supabase_client.py
- Credenciales: config/supabase.yaml (NOT in git)

## Rutas críticas (NO ROMPER)
- Normalización de cédula: `str(int(cedula)).zfill(10)`
- Consolidación de ingresos/egresos por clase
- Cálculo de DIAS desde clase=101
- Traducción de código a nombre desde dbtablas

## Últimas mejoras
- Búsqueda por código empleado primero (más rápido)
- Soporte dual SQL Server/Supabase
- Better error handling con logging
