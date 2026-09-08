# UX/UI Spec: Editar en cuadrícula + Cuadre masivo (MRL)

> Fuente: `Generador_Liquidaciones_INSEVIG.pyw`,
> `_abrir_cuadricula_edicion_masiva` (líneas 8303-8879) y
> `_abrir_carga_masiva_ajuste_cuadre` (líneas 8880-9127). Menos exhaustivo
> que `liquidaciones_gestion_UI.md` -- prioridad acordada más baja, se
> leyó lo suficiente para implementar sin adivinar lo esencial; algunos
> detalles menores de validación no se transcribieron línea por línea.

## 1. Editar en cuadrícula (`▦`)

**Qué es**: vista tipo Excel -- una fila por liquidación YA GUARDADA
(seleccionadas en Gestión de Liquidaciones), una columna por campo/
concepto. Edición rápida de varias liquidaciones a la vez sin abrir el
Editor uno por uno.

**Comportamiento clave (verificado)**:
- Los cambios quedan SOLO en memoria hasta apretar **"Guardar todos los
  cambios"** -- recién ahí se escribe, una liquidación a la vez.
- Si alguna de las seleccionadas ya está en estado avanzado
  (`{pagado, consignada, registrado_mrl, cheque_listo, legalizada_mrl,
  impreso, archivado}`), se pide confirmación: *"Editar sus valores aquí
  NO revierte el trámite, solo corrige los montos guardados. ¿Desea
  continuar de todos modos?"*.
- **Cada cambio de un concepto queda registrado como un AJUSTE** (motivo +
  quién + cuándo) -- mismo mecanismo que el botón "+" del Editor de
  Liquidaciones (tabla `liquidaciones_ajustes_concepto`, ya existente).
  Hay un campo único **"Motivo del ajuste"** que se aplica a TODOS los
  cambios de ese guardado (no uno por celda).
- A propósito NO reutiliza el mapeo completo de "guardar liquidación
  nueva" -- solo actualiza los campos que esta grilla edita, para no
  pisar `observaciones`/`motivo`/`tipo_liquidacion` de una liquidación ya
  guardada.

**Columnas administrativas** (`CAMPOS_ADMIN`):
| Clave | Label | Tipo |
|---|---|---|
| `FORMA_PAGO` | Forma de pago | combo: `['', 'Transferencia', 'Cheque', 'Efectivo', 'Otro']` |
| `CHEQUE_NUM` | N° Cheque/Comprob. | texto |
| `BANCO` | Banco | texto |
| `NOTA_PAGO` | Nota de pago | texto |
| `OBSERVACIONES` | Observación | texto |

**Columnas de conceptos editables** (`CONCEPTOS_GRID` → concepto real en
`liquidaciones_detalle`, mismos códigos que `_CONCEPTOS_DETALLE` de
`core/repos/liquidaciones.py` salvo aclaración):

| Clave de fila | Label | `concepto_codigo` |
|---|---|---|
| SUELDO | Sueldo | SUELDO |
| MANIOBRAS | Maniobras | MANIOBRAS |
| BONIFICACION | Bonificación | BONIFICACION |
| MOVILIZACION | Movilización | MOVILIZACION |
| REEMBOLSOS | Reembolsos | REEMBOLSOS |
| VAL_SOBT_25/50/100 | Horas 25%/50%/100% | SOBT_25/50/100 |
| FONDO_RESERVA | Fondo Reserva | FONDO_RESERVA |
| DECIMA_TERCERA_ANTERIOR/ACTUAL | Déc.13 Ant./Act. | DEC_TERCERA_ANT/ACT |
| DECIMA_CUARTA_ANTERIOR/ACTUAL | Déc.14 Ant./Act. | DEC_CUARTA_ANT/ACT |
| VACACIONES_CALCULADAS | Vacaciones | VACACIONES |
| DESAHUCIO | Desahucio | DESAHUCIO |
| INDEMNIZACION_DESPIDO | Indem. Despido | INDEM_DESPIDO |
| APORT_IESS / APORT_IESS_CONYUGE | IESS / IESS Cónyuge | IESS / IESS_CONYUGE |
| PRESTAMOS_QUIROGRAFARIOS/COMPANIA/HIPOTECARIO | Préstamo Quirograf./Cía./Hipot. | PREST_QUIROGRAFARIO/COMPANIA/HIPOTECARIO |
| ANTICIPO_SUELDO / ANTICIPOS_OTROS / ANTICIPOS_SURTIDOS | Anticipo Sueldo / Otros / Surtidos | igual |
| ANTICIPOS_OTROS_L / ANTICIPO_L_DESAHUCIO | Anticipo Otros (Liq.) / Desahucio (Liq.) | igual |
| MULTAS / PENSION_ALIMENTICIA / IMPUESTO_RENTA | igual | igual |
| DESCUENTOS_REGISTRADOS | Descuentos Registrados | `DESCUENTO_REGISTRADO` -- **código NUEVO, no está en `_CONCEPTOS_DETALLE` de `core/repos/liquidaciones.py` hoy** |
| **AJUSTE_CUADRE** | Ajuste Cuadre MRL | `AJUSTE_CUADRE` -- **admite negativo a propósito** ("corregir por centavos contra lo que registra el MRL"), tampoco existe hoy en `_CONCEPTOS_DETALLE` |
| OTRAS_INDEMNIZACIONES / OTROS_VALORES | Otras Indem. / Valor No Consid. | `OTRAS_INDEM` / `VALOR_NO_CONSIDERADO` -- tampoco existen hoy en `_CONCEPTOS_DETALLE` |

