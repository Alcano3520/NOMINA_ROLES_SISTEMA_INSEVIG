# Módulo: liquidaciones — Generador de finiquitos (módulo 9)

Origen: `~/Documentos/mis_proyecto/LIQUIDACIONES_SISTEMA_INSEVIG/`.

**Fuente de verdad actual: `nucleo_modular/`** (paquete UI-agnóstico ya extraído
y probado -- 16 módulos, 18 tests -- del `.pyw` que la empresa usa hoy en
producción: `Generador_Liquidaciones_INSEVIG.pyw`). La primera versión de este
`core/repos/liquidaciones.py` había portado en cambio
`Liquidaciones_generador_CON_VACACIONES.pyw` (versión vieja/deprecada, sin los
meses de correcciones reales de producción) -- se reemplazó por completo (ver
"Correcciones incorporadas" abajo).

## Qué hace
Dada una lista de `cédula, dd/mm/aaaa (fecha salida), motivo`, calcula la
liquidación legal de cada empleado y produce un Excel (hoja `FORMATO`).

## Cálculos portados (fórmulas exactas del legado, ya corregidas en producción)
| Concepto | Fórmula |
|---|---|
| Movimientos del mes de salida | RPINGDES → fallback RPHISTOR; mapeo CLASE→concepto (`core.concepts`); `EGR` sin mapeo → ANTICIPOS_SURTIDOS |
| Descuentos multi-mes | se suman hasta 36 meses después (o 3 seguidos sin datos) los conceptos de `DESCUENTOS_MULTI_MES` |
| Sobretiempos | si hay $ real en movimientos: horas = redondear($/valor_hora), $ se RECALCULA desde esas horas enteras (no se deja el redondeo de nómina). Si no hay $ real: cupo de RPEMPLEA (HOR25/50/100) × `(sueldo/240) × factor` (25%: 0.25, 50%: 1.5, 100%: 2.0) |
| Vacaciones | **TODOS** los periodos pendientes (no caducan en Ecuador), anclados en el DÍA EXACTO de ingreso (no el día 1 del mes); se descartan los que `vac_registros` (Supabase) marca como ya pagados/gozados (≥15 días) o se prorratean si el goce fue parcial; `calc = suma_total_pendiente / 24` |
| Décima 13ra | periodo 01/12 → 30/11 (últimos 2, recortados a [ingreso, salida] por reingreso); `total_periodo / 12`; anterior + actual |
| Décima 14ta | últimos 2 periodos (anclados en la fecha de salida, NO desde el ingreso); `(DIAS360(inicio_efectivo, fin_efectivo) + 1) × (SBU_año / 360)`; COSTA 01/03→28/02, SIERRA 01/08→31/07; "pagado" = el periodo ya terminó antes de la salida (no la fecha legal de pago 15/03 o 15/08) |
| Desahucio | `(sueldo/4) × años_completos` si > 360 días y contrato indefinido; años = `relativedelta + 0.00278` truncado |
| Indem. despido | motivo con "DESPIDO"/"INTEMPESTIVO": `3×sueldo` (<3 años) o `años×sueldo` (máx 25) |
| Fondo de reserva | `8.33% × base del mes de salida` |
| IESS | `9.45% × (SUELDO + SOBRETIEMPOS)` |
| Split anticipos (días < 90) | `ANTICIPOS_OTROS_L = int((vac+13act+14act+desahucio)/3.75)`; `ANTICIPO_L_DESAHUCIO = int(desahucio/3.75)` |
| Total a recibir | ingresos (sueldo, extras, FR, vac_calc, 13ant+13act, 14ant+14act, desahucio, indem) − descuentos |

Constantes en `core/repos/liquidaciones.py`: `DESCUENTOS_MULTI_MES`, `SBU_DEFECTO`
(2020-2027) (el mapeo CLASE→concepto ahora viene de `core.concepts`, compartido
con roles/reportes -- ya no se duplica aquí). `ConfigLiquidacion(region, iess_pct,
sbu_por_anio)`.

## Correcciones incorporadas al reemplazar la extracción inicial
Todas ya estaban confirmadas contra casos reales en el `.pyw` de producción
(documentadas en `nucleo_modular/README.md` y en los docstrings de cada
función) -- ninguna es una mejora inventada en esta migración:

1. **Vacaciones ancladas en el día 1 del mes → día exacto de ingreso.** Alguien
   que ingresó el 15/03 tenía su periodo mal calculado como 01/03→28/02 en vez
   de 15/03→14/03 -- ~2 semanas de diferencia que corre qué meses de sueldo
   entran en cada periodo, y puede no coincidir con la etiqueta ya registrada
   en `vac_registros`.
