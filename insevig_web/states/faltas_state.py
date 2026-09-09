"""Estado del módulo FALTAS (Gestión de Faltas / Permisos / Suspensiones /
Restas de Horas). 4 pestañas del legado `gestion_faltas.py` → 4 rutas.

Todas las llamadas a `core/` van por `asyncio.to_thread` (event loop libre).
Escrituras: `core.repos.faltas` con `dry_run` (vista previa) → confirmar → ejecutar.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt

import reflex as rx

from core.faltas import calculo as fc
from core.repos import faltas as repo
from insevig_web.states.auth_state import AuthState

_HOY = dt.date.today()

TIPOS_INDIVIDUAL = list(fc.TIPOS_REGISTRO_UNO_A_UNO)
TIPOS_MASIVO = ["FALTA", "PERMISO", "SUSPENSIÓN"]


def _roles(auth: AuthState) -> set[str]:
    return set(auth.roles or [])


class FaltasState(rx.State):
    # ── período compartido ─────────────────────────────────────────────
    anio: int = _HOY.year
    mes: int = _HOY.month

    @rx.var
    def vence_txt(self) -> str:
        try:
            return fc.obtener_fecha_fin_mes(self.anio, self.mes).strftime("%d/%m/%Y")
        except ValueError:
            return "—"

    @rx.event
    def set_anio(self, v: str):
        self.anio = int(v or _HOY.year)

    @rx.event
    def set_mes(self, v: str):
        self.mes = max(1, min(12, int(v or _HOY.month)))

    # ── buscador de empleado (compartido individual / masivo) ──────────
    emp_texto: str = ""
    emp_resultados: list[dict] = []
    emp_buscando: bool = False

    @rx.event
    def set_emp_texto(self, v: str):
        self.emp_texto = v

    @rx.event(background=True)
    async def buscar_empleado(self):
        termino = self.emp_texto.strip()
        if not termino:
            async with self:
                self.emp_resultados = []
            return
        async with self:
            self.emp_buscando = True
        try:
            res = await asyncio.to_thread(repo.buscar_empleados_texto, termino, 20)
        finally:
            async with self:
                self.emp_buscando = False
        async with self:
            self.emp_resultados = [dataclasses.asdict(e) | {"nombre": e.nombre} for e in res]

    # ═══════════════════════ 1. REGISTRO MASIVO ═══════════════════════
    masivo_pegado: str = ""
    masivo_filas: list[dict] = []        # {codigo,nombre,tipo,cant,fecha,observ,estado,detalle}
    masivo_log: list[dict] = []          # {nivel,texto}
    masivo_procesando: bool = False

    @rx.event
    def set_masivo_pegado(self, v: str):
        self.masivo_pegado = v

    @rx.event
    def masivo_cargar_pegado(self):
        """Parsea el TSV pegado a filas (una por línea)."""
        filas: list[dict] = []
        for linea in self.masivo_pegado.splitlines():
            if not linea.strip():
                continue
            vals = fc.parse_linea_pegado(linea)
            campos = fc.mapear_pegado_a_campos(0, vals)
            filas.append({
                "codigo": campos.get("codigo", ""), "nombre": "",
                "tipo": (campos.get("tipo", "") or "").upper(),
                "cant": campos.get("cant", ""), "fecha": campos.get("fecha", ""),
                "observ": campos.get("observ", ""), "estado": "", "detalle": "",
            })
        self.masivo_filas = filas
        self.masivo_log = []

    @rx.event
    def masivo_limpiar(self):
        self.masivo_pegado = ""
        self.masivo_filas = []
        self.masivo_log = []

    @rx.event(background=True)
    async def masivo_validar(self):
        """Resuelve nombres por código y marca filas válidas (botón VALIDAR)."""
        async with self:
            filas = list(self.masivo_filas)
        for f in filas:
            emp = await asyncio.to_thread(repo.buscar_empleado, codigo=f["codigo"]) if f["codigo"] else None
            f["nombre"] = emp.nombre if emp else "(no encontrado)"
            ok, err = fc.validar_fila_grid_masivo(f["codigo"], f["tipo"], f["cant"], f["fecha"])
            if ok and emp is None:
                ok, err = False, "código no existe en la nómina"
            f["estado"] = "ok" if ok else "error"
            f["detalle"] = "" if ok else (err or "inválida")
        async with self:
            self.masivo_filas = filas

    @rx.event(background=True)
    async def masivo_registrar(self):
        """Registra todas las filas válidas (botón REGISTRAR TODO)."""
        async with self:
            self.masivo_procesando = True
            self.masivo_log = []
            filas = list(self.masivo_filas)
            anio, mes = self.anio, self.mes
        auth = await self.get_state(AuthState)
        usuario, roles = auth.username, _roles(auth)
        log: list[dict] = []
        exitos = errores = 0
        for f in filas:
            ok, err, fecha = fc.validar_fila_registro(f["codigo"], f["tipo"], f["cant"], f["fecha"])
            if not ok:
                errores += 1
                log.append({"nivel": "error", "texto": f"{f['codigo']}: {err}"})
                continue
            try:
                v = await asyncio.to_thread(
                    repo.registrar, f["codigo"], f["tipo"], int(f["cant"]),
                    fecha.strftime("%d/%m/%Y"), anio, mes, f["observ"],
                    usuario=usuario, roles=roles, dry_run=False,
                )
            except Exception as e:  # noqa: BLE001
                errores += 1
                log.append({"nivel": "error", "texto": f"{f['codigo']}: {e}"})
                continue
            if v.ok:
                exitos += 1
                log.append({"nivel": "ok", "texto": f"{f['codigo']} · {v.detalle}"})
            else:
                errores += 1
                log.append({"nivel": "error", "texto": f"{f['codigo']}: {v.error}"})
        log.append({"nivel": "info", "texto": f"Listo: {exitos} registrados, {errores} con error."})
        async with self:
            self.masivo_log = log
            self.masivo_procesando = False

    @rx.var
    def masivo_conteo(self) -> str:
        ok = sum(1 for f in self.masivo_filas if f["estado"] == "ok")
        err = sum(1 for f in self.masivo_filas if f["estado"] == "error")
        return f"{len(self.masivo_filas)} filas · {ok} válidas · {err} con error"

    def elegir_emp_masivo(self, cod: str, nombre: str):
        # añade una fila con ese empleado
        self.masivo_filas = [
            *self.masivo_filas,
            {"codigo": cod, "nombre": nombre, "tipo": "FALTA", "cant": "1",
             "fecha": "", "observ": "", "estado": "", "detalle": ""},
        ]

    # ═══════════════════════ 2. REGISTRO UNO A UNO ═══════════════════════
    ind_codigo: str = ""
    ind_nombre: str = ""
    ind_tipo: str = "FALTA"
    ind_cantidad: str = "1"
    ind_fecha_evento: str = _HOY.isoformat()
    ind_fecha_inicio: str = _HOY.isoformat()      # SUSPENSIÓN: fecha de inicio
    ind_observ: str = ""
    ind_descontar: bool = True
    ind_preview: dict = {}                          # Vista.__dict__ del dry_run
    ind_msg: str = ""
    ind_error: str = ""

    @rx.event
    def set_ind_tipo(self, v: str):
        self.ind_tipo = v
        self.ind_preview = {}

    @rx.event
    def set_ind_codigo(self, v: str):
        self.ind_codigo = v

    @rx.event
    def set_ind_cantidad(self, v: str):
        self.ind_cantidad = v

    @rx.event
    def set_ind_fecha_evento(self, v: str):
        self.ind_fecha_evento = v

    @rx.event
    def set_ind_fecha_inicio(self, v: str):
        self.ind_fecha_inicio = v

    @rx.event
    def set_ind_observ(self, v: str):
        self.ind_observ = v

    @rx.event
    def toggle_ind_descontar(self, v: bool):
        self.ind_descontar = bool(v)

    @rx.var
    def ind_es_suspension(self) -> bool:
        return self.ind_tipo in ("SUSPENSIÓN", "LEVANTAMIENTO SUSPENSIÓN")

    @rx.var
    def ind_preview_detalle(self) -> str:
        return str(self.ind_preview.get("detalle", "")) if self.ind_preview else ""

    @rx.var
    def ind_preview_observ(self) -> str:
        return str(self.ind_preview.get("observ", "")) if self.ind_preview else ""

    @rx.var
    def ind_alerta_msg(self) -> str:
        al = self.ind_preview.get("alerta") if self.ind_preview else None
        return str(al.get("mensaje", "")) if al else ""

    @rx.var
    def ind_descuento_txt(self) -> str:
        d = self.ind_preview.get("descuento") if self.ind_preview else None
        if not d:
            return ""
        return (
            f"Porcentaje {d.get('pct', 0)}%  ·  HOR25 −{d.get('HOR25', 0)}  ·  "
            f"HOR50 −{d.get('HOR50', 0)}  ·  HOR100 −{d.get('HOR100', 0)}"
        )

    @rx.event(background=True)
    async def ind_buscar_nombre(self):
        cod = self.ind_codigo.strip()
        if not cod:
            return
        emp = await asyncio.to_thread(repo.buscar_empleado, codigo=cod)
        async with self:
            self.ind_nombre = emp.nombre if emp else "(no encontrado)"

    def elegir_emp_individual(self, cod: str, nombre: str):
        self.ind_codigo = cod
        self.ind_nombre = nombre
        self.emp_resultados = []

    def _fecha_para_repo(self) -> str:
        if self.ind_tipo == "SUSPENSIÓN":
            return self.ind_fecha_inicio
        return self.ind_fecha_evento

    @rx.event(background=True)
    async def ind_previsualizar(self):
        async with self:
            self.ind_error = ""
            self.ind_msg = ""
            args = (self.ind_codigo.strip(), self.ind_tipo, self._cant(),
                    self._fecha_para_repo(), self.anio, self.mes, self.ind_observ)
            descontar = self.ind_descontar
        if not args[0]:
            async with self:
                self.ind_error = "Ingresá un código de empleado."
            return
        v = await asyncio.to_thread(
            repo.registrar, *args, descontar_horas_extra=descontar, dry_run=True,
        )
        async with self:
            self.ind_preview = dataclasses.asdict(v)
            if not v.ok:
                self.ind_error = v.error

    def _cant(self) -> int:
        try:
            return max(0, int(self.ind_cantidad or "0"))
        except ValueError:
            return 0

    @rx.event(background=True)
    async def ind_registrar(self):
        async with self:
            args = (self.ind_codigo.strip(), self.ind_tipo, self._cant(),
                    self._fecha_para_repo(), self.anio, self.mes, self.ind_observ)
            descontar = self.ind_descontar
        auth = await self.get_state(AuthState)
        try:
            v = await asyncio.to_thread(
                repo.registrar, *args, descontar_horas_extra=descontar,
                usuario=auth.username, roles=_roles(auth), dry_run=False,
            )
        except Exception as e:  # noqa: BLE001
            async with self:
                self.ind_error = str(e)
            return
        async with self:
            self.ind_preview = dataclasses.asdict(v)
            if v.ok:
                self.ind_msg = f"Registrado: {v.detalle}"
                self.ind_observ = ""
                self.ind_cantidad = "1"
            else:
                self.ind_error = v.error

    # ═══════════════════════ 3. VER / EDITAR PERÍODO ═══════════════════════
    per_historicas: bool = False
    per_filas: list[dict] = []
    per_cargando: bool = False
    per_msg: str = ""

    # edición
    edit_abierto: bool = False
    edit_empleado: str = ""
    edit_fecha_ven: str = ""
    edit_totaus: str = ""
    edit_observ: str = ""

    @rx.event
    def toggle_historicas(self, v: bool):
        self.per_historicas = bool(v)

    @rx.var
    def per_editable(self) -> bool:
        return not self.per_historicas

    async def _recargar_periodo(self):
        anio, mes, hist = self.anio, self.mes, self.per_historicas
        filas = await asyncio.to_thread(repo.listar_periodo, anio, mes, historicas=hist)
        self.per_filas = [dataclasses.asdict(f) for f in filas]
        self.per_msg = f"{len(filas)} registros" if filas else "Sin registros en el período."

    @rx.event
    async def per_cargar(self):
        self.per_cargando = True
        yield
        try:
            await self._recargar_periodo()
        finally:
            self.per_cargando = False

    def abrir_edicion(self, fila: dict):
        self.edit_empleado = fila["empleado"]
        self.edit_fecha_ven = fila["fecha_ven"]
        self.edit_totaus = str(fila["totaus"])
        self.edit_observ = fila["observ"]
        self.edit_abierto = True

    @rx.event
    def cerrar_edicion(self):
        self.edit_abierto = False

    @rx.event
    def set_edit_totaus(self, v: str):
        self.edit_totaus = v

    @rx.event
    def set_edit_observ(self, v: str):
        self.edit_observ = v

    @rx.event
    async def guardar_edicion(self):
        emp, fv = self.edit_empleado, self.edit_fecha_ven
        try:
            totaus = float(self.edit_totaus or "0")
        except ValueError:
            self.per_msg = "TOTAUS inválido."
            return
        observ = self.edit_observ
        auth = await self.get_state(AuthState)
        v = await asyncio.to_thread(
            repo.editar_registro, emp, fv, totaus, observ,
            usuario=auth.username, roles=_roles(auth), dry_run=False,
        )
        self.edit_abierto = False
        self.per_msg = v.detalle if v.ok else (v.error or "error")
        await self._recargar_periodo()

    @rx.event
    async def eliminar_fila_periodo(self, fila: dict):
        auth = await self.get_state(AuthState)
        v = await asyncio.to_thread(
            repo.eliminar_registro, fila["empleado"], fila["fecha_ven"],
            usuario=auth.username, roles=_roles(auth), dry_run=False,
        )
        self.per_msg = v.detalle if v.ok else (v.error or "error")
        await self._recargar_periodo()

    @rx.event
    async def per_exportar(self):
        from core.excel.faltas_builders import periodo_xlsx

        anio, mes = self.anio, self.mes
        filas = self.per_filas
        data = await asyncio.to_thread(periodo_xlsx, filas, anio, mes)
        return rx.download(data=data, filename=f"faltas_{anio}{mes:02d}.xlsx")

    # ═══════════════════════ 4. CARGADOR DE RESTAS ═══════════════════════
    restas_filas: list[dict] = []
    restas_cargando: bool = False
    restas_msg: str = ""
    restas_ejecutado: bool = False

    @rx.event
    async def restas_subir(self, archivos: list[rx.UploadFile]):
        if not archivos:
            return
        self.restas_cargando = True
        self.restas_msg = ""
        self.restas_ejecutado = False
        anio, mes = self.anio, self.mes
        yield
        try:
            contenido = await archivos[0].read()
            filas, err = await asyncio.to_thread(_leer_excel_bytes, contenido)
            if err:
                self.restas_msg = err
                return
            conteo = fc.contar_faltas_por_cedula(filas, anio, mes)
            emps = await asyncio.to_thread(repo.empleados_por_cedulas, list(conteo.keys()))
            resultados = fc.calcular_resultados_resta(conteo, emps)
            self.restas_filas = resultados
            oks = sum(1 for r in resultados if r["ESTADO"] == "OK")
            self.restas_msg = f"{len(resultados)} empleados con faltas · {oks} con resta aplicable."
        finally:
            self.restas_cargando = False

    @rx.event(background=True)
    async def restas_ejecutar(self):
        async with self:
            filas = list(self.restas_filas)
        auth = await self.get_state(AuthState)
        res = await asyncio.to_thread(
            repo.aplicar_restas, filas, usuario=auth.username, roles=_roles(auth), dry_run=False,
        )
        async with self:
            self.restas_ejecutado = True
            self.restas_msg = f"Aplicadas {res['aplicados']} de {res['aplicables']} restas."

    @rx.event
    def restas_limpiar(self):
        self.restas_filas = []
        self.restas_msg = ""
        self.restas_ejecutado = False


def _leer_excel_bytes(contenido: bytes) -> tuple[list[dict], str]:
    """Lee el Excel de faltas desde bytes (equivalente a `leer_excel_faltas`)."""
    import io

    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        return [], f"pandas no disponible: {e}"
    try:
        df = pd.read_excel(io.BytesIO(contenido))
    except Exception as e:  # noqa: BLE001
        return [], f"No se pudo leer el Excel: {e}"
    df.columns = [str(c).strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "ced" in cl:
            col_map[c] = "Cedula"
        elif "fecha" in cl:
            col_map[c] = "Fecha_Falta"
        elif "tipo" in cl:
            col_map[c] = "Tipo_Falta"
    df = df.rename(columns=col_map)
    if "Cedula" not in df.columns or "Fecha_Falta" not in df.columns:
        return [], f"Se requieren columnas Cedula y Fecha_Falta. Encontradas: {list(df.columns)}"
    df["Fecha_Falta"] = pd.to_datetime(df["Fecha_Falta"], errors="coerce")
    df = df.dropna(subset=["Fecha_Falta"])
    return [
        {"cedula": row.get("Cedula"), "fecha": row["Fecha_Falta"].date(), "tipo": row.get("Tipo_Falta")}
        for _, row in df.iterrows()
    ], ""
