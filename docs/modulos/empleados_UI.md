# Empleados — especificación de la interfaz Tkinter

Spec "prompt maestro" de `empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw` (~3021
líneas) + `empleados/CARGA_MASIVA_EMPLEADOS.pyw` + `empleados/historial_empleado_GUI.pyw`,
para replicarla fiel en `insevig_web/pages/empleados/` + `states/empleados_state.py`.

Paleta dark: `COL_BG #1E1E1E`, `COL_HEADER #0D1B2A`, `COL_ACCENT #4A9EFF`,
`COL_OK #2ED573`, `COL_DANGER #FF6B6B`, fuente Segoe UI.

Leyenda: ✅ hecho · 🟡 parcial · ❌ falta.

---

## Layout general

Ventana con 3 zonas:
```
┌ Panel izquierdo (fijo) ─┐┌ Panel central: EMPLEADOS (lista) ─┐┌ Panel derecho: Notebook 6 pestañas ┐
│ BÚSQUEDA + ⚙ Acciones   ││ filtro + combo Mostrar + tabla    ││ Datos / Ingresos / Observaciones / │
│                          ││ + orden + Actualizar              ││ Otros / Certificados / Referencias │
└──────────────────────────┘└───────────────────────────────────┘└────────────────────────────────────┘
```

---

## 1. Panel BÚSQUEDA (izquierda)  🟡

| Control | Detalle | Web |
|---|---|---|
| **Cédula:** entry + botón **Buscar** | `_buscar_por_cedula` | 🟡 (web: un campo) |
| **Código:** entry + botón **Buscar** | `_buscar_por_codigo` | 🟡 |
| **Autocompletar:** entry | sugiere empleados al teclear | 🟡 (web: `employee_search`) |
| **🔍 Búsqueda Avanzada** (botón) | abre diálogo multi-criterio (`_abrir_buscador`) | ✅ `/empleados/avanzada` |

### 1.1 Menú "⚙ Acciones ▾"  🟡
| Ítem | Acción | Web |
|---|---|---|
| 🆕 Nuevo | `_nuevo_empleado` — limpia el formulario para alta | ✅ (crear) |
| ✏️ Modificar | `_modificar_empleado` — habilita edición del formulario | ✅ (botón "Modificar") |
| 🗑️ Eliminar | `_eliminar_empleado` — borrado triple con before-image | ✅ (`confirm_dialog`) |
| 📋 Vista Completa | `_abrir_vista_completa` — ventana read-only con TODOS los campos | 🟡 (web: ficha PDF `ficha_empleado`) |
| 📤 Exportar Catálogos | `_abrir_exportador_catalogos` — Excel de DBTABLAS (FNC/SEC/DPT/BAN) | ✅ (`exportar_catalogos`) |

---

## 2. Panel EMPLEADOS (lista, centro)  ✅

- Fila de filtro: `🔍` + entry (`_filtro_texto_var`, filtra la lista cargada).
- **Mostrar:** combobox (`_filtro_var`) — opciones tipo "Activos" / "Todos" / "Liquidados" (confirmar lista exacta).
- Navegación por páginas: botones `⏮ ◀ ▶ ⏭` (`nav`).
- Tabla `Treeview` 3 columnas: **Cód.** · **Apellidos** · **Nombres**.
- Radios de **orden** (`_orden_var`): por código / apellidos / … (confirmar) + botón **Actualizar**.
- Al seleccionar una fila → carga la ficha en el Notebook derecho.

Web: `/empleados/buscar` cumple la función (lista + filtro + selección).

---

## 3. Notebook — 6 pestañas del editor  ✅ (campos) / 🟡 (organización visual)

`ttk.Notebook`, marca la pestaña "sucia" (`_tabs_dirty`) si se editó algo.
Aviso "¿Guardar cambios antes de continuar?" al cambiar de empleado con cambios sin guardar.

### 3.1 "Datos Generales"  ✅
- **Información Personal**: nombres, apellidos, cédula, sexo, estado civil, nacimiento (fecha + lugar), nacionalidad, cónyuge.
- **Ubicación**: dirección, provincia, cantón, parroquia.
- **Información Laboral**: fecha ingreso/salida, depto·cargo·sección (combos DBTABLAS), estado, tipo empleado, actividad.
- **Auditoría** (`g4`, read-only): quién/cuándo creó y modificó (`_ultima_auditoria`).
- (web: falta la sub-caja "Estudios" que el legado tiene acá o en Referencias — confirmar).

