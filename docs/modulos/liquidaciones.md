# Módulo: liquidaciones — Generador de finiquitos (módulo 9)

Origen: `~/Documentos/mis_proyecto/LIQUIDACIONES_SISTEMA_INSEVIG/`
(`Liquidaciones_generador_CON_VACACIONES.pyw` — la versión con todos los cálculos).

## Qué hace
Dada una lista de `cédula, dd/mm/aaaa (fecha salida), motivo`, calcula la
liquidación legal de cada empleado y produce un Excel (hoja `FORMATO`).

## Cálculos portados (fórmulas exactas del legado)
| Concepto | Fórmula |
|---|---|
| Movimientos del mes de salida | RPINGDES → fallback RPHISTOR; mapeo CLASE→concepto; `EGR` sin mapeo → ANTICIPOS_SURTIDOS |
| Descuentos multi-mes | se suman hasta 36 meses después (o 3 seguidos sin datos) los conceptos de `DESCUENTOS_MULTI_MES` |
| Sobretiempos | de RPEMPLEA si no vinieron: `(sueldo/240) × factor × horas` (25%: 0.25, 50%: 1.5, 100%: 2.0) |
| Vacaciones | últimos 2 periodos anuales (01/mes_ingreso → fin mes anterior); base = SUELDO+BONIF+MANIOBRAS+SOBRETIEMPOS; `calc = último_periodo / 24` |
| Décima 13ra | periodo 01/12 → 30/11; `total_periodo / 12`; anterior + actual |
| Décima 14ta | `(DIAS360(inicio, salida) + 1 + ajuste_feb) × (SBU_año / 360)`; COSTA 01/03→28/02, SIERRA 01/08→31/07; pagadas→ANTERIOR, pendiente→ACTUAL |
| Desahucio | `(sueldo/4) × años_completos` si > 360 días y contrato indefinido; años = `relativedelta + 0.00278` truncado |
| Indem. despido | motivo con "DESPIDO"/"INTEMPESTIVO": `3×sueldo` (<3 años) o `años×sueldo` (máx 25) |
| Fondo de reserva | `8.33% × base del mes de salida` |
| IESS | `9.45% × (SUELDO + SOBRETIEMPOS)` |
| Split anticipos (días < 90) | `ANTICIPOS_OTROS_L = int((vac+13act+14act+desahucio)/3.75)`; `ANTICIPO_L_DESAHUCIO = int(desahucio/3.75)` |
| Total a recibir | ingresos (sueldo, extras, FR, vac_calc, 13act, 14act, desahucio, indem) − descuentos |

Constantes en `core/repos/liquidaciones.py`: `MAPEO_CONCEPTOS`, `CODIGOS_IGNORAR`,
`DESCUENTOS_MULTI_MES`, `SBU_DEFECTO` (2020-2027). `ConfigLiquidacion(region, iess_pct, sbu_por_anio)`.

## Rebanada
- `core/repos/liquidaciones.py` (cálculo completo)
- `core/excel/liquidaciones_builders.py` (Excel hoja FORMATO, ~62 columnas; los
  campos administrativos manuales van en blanco)
- `insevig_web/states/liquidaciones_state.py`, `insevig_web/pages/liquidaciones/index.py`
- `tests/unit/test_liquidaciones.py`

## Datos
Solo lectura de nómina. Por defecto **Supabase** (las tablas históricas grandes —
`rphistor_temp` 903K filas — están ahí). También funciona contra SQL Server.

## Pendiente / a validar contra el legado
- Sobretiempos del **mes en curso** proporcionales (el legado recalcula desde
  DBTABLAS SEC en lugar de leer RPINGDES stale): hoy se usa el valor de RPEMPLEA.
- Columnas mensuales dinámicas de remuneración (col 62+) del Excel: no incluidas aún.
- El diálogo "pedir fecha de ingreso" cuando FECHA_ING > FECHA_SAL: aquí devuelve error.
- Configuración de SBU/región editable desde `admin/config` (hoy: defaults + selector de región).
- **Comparar montos con el .pyw para varios empleados reales antes de usar en producción.**
