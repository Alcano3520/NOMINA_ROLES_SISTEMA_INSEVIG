# Módulo: HISTORIAL DE PRÉSTAMOS

## Estado: EN DESARROLLO - LISTO PARA INTEGRAR

## Descripción
Sistema de gestión y visualización del historial de préstamos de empleados.

## Archivo principal
- `HISTORIAL_PRESTAMOS_10.pyw` - Aplicación completa

## Funcionalidad
- Registro de préstamos por empleado
- Visualización de historial de transacciones
- Cálculo de cuotas y saldos
- Integración con SQL Server y Supabase

## Dependencias
- SQL Server (lectura/escritura)
- Supabase (lectura/escritura)
- `shared/obtener_datos.py`

## Rutas críticas
- Cálculo de cuotas (no cambiar lógica financiera)
- Integridad de transacciones

## Próximos pasos
1. Revisar que sea compatible con nueva estructura
2. Integrar como pestaña en Sistema_INSEVIG.pyw
3. Testear con datos reales

## Esfuerzo de integración
BAJO - Módulo documentado y aparentemente completo
