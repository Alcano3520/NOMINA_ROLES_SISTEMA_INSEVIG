# Módulo: bitacora — Agenda de cobro de liquidación de haberes

Módulo 8 (añadido por el usuario). Origen:
`~/Documentos/mis_proyecto/BITACORAS_AGENDA_EGRESOS_FORMATOS/Agenda_Liquidacion_Haberes.pyw`.

## Qué hace
Programa cuándo un empleado que sale de la empresa viene a cobrar su liquidación:
fecha de firma del acuerdo, fecha de cobro, hora, lugar, forma de pago, cheque/banco,
estado (pendiente → agendado → cobrado / no_asistió / anulado), observaciones.

## Particularidad
**Escribe a Supabase**, no a SQL Server — es agenda propia de RRHH, no toca nómina.
Tablas: `agenda_cobro_registros`, `agenda_cobro_historial`. Es el primer módulo que
escribe a Supabase (alinea con la Fase 7 futura). Requiere Internet; si Supabase no
responde, la página muestra el error y no rompe el resto de la app.

## Rebanada
- `core/repos/bitacora.py` — listar / obtener / crear / actualizar / cambiar_estado /
  eliminar. Historial propio + `core.audit.registrar_evento`.
- `insevig_web/states/bitacora_state.py`, `insevig_web/pages/bitacora/index.py`.
- `tests/unit/test_bitacora.py`.

## Permisos
`bitacora:ver` (consulta), `bitacora:crear` / `bitacora:editar` (editor), todo (admin).

## Pendiente
- `EGRESOS/` (Google Apps Script de comprobantes de egreso) — pieza separada, no migrada.
- Importar el `agenda_liquidacion.db` SQLite si tiene datos que no estén ya en Supabase.
