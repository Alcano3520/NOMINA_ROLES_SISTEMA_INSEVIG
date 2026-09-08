# Roles de pago — especificación de la interfaz Tkinter

Fuente: `roles/Roles_Principal.pyw` (~1920 líneas) — 2 pestañas:
**📋 Visualizador** y **📊 Generador**. Web: `insevig_web/pages/roles/`.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Pestaña "Generador"  ✅

| Caja / control | Detalle | Web |
|---|---|---|
| **📋 Parámetros de Generación** — Período | botón "Seleccionar…" abre diálogo año(combo)+mes(combo) | ✅ (input AAAA-MM) |
| Parámetros — Carpeta base | "Examinar…" (dónde guardar los PDF) | ✅ eliminado a propósito → Job + ZIP + `/trabajos` |
| **Opciones** — ☑ 2 roles por hoja | | ✅ |
| Opciones — ☑ Incluir logo + "Seleccionar logo…" | | ✅ logo INSEVIG automático (checkbox para quitarlo) |
| **🔍 Filtro por Cédulas Específicas (opcional)** | textarea de cédulas, una por línea | 🟡 (web: individual por cédula; para lote genera todos) |
| **ℹ️ Información** | resumen del período/empleados | 🟡 |
| **📊 Estado del Proceso** | barra de progreso + log | ✅ (`job_progress`) |
| **🚀 Generar Roles de Pago** / ❌ Salir | | ✅ (`/roles/lote` Job → ZIP; `/roles/generar` individual con preview) |

6 formatos de nombre de archivo (`core/pdf/layout.FORMATOS`): ✅.
Test de regresión "golden" del PDF (texto+posición vs rol real): ✅ (`tests/unit/test_fase4.py`).

## Pestaña "Visualizador"  ❌ (gap)

- Buscar roles ya generados (por período/empleado) — `_vis_buscar`.
- **💾 Descargar** el PDF encontrado — `_vis_descargar`.

Web: hoy los roles generados por lote quedan en `/trabajos` (descarga del ZIP del
Job). Falta una pantalla que liste/busque roles individuales ya generados en
`STORAGE_DIR` y permita re-descargar uno solo. Mismo hueco que "Visualizador de
roles" ya anotado en `docs/modulos/roles.md`.

---

## Lo que falta en la web

1. **Pestaña/página "Visualizador"** — buscar y re-descargar un rol ya generado
   (por período + empleado), sin regenerar. Preview embebido del PDF.
2. Filtro por lista de cédulas en el generador por lote (hoy: todos o uno).