2. **Vacaciones: solo últimos 2 periodos → TODOS los pendientes.** Las
   vacaciones no caducan en Ecuador; alguien con 3+ periodos sin pagar antes
   perdía el 3er periodo (y más antiguos) sin calcularlos ni pagarlos.
3. **Verificación contra `vac_registros` (Supabase) añadida por completo** --
   antes no existía en este archivo: sin esto, la liquidación puede volver a
   pagar en efectivo un periodo ya pagado o ya gozado como descanso (doble
   pago real, caso confirmado en producción). Si Supabase no responde, se
   degrada de forma segura (no descarta ningún periodo a ciegas, solo el más
   reciente se autocalcula; el resto queda alertado para revisión manual).
4. **Décima Cuarta: recorría TODOS los años desde el ingreso → solo los
   últimos 2, anclados en la fecha de salida.** Para alguien con 14 años de
   antigüedad esto inflaba el valor absurdamente (caso real: ~$5895 en vez de
   los ~$220 realmente pendientes) sumando periodos ya pagados año a año.
5. **Décima Cuarta: "pagado" comparaba contra la fecha legal de pago (15/03 o
   15/08) → ahora compara contra si el periodo ya terminó antes de la
   salida.** Confirmado contra actas de finiquito reales: la empresa liquida
   el periodo anterior en nómina regular antes de esa fecha legal, no en ella.
6. **Décima Tercera/Cuarta: sin recorte por reingreso → recortadas a
   [fecha_ingreso, fecha_salida].** Un reingreso a mitad de periodo sumaba
   sueldo de un ingreso anterior ya liquidado por separado.
