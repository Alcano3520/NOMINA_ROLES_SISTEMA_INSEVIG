# Plan de implementación por módulo — paridad con el sistema Tkinter

Objetivo: cada módulo de la web debe tener **todas** las funciones del programa de
escritorio original, no un subconjunto. Este documento inventaría el legado
función por función, marca lo que ya está y lo que falta, y da los pasos en orden
con criterio de aceptación.

Orden de trabajo: **1) Gestión de empleados** → 2) Roles de pago → 3) Reportes →
4) Préstamos → 5) Observaciones → 6) Registrador → 7) Envío de correos →
8) Liquidaciones → 9) Bitácora → 10) Administración.

Reglas transversales (no repetir en cada módulo):
- Lectura: la app elige el origen sola (sin selector visible para RRHH).
- Escritura: solo a SQL Server, con vista previa + auditoría (`core/audit`).
- La interfaz no muestra nombres de tablas/columnas ni jerga de BD.
- Cada operación > 300 ms va a un Job con barra de progreso.
- Responsive: 360 / 768 / 1280 px.

Leyenda: ✅ hecho · 🟡 parcial · ⬜ pendiente

---

# 1. Gestión de empleados

Legado: `empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw` (3021 líneas),
`empleados/historial_empleado_GUI.pyw` (1323), `empleados/CARGA_MASIVA_EMPLEADOS.pyw`
(664), `empleados/agregar_observaciones_masivas.py`.

## 1.1 Pantalla principal (maestro-detalle)

| # | Función del legado | Estado | Nota |
|---|---|---|---|
| 1 | Pantalla única: lista a la izquierda + ficha a la derecha | ✅ | `/empleados/buscar` |
| 2 | Lista de empleados cargada al abrir (Treeview cód/apellidos/nombres) | ✅ | 200 filas |
| 3 | Filtro en vivo de la lista por código/cédula/apellido/nombre | 🟡 | hoy: botón "Buscar"; falta filtrado incremental |
| 4 | Combo **Mostrar: ACTIVOS / INACTIVOS / TODOS** | 🟡 | hoy: casilla "solo activos" (2 estados, faltan LIQ/SUS) |
| 5 | Navegación **◀◀ ◀ ▶ ▶▶** (primer/anterior/siguiente/último de la lista) | ⬜ | |
| 6 | Búsqueda directa **por cédula** (caja + Enter) | 🟡 | la caja general ya busca por cédula |
| 7 | Búsqueda directa **por código** (caja + Enter) | 🟡 | idem |
| 8 | **Autocompletar** (código/cédula/apellido/nombre → lista desplegable) | ⬜ | |
| 9 | Menú **Acciones**: Nuevo · Modificar · Eliminar · Vista Completa · Exportar Catálogos | 🟡 | Nuevo/Modificar/Eliminar ✅; Vista Completa ⬜; Exportar Catálogos ⬜ |
| 10 | **Barra inferior**: Guardar · Cancelar · Imprimir · "Empleado actual: … (cód. …)" · Salir | 🟡 | Guardar ✅, Cerrar ✅; Cancelar ⬜, Imprimir ⬜, etiqueta ⬜ |
| 11 | Barra de estado con mensajes ("MODO EDICIÓN ACTIVO", "DATOS MODIFICADOS…") | ✅ | badge bajo el encabezado (`estado_barra` + `edit_dirty`) |
| 12 | Aviso al salir con cambios sin guardar | ⬜ | (menos crítico en web) |

## 1.2 Ficha del empleado — las 6 pestañas

El legado usa un **Notebook de 6 pestañas**. La web hoy usa un acordeón de 5 grupos.
**Decisión: pasar a pestañas (`rx.tabs`) para que se parezca al original**, y añadir
la pestaña Observaciones como una más.

