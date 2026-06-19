# Módulo: ENVÍO DE ROLES

## Estado: EN DESARROLLO - PARCIALMENTE COMPLETO

## Descripción
Sistema de envío automático de roles de pago a empleados.

## Archivos principales
- `ENVIO_ROLES_7.1.py` - Versión más reciente
- `ENVIO_ROLES_6_NUEVO.pyw` - Versión anterior
- Ejecutables: Envio_roles_v7.exe, .pkg

## Funcionalidad
- Envío de roles por email
- Gestión de distribución
- Control de entregas

## Nota
DUPLICA parcialmente funcionalidad de Roles_Principal.pyw

## Dependencias
- Roles generados
- Email configurado
- Supabase/SQL Server

## Decisión
⚠️ CONSIDERAR DESCARTAR - Duplica Roles_Principal
O FUSIONAR - Agregar función de envío a Roles_Principal

## Próximos pasos
1. Evaluar si vale la pena mantener
2. O integrar envío en Roles_Principal
3. Descartar versiones antiguas

## Esfuerzo de integración
ALTO - Duplicidad, requiere decisión arquitectónica
