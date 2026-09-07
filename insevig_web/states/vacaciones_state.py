"""Estado del módulo VACACIONES — búsqueda de empleado, GOCE/PAGO, cálculo y reportes.

Porta las pantallas de `VACACIONES_SISTEMA_INSEVIG/app.py`: panel de búsqueda +
tabs Historial/Gozadas/Pagadas/Cálculo/Reportes. Toda la lógica vive en
`core.repos.vacaciones` — este state solo orquesta UI + permisos, igual que
`BitacoraState`.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from contextlib import suppress

import reflex as rx

from core.repos import vacaciones as V
from core.utils import a_float
from insevig_web.states.auth_state import AuthState

ESTADOS_DOC = list(V.ESTADOS_DOC)
FORMAS_PAGO = ("TRANSFERENCIA", "CHEQUE", "EFECTIVO")

_FORM_GOZADA_VACIO = {
    "periodo": "", "fecha_comprobante": "", "desde": "", "hasta": "",
    "dias_tomados": "15", "dias_adicionales": "0", "firmado": "",
    "lo_cubrio_agente": "", "referencia": "", "estado_doc": "completado",
    "observaciones": "",
}

_FORM_PAGO_VACIO = {
    "forma_pago": "TRANSFERENCIA", "banco": "", "cta_cte_no": "",
    "no_cheque": "", "fecha_pago": "", "anticipo": "0", "observaciones": "",
}


def _fecha_es(iso: str) -> str:
    """'2026-09-06' -> '06/09/2026' (formato del comprobante de anticipo). Vacío si no parsea."""
    try:
        return dt.datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


class VacacionesState(rx.State):
    tab: str = "dashboard"

    # ── Dashboard "Pendientes de Firma" ────────────────────────────────────
    # Porta app.py::_build_tab_dashboard/_cargar_dashboard/_poblar_dashboard.
    # No es por-empleado — se carga solo, sin buscar/seleccionar antes.
    dash_n_activos: int = 0
    dash_n_sin_firmar: int = 0
    dash_n_pagadas_sin_firmar: int = 0
    dash_n_gozadas_anio: int = 0
    dash_n_pagadas_anio: int = 0
    dash_top5: list[dict] = []
    dash_pendientes_periodos: list[dict] = []
    dash_cargando: bool = False
    dash_actualizado: str = ""
    dash_error: str = ""

    # "Ver todos los sin firmar..." (ventana aparte en el .pyw, acá un panel)
    dash_mostrar_todos: bool = False
    dash_todos_sf: list[dict] = []
    dash_todos_cargando: bool = False
    dash_seleccionados: list[int] = []

    @rx.event
    async def cargar_dashboard(self):
        self.dash_cargando = True
        self.dash_error = ""
        yield
        try:
            s = await asyncio.to_thread(V.dashboard_stats)
            self.dash_n_activos = s["n_activos"]
            self.dash_n_sin_firmar = s["n_sin_firmar"]
            self.dash_n_pagadas_sin_firmar = s["n_pagadas_sin_firmar"]
            self.dash_n_gozadas_anio = s["n_gozadas_anio"]
            self.dash_n_pagadas_anio = s["n_pagadas_anio"]
            self.dash_top5 = s["top5_sin_firmar"]
            self.dash_pendientes_periodos = s["pendientes_periodos"]
            self.dash_actualizado = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        except Exception as e:  # noqa: BLE001
            self.dash_error = f"No se pudo cargar (¿hay conexión?): {e}"
        self.dash_cargando = False

    @rx.event
    async def abrir_ver_todos_sf(self):
        self.dash_mostrar_todos = True
        self.dash_seleccionados = []
        self.dash_todos_cargando = True
        yield
        try:
            self.dash_todos_sf = await asyncio.to_thread(V.sin_firmar_activos)
        except Exception as e:  # noqa: BLE001
            self.dash_error = f"No se pudo cargar: {e}"
        self.dash_todos_cargando = False

    @rx.event
    def cerrar_ver_todos_sf(self):
        self.dash_mostrar_todos = False

    @rx.event
    def toggle_seleccion_dash(self, vac_id: int):
        if vac_id in self.dash_seleccionados:
            self.dash_seleccionados = [v for v in self.dash_seleccionados if v != vac_id]
        else:
            self.dash_seleccionados = [*self.dash_seleccionados, vac_id]

    @rx.event
    async def marcar_seleccionados_firmado(self):
        auth = await self.get_state(AuthState)
        if "vacaciones:editar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        if not self.dash_seleccionados:
            self.msg = "Seleccione registros."
            return
        ids, usuario, roles = list(self.dash_seleccionados), auth.username, set(auth.roles)

        def _marcar_todos():
            errores = []
            for vid in ids:
                try:
                    V.marcar_firmada(vid, usuario=usuario, roles=roles)
                except Exception as e:  # noqa: BLE001
                    errores.append(str(e))
            return errores

        errores = await asyncio.to_thread(_marcar_todos)
        self.msg = (
            f"{len(ids) - len(errores)} registro(s) marcado(s) como firmado."
            if not errores else f"Algunos registros no pudieron marcarse: {errores[0]}"
        )
        self.dash_seleccionados = []
        await self.abrir_ver_todos_sf()
        await self.cargar_dashboard()

    # ── Confirmación de "período anterior pendiente" ──────────────────────
    # Porta app.py::_confirmar_periodo_prioritario: al guardar una gozada o
    # una pagada, si hay períodos MÁS ANTIGUOS que el que se está guardando
    # con días pendientes, se pregunta antes de continuar (el messagebox
    # bloqueante del .pyw se vuelve un diálogo modal aquí — mismo criterio de
    # "sí, guardar igual" / "no, cancelar").
    mostrar_confirmar_periodo: bool = False
    confirmar_periodo_detalle: list[dict] = []
    _accion_pendiente: str = ""  # "gozada" | "pagada"

    @rx.event
    async def confirmar_periodo_continuar(self):
        auth = await self.get_state(AuthState)
        self.mostrar_confirmar_periodo = False
        accion, self._accion_pendiente = self._accion_pendiente, ""
        if accion == "gozada":
            await self._guardar_gozada_ahora(auth)
        elif accion == "pagada":
            await self._registrar_pagada_ahora(auth)

    @rx.event
    def confirmar_periodo_cancelar(self):
        self.mostrar_confirmar_periodo = False
        self._accion_pendiente = ""

    # ── Búsqueda de empleado ─────────────────────────────────────────────
    query: str = ""
    resultados: list[dict] = []
    buscando: bool = False
    error: str = ""
    msg: str = ""

    empleado: dict = {}
    resumen: dict = {}
    alertas: dict[str, list[dict]] = {"pendientes": [], "sin_firmar": []}
    gozadas: list[dict] = []
    pagadas: list[dict] = []
    periodos_emp: list[str] = []  # solo las etiquetas ('2024-2025', ...) — los
    # dicts de core.repos.vacaciones.periodos_disponibles traen `date` crudos,
    # no serializables como Var de estado.

    @rx.event
    def set_query(self, v: str):
        self.query = v

    @rx.event
    async def buscar(self):
        if len(self.query.strip()) < 3:
            self.error = "Ingrese al menos 3 caracteres."
            return
        self.buscando = True
        self.error = ""
        yield
        try:
            self.resultados = await asyncio.to_thread(V.buscar_empleados, self.query.strip())
            if not self.resultados:
                self.error = "Sin resultados."
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo buscar (¿hay conexión?): {e}"
        self.buscando = False

    @rx.event
    async def seleccionar(self, emp: dict):
        self.empleado = emp
        self.msg = ""
        self.tab = "resumen"
        yield
        await self._cargar_empleado()

    async def _cargar_empleado(self):
        cedula = self.empleado.get("cedula", "")
        fi = self.empleado.get("fecha_ingreso", "")
        if not cedula:
            return
        try:
            self.resumen = await asyncio.to_thread(V.resumen_empleado, cedula)
            self.alertas = await asyncio.to_thread(V.get_alertas, cedula, fi)
            self.gozadas = await asyncio.to_thread(V.get_vacaciones_empleado, cedula, "gozada")
            self.pagadas = await asyncio.to_thread(V.get_vacaciones_empleado, cedula, "pagada")
            periodos = await asyncio.to_thread(V.periodos_disponibles, fi, None, 6) if fi else []
            self.periodos_emp = [p["label"] for p in periodos]
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo cargar el empleado: {e}"

    @rx.event
    def set_tab(self, v: str):
        self.tab = v
        if v == "dashboard":
            return VacacionesState.cargar_dashboard
        return None

    # ── Nueva / editar gozada ─────────────────────────────────────────────
    form_gozada: dict[str, str] = dict(_FORM_GOZADA_VACIO)
    mostrar_form_gozada: bool = False
    editando_gozada_id: int = 0  # 0 = nueva; >0 = editando ese registro. Porta
    # `app.py::_nueva_gozada`/`_editar_gozada` (mismo diálogo `DlgGozada` para
    # ambos casos, distinguido por si trae `vacacion` o no).

    @rx.event
    def nueva_gozada(self):
        form = dict(_FORM_GOZADA_VACIO)
        if self.periodos_emp:
            form["periodo"] = self.periodos_emp[0]  # ya es la etiqueta (str), no un dict
        form["fecha_comprobante"] = dt.date.today().strftime("%Y-%m-%d")
        self.form_gozada = form
        self.editando_gozada_id = 0
        self.mostrar_form_gozada = True
        self.msg = ""

    @rx.event
    def editar_gozada(self, vac: dict):
        self.form_gozada = {k: ("" if vac.get(k) in (None, False) else str(vac.get(k))) for k in _FORM_GOZADA_VACIO}
        self.editando_gozada_id = int(vac.get("id") or 0)
        self.mostrar_form_gozada = True
        self.msg = ""

    @rx.event
    def set_campo_gozada(self, campo: str, v: str):
        self.form_gozada = {**self.form_gozada, campo: v}

    @rx.event
    def cerrar_form_gozada(self):
        self.mostrar_form_gozada = False

    @rx.event
    async def guardar_gozada(self):
        auth = await self.get_state(AuthState)
        accion = "editar" if self.editando_gozada_id else "crear"
        if f"vacaciones:{accion}" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        # Advertir si hay períodos anteriores pendientes — solo al crear, no
        # al editar (igual que app.py::DlgGozada._guardar).
        if not self.editando_gozada_id:
            cedula = self.empleado.get("cedula", "")
            fi = self.empleado.get("fecha_ingreso", "")
            periodo = self.form_gozada.get("periodo", "")
            if cedula and fi and periodo:
                anteriores = await asyncio.to_thread(V.periodos_anteriores_pendientes, cedula, fi, periodo)
                if anteriores:
                    self.confirmar_periodo_detalle = anteriores
                    self._accion_pendiente = "gozada"
                    self.mostrar_confirmar_periodo = True
                    return
        await self._guardar_gozada_ahora(auth)

    async def _guardar_gozada_ahora(self, auth):
        try:
            if self.editando_gozada_id:
                datos_upd = dict(self.form_gozada)
                for campo in ("dias_tomados", "dias_adicionales"):
                    with suppress(ValueError):
                        datos_upd[campo] = int(datos_upd.get(campo) or 0)
                await asyncio.to_thread(
                    V.actualizar, self.editando_gozada_id, datos_upd,
                    usuario=auth.username, roles=set(auth.roles),
                )
                self.msg = "Vacación gozada actualizada."
            else:
                datos = {**self.form_gozada, "cedula": self.empleado.get("cedula", "")}
                await asyncio.to_thread(V.crear_gozada, datos, usuario=auth.username, roles=set(auth.roles))
                self.msg = "Vacación gozada registrada."
            self.mostrar_form_gozada = False
            await self._cargar_empleado()
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error: {e}"

    @rx.event
    async def firmar_gozada(self, vac_id: int):
        auth = await self.get_state(AuthState)
        if "vacaciones:editar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        await asyncio.to_thread(V.marcar_firmada, vac_id, usuario=auth.username, roles=set(auth.roles))
        await self._cargar_empleado()

    @rx.event
    async def eliminar_vacacion(self, vac_id: int):
        auth = await self.get_state(AuthState)
        if "vacaciones:eliminar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        await asyncio.to_thread(V.eliminar, vac_id, usuario=auth.username, roles=set(auth.roles))
        await self._cargar_empleado()

    @rx.event
    async def descargar_comprobante(self, vac_id: int):
        """PDF individual GOCE/PAGO con QR. Porta `data_extractor.get_vacacion_data`
        + `pdf_generator.generar_pago/goce_pdf` (`core/pdf/vacaciones_comprobante.py`)."""
        def _fn() -> bytes:
            from core.pdf.vacaciones_comprobante import comprobante_pdf

            d = V.datos_comprobante(vac_id)
            return comprobante_pdf(d, V.qr_texto(d))

        try:
            data = await asyncio.to_thread(_fn)
        except Exception as e:  # noqa: BLE001
            self.msg = f"No se pudo generar el PDF: {e}"
            return
        return rx.download(data=data, filename=f"comprobante_vacaciones_{vac_id}.pdf")

    # ── Editar pagada existente ───────────────────────────────────────────
    # Porta `app.py::_editar_pagada` (reabre `DlgPagada` con los valores
    # actuales). Reusa el shape de `form_pago` + los campos de valores.
    form_editar_pagada: dict[str, str] = {}
    editando_pagada_id: int = 0
    mostrar_form_editar_pagada: bool = False

    _CAMPOS_EDITAR_PAGADA = (
        "periodo", "total_periodo", "vacaciones_calc", "dias_adicionales",
        "anticipo", "total_pagar", "forma_pago", "banco", "cta_cte_no",
        "no_cheque", "fecha_pago", "estado_doc", "observaciones",
    )

    @rx.event
    def editar_pagada(self, vac: dict):
        self.form_editar_pagada = {
            k: ("" if vac.get(k) in (None, False) else str(vac.get(k))) for k in self._CAMPOS_EDITAR_PAGADA
        }
        self.editando_pagada_id = int(vac.get("id") or 0)
        self.mostrar_form_editar_pagada = True
        self.msg = ""

    @rx.event
    def set_campo_editar_pagada(self, campo: str, v: str):
        self.form_editar_pagada = {**self.form_editar_pagada, campo: v}

    @rx.event
    def cerrar_form_editar_pagada(self):
        self.mostrar_form_editar_pagada = False

    @rx.event
    async def guardar_edicion_pagada(self):
        auth = await self.get_state(AuthState)
        if "vacaciones:editar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        if not self.editando_pagada_id:
            return
        datos = dict(self.form_editar_pagada)
        for campo in ("total_periodo", "vacaciones_calc", "dias_adicionales", "anticipo", "total_pagar"):
            with suppress(ValueError):
                datos[campo] = float(datos.get(campo) or 0)
        try:
            await asyncio.to_thread(
                V.actualizar, self.editando_pagada_id, datos, usuario=auth.username, roles=set(auth.roles)
            )
            self.msg = "Vacación pagada actualizada."
            self.mostrar_form_editar_pagada = False
            await self._cargar_empleado()
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error: {e}"

    # ── Completar pago pendiente (cheque) ─────────────────────────────────
    # Porta `app.py::DlgRegistrarPago`/`_registrar_pago`: una pagada creada con
    # forma_pago='CHEQUE' queda `estado_doc='pendiente'` hasta que financiero
    # ingresa el número de cheque.
    form_registrar_pago: dict[str, str] = {"banco": "", "no_cheque": "", "fecha_pago": ""}
    registrando_pago_id: int = 0
    mostrar_form_registrar_pago: bool = False

    @rx.event
    def abrir_registrar_pago(self, vac: dict):
        self.form_registrar_pago = {
            "banco": str(vac.get("banco") or ""), "no_cheque": str(vac.get("no_cheque") or ""),
            "fecha_pago": dt.date.today().strftime("%Y-%m-%d"),
        }
        self.registrando_pago_id = int(vac.get("id") or 0)
        self.mostrar_form_registrar_pago = True
        self.msg = ""

    @rx.event
    def set_campo_registrar_pago(self, campo: str, v: str):
        self.form_registrar_pago = {**self.form_registrar_pago, campo: v}

    @rx.event
    def cerrar_form_registrar_pago(self):
        self.mostrar_form_registrar_pago = False

    @rx.event
    async def confirmar_registrar_pago(self):
        auth = await self.get_state(AuthState)
        if "vacaciones:editar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        if not self.registrando_pago_id:
            return
        f = self.form_registrar_pago
        if not f.get("no_cheque", "").strip():
            self.msg = "Ingrese el número de cheque/transferencia."
            return
        try:
            await asyncio.to_thread(
                V.registrar_pago, self.registrando_pago_id,
                banco=f.get("banco", ""), no_cheque=f.get("no_cheque", ""),
                fecha_pago=f.get("fecha_pago") or None,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.msg = "Pago registrado."
            self.mostrar_form_registrar_pago = False
            await self._cargar_empleado()
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error: {e}"

    # ── Comprobante de anticipo ────────────────────────────────────────────
    # Porta app.py::_dialogo_anticipo/_generar_pdf_anticipo — recibo puntual
    # (no persiste nada en vac_registros), para cuando el cálculo trae un
    # anticipo > 0 y financiero necesita el comprobante antes de registrar el
    # pago. "Previsualizar" y "Generar" del .pyw arman el mismo PDF; acá se
    # colapsan en un solo botón de descarga.
    mostrar_dialogo_anticipo: bool = False
    anticipo_fecha: str = ""

    @rx.event
    def abrir_dialogo_anticipo(self):
        anticipo = float(self.form_pago.get("anticipo") or 0)
        if anticipo <= 0:
            self.msg = "No hay anticipo registrado para generar el comprobante."
            return
        self.anticipo_fecha = dt.date.today().strftime("%Y-%m-%d")
        self.mostrar_dialogo_anticipo = True

    @rx.event
    def set_anticipo_fecha(self, v: str):
        self.anticipo_fecha = v

    @rx.event
    def cerrar_dialogo_anticipo(self):
        self.mostrar_dialogo_anticipo = False

    @rx.event
    async def descargar_comprobante_anticipo(self):
        anticipo = float(self.form_pago.get("anticipo") or 0)
        if anticipo <= 0:
            self.msg = "No hay anticipo registrado para generar el comprobante."
            return
        emp = self.empleado
        periodo = self.calc_periodo
        fecha = self.anticipo_fecha

        def _fn() -> bytes:
            from core.pdf.vacaciones_comprobante import anticipo_pdf

            data = {
                "nombre": f"{emp.get('apellidos', '')} {emp.get('nombres', '')}".strip(),
                "cedula": emp.get("cedula", ""), "cargo": emp.get("cargo", ""),
                "periodo": periodo, "valor": anticipo, "en_letras": V.valor_en_letras(anticipo),
                "fecha": _fecha_es(fecha), "referencia": "PREV",
            }
            return anticipo_pdf(data)

        try:
            data = await asyncio.to_thread(_fn)
        except Exception as e:  # noqa: BLE001
            self.msg = f"No se pudo generar el comprobante: {e}"
            return
        self.mostrar_dialogo_anticipo = False
        return rx.download(data=data, filename=f"comprobante_anticipo_{emp.get('cedula','')}.pdf")

    # ── Cálculo de pago (pestaña "Cálculo") ──────────────────────────────
    calc_periodo: str = ""
    calc_dias_gozados: int = 0
    calc_dias_adicionales: int = 0
    calc_total_periodo: float = 0.0
    calc_resultado: dict = {}
    calc_cargando: bool = False
    calc_detalles: list[dict] = []  # tabla de 12 meses de `calcular_meses_periodo`,
    # para persistir en vac_calculo al registrar (ver `crear_pagada(detalles_mensuales=...)`)
    form_pago: dict[str, str] = dict(_FORM_PAGO_VACIO)

    @rx.event
    def set_calc_periodo(self, v: str):
        self.calc_periodo = v

    @rx.event
    async def calcular(self):
        """Trae los 12 meses de nómina del período y aplica la fórmula real de pago
        (`core.repos.vacaciones.calcular_pago` — NO la de `calculos.py`, ver su docstring)."""
        cedula = self.empleado.get("cedula", "")
        fi = self.empleado.get("fecha_ingreso", "")
        if not cedula or not self.calc_periodo or not fi:
            self.msg = "Seleccione empleado y período."
            return
        self.calc_cargando = True
        yield
        try:
            anio_base = int(self.calc_periodo.split("-")[0])
            per = await asyncio.to_thread(V.calcular_periodo, fi, anio_base)
            cod = self.empleado.get("cod_empleado", "") or cedula
            movs = await asyncio.to_thread(V.get_movimientos_empleado, cod, per["inicio"], per["fin"])
            detalles_todos = await asyncio.to_thread(
                V.calcular_meses_periodo, movs, per["inicio"], per["fin"],
                sueldo_base=a_float(self.empleado.get("sueldo")),
                hor25=a_float(self.empleado.get("hor25")), hor50=a_float(self.empleado.get("hor50")),
                hor100=a_float(self.empleado.get("hor100")),
            )
            # meses_en_periodo() puede tocar 13 meses calendario (ej. 15-mar a
            # 14-mar): igual que app.py::_registrar_pagada, el cálculo usa solo
            # los primeros 12.
            detalles = detalles_todos[:12]
            self.calc_detalles = detalles
            total, _desglose = V.calcular_total_periodo(detalles)
            self.calc_total_periodo = round(total, 2)
            self.calc_dias_gozados = await asyncio.to_thread(V.get_dias_gozados_periodo, cedula, self.calc_periodo)
            dias_adic, _ = V.calcular_dias_adicionales(fi, per["fin"].strftime("%Y-%m-%d"))
            self.calc_dias_adicionales = dias_adic
            self.calc_resultado = V.calcular_pago(
                dias_gozados=self.calc_dias_gozados, dias_adicionales=dias_adic,
                total_periodo_12m=total, anticipo=float(self.form_pago.get("anticipo") or 0),
            )
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error al calcular: {e}"
        self.calc_cargando = False

    @rx.event
    def set_campo_pago(self, campo: str, v: str):
        self.form_pago = {**self.form_pago, campo: v}

    @rx.event
    async def registrar_pagada(self):
        auth = await self.get_state(AuthState)
        if "vacaciones:crear" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        cedula = self.empleado.get("cedula", "")
        if not cedula or not self.calc_periodo:
            self.msg = "Calcule el período primero."
            return
        # Advertir si hay períodos anteriores pendientes (igual que
        # app.py::_registrar_pagada, siempre — no distingue crear/editar acá).
        fi = self.empleado.get("fecha_ingreso", "")
        if fi:
            anteriores = await asyncio.to_thread(V.periodos_anteriores_pendientes, cedula, fi, self.calc_periodo)
            if anteriores:
                self.confirmar_periodo_detalle = anteriores
                self._accion_pendiente = "pagada"
                self.mostrar_confirmar_periodo = True
                return
        await self._registrar_pagada_ahora(auth)

    async def _registrar_pagada_ahora(self, auth):
        cedula = self.empleado.get("cedula", "")
        try:
            pago = self.form_pago
            vac_id, calculo = await asyncio.to_thread(
                V.crear_pagada,
                cedula=cedula, periodo=self.calc_periodo,
                dias_gozados=self.calc_dias_gozados, dias_adicionales=self.calc_dias_adicionales,
                total_periodo_12m=self.calc_total_periodo, forma_pago=pago.get("forma_pago", ""),
                anticipo=float(pago.get("anticipo") or 0), banco=pago.get("banco", ""),
                cta_cte_no=pago.get("cta_cte_no", ""), no_cheque=pago.get("no_cheque", ""),
                fecha_pago=pago.get("fecha_pago") or None, observaciones=pago.get("observaciones", ""),
                detalles_mensuales=self.calc_detalles,
                usuario=auth.username, roles=set(auth.roles),
            )
            self.msg = f"Vacación pagada registrada (id={vac_id}, total=${calculo['total_pagar']:.2f})."
            self.form_pago = dict(_FORM_PAGO_VACIO)
            self.calc_resultado = {}
            self.calc_detalles = []
            await self._cargar_empleado()
        except Exception as e:  # noqa: BLE001
            self.msg = f"Error: {e}"

    # ── Reportes ──────────────────────────────────────────────────────────
    rep_periodo: str = ""
    rep_departamento: str = ""
    rep_estado: str = ""
    rep_filas: list[dict] = []
    rep_cargando: bool = False

    @rx.event
    def set_rep_periodo(self, v: str):
        self.rep_periodo = "" if v == "(todos)" else v

    @rx.event
    def set_rep_estado(self, v: str):
        self.rep_estado = "" if v == "(todos)" else v

    @rx.event
    async def cargar_reporte(self):
        self.rep_cargando = True
        yield
        try:
            self.rep_filas = await asyncio.to_thread(
                V.reporte_completo, self.rep_periodo or None, self.rep_departamento or None, self.rep_estado or None
            )
        except Exception as e:  # noqa: BLE001
            self.error = f"No se pudo cargar el reporte: {e}"
        self.rep_cargando = False

    @rx.event
    async def exportar_excel(self):
        periodo, depto, estado = self.rep_periodo, self.rep_departamento, self.rep_estado

        def _fn() -> bytes:
            from core.excel.vacaciones_builders import reporte_completo_xlsx

            filas = V.reporte_completo(periodo or None, depto or None, estado or None)
            return reporte_completo_xlsx(filas)

        data = await asyncio.to_thread(_fn)
        return rx.download(data=data, filename="vacaciones_reporte_completo.xlsx")