| Pestaña legado | Campos | Estado |
|---|---|---|
| **Datos Generales** | código, cédula, cód.suc, cód.emp, nombres, apellidos, sexo (combo), estado civil (combo), lugar/fecha nac., dirección, provincia, cantón, parroquia, nacionalidad, fecha ingreso/salida, **depto/cargo/sección** (selector con catálogo + búsqueda en vivo), estado (combo), 2 teléfonos, email, tipo de empleado (combo), actividad, cónyuge, **panel de auditoría** (creado/modificado por/fecha) | 🟡 campos ✅ · pestaña ⬜ · panel auditoría 🟡 (una línea) · selector de catálogo con búsqueda ⬜ (hoy `<select>` plano) |
| **Ingresos / Dctos.** | sueldo, bonificación, compensación, transporte, horas 25/50/100; acumulados décimo 3/4, vacaciones, fdo. reserva; rol extra: moviliza, lunch, anticipo %, descuento, ing/dct extra, concepto; **casilla Fondo de Reserva** (escribe NUM_AFIL 0/9999999999, con protección si ya hay número real); flags "Décimo 13 aparte", "Décimo 14 aparte", "Aporta IESS cónyuge" | 🟡 campos ✅ · casilla Fondo de Reserva (NUM_AFIL 0/9999999999 + bloqueo si hay número real) ✅ · pestaña ⬜ |
| **Observaciones** | selector mes+año, botón Mostrar, 7 recuadros refer1..7 (llenos y vacíos), Guardar Obs., Imprimir Historial (HTML de TODAS las fechas) | 🟡 mostrar+editar+guardar ✅ · imprimir historial 🟡 (se lista, no HTML) · dentro del editor ✅ pero no como pestaña |
| **Otros Datos** | casillas "Incluir en el Rol" / "Acreditar" (S/N); cargas, últ. liquidación, últ. día trab., días trab., grupo sanguíneo (combo), período de pago (combo); cuentas contables (cta, cta depto, cta auxiliar); info bancaria (banco combo, cta cte, cta ahorros) | 🟡 campos ✅ · pestaña ⬜ |
| **Certificados** | 4 recuadros de archivo (cédula, votación, record policial, libreta militar) — **hoy solo dibujan recuadro vacío en el legado**; familiares (nombres/dirección/teléfonos); no familiares (idem) | 🟡 campos de familiares ✅ · recuadros de archivo ⬜ (adjuntar imágenes = mejora sobre el legado) |
| **Referencias** | cédula militar, edad, tipo sangre, nro cert. votación, licencia, código IESS, carnet Conadis, visita domiciliaria; estudios (primaria/secundaria/universidad checkboxes + título + años); servicios (tipo, contrato inspectoría, GIPASE, AFIS, certificados, reentrenamiento, vacuna); checkboxes Fuerza Pública / Servicio Militar; cert. violencia intrafamiliar, maniobras, **No. afiliación IESS** | 🟡 campos ✅ · pestaña ⬜ |

## 1.3 CRUD

| # | Función | Estado | Nota |
|---|---|---|---|
| 13 | **Nuevo**: limpia el formulario, modo edición, valida código/cédula únicos antes de INSERT | 🟡 valida obligatorios ✅ · chequeo de duplicado (código y cédula) ⬜ |
| 14 | **Modificar**: confirma → activa modo edición (campos editables) | ✅ botón "Modificar" |
| 15 | **Guardar**: confirmación con resumen (nombre/código/cédula), UPDATE/INSERT de RPEMPLEA, recarga lista | 🟡 guarda ✅ · diálogo de confirmación con resumen ⬜ |
| 16 | **Cancelar**: descarta cambios, vuelve a modo vista, repuebla desde datos originales | ⬜ (hoy "Cerrar" cierra la ficha) |
| 17 | **Eliminar**: triple confirmación (2× sí/no + reescribir el código) → DELETE | 🟡 pide reescribir el código ✅ · faltan los 2 diálogos previos con el detalle |
| 18 | Concurrencia optimista (token; si otro usuario modificó, rechaza) | ✅ `ConflictoConcurrencia` |
| 19 | Auditoría de cada escritura (antes/después) | ✅ `audit_scope` |
| 20 | Codificación por columna (S/N, '1'/'0', 1/0, combos, catálogos) | ✅ |
| 21 | Cédula sin ".0", fechas sin hora al mostrar | ✅ |

## 1.4 Diálogos y utilidades

