# Módulo: bitacora — Agenda de cobro de liquidación de haberes

Módulo 8/9 (añadido por el usuario). Origen:
`~/Documentos/mis_proyecto/BITACORAS_AGENDA_EGRESOS_FORMATOS/Agenda_Liquidacion_Haberes.pyw`
(app de escritorio de 3 pestañas que RRHH sigue usando).

## Qué hace
Programa cuándo un empleado que sale de la empresa viene a cobrar su liquidación:
firma del acuerdo, fecha/hora/lugar de cobro, forma de pago, cheque/banco, período,
estado (`PENDIENTE → AGENDADO → PAGADO / CANCELADO`), Q.A.P., horas de suspensión,
y el "texto para el sistema" que se sube a RPEMPOBSERV.

Tres pestañas, igual que el sistema anterior:
1. **Agenda** — formulario + lista con filtros (estado / período / texto), alta,
   edición, cambio rápido a PAGADO, eliminar. Botón "Generar" arma el texto para
   el sistema (`texto_en_sistema`, mismo formato que RPEMPOBSERV). Valida el dígito
   verificador de la cédula (aviso, no bloquea).
2. **Atención personal** — registro *append-only* de cada vez que se atiende a un
   empleado (motivo, fecha, hora, observación). Solo un admin puede borrar una
   entrada. Motivos desde `bitacora_motivos` (con lista por defecto de respaldo).
3. **Reportes** — resumen (registros / horas de suspensión / con Q.A.P.) por
   estado y período, exportación a Excel con formato, y trazabilidad de acciones.

## Particularidad
**Escribe a Supabase**, no a SQL Server — es agenda propia de RRHH, no toca nómina.
Tablas: `agenda_cobro_registros`, `agenda_cobro_historial` (FK `registro_id`),
`bitacora_atencion_personal`, `bitacora_motivos`. Es el primer módulo que escribe a
Supabase (alinea con la Fase 7 futura). Requiere Internet; si Supabase no responde,
la página muestra el error y no rompe el resto de la app. Los estados y los nombres
de columna se mantienen EXACTOS a los del `.pyw` porque la tabla es compartida.
`_todas_las_filas()` pagina con `.range()` (PostgREST corta a 1000 sin avisar).

## Rebanada
- `core/repos/bitacora.py` — agenda (listar/obtener/crear/actualizar/cambiar_estado/
  eliminar), reportes (`resumen`, `historial_reciente`, `filas_reporte`), atención
  personal (`atenciones`, `registrar_atencion`, `eliminar_atencion`, `motivos_activos`),
  utilidades de fecha/período y `texto_en_sistema`.
- `core/excel/bitacora_builders.py` — `reporte_agenda_xlsx`.
- `core/utils.cedula_valida` — dígito verificador ecuatoriano.
- `insevig_web/states/bitacora_state.py`, `insevig_web/pages/bitacora/index.py`.
- `tests/unit/test_bitacora.py`.

## Permisos
`bitacora:ver` (consulta), `bitacora:crear` / `bitacora:editar` / `bitacora:eliminar`
(editor), borrar atención personal = solo `admin`.

## Pendiente / no portado (deliberado)
- Cálculo de horas extra (`_calcular_horas_extra`, cupo de sección) — el `.pyw` lo
  marca "pendiente de subir a SQL Server"; el módulo web no lo hace todavía. Los
  campos `horas_extra_*` de la tabla los sigue manteniendo la app de escritorio.
- Botón "Registrar" (UPDATE a RPEMPLEA FECHA_SAL/ESTADO/HOR25/50/100) — es una
  escritura a nómina; iría por `core/repos/empleados` con auditoría.
- "Formato de Renuncia" / "Imprimir PDF" individual — formatos HTML/PDF del `.pyw`.
- `EGRESOS/` (Google Apps Script de comprobantes de egreso) — pieza separada.
- Administrar el catálogo `bitacora_motivos` desde la UI (hoy solo lectura + respaldo).
