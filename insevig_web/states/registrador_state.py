"""Estado del módulo Registrar egresos/ingresos — 6 pestañas del sistema anterior."""

from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import asdict

import reflex as rx

from core.repos import registrador
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

CLASES_OPCIONES = [
    {"codigo": c, "etiqueta": f"{c} — {registrador.NOMBRE_CLASE.get(c, c)} ({cfg['tipo']})"}
    for c, cfg in registrador.CLASES_SIMPLIFICADAS.items()
]

# Para el filtro de la consulta detallada (incluye préstamos 205 y "todas").
CLASES_CONSULTA = [
    {"codigo": "", "etiqueta": "Todos los tipos"},
    {"codigo": "205", "etiqueta": "205 — Préstamo"},
    *[{"codigo": o["codigo"], "etiqueta": o["etiqueta"]} for o in CLASES_OPCIONES],
]


def _hoy() -> str:
    return dt.date.today().isoformat()


def _periodo() -> str:
    return dt.date.today().strftime("%Y-%m")


def _split_linea(ln: str) -> list[str]:
    """Divide una línea pegada (TSV de Excel, o ; | , ) en celdas."""
    for sep in ("\t", ";", "|"):
        if sep in ln:
            return [x.strip() for x in ln.split(sep)]
    if ln.count(",") >= 2:
        return [x.strip() for x in ln.split(",")]
    return [ln.strip()]


def _fila_pm() -> dict:
    return {"codigo": "", "nombre": "", "empleado": "", "valor_total": "",
            "cuotas_valor": "", "fecha": _hoy(), "observacion": "", "valido": False}


def _fila_bi() -> dict:
    return {"codigo": "", "nombre": "", "empleado": "", "clase": "203", "valor": "",
            "fecha": _hoy(), "observacion": "", "valido": False}