| # | Función | Estado |
|---|---|---|
| 22 | **Búsqueda Avanzada** (diálogo): apellidos, nombres, cédula, estado, departamento, cargo → tabla con 12 columnas (incl. nombre de cargo/depto, sueldo, teléfono, email); Mostrar todos; Limpiar; **Exportar Excel**; doble-clic carga en la ficha | ⬜ |
| 23 | **Vista Completa** (diálogo): tabla de todos los empleados con muchas columnas + exportar | ⬜ |
| 24 | **Exportar Catálogos** (diálogo): vuelca DBTABLAS (cargos/secciones/deptos/…) a Excel | ⬜ |
| 25 | **Imprimir empleado** (ficha a papel/PDF) | ✅ `core/pdf/ficha_empleado.py` |
| 25b | **Foto del empleado** (subir / mostrar / quitar / **tomar foto con la cámara**) — ref. ManagementPro | ✅ `core/repos/fotos.py` (STORAGE_DIR/fotos/) + botón "Tomar foto" (getUserMedia→canvas→`guardar_foto_datauri`) |
| 25c | **Documentos**: hoja de vida, certificado de trabajo, contrato, carta de renuncia (PDF con los datos de la ficha) | ✅ `core/pdf/documentos_empleado.py`. Falta: plantillas editables desde Administración, huellas dactilares |
| 26 | **Historial de nómina del empleado** (`historial_empleado_GUI.pyw`): períodos recientes, detalle por concepto (ingreso/egreso), filtro, exportar Excel, ventana de detalle por fila | 🟡 `/empleados/historial` muestra consolidado de UN período · faltan: varios períodos a la vez, detalle por fila, exportar |

## 1.5 Carga masiva (`CARGA_MASIVA_EMPLEADOS.pyw`)

| # | Función | Estado |
|---|---|---|
| 27 | **Edición masiva**: descargar plantilla Excel (columnas seleccionables) → editar fuera → subir → validar (muestra qué cambia) → aplicar fila por fila con auditoría | 🟡 subir+aplicar+reporte ✅ · descargar plantilla con columnas a elegir ⬜ · paso de validación/preview ⬜ |
| 28 | **Observaciones masivas**: plantilla (cédula, mes, texto) → validar → aplicar (primer campo refer libre, o fila nueva) | ⬜ (`agregar_observaciones_masivas.py`, `core.repos.observaciones.guardar_observacion` ya existe) |
| 29 | Reporte de resultados descargable (OK / errores por fila) | ✅ |

## 1.6 Pasos en orden (Gestión de empleados)

1. **Pestañas en vez de acordeón** en la ficha (`rx.tabs` con las 6: Datos Generales,
   Ingresos/Dctos, Observaciones, Otros Datos, Certificados, Referencias). *(items 1.2)*
2. **Selector de catálogo con búsqueda** para Depto/Cargo/Sección (escribir filtra la
   lista) — hoy es un `<select>` con cientos de opciones. *(item 1.2 Datos Generales)*
3. **Barra inferior**: Guardar · Cancelar · Imprimir · etiqueta "Empleado actual" ·
   mensajes de estado ("modo edición", "datos modificados"). *(items 10, 11, 16)*
4. **Cancelar**: repuebla la ficha desde los datos originales sin recargar. *(item 16)*
5. **Diálogos de confirmación** con resumen en Guardar y triple en Eliminar. *(15, 17)*
6. **Nuevo**: validar código y cédula duplicados antes de crear. *(item 13)*
7. ~~**Casilla "Fondo de Reserva"** en Ingresos/Dctos con su lógica NUM_AFIL.~~ ✅ *(1.2)*
8. Combo **ACTIVOS/INACTIVOS/TODOS** + **navegación ◀◀ ◀ ▶ ▶▶** + **filtrado en vivo**
   de la lista + **autocompletar**. *(items 3, 4, 5, 8)*
9. **Búsqueda Avanzada** (diálogo/pantalla con 6 criterios + tabla ancha + exportar). *(22)*
10. **Vista Completa** (tabla de todos + exportar). *(23)*
11. **Exportar Catálogos** a Excel. *(24)*
12. **Imprimir ficha** del empleado a PDF. *(25)*
13. **Historial de nómina**: varios períodos, detalle por fila, exportar. *(26)*
14. **Carga masiva**: plantilla con columnas a elegir + paso de validación/preview. *(27)*
15. **Observaciones masivas** desde Excel. *(28)*
16. Adjuntar imágenes de certificados (mejora sobre el legado). *(1.2 Certificados)*

Criterio de aceptación del módulo: para 8–10 empleados reales, cada dato de las 6
pestañas coincide con lo que muestra el `.pyw`; alta/edición/baja viajan a SQL Server
con auditoría; búsqueda avanzada y vista completa exportan el mismo Excel que el legado.

