# Módulo: faltas (Gestión de Faltas y Restas de Horas)

> **FASE -1 (decidido):** módulo **aparte** con rutas `/faltas/*`. El visor de
> solo lectura de faltas que vive en `observaciones` (pestaña "Faltas",
> `core/repos/observaciones.py`) **queda igual** — no se toca. Toda la escritura
> nueva va en `core/repos/faltas.py`.
> **Cambios de contrato:** C1 (RPHORTOT a superficie de escritura) y C2 (alta del
> módulo) — ver `docs/modulos/CAMBIOS_CONTRATO_SANCIONES.md`. Aprobados por el
> usuario 2026-09-09.

> Estado en el repo Reflex: **PARCIAL** — `core/repos/observaciones.py` tiene un
> visor de solo lectura de faltas (`RPHORTOT`/`RPHORHIS`). Toda la **escritura**
> (registrar falta/permiso/suspensión, restas de horas extra, levantamiento de
> suspensión, carga masiva) **no existe todavía**. Este es el módulo con más
> trabajo real pendiente.

## Qué hace (para el usuario)

RRHH registra en el sistema legado de nómina (SQL Server `insevig`):
- **Faltas** y **permisos** de un empleado en un período (mes/año), sumando
  horas al acumulado `TOTAUS` de `RPHORTOT`.
- **Suspensiones**: registran las horas de la suspensión y, opcionalmente,
  **descuentan horas extra** (`HOR25`/`HOR50`/`HOR100` de `RPEMPLEA`) según un
  porcentaje = `(días_suspensión / 30) * 100`.
- **Levantamiento de suspensión**.
- **Permiso médico**.
- **Carga masiva** de faltas/permisos pegando desde Excel.
- **Cargador de Restas de Horas**: carga `FALTAS_PARA_RESTA.xlsx`, cuenta faltas
  por cédula, convierte `HOR50 → HOR100` (factor 0.75) para quien tenga > 3
  faltas, previsualiza y actualiza `RPEMPLEA`.
- **Ver / editar período**: consulta `RPHORTOT` (período actual, editable) o
  `RPHORHIS` (meses cerrados, solo lectura).

## Origen (código legado a portar)

| Archivo legado | Qué se reutiliza | Qué se reescribe |
|---|---|---|
| `gestion_faltas.py` (raíz, ~3100 líneas) — copia de `cargador_faltas/gestion_faltas.py` | queries SQL Server, cálculos de horas/fechas/suspensión, parsing de pegado, generación de reportes Excel | toda la UI Tkinter (4 pestañas, grids, diálogos de confirmación), `filedialog`, `messagebox`, threading, el `Text`-logger |

## Lógica ya extraída (sin Tkinter)

| `nucleo_modular/…` | Contenido | Espejo Reflex |
|---|---|---|
| `repos/faltas.py` | Fachada del módulo (API pública unificada). | `core/repos/faltas.py` |
| `faltas_datos.py` | Acceso SQL Server: `conectar`, `buscar_empleado_bd`, `cargar_periodo_bd(anio, mes, tabla=…)`, `verificar_existe`, y escrituras con `ejecutar=False` → `(exito, error, auditoria)`: `insertar_falta`, `actualizar_falta`, `eliminar_falta`, `actualizar_totaus_observ`, `aplicar_descuento_horas_extra`, `aplicar_resta_horas`, `leer_excel_faltas`. | `core/repos/faltas.py` + `core/db/*` |
| `faltas_calculo.py` | `calcular_horas`, `calcular_suspension`, `calcular_porcentaje_descuento_suspension`, `calcular_descuento_horas_extra(clamp=…)`, `generar_observacion*`, `evaluar_alerta_faltas`, `calcular_resta_horas`, `contar_faltas_por_cedula`, `calcular_resultados_resta`, `parse_linea_pegado`, `mapear_pegado_a_campos`, `validar_fila_*`. | `core/faltas/` (dominio) |
| `faltas_reportes.py` | `guardar_respaldo`, `generar_excel_log_registro`, `generar_excel_periodo`, `workbook_a_bytes`. | `core/excel/faltas_*.py` |

