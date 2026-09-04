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
7. **Décimo ANTERIOR (13ro y 14to) nunca se sumaba al total → se incluye por
   defecto.** La extracción inicial calculaba `DECIMA_TERCERA_ANTERIOR`/
   `DECIMA_CUARTA_ANTERIOR` pero jamás los sumaba a `TOTAL_INGRESOS` --
   subpagaba la liquidación en cualquier caso con décimo anterior pendiente.
   Se puede excluir explícitamente con
   `incluir_dec13_anterior`/`incluir_dec14_anterior=False` (parámetros nuevos
   de `procesar_empleado`, default `True`) para cuando ese décimo anterior ya
   se pagó por otra vía y no debe volver a sumarse.
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
  - **Edición manual de campos** de una liquidación ya guardada (el Editor
    del legado permite corregir a mano cualquier valor antes de re-guardar;
    aquí solo se puede cambiar el estado).
  - **Verificación de pago contra cartas bancarias** (`pagos_cartas.py` en
    `nucleo_modular`, carpeta `PAGOS_CARTAS/`) — columna "¿Pagado?" de
    Gestión de Liquidaciones.
  - **Generar Bot MRL** (exportar al formato del bot RPA del SUT) — lógica ya
    portada en `nucleo_modular/generacion_bot_mrl.py`, no conectada aquí.
  - **Edición masiva / carga masiva de ajuste de cuadre** (diálogos del
    legado, ~825 líneas de Tkinter entre los dos) — no evaluados todavía.
  - Desglose mensual de vacaciones/décimos en el PDF regenerado desde un
    registro guardado (`reconstruir_liquidacion` no lo tiene porque no se
    guarda ese detalle en Supabase; el total sale bien, falta el detalle).
- Columnas mensuales dinámicas de remuneración (col 62+) del Excel de lote: no incluidas aún.
- **Comparar montos con el .pyw para varios empleados reales antes de usar en producción**
  (bloqueante — sigue sin hacerse, no hay acceso a SQL Server real desde acá).
