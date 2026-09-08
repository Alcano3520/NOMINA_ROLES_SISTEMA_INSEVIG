# UX/UI Spec: Editor de Liquidaciones (pantalla dedicada, paridad con el `.pyw`)

> Fuente: `Generador_Liquidaciones_INSEVIG.pyw`, `_abrir_editor_liquidaciones`
> (líneas ~9495-12229, ~2735 líneas). Es la 4ta pantalla del sidebar
> original (Generar / **Editor** / Gestión / Descuentos Pendientes) --
> hoy en la web está repartida entre "Editar valores" del panel de
> detalle de Gestión y la cuadrícula; esto describe la pantalla dedicada
> maestro-detalle para paridad completa.

## Qué es

Maestro-detalle: lista de liquidaciones guardadas a la izquierda
(buscable + filtrable por estado), panel de edición COMPLETO a la
derecha al seleccionar una -- todos los conceptos editables uno por uno
(a diferencia de la cuadrícula, que edita varias liquidaciones a la vez
pero con menos contexto por campo).

## Panel izquierdo: lista

- Título "Editor de Liquidaciones" + contador.
- Búsqueda por texto (cédula/nombre, mismo patrón que ya usa `listar_liquidaciones`).
- Chips de filtro por estado, en 2 filas de 3 (el `.pyw` los separa así
  porque en un panel angosto no entran los 6 en una sola fila):
  fila 1: `Todos / borrador / generada`; fila 2: `aprobado / pagado / cancelado`
  (subconjunto de los 11 estados reales -- el resto se ve igual en la
  lista, solo no tienen chip propio).
- Cada ítem de la lista: nombre + fecha + estado (con color, ver tabla
  de abajo) + total.

**Labels de estado para mostrar** (`estado_db_a_label`, verificado):
| valor real (`estado`) | Label a mostrar | Color sugerido |
|---|---|---|
| `borrador` | Borrador | gris (ink_soft) |
| `generada` | Generada | primario |
| `aprobado` | Autorizada | advertencia |
| `registrado_mrl` | Registrada en MRL | secundario |
| `cheque_listo` | Cheque Listo | advertencia |
| `pagado` | Pagada | ok/verde |
| `consignada` | Consignada | advertencia |
| `legalizada_mrl` | Legalizada MRL | ok/verde |
| `impreso` | Impresa | (sin color propio confirmado) |
| `archivado` | Archivada/Lista | (sin color propio confirmado) |
| `cancelado` | Cancelado | error/rojo |

**Labels de tipo** (`tipo_db_a_label`, coincide EXACTO con
`clasificar_tipo_liquidacion` de `core/repos/liquidaciones.py` -- no hace
falta tocar nada del motor):
`despido→Despido, renuncia→Renuncia, termino_contrato→Término de
contrato, visto_bueno→Visto bueno, muerte→Muerte, jubilacion→Jubilación,
otro→Otro`.

## Panel derecho: formulario de edición

### Encabezado
Nombre + botón **"🔄 Recalcular Liquidación"** (arriba a la derecha).

### Secciones (en este orden, cada una con sus campos editables individualmente)

**DATOS DEL EMPLEADO**: cédula, nombre, cargo, sección, fecha de ingreso,
fecha de salida, motivo (combo con las mismas `TIPOS`/`MOTIVOS_SALIDA`
que el resto de la app), estado (combo con las 11 opciones de arriba).

**CONCEPTOS DE REMUNERACIÓN** (`CONCEPTOS_REMUNERACION`, ingresos) --
verificado línea por línea, mismos códigos que `_CONCEPTOS_DETALLE` de
`core/repos/liquidaciones.py`:
| Código | Label exacto del `.pyw` |
|---|---|
| SUELDO | Sueldo |
| SOBT_25 | Horas del 25% (recargo nocturno) |
| SOBT_50 | Horas del 50% (suplementarias) |
| SOBT_100 | Horas del 100% (extraordinarias) |
| MANIOBRAS | Maniobras |
| BONIFICACION | Bonificación |
| MOVILIZACION | Movilización / Bono transporte-alimentación |
| REEMBOLSOS | Devolución y/o Acreditación (Reembolsos) |
| FONDO_RESERVA | Fondo de Reserva 8,33% |

Las horas (`SOBT_25/50/100`, `CODIGOS_HORAS`) se muestran como **3
sub-campos**: cantidad, valor por hora, y total -- no un solo monto, "para
ver el insumo del cálculo, no solo el resultado" (mismo criterio que
`horas_25_cantidad`/`horas_25_valor_hora` que ya guarda `_mapear_registro`).

**CONCEPTOS DE BENEFICIOS** (`CONCEPTOS_BENEFICIOS`, ingresos):
| Código | Label exacto |
|---|---|
| DEC_TERCERA_ANT / DEC_TERCERA_ACT | Décima Tercera (anterior) / (actual) |
| DEC_CUARTA_ANT / DEC_CUARTA_ACT | Décima Cuarta (anterior) / (actual) |
| VACACIONES | Vacaciones Pendientes |
| DESAHUCIO | Bonificación Desahucio 25% |
| INDEM_DESPIDO | Indemnización por Despido |
| OTRAS_INDEM | Otras Indemnizaciones |
| VALOR_NO_CONSIDERADO | Por cualquier valor no considerado |
| AJUSTE_CUADRE | Ajuste de Cuadre (MRL) -- admite NEGATIVO, el resto de campos no |

