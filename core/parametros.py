"""Parámetros de negocio editables desde Administración (guardados en AppConfig).

Hoy: SBU por año (para liquidaciones). Ampliable a proveedor de IA, plantilla de
correo, etc.
"""

from __future__ import annotations

import json

import sqlmodel

from core.db import appdb
from core.db.models import AppConfig


def _leer(key: str) -> dict:
    with appdb.session() as s:
        row = s.exec(
            sqlmodel.select(AppConfig).where(AppConfig.key == key, AppConfig.scope == "global")
        ).first()
    if not row:
        return {}
    try:
        return json.loads(row.value_json) or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _guardar(key: str, data: dict) -> None:
    with appdb.session() as s:
        row = s.exec(
            sqlmodel.select(AppConfig).where(AppConfig.key == key, AppConfig.scope == "global")
        ).first()
        if row is None:
            row = AppConfig(key=key, scope="global")
        row.value_json = json.dumps(data)
        s.add(row)
        s.commit()


def get_sbu() -> dict[str, float]:
    """{'2026': 482.0, ...}. Si no hay nada guardado devuelve {} (se usan los
    valores por defecto de `core.repos.liquidaciones.SBU_DEFECTO`)."""
    d = _leer("sbu_por_anio")
    return {str(k): float(v) for k, v in d.items() if str(v).replace(".", "", 1).isdigit()}


def set_sbu(sbu: dict[str, float]) -> None:
    _guardar("sbu_por_anio", {str(k): float(v) for k, v in sbu.items()})


def get_liquidaciones_params() -> dict[str, float | str]:
    """IESS%/Fondo de Reserva%/Región por defecto/Anticipo (días umbral y
    divisor) -- la ventana "⚙ Configuración de Parámetros Anuales" del
    `.pyw` original (Generador_Liquidaciones_INSEVIG.pyw), antes fija en
    código (`IESS_PCT`/`FONDO_RESERVA_PCT`/`ANTICIPO_DIAS_UMBRAL`/
    `ANTICIPO_DIVISOR` de `core.repos.liquidaciones`) y ahora editable
    desde /admin/parametros, igual que el SBU."""
    from core.repos.liquidaciones import ANTICIPO_DIAS_UMBRAL, ANTICIPO_DIVISOR, FONDO_RESERVA_PCT, IESS_PCT

    d = _leer("liquidaciones_params")
    return {
        "iess_personal_pct": float(d.get("iess_personal_pct", IESS_PCT)),
        "fondo_reserva_pct": float(d.get("fondo_reserva_pct", FONDO_RESERVA_PCT)),
        "region_defecto": str(d.get("region_defecto") or "COSTA"),
        "anticipo_dias_umbral": float(d.get("anticipo_dias_umbral", ANTICIPO_DIAS_UMBRAL)),
        "anticipo_divisor": float(d.get("anticipo_divisor", ANTICIPO_DIVISOR)),
    }


def set_liquidaciones_params(
    *, iess_personal_pct: float | None = None, fondo_reserva_pct: float | None = None,
    region_defecto: str | None = None, anticipo_dias_umbral: float | None = None,
    anticipo_divisor: float | None = None,
) -> None:
    actuales = get_liquidaciones_params()
    cambios = {
        "iess_personal_pct": iess_personal_pct, "fondo_reserva_pct": fondo_reserva_pct,
        "region_defecto": region_defecto.upper() if region_defecto else None,
        "anticipo_dias_umbral": anticipo_dias_umbral, "anticipo_divisor": anticipo_divisor,
    }
    actuales.update({k: v for k, v in cambios.items() if v is not None})
    _guardar("liquidaciones_params", actuales)


_EMAIL_ASUNTO_DEFECTO = "ROL {{mes}}/{{anio}}"
_EMAIL_HTML_DEFECTO = (
    "<p>Estimado/a {{StrNombres}},</p>"
    "<p>Adjunto encontrará su rol de pago correspondiente a {{mes}}/{{anio}}.</p>"
    "<p>Cédula: {{StrCedula}} · Código: {{StrEmpleado}}</p>"
    "<p>Recursos Humanos — INSEVIG</p>"
)


def get_email_plantilla() -> dict[str, str]:
    """{'asunto': ..., 'html': ...} para el envío de roles."""
    d = _leer("email_plantilla_roles")
    return {
        "asunto": str(d.get("asunto") or _EMAIL_ASUNTO_DEFECTO),
        "html": str(d.get("html") or _EMAIL_HTML_DEFECTO),
    }


def set_email_plantilla(asunto: str, html: str) -> None:
    _guardar("email_plantilla_roles", {
        "asunto": asunto.strip() or _EMAIL_ASUNTO_DEFECTO,
        "html": html.strip() or _EMAIL_HTML_DEFECTO,
    })


def get_ia_config() -> dict[str, str]:
    """Config del proveedor de narrativa IA. `provider/base_url/model` se pueden
    editar desde Administración; la API key sigue viniendo SOLO de `.env`
    (no se guarda en la BD de la app)."""
    from core.config import get_settings

    s = get_settings()
    base = {"provider": s.ia_provider, "base_url": s.ia_base_url, "model": s.ia_model}
    ov = _leer("ia_config")
    for k in ("provider", "base_url", "model"):
        if str(ov.get(k, "")).strip():
            base[k] = str(ov[k]).strip()
    base["api_key"] = s.ia_api_key  # nunca desde la BD
    return base


def set_ia_config(provider: str, base_url: str, model: str) -> None:
    _guardar("ia_config", {
        "provider": provider.strip().lower(),
        "base_url": base_url.strip(),
        "model": model.strip(),
    })


def config_liquidacion(region: str = ""):
    """`ConfigLiquidacion` con los SBU + IESS%/Fondo Reserva%/Anticipo
    guardados (o los valores por defecto de `core.repos.liquidaciones`).
    `region`: si se omite, usa la "Región por defecto" guardada (COSTA si
    nunca se configuró) -- todos los llamadores existentes ya pasan una
    región explícita, así que esto no les cambia nada."""
    from core.repos.liquidaciones import SBU_DEFECTO, ConfigLiquidacion

    sbu = dict(SBU_DEFECTO)
    sbu.update(get_sbu())
    p = get_liquidaciones_params()
    return ConfigLiquidacion(
        region=region or str(p["region_defecto"]),
        iess_personal_pct=float(p["iess_personal_pct"]),
        fondo_reserva_pct=float(p["fondo_reserva_pct"]),
        anticipo_dias_umbral=float(p["anticipo_dias_umbral"]),
        anticipo_divisor=float(p["anticipo_divisor"]),
        sbu_por_anio=sbu,
    )
