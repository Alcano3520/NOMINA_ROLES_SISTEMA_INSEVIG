# _utilitarios — programas utilitarios de RRHH a integrar

Acá van los **programas sueltos** (Python/Tkinter, scripts, macros, etc.) que
RRHH usa para tareas puntuales y que hay que **absorber en la app web Reflex**.

Muchos son **anexos** de un módulo que ya existe (empleados, roles, préstamos,
liquidaciones, vacaciones, observaciones, agenda, reportes, registrador,
admin). Otros pueden convertirse en una herramienta nueva bajo *Reportes* o
*Administración*.

## Por qué esta carpeta

- **No se despliega ni se empaqueta**: el build de Reflex solo toma `core/`,
  `insevig_web/` y `assets/`; el auto-deploy solo se dispara con esas rutas.
  Esto es material de origen, se queda en el repo como respaldo y referencia.
- El prefijo `_` la deja arriba en el listado y marca "no es código activo".

## Cómo dejar cada programa

Una subcarpeta por programa, con el nombre real del `.py`/`.pyw`:

```
_utilitarios/
  <NOMBRE_DEL_PROGRAMA>/
    <archivo>.pyw            ← el código (o varios, como venga)
    requirements.txt         ← si lo tiene
    ejemplos/                ← Excel/PDF/plantillas de entrada o salida (opcional)
    NOTAS.txt                ← 2-3 líneas: qué hace y a qué módulo va (opcional)
```

Si no sabés a qué módulo pertenece, no importa — lo analizo yo del código.
Si sabés, poné una línea en `NOTAS.txt` (ej. "anexo de Vacaciones: calcula X").

## Qué hago con cada uno

1. Leo el código y lo que hace (entradas, salidas, BD que toca).
2. Decido: (a) se vuelve una acción/pantalla dentro de un módulo existente,
   (b) es una herramienta nueva chica, o (c) ya está cubierto y se descarta.
3. La lógica va a `core/` (repo/excel/pdf según corresponda), la interfaz a
   `insevig_web/pages/<mod>/` o `states/<mod>_state.py`.
4. Anoto el resultado en `docs/modulos/<mod>.md`.

## Índice (se completa a medida que llegan)

| Programa | Qué hace | Módulo destino | Estado |
|---|---|---|---|
| _(vacío)_ | | | |