7. **Décimo ANTERIOR (13ro y 14to): antes nunca se podía sumar al total →
   ahora es opcional vía `incluir_dec13_anterior`/`incluir_dec14_anterior`.**
   La extracción inicial calculaba `DECIMA_TERCERA_ANTERIOR`/
   `DECIMA_CUARTA_ANTERIOR` pero no existía forma de incluirlos en
   `total_ingresos`. **Corrección sobre esta misma corrección (2026-09-06)**:
   al agregar el parámetro se le puso default `True`, asumiendo que la
   omisión total anterior era el bug a corregir. Verificado después contra
   `Generador_Liquidaciones_INSEVIG.pyw` línea por línea
   (`_parsear_entrada_cedulas`, `_procesar_empleado`): el comportamiento real
   en las DOS pantallas que existen hoy es excluirlo por defecto -- en modo
   LOTE el campo está hardcodeado en `False` sin forma de activarlo ("pedido
   explícito del usuario: incluir el décimo anterior es una decisión
   puntual, caso por caso... nunca en un proceso masivo"), y en modo
   individual la casilla nace desmarcada. El default `True` de la función
   `_procesar_empleado` del `.pyw` nunca se ejercita en la práctica porque
   los dos únicos llamadores siempre pasan un valor explícito. Con el
   default `True` que este archivo tuvo temporalmente, `procesar_lote()`
   (que no pasa el argumento) estuvo incluyendo de más el décimo anterior en
   cada liquidación de lote generada por el sistema web -- **esto sí era un
   bug real que sobrepagaba**, ya corregido: el default es ahora `False` en
   ambos parámetros, coincidiendo con el `.pyw` real.
8. **Horas de sobretiempo (HORAS_25/50/100) desconectadas del $ real →
   reconstruidas desde el $ cuando existe.** Antes, si ya había un valor $ de
   sobretiempo real en los movimientos, las "horas" mostradas seguían viniendo
   del cupo asignado en RPEMPLEA (sin relación con ese $), pudiendo no
   coincidir entre sí. Ahora, cuando hay $ real, las horas se derivan de él
   (redondeando) y el $ final se recalcula desde esas horas enteras.

## Rebanada
- `core/repos/liquidaciones.py` (cálculo completo)
- `core/excel/liquidaciones_builders.py` (Excel hoja FORMATO, ~62 columnas; los
  campos administrativos manuales van en blanco)
- `core/pdf/liquidacion_individual.py` — PDF de 1 hoja (ReportLab), porta
  `generacion_pdf.py` de `nucleo_modular` verbatim; `_a_fila` adapta
  `Liquidacion` al dict que espera esa función.
- Persistencia en Supabase (`core/repos/liquidaciones.py`): `guardar_liquidacion`,
  `buscar_liquidacion_existente`, `listar_liquidaciones`, `obtener_liquidacion`,
  `cambiar_estado_liquidacion`, `eliminar_liquidacion`, `reconstruir_liquidacion`
  (para regenerar el PDF de un registro ya guardado sin recalcular contra SQL
  Server) — porta `acceso_supabase.py`/`mapeo_liquidacion.py` de `nucleo_modular`,
  adaptado a leer directamente del dataclass `Liquidacion` en vez del dict `fila`
  del legado. Tablas: `liquidaciones`, `liquidaciones_detalle`,
  `liquidaciones_historial_estados`, `liquidaciones_eliminadas_historial`.
- `insevig_web/states/liquidaciones_state.py`, `insevig_web/pages/liquidaciones/index.py`
  — "Generar PDF" y "Guardar" por fila del lote previsualizado.
- `insevig_web/states/liquidaciones_guardadas_state.py`,
  `insevig_web/pages/liquidaciones/guardadas.py` (`/liquidaciones/guardadas`) —
  Editor + Gestión combinados en una pantalla: buscar (texto/estado), ver
  detalle (conceptos), cambiar estado, regenerar PDF, eliminar (solo admin,
  con respaldo en `liquidaciones_eliminadas_historial`).
- `tests/unit/test_liquidaciones.py`

## Datos
Solo lectura de nómina. Por defecto **Supabase** (las tablas históricas grandes —
`rphistor_temp` 903K filas — están ahí). También funciona contra SQL Server.

## Pantalla principal (`/liquidaciones`) — reconstruida a fondo (2026-09-04)
Tras revisar `_crear_interfaz`/`_crear_panel_preview` del `.pyw` (líneas ~1124-2000),
se detectó que la pantalla principal solo tenía el modo Masivo (textarea + Excel) y
le faltaba casi toda la estructura real. Añadido, en la misma pantalla:
- **"RESUMEN DE LIQUIDACIONES GUARDADAS"**: 4 tarjetas por estado
  (`core.repos.liquidaciones.resumen_liquidaciones`), igual que
  `_actualizar_resumen_liquidaciones` del legado.
- **"1. Formato de Salida"**: selector Masivo (Excel, por plantilla) ⇄ Individual
  (PDF de simulación, 1 empleado) — cambia toda la sección 2 debajo.
- **"2. Datos de Empleados"** en modo Individual: combo "Buscar por"
  (Cédula/Código/Nombre, `core.repos.liquidaciones.buscar_empleado_preview`),
  panel de solo lectura con los datos del empleado encontrado, fecha de salida,
  motivo (campo libre + combo de `MOTIVOS_SALIDA`), y 3 de las 6 casillas del
  legado ya conectadas al motor de cálculo: incluir Décima 13/14 ANTERIOR en la
  vista previa (`incluir_dec13_anterior`/`incluir_dec14_anterior` de
  `procesar_empleado` — además, paridad exacta con el legado: si la casilla
  está desmarcada, la fila del décimo anterior NI SIQUIERA se muestra en la
  tabla de vista previa, no solo se excluye del total) y "mostrar insumos del
  cálculo" (`liquidacion_pdf(..., mostrar_insumos=...)`).
- **"👁 VISTA PREVIA"**: tabla concepto/tipo/valor + totales, calculada en vivo
  con `procesar_empleado` + `previsualizar_conceptos` (sin guardar nada) al
  presionar "Calcular / Generar Liquidación"; botones "PDF" y "💾 Guardar
  Liquidación" ya conectados (mismo `guardar_liquidacion`/`liquidacion_pdf`
  que el modo Masivo).
- Modo Masivo: sin cambios funcionales, solo reordenado bajo el nuevo selector.

**Casillas del modo Individual** (2026-09-06): 5 de 6 conectadas.
- `incluir_dec13_anterior` / `incluir_dec14_anterior` — ✅ (ocultan la fila si
  se desmarcan, paridad exacta con el legado).