### 3.2 "Ingresos / Dctos."  ✅
- **Sueldo y Beneficios de Ley**: sueldo, bonif, compen, transporte, horas 25/50/100.
- **Acumulados de Beneficios Sociales Históricos**: décimos 13/14, vacaciones, fondo reserva.
- **Rol Extra**: movilización, lunch, anticipo, descuento, ing/dct extra, concepto.
- **Parámetros de Nómina (usados por Procesar Rol)**: `CAT_PROYECT_7/8` (décimo se paga aparte), `RPCAM2` (aporta IESS cónyuge).

### 3.3 "Observaciones"  ✅
- **Período:** entry + botón **Mostrar** (`_mostrar_obs`) — carga los 7 slots `refer1..7` del mes.
- Los 7 `Text` editables (uno por slot). Label `_lbl_fecha_fin` con la fecha de corte.
- Botones: **💾 Guardar Obs.** (`_guardar_obs`, advisory lock + auditoría) · **🖨 Imprimir Historial** (`_imprimir_observaciones`, HTML/PDF).

### 3.4 "Otros Datos"  ✅
- Generales: `INCL_ROL`/`INCL_BAN` (S/N), cargas, últ. liquidación, últ. día trabajado, días trab., grupo sanguíneo, período de pago.
- Cuentas contables: CODCTA / CTADPT / CTAAUX.
- Información bancaria: banco (RUTA4, combo BAN), cta. cte., cta. ahorros.

### 3.5 "Certificados"  🟡
- Datos de familiar (nombres/dirección/teléfonos) y no familiar.
- Certificados: reentrenamiento, vacuna, cert. violencia intrafamiliar, etc.
- **Recuadros para imágenes de certificados escaneados** — en el `.pyw` son recuadros vacíos (nunca se implementó la carga real). Web: ❌ (deliberadamente pendiente).

### 3.6 "Referencias"  ✅
- Cédula militar, edad, nro cert. votación, licencia conducir, código IESS, carnet Conadis, visita domiciliaria.
- Estudios (primaria/secundaria/superior 1/0, título, años), universidad.
- Servicios: GIPASE, AFIS, tipo de servicio, contrato inspectoría, miembro Fuerza Pública, servicio militar.
- Maniobras, No. afiliación IESS.

### 3.7 Barra inferior del editor
Botones **Guardar** (`_guardar_cambios`, escritura multi-tabla + auditoría por tabla + concurrencia optimista) · **Cancelar**.
Web: ✅ ("Guardar" / editor en acordeón).

---

## 4. Diálogo "Búsqueda Avanzada" (`_abrir_buscador`)  ✅
Multi-criterio: código, apellidos, nombres, cédula, cargo, depto, estado, … → lista de resultados → seleccionar.
Web: `/empleados/avanzada`.

---

## 5. Carga Masiva (`CARGA_MASIVA_EMPLEADOS.pyw`, ~1185 líneas)  ✅
Descargar plantilla Excel → editar → subir → validar fila por fila → aplicar (Job) →
reporte de fallos parciales + auditoría por fila.
Web: `/empleados/carga-masiva` (rx.upload + Job).

---

## 6. Historial del Empleado (`historial_empleado_GUI.pyw`, ~1323 líneas)  ✅
Consulta de nómina histórica del empleado con rango de fechas + resumen.
Web: `/empleados/historial`.

---

## 7. Resumen de lo que falta en la web (orden sugerido)

1. **"Vista Completa"** — ventana/página read-only con los 68 campos de RPEMPLEA de un vistazo (hoy solo el PDF de ficha).
2. Buscador rápido con **campos separados** cédula / código / autocompletar (hoy un solo campo).
3. Combo **"Mostrar"** (Activos / Todos / Liquidados) en la lista.
4. Radios de **orden** de la lista.
5. Sub-caja **"Estudios"** en Datos Generales si el legado la tiene ahí.
6. (baja) Recuadros/carga de **imágenes de certificados** — nunca se implementó en el `.pyw`.
