"""Editor de Liquidaciones — pantalla dedicada maestro-detalle (4ta del
sidebar del `.pyw`). Ver docs/modulos/liquidaciones_editor_UI.md."""

from __future__ import annotations

import asyncio
import contextlib

import reflex as rx

from core.repos import liquidaciones as repo
from insevig_web.states.auth_state import AuthState
from insevig_web.states.datasource_state import DataSourceState

# (código, label, tipo) por sección — labels exactos del `.pyw`.
SEC_REMUNERACION = [
    ("SUELDO", "Sueldo"),
    ("SOBT_25", "Horas del 25% (recargo nocturno)"),
    ("SOBT_50", "Horas del 50% (suplementarias)"),
    ("SOBT_100", "Horas del 100% (extraordinarias)"),
    ("MANIOBRAS", "Maniobras"),
    ("BONIFICACION", "Bonificación"),
    ("MOVILIZACION", "Movilización / Bono transporte-alimentación"),
    ("REEMBOLSOS", "Devolución y/o Acreditación (Reembolsos)"),
    ("FONDO_RESERVA", "Fondo de Reserva 8,33%"),
]
SEC_BENEFICIOS = [
    ("DEC_TERCERA_ANT", "Décima Tercera (anterior)"),
    ("DEC_TERCERA_ACT", "Décima Tercera (actual)"),
    ("DEC_CUARTA_ANT", "Décima Cuarta (anterior)"),
    ("DEC_CUARTA_ACT", "Décima Cuarta (actual)"),
    ("VACACIONES", "Vacaciones Pendientes"),
    ("DESAHUCIO", "Bonificación Desahucio 25%"),
    ("INDEM_DESPIDO", "Indemnización por Despido"),
    ("OTRAS_INDEM", "Otras Indemnizaciones"),
    ("VALOR_NO_CONSIDERADO", "Por cualquier valor no considerado"),
    ("AJUSTE_CUADRE", "Ajuste de Cuadre (MRL) — admite negativo"),
]
SEC_DESCUENTOS = [
    ("IESS", "Aporte IESS Personal"),
    ("ANTICIPO_SUELDO", "Anticipo de sueldo"),
    ("ANTICIPOS_OTROS", "Anticipos otros"),
    ("ANTICIPOS_SURTIDOS", "Anticipos surtidos"),
    ("PREST_QUIROGRAFARIO", "Préstamo quirografario"),
    ("PREST_COMPANIA", "Préstamo compañía"),
    ("PREST_HIPOTECARIO", "Préstamo hipotecario"),
    ("IESS_CONYUGE", "Aporte IESS Cónyuge"),
    ("IMPUESTO_RENTA", "Impuesto a la renta"),
    ("MULTAS", "Multas"),
    ("PENSION_ALIMENTICIA", "Pensión alimenticia"),
    ("ANTICIPOS_OTROS_L", "Anticipo otros (liquidado)"),
    ("ANTICIPO_L_DESAHUCIO", "Anticipo desahucio (liquidado)"),
    ("DESCUENTO_REGISTRADO", "Descuentos Registrados (pendientes)"),
]
_INGRESOS = {c for c, _ in SEC_REMUNERACION} | {c for c, _ in SEC_BENEFICIOS}
_DESCUENTOS = {c for c, _ in SEC_DESCUENTOS}
_TODOS = [*SEC_REMUNERACION, *SEC_BENEFICIOS, *SEC_DESCUENTOS]

ESTADOS = list(repo.ESTADOS_LIQUIDACION)


def _f(txt: object) -> float:
    try:
        return round(float(str(txt).replace(",", ".").strip() or 0), 2)
    except ValueError:
        return 0.0


