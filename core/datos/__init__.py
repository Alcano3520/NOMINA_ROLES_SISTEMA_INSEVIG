"""Búsqueda y consolidación de datos de nómina de un empleado.

Reemplaza `shared/obtener_datos.py` (clase `ObtenerDatos`), de-duplicando las
~120 líneas de post-procesado que hoy están copiadas en
`obtener_datos_empleado_rapido` (SQL Server) y `obtener_datos_empleado_supabase`.

Arquitectura:
  fuente_sqlserver / fuente_supabase  -> solo el fetch crudo -> DatosCrudos
  postproceso.construir_empleado_nomina(DatosCrudos) -> EmpleadoNomina  (común)
  service.datos_empleado(periodo, id, fuente) -> EmpleadoNomina | None   (fachada)
"""