class RegistradorState(rx.State):
    tab: str = "prestamo"
    error: str = ""
    resultado: str = ""

    # búsqueda de empleado (compartida)
    busca: str = ""
    encontrados: list[dict] = []
    emp_sel: str = ""
    emp_nombre: str = ""

    @rx.event
    def on_load(self):
        if not self.p_fecha:
            self.p_fecha = _hoy()
        if not self.ind_fecha:
            self.ind_fecha = _hoy()
        if not self.periodo:
            self.periodo = _periodo()

    @rx.event
    def set_tab(self, v: str):
        self.tab = v
        self.error = self.resultado = ""

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return await ds.resolver("registrador")

    @rx.event
    def set_busca(self, v: str):
        self.busca = v

    @rx.event
    async def buscar_emp(self):
        if not self.busca.strip():
            return
        from core.repos import observaciones

        fuente = await self._fuente()
        self.encontrados = await asyncio.to_thread(observaciones.buscar_empleados, self.busca, fuente)

    @rx.event
    async def elegir_emp(self, empleado: str, nombre: str):
        self.emp_sel = empleado
        self.emp_nombre = nombre
        self.encontrados = []
        if self.tab == "prestamo":
            await self._cargar_proyeccion()
        await self._cargar_movimientos_emp()

    # movimientos vigentes (no asentados) del empleado elegido — mismo panel
    # "Historial de Registros" que el legado muestra en Préstamo / Egresos.
    emp_movimientos: list[dict] = []

    async def _cargar_movimientos_emp(self):
        self.emp_movimientos = []
        if not self.emp_sel:
            return
        fuente = await self._fuente()
        movs = await asyncio.to_thread(
            registrador.historial_movimientos, fuente, "", 50, empleado=self.emp_sel
        )
        self.emp_movimientos = [asdict(m) for m in movs]

    # carga programada del empleado (deducciones ya agendadas por mes)
    p_proyeccion: list[dict] = []

    async def _cargar_proyeccion(self):
        self.p_proyeccion = []
        if not self.emp_sel:
            return
        fuente = await self._fuente()
        try:
            fecha = dt.date.fromisoformat(self.p_fecha or _hoy())
        except ValueError:
            fecha = dt.date.today()
        proy = await asyncio.to_thread(
            registrador.proyeccion_pagos_futuros, self.emp_sel, fuente, fecha
        )
        self.p_proyeccion = [
            {"mes": f"{a:04d}-{m:02d}", "valor": round(v, 2)}
            for (a, m), v in sorted(proy.items())
        ]

    @rx.event
    async def refrescar_proyeccion(self):
        await self._cargar_proyeccion()

    # ── 1. Préstamo individual ───────────────────────────────────────────
    p_valor: str = ""
    p_modo: str = "cuotas"          # "cuotas" (nº de cuotas) | "valor" (cuota mensual)
    p_num_cuotas: str = "12"
    p_cuota_mensual: str = ""
    p_fecha: str = ""
    p_observ: str = ""
    p_preview: list[dict] = []      # [{'secuencia','fecha_vencimiento','valor'}]
    p_aviso: str = ""

    @rx.event
    def set_p(self, campo: str, v: str):
        setattr(self, f"p_{campo}", v)

    @rx.event
    async def calcular_cuotas(self):
        self.error = self.resultado = self.p_aviso = ""
        self.p_preview = []
        try:
            total = float(self.p_valor)
            fecha = dt.date.fromisoformat(self.p_fecha or _hoy())
        except ValueError:
            self.error = "Revisa el valor y la fecha."
            return
        try:
            if self.p_modo == "cuotas":
                cuotas = registrador.cuotas_tradicional(total, int(self.p_num_cuotas), fecha)
            else:
                fuente = await self._fuente()
                proy = {}
                if self.emp_sel:
                    proy = await asyncio.to_thread(
                        registrador.proyeccion_pagos_futuros, self.emp_sel, fuente, fecha
                    )
                cuotas, aviso = await asyncio.to_thread(
                    registrador.cuotas_por_valor, total, float(self.p_cuota_mensual), fecha, proy
                )
                self.p_aviso = aviso
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
            return
        self.p_preview = [asdict(c) for c in cuotas]

    @rx.event
    def set_preview_cuota(self, idx: int, campo: str, v: str):
        """Ajuste manual de una cuota del preview antes de registrar."""
        filas = list(self.p_preview)
        if not 0 <= idx < len(filas):
            return
        if campo == "valor":
            try:
                filas[idx] = {**filas[idx], "valor": round(float(v), 2)}
            except ValueError:
                return
        else:
            filas[idx] = {**filas[idx], campo: v}
        self.p_preview = filas

    @rx.var
    def p_preview_total(self) -> float:
        return round(sum(float(c.get("valor", 0)) for c in self.p_preview), 2)

    @rx.event
    async def guardar_prestamo(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            self.error = "Sin permiso."
            return
        if not self.emp_sel or not self.p_preview:
            self.error = "Elige un empleado y calcula las cuotas."
            return
        from core.repos.registrador import Cuota

        cuotas = [Cuota(c["secuencia"], c["fecha_vencimiento"], c["valor"]) for c in self.p_preview]
        total = round(sum(c.valor for c in cuotas), 2)
        emp, fecha, obs = self.emp_sel, self.p_fecha or _hoy(), self.p_observ
        usuario, roles = auth.username, set(auth.roles)
        self.error = self.resultado = ""
        try:
            res = await asyncio.to_thread(
                registrador.registrar_prestamo, emp, total, fecha, obs, cuotas,
                usuario=usuario, roles=roles, dry_run=False,
            )
            self.resultado = res.detalle if res.ok else ""
            self.error = "" if res.ok else res.detalle
            if res.ok:
                self.p_preview = []
                self.p_valor = self.p_observ = ""
                await self._cargar_proyeccion()
                await self._cargar_movimientos_emp()
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    # ── 2. Carga masiva de préstamos (grilla editable + pegar de Excel) ──
    pm_modo: str = "cuotas"          # "cuotas" (nº de cuotas) | "valor" (cuota mensual)
    pm_pegar: str = ""
    pm_grid: list[dict] = []         # filas editables
    masiva_job: int = 0
    masiva_status: str = ""
    masiva_msg: str = ""
    masiva_path: str = ""

    @rx.event
    def set_pm_modo(self, v: str):
        self.pm_modo = v

    @rx.event
    def set_pm_pegar(self, v: str):
        self.pm_pegar = v

    @rx.event
    def pm_nueva_fila(self):
        self.pm_grid = [*self.pm_grid, _fila_pm()]

    @rx.event
    def pm_quitar_fila(self, idx: int):
        self.pm_grid = [r for i, r in enumerate(self.pm_grid) if i != idx]

    @rx.event
    def pm_limpiar(self):
        self.pm_grid = []
        self.masiva_job = 0
        self.masiva_status = self.masiva_msg = self.masiva_path = ""

    @rx.event
    def pm_set_celda(self, idx: int, campo: str, v: str):
        g = list(self.pm_grid)
        if 0 <= idx < len(g):
            g[idx] = {**g[idx], campo: v, "valido": False, "nombre": ""}
            self.pm_grid = g

    @rx.event
    def pm_cargar_pegado(self):
        """Convierte lo pegado (TSV de Excel, o ; | , ) en filas de la grilla."""
        campos = ("codigo", "valor_total", "cuotas_valor", "fecha", "observacion")
        filas = []
        for ln in self.pm_pegar.splitlines():
            if not ln.strip():
                continue
            partes = _split_linea(ln)
            fila = _fila_pm()
            for j, c in enumerate(campos):
                if j < len(partes) and partes[j]:
                    fila[c] = partes[j]
            filas.append(fila)
        if filas:
            self.pm_grid = filas
            self.pm_pegar = ""

    @rx.event
    async def pm_validar(self):
        from core.repos import observaciones

        self.error = ""
        fuente = await self._fuente()
        codigos = sorted({str(r["codigo"]).strip() for r in self.pm_grid if str(r["codigo"]).strip()})

        def _resolver():
            cache = {}
            for c in codigos:
                r = observaciones.buscar_empleados(c, fuente)
                cache[c] = r[0] if r else None
            return cache

        cache = await asyncio.to_thread(_resolver)
        nueva = []
        for r in self.pm_grid:
            cod = str(r["codigo"]).strip()
            e = cache.get(cod)
            tiene_datos = bool(str(r["valor_total"]).strip()) and bool(str(r["cuotas_valor"]).strip())
            nueva.append({
                **r,
                "empleado": e["empleado"] if e else "",
                "nombre": (e["apellidos_nombres"] if e else ("NO ENCONTRADO" if cod else "")),
                "valido": bool(e) and tiene_datos,
            })
        self.pm_grid = nueva

    @rx.event
    async def aplicar_masiva(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        filas = [f for f in self.pm_grid if f.get("valido") and f.get("empleado")]
        if not filas:
            return rx.toast.error("Valida primero: no hay filas listas.")
        modo = self.pm_modo
        usuario, roles = auth.username, set(auth.roles)

        def _fn(ctx):
            import csv
            import io

            from core import storage
            from core.repos.registrador import (
                Cuota,
                cuotas_por_valor,
                cuotas_tradicional,
                registrar_prestamo,
            )

            res = []
            for i, f in enumerate(filas, 1):
                try:
                    total = float(f["valor_total"])
                    fecha = dt.date.fromisoformat(str(f["fecha"])[:10])
                    if modo == "valor":
                        cuotas, _aviso = cuotas_por_valor(total, float(f["cuotas_valor"]), fecha)
                    else:
                        cuotas = cuotas_tradicional(total, int(float(f["cuotas_valor"])), fecha)
                    r = registrar_prestamo(
                        f["empleado"], round(sum(c.valor for c in cuotas), 2),
                        fecha.isoformat(), (f.get("observacion") or "CARGA MASIVA"),
                        [Cuota(c.secuencia, c.fecha_vencimiento, c.valor) for c in cuotas],
                        usuario=usuario, roles=roles, dry_run=False,
                    )
                    res.append({"empleado": f["empleado"], "ok": r.ok, "detalle": r.detalle})
                except Exception as e:  # noqa: BLE001
                    res.append({"empleado": f["empleado"], "ok": False, "detalle": str(e)[:150]})
                ctx.progreso(i, len(filas), f"{i}/{len(filas)}")
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=["empleado", "ok", "detalle"])
            w.writeheader()
            w.writerows(res)
            ruta = storage.guardar(ctx.job_id, "CARGA_PRESTAMOS.csv", buf.getvalue().encode("utf-8"))
            ctx.set_resultado(str(ruta))
            ok = sum(1 for r in res if r["ok"])
            ctx.progreso(len(filas), len(filas), f"{ok} OK, {len(res) - ok} con error")

        from core.jobs.runner import get_runner

        self.masiva_path = ""
        self.masiva_job = get_runner().encolar("carga_prestamos", {"n": len(filas)}, creado_por=usuario, fn=_fn)
        self.masiva_status = "pendiente"
        return RegistradorState.vigilar_masiva

    @rx.event(background=True)
    async def vigilar_masiva(self):
        from core.jobs.runner import leer_job

        for _ in range(1800):
            async with self:
                jid = self.masiva_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.masiva_status = j.status
                self.masiva_msg = j.message
                self.masiva_path = j.result_path
            if j.status in ("ok", "error", "cancelado"):
                return
            await asyncio.sleep(1)

    @rx.event
    def descargar_masiva(self):
        if not self.masiva_path:
            return
        from pathlib import Path

        p = Path(self.masiva_path)
        return rx.download(data=p.read_bytes(), filename=p.name)

    # ── 3 y 6. Consulta de movimientos ──────────────────────────────────
    consulta_filtro: str = ""
    movimientos: list[dict] = []
    cargando_mov: bool = False
    detalle_cuotas: list[dict] = []
    detalle_titulo: str = ""

    @rx.event
    def set_consulta_filtro(self, v: str):
        self.consulta_filtro = v

    @rx.event
    async def buscar_movimientos(self):
        self.cargando_mov = True
        self.detalle_cuotas = []
        yield
        await self._recargar_movimientos()

    detalle_numero: str = ""
    detalle_empleado: str = ""
    mover_fecha: str = ""

    @rx.event
    def set_mover_fecha(self, v: str):
        self.mover_fecha = v

    @rx.event
    async def ver_cuotas(self, numero: str, empleado: str, nombre: str):
        fuente = await self._fuente()
        self.detalle_titulo = f"Préstamo N° {numero} — {nombre}"
        self.detalle_numero, self.detalle_empleado = numero, empleado
        self.detalle_cuotas = await asyncio.to_thread(
            registrador.cuotas_prestamo, numero, empleado, fuente
        )

    @rx.event
    async def mover_cuotas(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        if not self.mover_fecha or not self.detalle_numero:
            self.error = "Indica la nueva fecha de inicio."
            return
        try:
            n = await asyncio.to_thread(
                registrador.mover_cuotas_pendientes,
                self.detalle_numero, self.detalle_empleado, self.mover_fecha,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.resultado = f"Se reprogramaron {n} cuota(s)."
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        fuente = await self._fuente()
        self.detalle_cuotas = await asyncio.to_thread(
            registrador.cuotas_prestamo, self.detalle_numero, self.detalle_empleado, fuente
        )

    @rx.event
    async def eliminar_movimiento(self, numero: str, empleado: str, clase: str):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            yield rx.toast.error("Sin permiso.")
            return
        try:
            n = await asyncio.to_thread(
                registrador.eliminar_movimiento, numero, empleado, clase,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.resultado = f"Se borraron {n} fila(s) del movimiento {numero}."
            self.detalle_cuotas = []
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        self.cargando_mov = True
        yield
        await self._recargar_movimientos()

    async def _recargar_movimientos(self):
        fuente = await self._fuente()
        try:
            movs = await asyncio.to_thread(
                registrador.historial_movimientos, fuente, self.consulta_filtro
            )
            self.movimientos = [asdict(m) for m in movs]
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        self.cargando_mov = False

    # ── 4. Registro individual (cualquier tipo) ─────────────────────────
    ind_clase: str = "203"
    ind_valor: str = ""
    ind_fecha: str = ""
    ind_observ: str = ""
    ind_preview: str = ""

    @rx.event
    def set_ind(self, campo: str, v: str):
        setattr(self, f"ind_{campo}", v)

    @rx.event
    async def previsualizar_individual(self):
        self.error = self.resultado = ""
        try:
            valor = float(self.ind_valor)
        except ValueError:
            self.error = "El valor debe ser numérico."
            return
        res = registrador.registrar_movimiento(
            self.emp_sel, self.ind_clase, valor, self.ind_fecha or _hoy(), self.ind_observ,
            usuario="", roles=set(), dry_run=True,
        )
        self.ind_preview = res.detalle if res.ok else ""
        self.error = "" if res.ok else res.detalle

    @rx.event
    async def guardar_individual(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            self.error = "Sin permiso."
            return
        if not self.emp_sel:
            self.error = "Elige un empleado."
            return
        try:
            valor = float(self.ind_valor)
        except ValueError:
            self.error = "El valor debe ser numérico."
            return
        try:
            res = await asyncio.to_thread(
                registrador.registrar_movimiento,
                self.emp_sel, self.ind_clase, valor, self.ind_fecha or _hoy(), self.ind_observ,
                usuario=auth.username, roles=set(auth.roles), dry_run=False,
            )
            if res.ok:
                self.resultado = res.detalle
                self.ind_valor = self.ind_observ = self.ind_preview = ""
                await self._cargar_movimientos_emp()
            else:
                self.error = res.detalle
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    # ── 4b. Carga masiva de egresos / ingresos (grilla editable) ────────
    bulk_pegar: str = ""
    bulk_grid: list[dict] = []
    bulk_job: int = 0
    bulk_status: str = ""
    bulk_msg: str = ""
    bulk_path: str = ""

    @rx.event
    def set_bulk_pegar(self, v: str):
        self.bulk_pegar = v

    @rx.event
    def bulk_nueva_fila(self):
        self.bulk_grid = [*self.bulk_grid, _fila_bi()]

    @rx.event
    def bulk_quitar_fila(self, idx: int):
        self.bulk_grid = [r for i, r in enumerate(self.bulk_grid) if i != idx]

    @rx.event
    def bulk_limpiar(self):
        self.bulk_grid = []
        self.bulk_job = 0
        self.bulk_status = self.bulk_msg = self.bulk_path = ""

    @rx.event
    def bulk_set_celda(self, idx: int, campo: str, v: str):
        g = list(self.bulk_grid)
        if 0 <= idx < len(g):
            g[idx] = {**g[idx], campo: v, "valido": False, "nombre": ""}
            self.bulk_grid = g

    @rx.event
    def bulk_cargar_pegado(self):
        campos = ("codigo", "clase", "valor", "fecha", "observacion")
        filas = []
        for ln in self.bulk_pegar.splitlines():
            if not ln.strip():
                continue
            partes = _split_linea(ln)
            fila = _fila_bi()
            for j, c in enumerate(campos):
                if j < len(partes) and partes[j]:
                    fila[c] = partes[j]
            filas.append(fila)
        if filas:
            self.bulk_grid = filas
            self.bulk_pegar = ""

    @rx.event
    async def bulk_validar(self):
        from core.repos import observaciones

        self.error = ""
        fuente = await self._fuente()
        codigos = sorted({str(r["codigo"]).strip() for r in self.bulk_grid if str(r["codigo"]).strip()})

        def _resolver():
            return {c: (observaciones.buscar_empleados(c, fuente) or [None])[0] for c in codigos}

        cache = await asyncio.to_thread(_resolver)
        nueva = []
        for r in self.bulk_grid:
            cod = str(r["codigo"]).strip()
            e = cache.get(cod)
            clase = str(r["clase"]).strip()
            cfg = registrador.CLASES_SIMPLIFICADAS.get(clase)
            nueva.append({
                **r,
                "empleado": e["empleado"] if e else "",
                "nombre": (e["apellidos_nombres"] if e else ("NO ENCONTRADO" if cod else "")),
                "tipo": registrador.NOMBRE_CLASE.get(clase, clase),
                "valido": bool(e) and cfg is not None and bool(str(r["valor"]).strip()),
            })
        self.bulk_grid = nueva

    @rx.event
    async def aplicar_bulk(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        filas = [f for f in self.bulk_grid if f.get("valido") and f.get("empleado")]
        if not filas:
            return rx.toast.error("Valida primero: no hay filas listas.")
        usuario, roles = auth.username, set(auth.roles)

        def _fn(ctx):
            import csv
            import io

            from core import storage
            from core.repos.registrador import NOMBRE_CLASE, registrar_movimiento

            res = []
            for i, f in enumerate(filas, 1):
                try:
                    r = registrar_movimiento(
                        f["empleado"], str(f["clase"]).strip(), float(f["valor"]),
                        str(f["fecha"])[:10], f.get("observacion") or NOMBRE_CLASE.get(str(f["clase"]).strip(), ""),
                        usuario=usuario, roles=roles, dry_run=False,
                    )
                    res.append({"empleado": f["empleado"], "clase": f["clase"],
                                "ok": r.ok, "detalle": r.detalle})
                except Exception as e:  # noqa: BLE001
                    res.append({"empleado": f["empleado"], "clase": f["clase"],
                                "ok": False, "detalle": str(e)[:150]})
                ctx.progreso(i, len(filas), f"{i}/{len(filas)}")
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=["empleado", "clase", "ok", "detalle"])
            w.writeheader()
            w.writerows(res)
            ruta = storage.guardar(ctx.job_id, "CARGA_EGRESOS_INGRESOS.csv", buf.getvalue().encode("utf-8"))
            ctx.set_resultado(str(ruta))
            ok = sum(1 for r in res if r["ok"])
            ctx.progreso(len(filas), len(filas), f"{ok} OK, {len(res) - ok} con error")

        from core.jobs.runner import get_runner

        self.bulk_path = ""
        self.bulk_job = get_runner().encolar("carga_egr_ing", {"n": len(filas)}, creado_por=usuario, fn=_fn)
        self.bulk_status = "pendiente"
        return RegistradorState.vigilar_bulk

    @rx.event(background=True)
    async def vigilar_bulk(self):
        from core.jobs.runner import leer_job

        for _ in range(1800):
            async with self:
                jid = self.bulk_job
            j = leer_job(jid)
            if j is None:
                return
            async with self:
                self.bulk_status = j.status
                self.bulk_msg = j.message
                self.bulk_path = j.result_path
            if j.status in ("ok", "error", "cancelado"):
                return
            await asyncio.sleep(1)

    @rx.event
    def descargar_bulk(self):
        if not self.bulk_path:
            return
        from pathlib import Path

        p = Path(self.bulk_path)
        return rx.download(data=p.read_bytes(), filename=p.name)

    # ── 6b. Consulta detallada de filas de RPINGDES ────────────────────
    cq_empleado: str = ""
    cq_clase: str = ""
    cq_desde: str = ""
    cq_hasta: str = ""
    cq_numero: str = ""
    cq_solo_pend: bool = False
    cq_filas: list[dict] = []
    cq_cargando: bool = False
    cq_edit_val: dict = {}  # clave -> nuevo valor en edición

    @rx.event
    def set_cq(self, campo: str, v: str):
        setattr(self, f"cq_{campo}", v)

    @rx.event
    def toggle_cq_pend(self):
        self.cq_solo_pend = not self.cq_solo_pend

    @rx.event
    def limpiar_cq(self):
        self.cq_empleado = self.cq_clase = self.cq_desde = self.cq_hasta = self.cq_numero = ""
        self.cq_solo_pend = False

    @rx.event
    async def buscar_filas(self):
        self.cq_cargando = True
        self.error = ""
        yield
        fuente = await self._fuente()
        try:
            filas = await asyncio.to_thread(
                registrador.consultar_filas, fuente,
                empleado=self.cq_empleado, clase=self.cq_clase,
                desde=self.cq_desde, hasta=self.cq_hasta,
                numero=self.cq_numero, solo_pendientes=self.cq_solo_pend,
            )
            self.cq_filas = [asdict(f) for f in filas]
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        self.cq_cargando = False

    @rx.event
    def set_cq_edit(self, clave: str, v: str):
        self.cq_edit_val = {**self.cq_edit_val, clave: v}

    @rx.event
    async def guardar_valor_fila(self, fila: dict):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        clave = f"{fila['numero']}-{fila['empleado']}-{fila['clase']}-{fila['secuencia']}"
        nuevo = self.cq_edit_val.get(clave, "")
        try:
            val = float(nuevo)
        except (TypeError, ValueError):
            return rx.toast.error("Valor inválido.")
        try:
            n = await asyncio.to_thread(
                registrador.editar_valor_fila,
                fila["numero"], fila["empleado"], fila["clase"],
                int(fila["secuencia"]), fila["fecha_ven"], val,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.resultado = f"Valor actualizado ({n} fila)."
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        await self.buscar_filas()

    @rx.event
    async def eliminar_fila(self, fila: dict):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            yield rx.toast.error("Sin permiso.")
            return
        if fila.get("asentado"):
            yield rx.toast.error("La fila ya fue procesada.")
            return
        try:
            n = await asyncio.to_thread(
                registrador.eliminar_fila,
                fila["numero"], fila["empleado"], fila["clase"],
                int(fila["secuencia"]), fila["fecha_ven"],
                usuario=auth.username, roles=set(auth.roles),
            )
            self.resultado = f"Fila eliminada ({n})."
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        yield
        await self.buscar_filas()

    @rx.event
    def exportar_cq_csv(self):
        if not self.cq_filas:
            return
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["N°", "Empleado", "Nombre", "Clase", "Concepto", "Observación",
                    "Secuencia", "Vence", "Valor", "Estado"])
        for f in self.cq_filas:
            w.writerow([f["numero"], f["empleado"], f["nombre"], f["clase"], f["concepto"],
                        f["observ"], f["secuencia"], f["fecha_ven"], f["valor"],
                        "Procesado" if f["asentado"] else "Pendiente"])
        return rx.download(
            data=("﻿" + buf.getvalue()).encode("utf-8"),
            filename="movimientos_rpingdes.csv",
        )

    # ── 5. BIESS quirografarios / hipotecarios ─────────────────────────
    periodo: str = ""
    _biess_bytes: bytes = b""
    biess_archivo: str = ""
    biess_tipo: str = "204"            # 204 quirografario | 207 hipotecario
    biess_fecha: str = ""
    biess_obs: str = ""
    biess_fila: str = "18"
    biess_col_ced: str = "E"
    biess_col_val: str = "AA"
    biess_confianza: float = 0.0
    biess_diag: list[list[str]] = []
    biess_ver_diag: bool = False
    filas_biess: list[dict] = []       # [{'cedula','valor'}]
    avisos: list[str] = []
    movs: list[dict] = []              # [{'empleado','cedula','nombre','valor','estado_biess'}]
    dry: dict = {}

    @rx.event
    def set_periodo(self, v: str):
        self.periodo = v.strip()

    @rx.event
    def set_biess(self, campo: str, v: str):
        setattr(self, f"biess_{campo}", v)
        if campo in ("tipo", "fecha"):
            self.biess_obs = registrador.observacion_biess(
                self.biess_tipo, self.biess_fecha or _hoy()
            )

    @rx.event
    def toggle_biess_diag(self):
        self.biess_ver_diag = not self.biess_ver_diag

    @rx.event
    async def subir_biess(self, files: list[rx.UploadFile]):
        if not files:
            return
        from core.excel.parsers import biess_autodetectar, biess_diagnostico

        datos = await files[0].read()
        self._biess_bytes = datos
        self.biess_archivo = files[0].name or "archivo.xlsx"
        self.filas_biess = []
        self.movs = []
        self.dry = {}
        self.resultado = self.error = ""
        det = await asyncio.to_thread(biess_autodetectar, datos)
        self.biess_fila = str(det["fila"])
        self.biess_col_ced = det["col_cedula"]
        self.biess_col_val = det["col_valor"]
        self.biess_confianza = det["confianza"]
        self.biess_diag = await asyncio.to_thread(biess_diagnostico, datos)
        if not self.biess_fecha:
            self.biess_fecha = _hoy()
        self.biess_obs = registrador.observacion_biess(self.biess_tipo, self.biess_fecha)
        await self._releer_biess()

    async def _releer_biess(self):
        from core.excel.parsers import parse_biess_manual

        if not self._biess_bytes:
            return
        try:
            filas, errores = await asyncio.to_thread(
                parse_biess_manual, self._biess_bytes,
                fila_inicio=int(self.biess_fila or 1),
                col_cedula=self.biess_col_ced, col_valor=self.biess_col_val,
            )
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo leer con esas columnas: {e}"
            return
        self.filas_biess = filas
        self.avisos = errores[:50]
        self.movs = []
        self.dry = {}

    @rx.event
    async def releer_biess(self):
        await self._releer_biess()

    @rx.event
    async def preparar_biess(self):
        if not self.filas_biess:
            return
        periodo = self.periodo or _periodo()
        filas = list(self.filas_biess)
        clase = self.biess_tipo

        def _prep():
            movs, avisos = registrador.preparar_biess(filas, periodo, clase=clase)
            dry = registrador.postear_biess(
                movs, clase=clase, fecha=(self.biess_fecha or _hoy()),
                observacion=self.biess_obs, usuario="", roles=set(), dry_run=True,
            )
            return (
                [{"empleado": m.empleado, "cedula": m.cedula, "nombre": m.nombre,
                  "valor": m.valor, "estado_biess": m.estado_biess} for m in movs],
                avisos, dry,
            )

        self.movs, avisos, self.dry = await asyncio.to_thread(_prep)
        self.avisos = avisos[:50]

    @rx.event
    async def postear_biess(self):
        auth = await self.get_state(AuthState)
        if "registrador:registrar_rpingdes" not in auth.permisos_flat:
            self.error = "Sin permiso."
            return
        if not self.biess_obs.strip():
            self.error = "La observación es obligatoria."
            return
        periodo = self.periodo or _periodo()
        filas = list(self.filas_biess)
        clase, fecha, obs = self.biess_tipo, (self.biess_fecha or _hoy()), self.biess_obs
        usuario, roles = auth.username, set(auth.roles)
        self.error = ""

        def _post():
            movs, _ = registrador.preparar_biess(filas, periodo, clase=clase)
            return registrador.postear_biess(
                movs, clase=clase, fecha=fecha, observacion=obs,
                usuario=usuario, roles=roles, dry_run=False,
            )

        try:
            res = await asyncio.to_thread(_post)
            self.resultado = (
                f"BIESS N° {res['numero']:05d}: {res['insertados']} registrados · "
                f"liquidados {res['liquidados']} · sin empleado {res['no_encontrados']} · "
                f"total ${res['total']:.2f}"
            )
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    @rx.event
    def exportar_biess(self):
        if not self.movs:
            return
        import csv
        import io

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Cédula", "Código", "Nombre", "Valor", "Estado"])
        for m in self.movs:
            w.writerow([m["cedula"], m["empleado"], m["nombre"], m["valor"], m["estado_biess"]])
        return rx.download(data=("﻿" + buf.getvalue()).encode("utf-8"), filename="biess_consolidado.csv")