## Rebanada (archivos que toca el agente en el repo Reflex)

- `core/repos/faltas.py`
- `core/faltas/` (cálculos), `core/excel/faltas_*.py`
- `insevig_web/states/faltas_state.py`
- `insevig_web/pages/faltas/*.py` (ver `faltas_UI.md` → 4 rutas)
- `insevig_web/components/faltas/*.py` (grid editable de pegado, si no hay uno reusable)
- `tests/unit/test_faltas_*.py`, `tests/integration/test_faltas_*.py`
- `docs/modulos/faltas.md`, `docs/modulos/faltas_UI.md`

## Contratos que consume (NO edita)

- `core.db.*` (conexión SQL Server), `core.audit` (auditoría de escrituras),
  `core.jobs` (carga masiva y restas como Job), `core.utils.normalizar_cedula`.
- `insevig_web.components.layout.pagina`, `components/ui/*`, `AuthState`,
  `DataSourceState`, `registry.ModuleSpec`.

## Rutas y permisos

| Ruta | Acción requerida |
|---|---|
| `/faltas/masivo` | `faltas.registrar` |
| `/faltas/individual` | `faltas.registrar` |
| `/faltas/periodo` | `faltas.ver` (editar requiere `faltas.editar`) |
| `/faltas/restas` | `faltas.restas` |

## Datos

- **Lectura**: SQL Server `RPHORTOT` (período actual), `RPHORHIS` (meses
  cerrados), `RPEMPLEA` (maestro + `HOR25/HOR50/HOR100`). Respeta el selector
  de fuente (el legado ya tiene un toggle propio RPHORTOT/RPHORHIS en la
  pestaña "Ver / Editar Período").
- **Escritura**: SOLO SQL Server, sobre `RPHORTOT` y `RPEMPLEA`. Con
  `AuditWriter` + vista previa (`ejecutar=False` ya devuelve la sentencia y los
  valores en el dict `auditoria`). **Nota de contrato**: `docs/CONTRATOS.md` del
  repo Reflex limita la superficie de escritura a `RPEMPLEA`, `RPEMPOBSERV`,
  `RPINGDES`. `RPHORTOT` **no está en esa lista** → registrar como cambio de
  contrato antes de portar la escritura de faltas.
- **Respaldo/auditoría**: el legado hace respaldo JSON en `respaldos/` antes de
  cada operación (`faltas_reportes.guardar_respaldo`). En la web = `core.audit`.

## Operaciones largas → `core.jobs`

- Carga masiva de faltas (pestaña "Registro Masivo", grid de hasta 100 filas).
- Cargador de restas de horas (recorre todo `RPEMPLEA` cruzando con el Excel).

## Diferencias / bugs del legado (documentados, NO corregidos — ver
`nucleo_modular/README.md` §15-21)

- **`SUSPENSION` (sin tilde) vs `SUSPENSIÓN` (con tilde)**: "✓ VALIDAR" y
  "✔ REGISTRAR TODO" aceptan tipos distintos.
- **Suspensión: desfase de 1 día** entre la vista previa de "Uno a Uno"
  (`.days`) y el registro real (`.days + 1`).
- **Descuento de horas extra sin clamping en el flujo batch**: "REGISTRAR TODO"
  puede dejar `HOR25/50/100` negativos; "Uno a Uno" sí acota con `min(...)`.
- **LEVANTAMIENTO SUSPENSIÓN** suma horas a `TOTAUS` igual que una falta —
  parece invertido (debería devolver/restar).
- Rama `SUSPENSION` de `generar_observacion()` es código muerto.

## Criterio de "hecho"

- [ ] Paridad con el legado para: 1 falta simple, 1 suspensión con descuento,
      1 carga masiva de 10 filas, 1 corrida del cargador de restas.
- [ ] Decisión explícita sobre cada bug de arriba (replicar o corregir con nota).
- [ ] `RPHORTOT` aprobado como superficie de escritura (cambio de contrato).
- [ ] `pytest tests/unit/test_faltas_*` verde; `ruff` + `mypy core` limpios.
- [ ] 4 páginas compilan (`test_arquitectura`).
- [ ] Revisado a 360 / 768 / 1280 px.
