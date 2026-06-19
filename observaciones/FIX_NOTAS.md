# Arreglos necesarios para TOTAL_OSERVACIONES_4_0.pyw

## Problemas identificados:

1. **Connection is busy error**
   - Causa: Múltiples cursores/queries sin cerrar properly
   - Solución: Usar single connection con fetch() antes de nuevo execute()

2. **No adaptado a Linux**
   - Causa: Hardcoding de rutas, credenciales directas
   - Solución: Usar detect_db.py para fallback automático a Supabase

3. **Sin soporte Supabase**
   - Causa: Solo SQL Server
   - Solución: Agregar VisorEmpleadosSupabase como fallback

## Plan de fix:

1. Crear wrapper que cierre cursores correctamente
2. Agregar try-except para cada query
3. Agregar fallback automático a Supabase
4. Documentar configuración

## Estado actual:
⚠️ Módulo requiere refactor completo para Linux
✅ Solución temporal: mostrar advertencia de que necesita SQL Server en Windows