---

# 2. Roles de pago

Legado: `roles/Roles_Principal.pyw` (1920), `Roles_generador_VIZUALIZADOR_10.pyw` (69K),
`Roles_VISUALIZADOR*.pyw`, `envio_roles/*` (ver módulo 7).

| # | Función | Estado |
|---|---|---|
| 1 | Generar rol individual (PDF) para un período | ✅ |
| 2 | Dibujo del rol fiel a `dibujar_rol_en_posicion` (encabezado, tabla, fondo de reserva calculado, firma) | ✅ |
| 3 | **Previsualización** embebida antes de descargar | ✅ |
| 4 | **2 roles por hoja** | ✅ |
| 5 | **Toggle logo** (gris) | ✅ |
| 6 | Generación por **lote** → ZIP en storage, con progreso y cancelación | ✅ |
| 7 | **6 formatos de nombre de archivo** (cedula-nombre, nombre-cedula, …) | ✅ `core/pdf/layout.FORMATOS` |
| 8 | **Visualizador**: buscar empleado, ver su rol en pantalla, navegar entre empleados del período | ⬜ |
| 9 | Selección de empleados del lote desde una lista (no solo pegar cédulas) | 🟡 hoy: pegar identificaciones |
| 10 | Recalcular sobretiempos del mes en curso proporcionales (el legado lo hace desde DBTABLAS SEC) | ⬜ (hoy usa el valor de RPEMPLEA) |
| 11 | Test de regresión "golden" (texto + posiciones) contra PDFs reales | ⬜ |

Pasos: 8 → 9 → 10 → 11.

---

# 3. Reportes

Legado: `reportes/reporte_nomina_GUI.pyw` (648) + `_SQL_SERVER` / `_SUPABASE` / `_COMPARADOR`.

| # | Función | Estado |
|---|---|---|
| 1 | Consolidado de nómina (una fila por empleado, columnas por concepto) — período actual | ✅ |
| 2 | Consolidado **histórico** (RPHISTOR ~2.5M) como Job con progreso | ✅ |
| 3 | Excel con hoja **"Por departamento"** (subtotales) | ✅ |
| 4 | Resumen de totales en pantalla al terminar | ✅ (mensaje del job) |
| 5 | **Comparador** de los dos orígenes (diferencias) — movido a Administración | ✅ |
| 6 | Elegir carpeta de salida | ✅ eliminado por diseño (descarga directa) |
| 7 | **Reporte por empleado** individual (detalle) | 🟡 cubierto por `/empleados/historial` |
| 8 | Reporte por rango de fechas arbitrario (no solo un mes) | ⬜ |
| 9 | Reporte "anexo banco" (solo INCL_BAN='S') — si RRHH lo usa | ⬜ a confirmar con el usuario |

Pasos: confirmar con el usuario si faltan variantes (anexo banco, rango de fechas); si no, el módulo está a paridad.

---

# 4. Préstamos

Legado: `prestamos/HISTORIAL_PRESTAMOS_10.pyw` (3158).

| # | Función | Estado |
|---|---|---|
| 1 | Historial de préstamos de un empleado (vivo + histórico + migrado del SQLite) | ✅ |
| 2 | Saldo por empleado + exportación de todos los saldos a Excel | ✅ |
| 3 | **Resumen agrupado por N° de préstamo** (prestado/abonado/saldo/cuotas) | ✅ |
| 4 | **Filtro por rango de fechas** | ✅ |
| 5 | **Exportar Excel por empleado** (Historial + Resumen) | ✅ |
| 6 | **Narrativa IA** del comportamiento de pago (Job) | ✅ |
| 7 | **Lectura en voz alta** de la narrativa (navegador) | ✅ |
| 8 | **Detalle por préstamo** (ver movimientos individuales) | ✅ botón "Ver" |
| 9 | Brechas entre cuotas, cuota promedio, estimación meses para cancelar | ✅ en `agrupar_por_numero` |
| 10 | Excel por-empleado con estilo (banner, hojas Historial/Resumen con formato) | ✅ banner INSEVIG, anchos de columna, bordes, fila TOTAL |
| 11 | Config del proveedor IA desde la UI (hoy: `.env`) | ✅ `/admin/parametros` (proveedor/URL/modelo; API key sigue en `.env`) |

