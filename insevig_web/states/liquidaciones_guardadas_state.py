"""Estado de 'Liquidaciones guardadas' — Editor + Gestión de liquidaciones
(módulo 9), combinados en una sola pantalla: buscar, ver detalle, cambiar
estado, eliminar y regenerar PDF de lo ya guardado en Supabase."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses

import reflex as rx

from core.repos import liquidaciones as repo
from insevig_web.states.auth_state import AuthState

ESTADOS = list(repo.ESTADOS_LIQUIDACION)


@dataclasses.dataclass
class _Celda:
    clave: str
    valor: str


@dataclasses.dataclass
class _FilaGrid:
    label: str
    celdas: list[_Celda]

# Colores de etiqueta (marcador libre por liquidación, como COLORES_ETIQUETA del .pyw).
COLORES_ETIQUETA = [
    ("Rojo", "#e74c3c"), ("Naranja", "#e67e22"), ("Amarillo", "#f1c40f"),
    ("Verde", "#2ecc71"), ("Azul", "#3498db"), ("Violeta", "#9b59b6"), ("Gris", "#95a5a6"),
]
FORMAS_PAGO = ["Transferencia", "Cheque", "Efectivo", "Otro"]
LUGARES_FIRMA = ["Consignación", "Oficina"]

# Conceptos editables en la cuadrícula de edición masiva (concepto_codigo -> label),
# ver docs/modulos/liquidaciones_cuadricula_UI.md.
CONCEPTOS_GRID = [
    ("SUELDO", "Sueldo"), ("BONIFICACION", "Bonificación"), ("MANIOBRAS", "Maniobras"),
    ("MOVILIZACION", "Movilización"), ("REEMBOLSOS", "Reembolsos"),
    ("SOBT_25", "Horas 25%"), ("SOBT_50", "Horas 50%"), ("SOBT_100", "Horas 100%"),
    ("FONDO_RESERVA", "Fondo de reserva"),
    ("DEC_TERCERA_ANT", "Déc. 13 anterior"), ("DEC_TERCERA_ACT", "Déc. 13 actual"),
    ("DEC_CUARTA_ANT", "Déc. 14 anterior"), ("DEC_CUARTA_ACT", "Déc. 14 actual"),
    ("VACACIONES", "Vacaciones"), ("DESAHUCIO", "Desahucio"),
    ("INDEM_DESPIDO", "Indem. despido"), ("OTRAS_INDEM", "Otras indemnizaciones"),
    ("VALOR_NO_CONSIDERADO", "Valor no considerado"),
    ("IESS", "Aporte IESS"), ("IESS_CONYUGE", "IESS cónyuge"),
    ("PREST_QUIROGRAFARIO", "Préstamo quirografario"), ("PREST_COMPANIA", "Préstamo compañía"),
    ("PREST_HIPOTECARIO", "Préstamo hipotecario"),
    ("ANTICIPO_SUELDO", "Anticipo sueldo"), ("ANTICIPOS_OTROS", "Anticipos otros"),
    ("ANTICIPOS_SURTIDOS", "Anticipos surtidos"), ("ANTICIPOS_OTROS_L", "Anticipo otros (liq.)"),
    ("ANTICIPO_L_DESAHUCIO", "Anticipo desahucio (liq.)"),
    ("MULTAS", "Multas"), ("PENSION_ALIMENTICIA", "Pensión alimenticia"),
    ("IMPUESTO_RENTA", "Impuesto a la renta"),
    ("DESCUENTO_REGISTRADO", "Descuentos registrados"), ("AJUSTE_CUADRE", "Ajuste cuadre MRL"),
]

# Acción disponible según el estado de la fila (label, tipo de diálogo, estado destino
# para el diálogo genérico "avance"). Ver docs/modulos/liquidaciones_gestion_UI.md.
ACCION_POR_ESTADO = {
    "generada": ("Autorizar", "autorizar", ""),
    "aprobado": ("Registrar en MRL", "avance", "registrado_mrl"),
    "registrado_mrl": ("Marcar cheque listo", "cheque", ""),
    "cheque_listo": ("Pagar / Consignar", "pago", ""),
    "pagado": ("Legalizar en MRL", "avance", "legalizada_mrl"),
    "consignada": ("Legalizar en MRL", "avance", "legalizada_mrl"),
}

# Nombre legible de cada estado.
ESTADO_LABEL = {
    "borrador": "Borrador", "generada": "Generada", "aprobado": "Aprobado",
    "registrado_mrl": "Registrado en MRL", "cheque_listo": "Cheque listo",
    "consignada": "Consignada", "pagado": "Pagado", "legalizada_mrl": "Legalizada en MRL",
    "impreso": "Impreso", "archivado": "Archivado", "cancelado": "Cancelado",
}


class LiquidacionesGuardadasState(rx.State):
    texto: str = ""
    estado_filtro: str = ""
    f_lote: str = ""
    f_desde: str = ""
    f_hasta: str = ""
    f_orden: str = ""
    filas: list[dict] = []
    lotes: list[str] = []
    cargando: bool = False
    msg: str = ""

    @rx.event
    def set_texto(self, v: str):
        self.texto = v

    @rx.event
    def set_estado_filtro(self, v: str):
        self.estado_filtro = "" if v in ("", "(todos)") else v

    @rx.event
    def set_filtro(self, campo: str, v: str):
        setattr(self, f"f_{campo}", "" if v == "(todos)" else v)

    @rx.event
    def limpiar_filtros(self):
        self.texto = self.estado_filtro = self.f_lote = self.f_desde = self.f_hasta = self.f_orden = ""

    @rx.event
    async def buscar(self):
        self.cargando = True
        self.msg = ""
        yield
        try:
            kw = {"texto": self.texto, "estado": self.estado_filtro, "lote": self.f_lote,
                  "desde": self.f_desde, "hasta": self.f_hasta}
            if self.f_orden:
                kw["orden"] = self.f_orden
            filas = await asyncio.to_thread(repo.listar_liquidaciones, **kw)
        except Exception as e:  # noqa: BLE001
            self.msg = f"No se pudo cargar: {e}"
            filas = []
        self.filas = filas
        if not self.lotes:
            self.lotes = sorted({str(f.get("codigo_lote") or f.get("lote") or "") for f in filas} - {""})
        self.cargando = False

    @rx.var
    def conteo(self) -> str:
        return f"{len(self.filas)} liquidación(es)"

    @rx.var
    def lote_opciones(self) -> list[str]:
        return ["(todos)", *self.lotes]

    @rx.event
    async def exportar_listado(self):
        from core.excel.liquidaciones_builders import listado_liquidaciones_xlsx

        data = await asyncio.to_thread(listado_liquidaciones_xlsx, list(self.filas))
        return rx.download(data=data, filename="liquidaciones_listado.xlsx")

    # ── Editar en cuadrícula (edición masiva de conceptos) ──────────
    grid_abierta: bool = False
    grid_liqs: list[dict] = []        # [{id, nombre}]
    grid_valores: dict[str, str] = {}  # "{id}|{codigo}" -> valor (texto)
    grid_orig: dict[str, str] = {}
    grid_motivo: str = ""
    grid_msg: str = ""

    @rx.event
    async def abrir_grid(self):
        ids = list(self.seleccion)
        if not ids:
            self.msg = "Marcá una o más liquidaciones para editar en cuadrícula."
            return
        self.grid_abierta = True
        self.grid_msg = ""
        self.grid_motivo = ""
        liqs, valores = [], {}
        for lid in ids:
            registro, conceptos = await asyncio.to_thread(repo.obtener_liquidacion, lid)
            if registro is None:
                continue
            liqs.append({
                "id": lid,
                "nombre": f"{registro.get('empleado_apellidos', '')} "
                          f"{registro.get('empleado_nombres', '')}".strip(),
            })
            por_cod = {str(c["concepto_codigo"]): round(float(c.get("valor_total") or 0), 2)
                       for c in conceptos}
            for cod, _lbl in CONCEPTOS_GRID:
                valores[f"{lid}|{cod}"] = str(por_cod.get(cod, 0.0))
        self.grid_liqs = liqs
        self.grid_valores = valores
        self.grid_orig = dict(valores)

    @rx.event
    def cerrar_grid(self):
        self.grid_abierta = False
        self.grid_liqs = []
        self.grid_valores = {}
        self.grid_orig = {}

    @rx.event
    def set_grid_valor(self, clave: str, v: str):
        self.grid_valores = {**self.grid_valores, clave: v}

    @rx.var
    def grid_matriz(self) -> list[_FilaGrid]:
        """Filas de la cuadrícula: una por concepto, con una celda por liquidación."""
        out: list[_FilaGrid] = []
        for cod, lbl in CONCEPTOS_GRID:
            celdas = [
                _Celda(clave=f"{lq['id']}|{cod}",
                       valor=self.grid_valores.get(f"{lq['id']}|{cod}", "0"))
                for lq in self.grid_liqs
            ]
            out.append(_FilaGrid(label=lbl, celdas=celdas))
        return out

    @rx.event
    def set_grid_motivo(self, v: str):
        self.grid_motivo = v

    @rx.event
    async def guardar_grid(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        motivo = self.grid_motivo.strip() or "Edición en cuadrícula"
        n_ok = n_err = 0
        errs: list[str] = []
        for clave, txt in self.grid_valores.items():
            try:
                nuevo = round(float(str(txt).replace(",", ".").strip() or 0), 2)
                viejo = round(float(self.grid_orig.get(clave, "0")), 2)
            except ValueError:
                n_err += 1
                errs.append(f"{clave}: valor inválido")
                continue
            if abs(nuevo - viejo) < 0.005:
                continue
            lid, cod = clave.split("|", 1)
            ok, error = await asyncio.to_thread(
                repo.ajustar_concepto, lid, cod, round(nuevo - viejo, 2),
                motivo=motivo, usuario=auth.username, roles=set(auth.roles),
            )
            if ok:
                n_ok += 1
            else:
                n_err += 1
                errs.append(error)
        self.grid_msg = f"{n_ok} ajuste(s) aplicado(s)." + (
            f"  {n_err} error(es): {' · '.join(errs[:5])}" if n_err else ""
        )
        if n_ok:
            self.grid_orig = dict(self.grid_valores)
            await self.buscar()

    # ── Cuadre masivo (MRL) ─────────────────────────────────────────
    cuadre_abierto: bool = False
    cuadre_texto: str = ""
    cuadre_msg: str = ""

    @rx.event
    def abrir_cuadre(self):
        self.cuadre_abierto = True
        self.cuadre_texto = self.cuadre_msg = ""

    @rx.event
    def cerrar_cuadre(self):
        self.cuadre_abierto = False

    @rx.event
    def set_cuadre_texto(self, v: str):
        self.cuadre_texto = v

    @rx.event
    async def aplicar_cuadre(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        if not self.cuadre_texto.strip():
            self.cuadre_msg = "Pegá al menos una línea (cédula, fecha de salida, monto)."
            return
        n, errores = await asyncio.to_thread(
            repo.cuadre_masivo, self.cuadre_texto, usuario=auth.username, roles=set(auth.roles),
        )
        self.cuadre_msg = f"{n} liquidación(es) ajustada(s)." + (
            f"  {len(errores)} error(es): {' · '.join(errores[:5])}" if errores else ""
        )
        if n:
            await self.buscar()

    # ── Detalle ──────────────────────────────────────────────────────
    detalle_id: str = ""
    detalle: dict = {}
    detalle_conceptos: list[dict] = []
    detalle_msg: str = ""

    historial: list[dict] = []
    # ── Seguimiento de firma y cobro + color + observaciones ─────────
    seg: dict[str, str] = {}
    seg_msg: str = ""

    @rx.event
    async def ver_detalle(self, liquidacion_id: str):
        self.detalle_id = liquidacion_id
        self.detalle = {}
        self.detalle_conceptos = []
        self.detalle_msg = ""
        self.historial = []
        self.seg_msg = ""
        yield
        registro, conceptos = await asyncio.to_thread(repo.obtener_liquidacion, liquidacion_id)
        if registro is None:
            self.detalle_msg = "No se encontró esa liquidación."
            return
        self.detalle = registro
        self.detalle_conceptos = conceptos
        self.seg = {
            k: str(registro.get(k) or "")
            for k in ("color_etiqueta", "lugar_firma", "numero_acta", "fecha_firma_acuerdo",
                      "fecha_lista_cobro", "fecha_citado_cobro", "fecha_consignacion", "observaciones")
        }
        with contextlib.suppress(Exception):
            self.historial = await asyncio.to_thread(repo.historial_estados, liquidacion_id)

    @rx.event
    def set_seg(self, campo: str, v: str):
        self.seg = {**self.seg, campo: v}

    @rx.event
    def set_color(self, hexv: str):
        self.seg = {**self.seg, "color_etiqueta": "" if self.seg.get("color_etiqueta") == hexv else hexv}

    @rx.event
    async def guardar_seguimiento(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso.")
        ok, error = await asyncio.to_thread(
            repo.guardar_seguimiento, self.detalle_id, dict(self.seg),
            usuario=auth.username, roles=set(auth.roles),
        )
        self.seg_msg = "Guardado." if ok else f"No se pudo guardar: {error}"
        if ok:
            await self.buscar()

    @rx.var
    def conceptos_ingreso(self) -> list[dict]:
        return [c for c in self.detalle_conceptos if c.get("concepto_tipo") == "ingreso"]

    @rx.var
    def conceptos_egreso(self) -> list[dict]:
        return [c for c in self.detalle_conceptos if c.get("concepto_tipo") == "descuento"]

    @rx.var
    def total_ingresos_detalle(self) -> float:
        return round(sum(float(c.get("valor_total") or 0) for c in self.conceptos_ingreso), 2)

    @rx.var
    def total_egresos_detalle(self) -> float:
        return round(sum(float(c.get("valor_total") or 0) for c in self.conceptos_egreso), 2)

    @rx.event
    def cerrar_detalle(self):
        self.detalle_id = ""
        self.detalle = {}
        self.detalle_conceptos = []
        self.historial = []
        self.seg = {}
        self.editando = False
        self.edit_valores = {}

    # ── Edición manual de valores (Editor del legado) ────────────────
    editando: bool = False
    edit_valores: dict[str, str] = {}   # concepto_codigo -> valor (texto)
    edit_msg: str = ""

    @rx.var
    def conceptos_editables(self) -> list[dict]:
        """`detalle_conceptos` + el valor en edición de cada concepto (texto)."""
        out = []
        for c in self.detalle_conceptos:
            cod = str(c["concepto_codigo"])
            out.append({**c, "edit_valor": self.edit_valores.get(cod, str(c["valor_total"]))})
        return out

    @rx.event
    def abrir_edicion(self):
        self.edit_valores = {
            str(c["concepto_codigo"]): str(c["valor_total"]) for c in self.detalle_conceptos
        }
        self.editando = True
        self.edit_msg = ""

    @rx.event
    def cancelar_edicion(self):
        self.editando = False
        self.edit_valores = {}
        self.edit_msg = ""

    @rx.event
    def set_edit_valor(self, codigo: str, v: str):
        self.edit_valores = {**self.edit_valores, codigo: v}

    @rx.event
    async def guardar_edicion(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            return rx.toast.error("Sin permiso para editar liquidaciones.")
        originales = {str(c["concepto_codigo"]): round(float(c["valor_total"]), 2) for c in self.detalle_conceptos}
        cambios: dict[str, float] = {}
        for cod, txt in self.edit_valores.items():
            try:
                nuevo = round(float(str(txt).replace(",", ".").strip() or 0), 2)
            except ValueError:
                self.edit_msg = f"Valor inválido en {cod}: «{txt}»."
                return
            if nuevo != originales.get(cod):
                cambios[cod] = nuevo
        if not cambios:
            self.edit_msg = "No cambiaste ningún valor."
            return
        ok, error = await asyncio.to_thread(
            repo.editar_valores_liquidacion, self.detalle_id, cambios,
            usuario=auth.username, roles=set(auth.roles),
        )
        if not ok:
            self.edit_msg = error
            return
        self.editando = False
        self.edit_valores = {}
        self.msg = f"Liquidación corregida ({len(cambios)} concepto(s))."
        await self.ver_detalle(self.detalle_id)
        await self.buscar()

    # ── Flujo de estados (diálogos de acción por estado) ────────────
    accion_abierta: str = ""     # "" | autorizar | avance | cheque | pago
    accion_ids: list[str] = []   # a qué liquidaciones aplica
    accion_estado: str = ""      # estado nuevo para "avance"
    f_autorizado_por: str = ""
    f_responsable: str = ""
    f_forma_pago: str = "Transferencia"
    f_comprobante: str = ""
    f_fecha: str = ""

    @rx.event
    def abrir_accion(self, tipo: str, ids: list[str], estado_nuevo: str = ""):
        self.accion_abierta = tipo
        self.accion_ids = ids
        self.accion_estado = estado_nuevo
        self.f_autorizado_por = self.f_responsable = self.f_comprobante = self.f_fecha = ""
        self.f_forma_pago = "Transferencia"

    @rx.event
    def cerrar_accion(self):
        self.accion_abierta = ""
        self.accion_ids = []

    @rx.event
    def set_accion_campo(self, campo: str, v: str):
        setattr(self, f"f_{campo}", v)

    async def _aplicar(self, fn, **kw) -> None:
        auth = await self.get_state(AuthState)
        if "liquidaciones:editar" not in auth.permisos_flat:
            self.msg = "Sin permiso."
            return
        ok_n = err = 0
        detalles: list[str] = []
        for lid in self.accion_ids:
            try:
                ok, error = await asyncio.to_thread(
                    fn, lid, usuario=auth.username, roles=set(auth.roles), **kw
                )
            except Exception as e:  # noqa: BLE001
                ok, error = False, str(e)[:120]
            if ok:
                ok_n += 1
            else:
                err += 1
                detalles.append(error)
        self.msg = f"{ok_n} liquidación(es) actualizada(s)." + (
            f" {err} con error: {'; '.join(detalles[:3])}" if err else ""
        )
        self.cerrar_accion()
        await self.buscar()
        if self.detalle_id and self.detalle_id in self.accion_ids:
            await self.ver_detalle(self.detalle_id)

    @rx.event
    async def confirmar_autorizar(self):
        if not self.f_autorizado_por.strip():
            self.msg = "Ingrese quién autoriza."
            return
        await self._aplicar(repo.autorizar, autorizado_por=self.f_autorizado_por.strip())

    @rx.event
    async def confirmar_avance(self):
        if not self.f_responsable.strip():
            self.msg = "Ingrese el responsable."
            return
        await self._aplicar(repo.avanzar_estado, nuevo_estado=self.accion_estado,
                            responsable=self.f_responsable.strip())

    @rx.event
    async def confirmar_cheque(self):
        indiv = len(self.accion_ids) == 1
        if indiv and not self.f_comprobante.strip():
            self.msg = "Ingrese el número de cheque/comprobante."
            return
        await self._aplicar(repo.marcar_cheque_listo, forma_pago=self.f_forma_pago,
                            comprobante_pago=self.f_comprobante.strip())

    @rx.event
    async def confirmar_pago(self, final: str):
        if not self.f_fecha.strip():
            self.msg = "Ingrese la fecha."
            return
        fn = repo.marcar_pagada if final == "pagado" else repo.marcar_consignada
        await self._aplicar(fn, fecha=self.f_fecha.strip())

    @rx.event
    async def eliminar(self, liquidacion_id: str):
        auth = await self.get_state(AuthState)
        if "admin" not in auth.roles:
            return rx.toast.error("Solo un administrador puede eliminar una liquidación guardada.")
        ok, error = await asyncio.to_thread(
            repo.eliminar_liquidacion, liquidacion_id, "Eliminada desde Liquidaciones guardadas",
            usuario=auth.username, roles=set(auth.roles),
        )
        self.msg = "Liquidación eliminada." if ok else f"No se pudo eliminar: {error}"
        if ok and self.detalle_id == liquidacion_id:
            self.cerrar_detalle()
        await self.buscar()

    # ── Bot MRL (selección múltiple) ────────────────────────────────
    seleccion: list[str] = []

    @rx.event
    def toggle_seleccion(self, liquidacion_id: str):
        self.seleccion = (
            [x for x in self.seleccion if x != liquidacion_id]
            if liquidacion_id in self.seleccion
            else [*self.seleccion, liquidacion_id]
        )

    @rx.event
    async def generar_bot_mrl(self):
        auth = await self.get_state(AuthState)
        if "liquidaciones:ver" not in auth.permisos_flat:
            yield rx.toast.error("Sin permiso.")
            return
        ids = list(self.seleccion)
        if not ids:
            yield rx.toast.error("Marca una o más liquidaciones en la lista.")
            return
        from core.excel.liquidaciones_bot_mrl import bot_mrl_xlsx

        data, advertencias, error = await asyncio.to_thread(bot_mrl_xlsx, ids)
        if error:
            yield rx.toast.error(error)
            return
        for a in advertencias[:4]:
            yield rx.toast.warning(a)
        self.msg = f"Bot MRL generado ({len(ids)} liquidación(es))." + (
            f" {len(advertencias)} advertencia(s)." if advertencias else ""
        )
        yield rx.download(data=data, filename="bot_mrl_liquidaciones.xlsx")

    @rx.event
    async def generar_pdf(self, liquidacion_id: str):
        def _build():
            from core.pdf.liquidacion_individual import liquidacion_pdf

            registro, conceptos = repo.obtener_liquidacion(liquidacion_id)
            if registro is None:
                return None
            liq = repo.reconstruir_liquidacion(registro, conceptos)
            return liq.empleado, liq.fecha_salida, liquidacion_pdf(liq, es_simulacion=False)

        res = await asyncio.to_thread(_build)
        if res is None:
            return rx.toast.error("No se encontró esa liquidación.")
        emp, fsal, data = res
        return rx.download(data=data, filename=f"liquidacion_{emp}_{fsal}.pdf")