- `mostrar_insumos` — ✅.
- `incluir_sueldo` (default `True`, "incluir/excluir el sueldo del mes de
  salida") — ✅ cableada.
- `usar_ingresos_reales_desahucio` (default `False`, "desahucio sobre
  ingresos reales") — ✅ cableada.
- `usar_valores_reales_mes_actual` ("usar valores YA cargados en RPINGDES
  para el mes en curso"): ⛔ el motor **todavía no tiene** la alternativa que
  este flag debería togglear -- el cálculo de sobretiempos del mes en curso
  vía cupo de sección (DBTABLAS SEC) simplemente no está portado (ver más
  abajo), así que exponer el parámetro ahora sería un no-op. Portar esa
  fórmula primero.

"3. Periodo para Calcular Horas", "4. Valores por Defecto" (multas/
anticipos si el rubro es 0) y "5. Carpeta de Salida" (N/A en web, se
descarga directo) del legado no se portaron — evaluar si siguen siendo
necesarios ya que el modo Individual no depende de un periodo de corte fijo.

## Pendiente / a validar contra el legado
- Sobretiempos del **mes en curso** (todavía sin cerrar, RPINGDES stale): el
  `.pyw` de producción recalcula desde el cupo mensual de la sección
  (DBTABLAS SEC), prorrateado por días trabajados; aquí se sigue usando el
  cupo fijo de RPEMPLEA (HOR25/50/100) tal cual, sin ese prorrateo por días
  del mes en curso. Diferencia solo relevante para simulaciones a mitad del
  mes en curso, no para meses ya cerrados.
- `DETALLE_MOVIMIENTOS` (desglose por movimiento -- fecha, código, número,
  observación -- de cada concepto): existe en `nucleo_modular` para que un
  futuro Editor pueda mostrar "de dónde salió" cada valor; no se portó aquí
  porque esta página no tiene un Editor que lo muestre todavía.
- Columnas mensuales dinámicas de remuneración (col 62+) del Excel: no incluidas aún.
- El diálogo "pedir fecha de ingreso" cuando FECHA_ING > FECHA_SAL: aquí
  devuelve error (se puede resolver pasando la fecha correcta como 4º dato de
  la línea); el `.pyw` original la pide con un diálogo modal.
- Configuración de SBU/región editable desde `admin/config` (hoy: defaults + selector de región).
- **Guardado en Supabase + PDF individual: hechos** (ver "Rebanada" arriba).
  `/liquidaciones/guardadas` es una versión MVP del Editor + Gestión del
  legado (~5700 líneas de Tkinter entre ambas pantallas) — cubre buscar, ver,
  cambiar estado y eliminar, pero NO todavía:
  - ~~**Edición manual de campos**~~ ✅ **hecho** (2026-09-06):
    `core.repos.liquidaciones.editar_valores_liquidacion` — en el detalle de
    `/liquidaciones/guardadas`, botón "Editar valores" (gated `liquidaciones:
    editar`) hace editable cada valor de concepto; al guardar recalcula todos
    los totales y columnas derivadas de `liquidaciones`, con auditoría e
    historial. No toca una liquidación en estado 'pagada'. Un valor a 0 quita
    el concepto.
  - **Verificación de pago contra cartas bancarias** (`pagos_cartas.py` en
    `nucleo_modular`, carpeta `PAGOS_CARTAS/`) — columna "¿Pagado?" de
    Gestión de Liquidaciones.
  - ~~**Generar Bot MRL**~~ ✅ **hecho** (2026-09-06):
    `core/excel/liquidaciones_bot_mrl.bot_mrl_xlsx` (port 1:1 de
    `nucleo_modular/generacion_bot_mrl.py`). En `/liquidaciones/guardadas`:
    checkbox por fila + botón "Generar Bot MRL (N)" → Excel de 99 columnas del
    formato SUT. El desglose mensual del décimo tercero (24 columnas) sale de
    `liquidaciones_periodos_calculo`, que `guardar_liquidacion` ahora persiste
    desde `Liquidacion.detalle_decimo_tercera` (motor: sólo el periodo ACTUAL,
    el anterior nunca se detalla — regla de negocio). Liquidaciones guardadas
    antes de este cambio tienen esas 24 columnas en 0 y el export lo avisa.
  - **Edición masiva / carga masiva de ajuste de cuadre** (diálogos del
    legado, ~825 líneas de Tkinter entre los dos) — no evaluados todavía.
  - Desglose mensual de vacaciones/décimos en el PDF regenerado desde un
    registro guardado (`reconstruir_liquidacion` no lo tiene porque no se
    guarda ese detalle en Supabase; el total sale bien, falta el detalle).
- Columnas mensuales dinámicas de remuneración (col 62+) del Excel de lote: no incluidas aún.
- **Comparar montos con el .pyw para varios empleados reales antes de usar en producción**
  (bloqueante — sigue sin hacerse, no hay acceso a SQL Server real desde acá).