Pasos: 10 (formato del Excel por-empleado).

---

# 5. Observaciones / Multas / Faltas

Legado: `observaciones/TOTAL_OSERVACIONES_4_0.pyw` (1823).

| # | Función | Estado |
|---|---|---|
| 1 | Buscar empleado y ver Observaciones / Multas / Faltas en pestañas | ✅ |
| 2 | Faltas del período actual (RPHORTOT) + histórico (RPHORHIS) | ✅ |
| 3 | **Añadir observación** (primer campo refer libre, auditoría) | ✅ |
| 4 | Edición inline de los 7 campos de un mes (en la ficha del empleado) | ✅ |
| 5 | **Reporte HTML imprimible** | ✅ |
| 6 | **Panel de datos del empleado** arriba | ✅ `datos_basicos_empleado` |
| 7 | **Ventana de detalle** de una observación (los 7 campos separados, copiar) | ✅ diálogo "Ver detalle" con botón Copiar por campo (`slots7`) |
| 8 | "Mostrar todos" — lista de empleados que tienen observaciones | ✅ `empleados_con_observaciones` (código/nombre/meses/última) |
| 9 | Reporte HTML de **varios empleados** a la vez (`guardar_texto`) | ✅ `reporte_html_varios` (selección o todos) |

Módulo a paridad.

---

# 6. Registrar egresos/ingresos (Registrador)

Legado: `registrdor_vizulizador_egresosingresos/REGISTRAR_PRESTAMOS_UNIFICADO.pyw` (5436).
**Acotado por decisión del usuario** a lo mínimo utilizable.

| # | Función | Estado |
|---|---|---|
| 1 | Importar Excel del BIESS (autodetección de columnas cédula/valor) | ✅ |
| 2 | Emparejar con empleados (activo/liquidado/no encontrado) | ✅ |
| 3 | Vista previa antes de registrar | ✅ |
| 4 | Postear a RPINGDES (CLASE 204) con auditoría + dedupe | ✅ |
| 5 | Alta manual de un ingreso/egreso (cualquier CLASE) | ✅ `registrar_movimiento` |
| 6 | Préstamo individual con planificación de cuotas (nº o valor) | ✅ `cuotas_tradicional` / `cuotas_por_valor` / `proyeccion_pagos_futuros` |
| 7 | Carga masiva de préstamos | ✅ (Job + CSV) |
| 8 | Consulta / edición: lista, ver cuotas, borrar, editar cuota | ✅ `historial_movimientos` / `cuotas_prestamo` / `eliminar_movimiento` / `editar_cuota` |
| 9 | "Mover cuotas pendientes desde una fecha" | ✅ `mover_cuotas_pendientes` + botón en Consulta/edición |
| 10 | Respaldo por operación | ⬜ (`modulo_seguridad_prestamos` del legado no existía; cubierto por `core.audit`) |

**Módulo portado por completo** (6 pestañas).

---

# 7. Envío de roles por correo

Legado: `envio_roles/ENVIO_ROLES_7_NUEVO.pyw` (801) + variantes.

| # | Función | Estado |
|---|---|---|
| 1 | Extraer destinatarios de un Excel | ✅ |
| 2 | Emparejar PDF de rol por cédula | ✅ |
| 3 | Sustituir marcadores en la plantilla HTML ({{StrNombres}} legado + Jinja) | ✅ |
| 4 | Envío por SMTP **o** Microsoft Graph (sin Outlook COM) | ✅ |
| 5 | Job reanudable, con intervalo, stop/continuar, idempotente (no doble envío) | ✅ |
| 6 | Editor de la plantilla HTML desde la UI | ✅ asunto + cuerpo, guardado en `AppConfig` (`core.parametros.get/set_email_plantilla`) |
| 7 | Vista previa del correo de un destinatario | ✅ botón "Previsualizar" (render con datos de ejemplo o del 1er destinatario) |
| 8 | Log de envíos en pantalla | ✅ botón "Ver log de envíos" |

Módulo a paridad.

---

# 8. Liquidaciones (finiquitos)

Legado: `LIQUIDACIONES_SISTEMA_INSEVIG/Liquidaciones_generador_CON_VACACIONES.pyw`.

