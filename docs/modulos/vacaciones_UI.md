# Vacaciones — especificación de la interfaz Tkinter

Spec "prompt maestro" de `VACACIONES_SISTEMA_INSEVIG/app.py` (~5969 líneas),
para `insevig_web/pages/vacaciones/index.py` + `states/vacaciones_state.py`.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Layout

Barra superior: buscador de empleado (`🔍`) + selector de fuente.
`ttk.Notebook` con 6 pestañas:
**Pendientes de Firma** · **Datos** · **Historial** · **Gozadas** · **Pagadas** · **Cálculo**.

| Pestaña web actual | Estado |
|---|---|
| Pendientes de Firma | ✅ (dashboard, tab por defecto, bulk marcar firmado) |
| Buscar | ✅ (equivalente al buscador superior + "Datos") |
| Resumen | ✅ (≈ "Historial" / "Resumen Vacaciones") |
| Gozadas | ✅ |
| Pagadas | ✅ |
| Cálculo | ✅ |
| Reportes | ✅ (nuevo: reporte completo + pendientes global) |

---

## 1. "Pendientes de Firma" (dashboard)  ✅
- `dashboard_stats`: contadores (activos, sin firmar, pagadas sin firma, gozadas/pagadas del año).
- `sin_firmar_activos`: lista del personal activo con vacación sin firmar.
- Acción bulk "marcar firmado".

## 2. "Datos"  🟡
Ficha del empleado + **Períodos Pendientes (por gozar o cobrar)** (`frm_pend`) +
**Resumen Vacaciones** (`frm2`). Web: cubierto entre "Buscar" + "Resumen"; falta
la caja explícita "Períodos Pendientes" con su detalle por período.

## 3. "Historial"  🟡
Historial completo de gozadas + pagadas del empleado (una tabla combinada).
Web: "Resumen" muestra parte; el `.pyw` lo tiene como pestaña propia.

## 4. "Gozadas"  ✅
Tabla de vacaciones gozadas del empleado. Alta/edición de una gozada
(fecha desde/hasta, días). Botón **PDF** (comprobante GOCE). Confirmación de
período anterior pendiente antes de guardar.

## 5. "Pagadas"  ✅
Tabla de vacaciones pagadas. Registrar pago (§6). Completar pago (cheque).
Botón **PDF** (comprobante PAGO / LIQUIDACIÓN DE VACACIONES PAGADAS).

## 6. "Cálculo"  ✅ (🟡 en detalle fino)
- **Días del Período** (`dias_frame`): entries `Días período` · `Gozados` · `Adicionales Art.69` · label **A PAGAR** (verde). Botón **✏ Modificar días adic.** (`_modificar_dias_adic`).
- **Tabla de 12 meses** editable (`_panel_tabla`, canvas con scroll): valor por mes.
- **Resultado** (`frm_res`): subtotal, valor 15 días (÷24), valor día, valor adicionales, total a pagar.
- **Datos de Pago** (`frm_pago`): Forma de pago (combo) · Banco (combo) · Cta. Cte. · Cheque # · Fecha.
- Al confirmar → registra la vacación pagada + `vac_calculo`.

Web: el tab "Cálculo" tiene la mecánica; confirmar que la tabla de 12 meses es
editable igual y que "Modificar días adic." existe.

## 7. Diálogo "Anticipo de Vacaciones"  ✅
`Monto` + `Fecha del Comprobante (DD/MM/YYYY)` → botones **📋 Previsualizar** ·
**✔️ Generar** · **❌ Cancelar**. Web: ✅ (`anticipo_pdf` + diálogo).

## 8. PDF individual (comprobante GOCE / PAGO)  ✅
Port fiel de `src/pdf_generator.py` (`generar_goce` / `generar_pago`) →
`core/pdf/vacaciones_comprobante.py` (commit `5a8decd`). Encabezado con
logo + QR + metadata, tabla de 12 meses, filas condicionales, TOTAL NETO,
tabla de firmas EMPLEADOR / T.HUMANO(RRHH) / EMPLEADO con recuadro de huella.

## 9. Diálogo de configuración (`_abrir_config`)  ❌ (baja prioridad)
4 sub-pestañas: **Bancos** (lista editable) · **Observaciones** (plantillas) ·
**Rutas** (carpeta de red de financiero) · **Base de Datos** (credenciales).
Web: en la migración esto va por `core.config` / `vac_config` / selector global.

## 10. Reportes secundarios  🟡
`reporte_completo` ✅ · `reporte_pendientes_global` ✅ (nuevo).
Falta pantalla para: `reporte_pendientes` (por tipo), `reporte_dias_empleado`.

---

## Lo que falta en la web (orden sugerido)

1. Pestaña/caja **"Períodos Pendientes (por gozar o cobrar)"** con detalle por período — §2.
2. Pestaña **"Historial"** combinada gozadas+pagadas del empleado — §3.
3. Verificar que el tab **"Cálculo"** tiene la tabla de 12 meses editable + "Modificar días adic." — §6.
4. (baja) Diálogo de configuración (bancos / plantillas de obs.) — §9.
5. (baja) `reporte_pendientes` por tipo y `reporte_dias_empleado` — §10.