**Pendiente si se implementa esto**: `core/repos/liquidaciones.py` no
tiene los conceptos `DESCUENTO_REGISTRADO`/`AJUSTE_CUADRE`/`OTRAS_INDEM`/
`VALOR_NO_CONSIDERADO` en `_CONCEPTOS_DETALLE` todavía (mismo hueco que ya
documenté en `core/excel/liquidaciones_import.py` para
`OTRAS_INDEM_EXCEL`/`VALOR_NO_CONSIDERADO_EXCEL`). Avisame cuando vayas a
construir esta pantalla y agrego esos 4 códigos + una función
`ajustar_concepto(id, concepto_codigo, delta, *, motivo, usuario, roles)`
que registre el ajuste igual que el "+" del Editor.

## 2. Cuadre masivo (MRL) (`🧮`)

**Qué es**: carga por texto libre (pegar una lista), SIN necesidad de
seleccionar filas primero en Gestión -- cada línea identifica su propia
liquidación.

**Formato de línea** (verificado):
```
cedula, fecha_salida (dd/mm/aaaa), monto_a_agregar
```
- La fecha de salida es necesaria porque una misma cédula puede tener
  más de una liquidación real (ej. reingreso).
- El monto es lo que se **SUMA** al ajuste de cuadre que ya hubiera (no
  reemplaza) -- admite negativo. Mismo criterio "monto a agregar" que el
  "+" del Editor.
- Un solo campo **"Motivo"** (default: "Cuadre contra MRL") se aplica a
  TODAS las líneas de esa carga.
- Reutiliza el mismo mecanismo de ajuste por concepto que la cuadrícula
  (`AJUSTE_CUADRE`) -- ver el pendiente de arriba.

**Ejemplo del propio `.pyw`**:
```
0704090805, 31/07/2026, 0.01
0921509527, 15/08/2026, -0.02
```

Formato de errores: por línea, "Línea N: faltan datos.../cédula o fecha
inválida...", junta todos los errores antes de mostrar un solo mensaje
(no se detiene en el primero).

## Labels confirmados para el panel de seguimiento (pedido puntual)

Verificado línea por línea contra `_campo_fecha`/`_campo_entry`
(líneas 12548-12556) -- tus labels actuales son paráfrasis razonables,
más cortas; el texto EXACTO del `.pyw` es:

| Campo | Texto exacto del `.pyw` |
|---|---|
| `numero_acta` | "Número de Acta" |
| `fecha_firma_acuerdo` | "Firma de acuerdo entre las partes (fecha - cuándo se acercó)" |
| `fecha_lista_cobro` | "La liquidación ya está lista para su cobro (fecha - desde)" |
| `fecha_citado_cobro` | "Para qué fecha está citado para el cobro" |
| `fecha_consignacion` | "Cuándo se acercó o se consignó la liquidación (fecha)" |
| `lugar_firma` | "Lugar donde firma la liquidación" (combo: `['Consignación', 'Oficina']`) |

Son bastante largos para un label de formulario web -- tu versión corta
funciona bien como label visible; si el usuario quiere el texto EXACTO
(paridad literal, no solo funcional), usalo como `title`/tooltip o label
completo según el espacio disponible.
