# Módulo: empleados

Estado: **CRUD completo (paridad de campos con el legado)** + historial de nómina.

## Editor de empleado (paridad con las 6 pestañas del legado)
5 grupos en acordeón + observaciones por período:
- **Datos generales** (24): nombres/apellidos/cédula, sexo·estado civil·tipo empleado
  (combos), nacimiento, ubicación, fechas ingreso/salida, depto·cargo·sección
  (combos desde DBTABLAS FNC/SEC/DPT/BAN), estado, 2 teléfonos, email, actividad, cónyuge.
- **Ingresos / descuentos** (21): sueldo, bonif, compen, transporte, horas 25/50/100,
  décimos, fdo. reserva, movilización, lunch, anticipo, ing/dct extra, concepto,
  flags CAT_PROYECT_7/8 y RPCAM2 ('1'/'0').
- **Otros datos** (14): INCL_ROL / INCL_BAN ('S'/'N'), cargas, últ. liquidación,
  días trab., grupo sanguíneo, período de pago, cuentas contables y bancarias.
- **Certificados / familiares** (6): datos de familiar y no familiar.
- **Referencias** (24): cédula militar, edad, votación, licencia, IESS, Conadis,
  visita domiciliaria, estudios (1/0), título, servicios (GIPASE/AFIS/…),
  FZA_PUB / SER_MIL (1/0), cert. violencia intrafamiliar, maniobras, No. afiliación.

Codificación por columna en `core/repos/empleados.py`: `CAMPOS_NUMERICOS`, `CAMPOS_SN`,
`CAMPOS_FLAG_TXT`, `CAMPOS_FLAG_INT`, `CAMPOS_COMBO`, `CAMPOS_CATALOGO`.

Botón **Modificar** (como el legado: hay que habilitar la edición); campos obligatorios
EMPLEADO/CÉDULA/NOMBRES/APELLIDOS; concurrencia optimista por token; auditoría en cada
escritura; borrado con reescritura del código.

**Observaciones por período** (RPEMPOBSERV): mostrar los 7 slots refer1..7 de un mes,
editarlos inline y guardar (advisory lock + auditoría), ver historial completo.
`observaciones.observaciones_mes / guardar_observaciones_mes / historial_observaciones`.

## Pendiente
- Validar nombres de columna de RPEMPLEA contra la BD real (algunos son columnas
  varchar genéricas reutilizadas; el legado los escribe pero conviene confirmar).
- Adjuntar imágenes de certificados (el legado solo dibuja recuadros vacíos).
- Impresión del historial de observaciones a PDF/HTML (hoy se lista en pantalla).

## Origen legado
empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw, empleados/CARGA_MASIVA_EMPLEADOS.pyw, empleados/historial_empleado_GUI.pyw

## Rebanada (recordatorio)
`core/repos/empleados.py` · `insevig_web/states/empleados_state.py` ·
`insevig_web/pages/empleados/*.py` · `insevig_web/components/empleados/*.py` ·
`tests/unit/test_empleados_*.py` · este documento.

## Contratos que consume
Ver `docs/CONTRATOS.md`. No editar el núcleo congelado.