**DESCUENTOS** (`CONCEPTOS_FIJOS_DESCUENTOS`):
IESS (Aporte IESS Personal), ANTICIPO_SUELDO, ANTICIPOS_OTROS,
ANTICIPOS_SURTIDOS, PREST_QUIROGRAFARIO, PREST_COMPANIA,
PREST_HIPOTECARIO, IESS_CONYUGE (Aporte IESS Cónyuge), IMPUESTO_RENTA,
MULTAS, PENSION_ALIMENTICIA, ANTICIPOS_OTROS_L, ANTICIPO_L_DESAHUCIO,
DESCUENTO_REGISTRADO (Descuentos Registrados (pendientes)).

**Filas libres**: además de los conceptos fijos de arriba, se pueden
agregar filas de ingreso/descuento ad-hoc con nombre+valor libres
(`_crear_agregador_filas_libres`) -- para algo que no tiene código fijo.
Al guardar se persisten como conceptos sueltos en `liquidaciones_detalle`
(sin `concepto_codigo` fijo conocido).

**Totales en vivo**: cada cambio de campo recalcula subtotales/total en
pantalla (sin ir a red) -- mismo patrón que `_totales_desde_valores` de
`core/repos/liquidaciones.py`, ya disponible.

### El botón "+" -- ajuste incremental por concepto

Al lado de CADA campo fijo hay un botón **"+"** que abre
`_abrir_dialogo_ajuste_concepto`: muestra el valor actual, pide **Monto a
agregar** (obligatorio, no puede ser 0) y **Motivo (opcional)**. Al
confirmar, SUMA (no reemplaza) al campo y dispara `_recalcular_totales()`
en pantalla al instante -- función del motor ya lista:
`ajustar_concepto(id, concepto_codigo, delta, motivo="", usuario=, roles=)`
(commit `beb4506`, motivo opcional confirmado). Debajo de cada campo con
ajustes hay un indicador clickeable para ver/editar/eliminar el
historial de ajustes de ESE concepto (commit del repo viejo "Editor:
permite editar y eliminar ajustes ('+') ya registrados" -- no se leyó el
detalle de esa edición/eliminación línea por línea en esta pasada, pedir
aparte si hace falta).

### "🔄 Recalcular Liquidación"

Confirmación (`askyesno`) -- "se pierden los valores en pantalla si no
se guardaron". Vuelve a correr `procesar_empleado` completo desde cero
contra los datos ACTUALES de nómina, usando cédula + fecha_salida **tal
como están escritas en el formulario en ese momento** (no necesariamente
lo ya guardado -- si el usuario ya editó la fecha antes de recalcular,
recalcula con la fecha nueva). Función del motor ya lista:
`recalcular_liquidacion(id, fuente, cfg, cedula=, fecha_salida=,
motivo=)` (commit `beb4506`) -- pasar los valores actuales del
formulario como overrides. Después de recalcular, guarda en
`fecha_calculos_validos_para` la fecha_salida usada (ver validación de
abajo).

**Caso real que motivó el botón**: un período de vacaciones con goce
PARCIAL (ej. 3 días de 15 ya tomados) se sumaba completo en vez de
prorratear -- ya corregido en el motor actual (`total_vacaciones_a_pagar`,
verificado con tests).

### Validación crítica al guardar (verificado, no se puede omitir)

**Si la `fecha_salida` del formulario es distinta a la fecha con la que
se calcularon por última vez los campos en pantalla** (décimos,
vacaciones, desahucio, IESS, fondo de reserva, horas), **"Guardar
cambios" se BLOQUEA** con el mensaje: *"La fecha de salida es distinta a
la que se usó para calcular los décimos, vacaciones, desahucio, IESS y
fondo de reserva que se ven en pantalla... Presiona '🔄 Recalcular
Liquidación', revisa los valores nuevos y recién entonces guarda."*

Implementación sugerida en el `state`: guardar `fecha_calculos_validos_para`
al cargar un registro (= su `fecha_salida` guardada) y al recalcular (=
la fecha usada en ese recálculo); comparar contra el campo de fecha del
formulario antes de permitir guardar.

### Botones inferiores

Guardar cambios / Cancelar / Eliminar / **"Generar PDF/Excel"** (mismo
`generar_pdf_individual`/`generar_excel_simulacion` que el resto de la
app) -- todos con funciones de motor ya existentes
(`guardar_liquidacion` con `liquidacion_id_existente`, `eliminar_liquidacion`).

## Lo que este documento NO cubre en detalle

- El sub-diálogo de editar/eliminar un ajuste YA registrado (mencionado
  arriba, existe pero no se leyó línea por línea).
- Filas libres: el mecanismo exacto de persistencia a
  `liquidaciones_detalle` para un concepto sin código fijo no se
  verificó al detalle -- pedir aparte si hace falta antes de implementar.
