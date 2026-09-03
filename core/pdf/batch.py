"""Generación por lotes de roles de pago -> ZIP en memoria."""

from __future__ import annotations

import io
import zipfile

from core.datos.service import datos_empleado
from core.pdf.layout import formatear_nombre_archivo
from core.pdf.rol_pago import OpcionesRol, rol_pago_pdf


def job_lote_roles(
    ctx,
    periodo: str,
    identificadores: list[str],
    fuente: str,
    formato: str,
    opciones: OpcionesRol,
) -> None:
    """`identificadores`: códigos/cédulas/nombres. Genera un PDF por empleado y los
    empaqueta en un ZIP guardado en storage."""
    from core import storage

    buf = io.BytesIO()
    total = len(identificadores)
    generados = 0
    fallos: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, ident in enumerate(identificadores, 1):
            if ctx.cancelado:
                break
            try:
                emp = datos_empleado(periodo, ident, fuente)
                if emp is None:
                    fallos.append(f"{ident}: no encontrado")
                    continue
                d = emp.to_dict()
                nombre_arch = formatear_nombre_archivo(
                    formato,
                    empleado=str(d.get("EMPLEADO", "")),
                    nombre=str(d.get("APELLIDOS_NOMBRES", "")),
                    cedula=d.get("CEDULA"),
                    cargo=str(d.get("CARGO", "")),
                    depto=str(d.get("DEPTO", "")),
                    periodo=periodo,
                )
                zf.writestr(nombre_arch, rol_pago_pdf(emp, opciones))
                generados += 1
            except Exception as e:  # noqa: BLE001, PERF203
                fallos.append(f"{ident}: {e}")
            ctx.progreso(i, total, f"{generados} PDF generados")
        if fallos:
            zf.writestr("_ERRORES.txt", "\n".join(fallos))
    ruta = storage.guardar(ctx.job_id, f"ROLES_{periodo}.zip", buf.getvalue())
    ctx.set_resultado(str(ruta))
    ctx.progreso(total, total, f"Listo: {generados} roles, {len(fallos)} con error")
