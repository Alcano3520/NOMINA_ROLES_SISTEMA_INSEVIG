# Módulo: roles

Estado: **PDF completo (paridad con el legado) + envío**.

## Rol de pago (`core/pdf/rol_pago.py`)
Porta `dibujar_rol_en_posicion` de `Roles_generador_VIZUALIZADOR_10.pyw` línea por línea:
encabezado "SOBRES DE PAGOS / INSEVIG CIA.LTDA.", datos del empleado, tabla
Concepto/Ingresos/Descuentos/Neto, SUELDO+días, horas extras, **fondo de reserva**
(si RPEMPLEA no lo trae → 8.33% sobre SUELDO+BONIF+MANIOBRAS+SOBRETIEMPOS, mostrado
como ingreso Y como "... EN IESS" en descuentos), otros ingresos (reembolsos, décimos,
bonif, maniobras, movilización), 11 descuentos, totales y firma.

## UI
- `/roles/generar`: individual, selector de fuente, período, 2-por-hoja, incluir logo,
  **previsualización PDF embebida** (`<iframe>` con data URI) + descarga.
- `/roles/lote`: Job → ZIP en `STORAGE_DIR`, 6 formatos de nombre (`core/pdf/layout.FORMATOS`),
  2-por-hoja, logo, progreso en vivo, cancelación.

## Pendiente
- Test de regresión "golden" contra PDFs reales del legado (texto + posiciones).
- Visualizador para navegar roles ya generados en STORAGE_DIR.

## Origen legado
roles/Roles_Principal.pyw, envio_roles/ENVIO_ROLES_7_NUEVO.pyw

## Rebanada (recordatorio)
`core/repos/roles.py` · `insevig_web/states/roles_state.py` ·
`insevig_web/pages/roles/*.py` · `insevig_web/components/roles/*.py` ·
`tests/unit/test_roles_*.py` · este documento.

## Contratos que consume
Ver `docs/CONTRATOS.md`. No editar el núcleo congelado.
