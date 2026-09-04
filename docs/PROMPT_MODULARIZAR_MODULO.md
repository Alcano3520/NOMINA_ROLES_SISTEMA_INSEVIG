# Prompt reutilizable — modularizar un módulo legado para conectarlo a Reflex

Pegar en el chat que trabaja cada módulo Tkinter suelto (roles/, prestamos/,
envio_roles/, SACAR_SEC/, `HISTORIAL PRESTAMOS/`, `TOTAL_OSERVACIONES/`, etc.).
Cambiar solo la línea "Módulo:" al inicio.

---

Módulo: `<ruta de la carpeta de este módulo, ej. HISTORIAL PRESTAMOS/>`

Este programa se va a conectar más adelante a un sistema web nuevo, hecho en
Reflex (`NOMINA_ROLES_SISTEMA_INSEVIG/insevig_web/`), que le pondrá una interfaz
adecuada y responsiva. **Tú no tocas ese repo ni construyes ninguna interfaz** —
tu única tarea es dejar la lógica de este módulo en un paquete Python limpio,
separado de Tkinter, para que conectarlo después sea trasplantar código, no
reescribirlo desde cero.

## Qué crear

Una carpeta nueva **dentro de esta misma carpeta del módulo**, llamada
`nucleo_modular/` (paquete Python: `__init__.py` + los archivos que hagan falta).
Ahí va TODA la lógica que hoy vive mezclada con Tkinter en el `.pyw`:

- Acceso a datos (SQL Server / Supabase / SQLite): funciones que reciben la
  fuente y los filtros como parámetros y devuelven datos planos (dataclasses o
  dicts), nunca un `pandas.DataFrame` crudo de UI ni nada atado a un widget.
- Cálculos de negocio (lo que hoy está enterrado en métodos de la clase de la
  ventana).
- Generación de PDF / Excel / email: funciones puras `datos -> bytes`, sin
  `filedialog` ni rutas de disco fijas.
- Reglas de validación, catálogos, constantes (`CLASE -> concepto`, estados, etc.).

## Reglas duras

1. **Cero imports de Tkinter/customtkinter** en `nucleo_modular/` (nada de
   `tkinter`, `ttk`, `messagebox`, `filedialog`). Si una función hoy muestra un
   `messagebox` de error, en el módulo debe **lanzar una excepción** o devolver
   un resultado con un campo de error — la UI (la de hoy o la futura de Reflex)
   decide cómo mostrarlo.
2. Funciones con **firma explícita**: parámetros de entrada claros (empleado,
   fuente, fechas, filtros...), sin leer `self.algo_var.get()`. Nada de estado
   global oculto.
3. **Credenciales fuera del código**: si hay usuario/password/API key
   hardcodeados en el `.pyw`, muévelos a variables de entorno o a un
   `config.py` con valores por defecto vacíos — no los repitas ni los dejes
   igual "porque ya estaban así".
4. Si el módulo **escribe** en SQL Server: la superficie de escritura debe ser
   la mínima imprescindible, con vista previa antes de escribir y algún tipo de
   registro de auditoría (quién, cuándo, qué cambió). No agregues escrituras
   nuevas que el programa no tenía.
5. Cada función pública lleva **docstring corto**: qué hace, qué recibe, qué
   devuelve. Si porta una función del `.pyw`, dilo (`Porta X() de <archivo>`).
6. Debe ser **testeable con pytest sin abrir ninguna ventana** — es decir,
   `import nucleo_modular` no debe intentar crear un `Tk()` ni conectarse a
   nada al importarse.
7. No inventes funcionalidad nueva ni "mejores" el flujo por tu cuenta — el
   objetivo es que la lógica actual quede reutilizable tal cual, con los mismos
   resultados que el programa de hoy. Cambios de comportamiento, repórtalos
   aparte en vez de aplicarlos en silencio.

## Qué entregar

```
<carpeta del módulo>/
  nucleo_modular/
    __init__.py
    <archivos>.py        # organizados por tema (datos, calculos, pdf, excel...)
  nucleo_modular/README.md
```

El `README.md` debe listar:
- Las funciones/clases públicas del paquete, con su firma y una línea de qué hacen.
- Qué pantallas/botones del programa original usa cada una (para poder mapear
  "esto es el botón X de la pestaña Y").
- Qué queda sin portar todavía y por qué (dependencias externas raras, lógica
  poco clara, algo que requiere decidir algo con el usuario primero).
- Cualquier diferencia de comportamiento que hayas detectado entre lo que el
  código hace y lo que parece que debería hacer (bugs existentes) — repórtalos,
  no los arregles silenciosamente salvo que el usuario lo pida.

## Antes de avisar que terminaste

- `python3 -m py_compile` (o el equivalente) sobre todo `nucleo_modular/` sin errores.
- El programa original (`.pyw`) sigue funcionando exactamente igual — si ya
  importa desde `nucleo_modular/` en vez de tener el código duplicado, probado
  a mano; si lo dejaste duplicado por ahora, dilo explícitamente en el README.
- Nada en `nucleo_modular/` importa `tkinter` (`grep -r "^import tkinter\|^from tkinter" nucleo_modular/` vacío).
- Si hay tests, corren en verde.