class LiquidacionesEditorState(rx.State):
    # ── Lista (panel izquierdo) ──────────────────────────────────────
    ed_texto: str = ""
    ed_estado: str = ""
    ed_lista: list[dict] = []
    ed_cargando_lista: bool = False

    @rx.event
    def set_ed_texto(self, v: str):
        self.ed_texto = v

    @rx.event
    def set_ed_estado(self, v: str):
        self.ed_estado = "" if v in ("", "Todos") else v

    @rx.event
    async def cargar_lista(self):
        self.ed_cargando_lista = True
        yield
        with contextlib.suppress(Exception):
            self.ed_lista = await asyncio.to_thread(
                repo.listar_liquidaciones, texto=self.ed_texto, estado=self.ed_estado, limite=300
            )
        self.ed_cargando_lista = False

    # ── Formulario (panel derecho) ───────────────────────────────────
    ed_id: str = ""
    ed_datos: dict[str, str] = {}      # cedula, nombre, cargo, seccion, fecha_ingreso, fecha_salida, motivo, estado
    ed_campos: dict[str, str] = {}     # concepto_codigo -> valor (texto)
    ed_orig: dict[str, str] = {}
    ed_fecha_calc_valida: str = ""     # fecha con la que se calcularon los valores en pantalla
    ed_msg: str = ""

    async def _fuente(self) -> str:
        ds = await self.get_state(DataSourceState)
        return await ds.resolver("liquidaciones")

    @rx.event
    async def abrir(self, liquidacion_id: str):
        self.ed_id = liquidacion_id
        self.ed_msg = ""
        yield
        registro, conceptos = await asyncio.to_thread(repo.obtener_liquidacion, liquidacion_id)
        if registro is None:
            self.ed_msg = "No se encontró esa liquidación."
            return
        self.ed_datos = {
            "cedula": str(registro.get("empleado_cedula") or ""),
            "nombre": f"{registro.get('empleado_apellidos', '')} "
                      f"{registro.get('empleado_nombres', '')}".strip(),
            "cargo": str(registro.get("cargo") or ""),
            "seccion": str(registro.get("seccion") or ""),
            "fecha_ingreso": str(registro.get("fecha_ingreso") or ""),
            "fecha_salida": str(registro.get("fecha_salida") or ""),
            "motivo": str(registro.get("motivo") or ""),
            "estado": str(registro.get("estado") or ""),
        }
        por_cod = {str(c["concepto_codigo"]): round(float(c.get("valor_total") or 0), 2)
                   for c in conceptos}
        self.ed_campos = {cod: str(por_cod.get(cod, 0.0)) for cod, _ in _TODOS}
        self.ed_orig = dict(self.ed_campos)
        self.ed_fecha_calc_valida = self.ed_datos["fecha_salida"]

    @rx.event
    def cerrar(self):
        self.ed_id = ""
        self.ed_datos = {}
        self.ed_campos = {}
        self.ed_orig = {}
        self.ed_msg = ""

    @rx.event
    def set_ed_campo(self, cod: str, v: str):
        self.ed_campos = {**self.ed_campos, cod: v}

    @rx.event
    def set_ed_dato(self, k: str, v: str):
        self.ed_datos = {**self.ed_datos, k: v}

    @rx.var
    def ed_total_ingresos(self) -> float:
        return round(sum(_f(self.ed_campos.get(c, 0)) for c in _INGRESOS), 2)

    @rx.var
    def ed_total_descuentos(self) -> float:
        return round(sum(_f(self.ed_campos.get(c, 0)) for c in _DESCUENTOS), 2)

    @rx.var
    def ed_total_liquido(self) -> float:
        return round(self.ed_total_ingresos - self.ed_total_descuentos, 2)

    @rx.var
    def ed_fecha_desalineada(self) -> bool:
        """La fecha del formulario no coincide con la del último cálculo."""
        return bool(self.ed_id) and self.ed_datos.get("fecha_salida", "") != self.ed_fecha_calc_valida

    # ── "+" ajuste incremental por concepto ─────────────────────────
    aj_abierto: str = ""   # concepto_codigo del "+" abierto ("" = ninguno)
    aj_monto: str = ""
    aj_motivo: str = ""

    @rx.event
    def abrir_ajuste(self, cod: str):
        self.aj_abierto = cod
        self.aj_monto = self.aj_motivo = ""

    @rx.event
    def cerrar_ajuste(self):
        self.aj_abierto = ""

    @rx.event
    def set_aj(self, campo: str, v: str):
        setattr(self, f"aj_{campo}", v)

    @rx.event
    async def confirmar_ajuste(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        delta = _f(self.aj_monto)
        if delta == 0:
            self.ed_msg = "El monto a agregar no puede ser 0."
            return
        ok, error = await asyncio.to_thread(
            repo.ajustar_concepto, self.ed_id, self.aj_abierto, delta,
            motivo=self.aj_motivo.strip(), usuario=auth.username, roles=set(auth.roles),
        )
        if not ok:
            self.ed_msg = error
            return
        cod = self.aj_abierto
        self.ed_campos = {**self.ed_campos, cod: str(round(_f(self.ed_campos.get(cod, 0)) + delta, 2))}
        self.ed_orig = {**self.ed_orig, cod: self.ed_campos[cod]}
        self.aj_abierto = ""
        self.ed_msg = f"Ajuste de {delta:+.2f} aplicado a {cod}."

    # ── Recalcular ─────────────────────────────────────────────────
    @rx.event
    async def recalcular(self):
        from core.parametros import config_liquidacion

        fuente = await self._fuente()
        cfg = config_liquidacion("COSTA")
        d = self.ed_datos
        try:
            liq = await asyncio.to_thread(
                repo.recalcular_liquidacion, self.ed_id, fuente, cfg,
                cedula=d.get("cedula", ""), fecha_salida=d.get("fecha_salida", ""),
                motivo=d.get("motivo", ""),
            )
        except Exception as e:  # noqa: BLE001
            self.ed_msg = f"No se pudo recalcular: {e}"
            return
        if liq.error:
            self.ed_msg = f"Recálculo con error: {liq.error}"
            return
        self.ed_campos = {cod: str(round(float(liq.campos.get(cod, 0) or 0), 2)) for cod, _ in _TODOS}
        # los valores del bot MRL usan claves internas distintas a concepto_codigo;
        # mapeamos las que difieren:
        _MAP = {
            "SOBT_25": "VAL_SOBT_25", "SOBT_50": "VAL_SOBT_50", "SOBT_100": "VAL_SOBT_100",
            "DEC_TERCERA_ANT": "DECIMA_TERCERA_ANTERIOR", "DEC_TERCERA_ACT": "DECIMA_TERCERA_ACTUAL",
            "DEC_CUARTA_ANT": "DECIMA_CUARTA_ANTERIOR", "DEC_CUARTA_ACT": "DECIMA_CUARTA_ACTUAL",
            "VACACIONES": "VACACIONES_CALCULADAS", "IESS": "APORT_IESS",
            "IESS_CONYUGE": "APORT_IESS_CONYUGE", "PREST_QUIROGRAFARIO": "PRESTAMOS_QUIROGRAFARIOS",
            "PREST_COMPANIA": "PRESTAMOS_COMPANIA", "PREST_HIPOTECARIO": "PRESTAMO_HIPOTECARIO",
            "DESCUENTO_REGISTRADO": "DESCUENTOS_REGISTRADOS",
        }
        for cod, clave in _MAP.items():
            self.ed_campos[cod] = str(round(float(liq.campos.get(clave, 0) or 0), 2))
        self.ed_orig = dict(self.ed_campos)
        self.ed_fecha_calc_valida = d.get("fecha_salida", "")
        self.ed_msg = "Recalculado. Revisá los valores y guardá si están bien."

    # ── Guardar ───────────────────────────────────────────────────
    @rx.event
    async def guardar(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        if self.ed_fecha_desalineada:
            self.ed_msg = (
                "La fecha de salida es distinta a la que se usó para calcular los valores "
                "en pantalla. Pulsá '🔄 Recalcular Liquidación', revisá los valores nuevos "
                "y recién entonces guardá."
            )
            return
        cambios = {
            cod: _f(txt) for cod, txt in self.ed_campos.items()
            if abs(_f(txt) - _f(self.ed_orig.get(cod, "0"))) >= 0.005
        }
        if not cambios:
            self.ed_msg = "No cambiaste ningún valor."
            return
        ok, error = await asyncio.to_thread(
            repo.editar_valores_liquidacion, self.ed_id, cambios,
            usuario=auth.username, roles=set(auth.roles),
        )
        if not ok:
            self.ed_msg = error
            return
        self.ed_orig = dict(self.ed_campos)
        self.ed_msg = f"Guardado ({len(cambios)} concepto(s) corregido(s))."
        await self.cargar_lista()

    @rx.event
    async def eliminar(self):
        auth = await self.get_state(AuthState)
        if "admin" not in auth.roles:
            return rx.toast.error("Solo un administrador puede eliminar una liquidación.")
        ok, error = await asyncio.to_thread(
            repo.eliminar_liquidacion, self.ed_id, "Eliminada desde el Editor de Liquidaciones",
            usuario=auth.username, roles=set(auth.roles),
        )
        self.ed_msg = "Eliminada." if ok else f"No se pudo eliminar: {error}"
        if ok:
            self.cerrar()
            await self.cargar_lista()

    @rx.event
    def generar_pdf(self):
        registro, conceptos = repo.obtener_liquidacion(self.ed_id)
        if registro is None:
            return rx.toast.error("No se encontró esa liquidación.")
        from core.pdf.liquidacion_individual import liquidacion_pdf

        liq = repo.reconstruir_liquidacion(registro, conceptos)
        return rx.download(
            data=liquidacion_pdf(liq, es_simulacion=False),
            filename=f"liquidacion_{liq.empleado}_{liq.fecha_salida}.pdf",
        )
