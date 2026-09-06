# Módulo: admin

Estado: **Fase 3 (usuarios/roles/auditoría/config)**. Detalle en `~/.claude/plans/wise-soaring-turing.md`
(sección "Mapeo Tkinter → Reflex", entrada "Administración").

## Origen legado
—

## Rebanada
`core/repos/admin.py` · `insevig_web/states/admin_state.py` ·
`insevig_web/pages/admin/*.py` · `insevig_web/components/admin/*.py` ·
`tests/unit/test_admin.py` · este documento.

## Contratos que consume
Ver `docs/CONTRATOS.md`. No editar el núcleo congelado.

## Estado por pantalla
- `/admin/usuarios` — alta, activar/desactivar, resetear clave. OK.
- `/admin/auditoria` — tabla de `app_audit_log` con filtros usuario (substring),
  módulo, estado y rango de fechas (inclusivo), + contador de coincidencias.
  Muestra las 200 más recientes. Lógica en `core/repos/admin.buscar_auditoria`.
- `/admin/parametros` — SBU por año, proveedor de narrativa IA. OK.
- `/admin/roles` — **solo lectura** de `auth.PERMISOS_POR_DEFECTO`. Pendiente:
  hacerla editable (matriz `RolePermission` en la BD de la app que sobreescriba
  los defaults; toca `auth.py` congelado → cambio de contrato).

## Pendiente
- `admin/roles` editable (ver arriba).
- Exportar la auditoría filtrada a Excel/CSV.