| # | Función | Estado |
|---|---|---|
| 1 | Entrada: cédula, dd/mm/aaaa, motivo (una línea por empleado) | ✅ |
| 2 | Cálculo legal completo (vacaciones, décimo 13/14 COSTA/SIERRA, desahucio, indemnización, IESS, fondo reserva, DIAS360, split anticipos, descuentos multi-mes) | ✅ |
| 3 | Excel hoja FORMATO (~62 columnas) | ✅ |
| 4 | Selección de región | ✅ |
| 5 | Configuración de SBU por año editable (hoy: valores por defecto) | ✅ `/admin/parametros` (`config_liquidacion` mezcla los SBU guardados) |
| 6 | Columnas mensuales dinámicas de remuneración (col 62+) del Excel | ⬜ |
| 7 | Fecha de ingreso override cuando FECHA_ING > FECHA_SAL | ✅ 4º dato de la línea |
| 8 | **Validar montos contra el `.pyw` con empleados reales** | ⬜ **bloqueante para producción** |

Pasos: 8 (validación) → 5 → 6 → 7.

---

# 9. Bitácora / Agenda de liquidaciones

Legado: `BITACORAS_AGENDA_EGRESOS_FORMATOS/Agenda_Liquidacion_Haberes.pyw` (3 pestañas).

| # | Función | Estado |
|---|---|---|
| 1 | Pestaña **Agenda**: alta/edición/consulta, filtros estado + período + texto | ✅ |
| 2 | Estados EXACTOS del legado (`PENDIENTE/AGENDADO/PAGADO/CANCELADO`) + cambio rápido | ✅ (antes tenía estados inventados) |
| 3 | Trazabilidad de cambios (`agenda_cobro_historial`, FK `registro_id`) + detalle "campo: antes → después" | ✅ (antes escribía `agenda_id`, columna inexistente) |
| 4 | Eliminar (con entrada de historial) | ✅ |
| 5 | "Texto para el sistema" (`texto_en_sistema`, formato RPEMPOBSERV) + botón Generar | ✅ |
| 6 | Validación del dígito verificador de la cédula (aviso) | ✅ `core.utils.cedula_valida` |
| 7 | Pestaña **Atención Personal** (append-only, motivos, borrar solo admin) | ✅ |
| 8 | Pestaña **Reportes**: resumen (registros/hrs susp./QAP) + Excel con formato + trazabilidad | ✅ |
| 9 | Paginación `.range()` para pasar el corte de 1000 filas de PostgREST | ✅ `_todas_las_filas` |
| 10 | Cálculo de horas extra por cupo de sección | ⬜ (el `.pyw` lo marca "pendiente de subir a SQL Server") |
| 11 | Botón "Registrar" → UPDATE a RPEMPLEA (FECHA_SAL/ESTADO/HOR*) | ⬜ (escritura a nómina; iría por `core/repos/empleados`) |
| 12 | "Formato de Renuncia" / PDF individual del registro | ⬜ |
| 13 | `EGRESOS/` (Google Apps Script de comprobantes de egreso) | ⬜ pieza separada, no es Python |

---

# 10. Administración

| # | Función | Estado |
|---|---|---|
| 1 | Usuarios: alta, roles, activar/desactivar | ✅ (`/admin/usuarios`) |
| 2 | Matriz de permisos por rol/módulo/acción editable | ✅ (`/admin/roles`) |
| 3 | Auditoría con filtros por usuario y módulo | ✅ |
| 4 | Configuración: ver credenciales enmascaradas, healthcheck de orígenes | ✅ |
| 5 | Verificación de datos (ex-comparador) | ✅ |
| 6 | Editar parámetros: SBU por año ✅ · plantilla de correo ✅ (en Envío) · proveedor IA ✅ (`/admin/parametros`, la API key sigue en `.env`) | ✅ |
| 7 | Cambiar la propia contraseña / que un admin resetee la de otro | ✅ `/mi-cuenta` (autoservicio) + "Resetear clave" en `/admin/usuarios` |

Pasos: proveedor IA (parte de 6).

---

## Seguimiento

Al cerrar cada paso: marcar ✅ aquí, actualizar `docs/modulos/<mod>.md`, y añadir
test. El módulo se da por terminado cuando su tabla no tiene 🟡 ni ⬜ (salvo mejoras
explícitamente pospuestas).
