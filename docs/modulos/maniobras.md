# Módulo: maniobras (Registro de Maniobras / Multas)

> Estado en el repo Reflex: **YA PORTADO** (con otro origen). `core/repos/registrador.py`
> — "puerto completo de `REGISTRAR_PRESTAMOS_UNIFICADO.pyw`" — cubre en su
> pestaña 3 "Egresos / Ingresos" los tipos de `CLASES_SIMPLIFICADAS`, que
> incluyen **CLASE 110 = MANIOBRAS** y **CLASE 203 = MULTAS**, con grilla
> editable + pegar de Excel + cargar archivo + modo individual/agrupado + Job +
> CSV. Ver `docs/modulos/registrador.md` y `registrador_UI.md` en el repo Reflex.
>
> **Acción recomendada: NO portar de cero.** Hacer FASE -1 (diff): verificar que
> `registro_maniobras.py` (este repo) no aporte nada que `registrador` no tenga
> ya, y en ese caso marcar este módulo como cubierto.

## Qué hace (para el usuario)

Registrar de forma masiva movimientos de **maniobras (CLASE 110)** o **multas
(CLASE 203)** en `RPINGDES` para hasta ~2500 empleados: se pega un bloque desde
Excel (`Código | Fecha | Valor | Observación`), se valida contra `RPEMPLEA`, y
se inserta cada fila con numeración correlativa tomada de `RPCONTRL`.

## Origen (código legado)

| Archivo legado | Qué se reutiliza | Qué se reescribe |
|---|---|---|
| `registro_maniobras.py` (raíz, ~2100 líneas) | queries SQL Server (`RPEMPLEA`, `RPCONTRL`, `RPINGDES`), parsing de pegado, cálculo de fecha, numeración | toda la UI Tkinter (grid navegable de 2500 filas, canvas con scroll), `filedialog`, threading, `CacheMasivo` |

Nota: `registro_maniobras.py` y el `REGISTRAR_PRESTAMOS_UNIFICADO.pyw` del repo
Reflex son **dos apps Tkinter hermanas** sobre las mismas tablas de producción
(históricamente copiadas entre codebases). El repo Reflex ya portó la segunda.

## Lógica ya extraída (sin Tkinter)

| `nucleo_modular/…` | Contenido | Espejo Reflex |
|---|---|---|
| `repos/maniobras.py` | Fachada. | ya cubierto por `core/repos/registrador.py` |
| `maniobras_datos.py` | `conectar_bd`, `buscar_empleados_batch`, `buscar_empleados_por_texto`, `obtener_proximo_numero`, `insertar_movimiento_rapido(..., ejecutar=False)` → `(exito, msg, auditoria)`. | `core/repos/registrador.py` (`registrar_movimiento`, RPCONTRL) |
| `maniobras_calculo.py` | `parsear_linea_pegado`, `aplicar_valores_pegado_en_fila`, `resolver_fecha_movimiento`, `validar_filas_para_procesar`, `calcular_resumen_grid`, `generar_contenido_reporte`, `armar_datos_reporte_excel`. | `core/repos/registrador.py` + `core/excel/registrador_*` |

## Diferencias / bugs del legado (documentados — ver `nucleo_modular/README.md` §9-14)

- `insertar_movimiento(conn, ...)` ignora `conn` (código muerto).
- `obtener_detalles_empleado` / `actualizar_ultimo_numero` nunca se llaman;
  `insertar_movimiento_rapido` duplica esa lógica en línea.
- `generar_contenido_reporte` deriva el "Código de Clase" por posición del dict
  (`list(CLASES_SIMPLIFICADAS.keys())[0/1]`) en vez del código real.
- INSERT en `RPINGDES` + UPDATE de `RPCONTRL` en dos autocommits separados (no
  transacción). El `registrador` del repo Reflex ya lo hace mejor
  (`RPCONTRL WITH (UPDLOCK, HOLDLOCK)`).

## Rutas y permisos

No aplica página nueva — usar `/registrador` (pestaña Egresos/Ingresos) del repo
Reflex, filtrando por CLASE 110 / 203.

## Criterio de "hecho"

- [ ] FASE -1: diff `registro_maniobras.py` vs `core/repos/registrador.py`.
- [ ] Confirmar que CLASE 110 y 203 se pueden registrar masivamente desde
      `/registrador` con pegar-Excel + validar + Job.
- [ ] Si algo del legado falta → issue puntual contra `registrador`, no un
      módulo nuevo.
