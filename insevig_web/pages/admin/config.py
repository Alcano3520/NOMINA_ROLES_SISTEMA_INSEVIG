from __future__ import annotations

import reflex as rx

from core.config import get_settings
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading
from insevig_web.states.auth_state import AuthState


def _fila(k: str, v: str) -> rx.Component:
    return rx.hstack(rx.text(k, weight="bold", size="1", width="220px"), rx.text(v, size="1"), spacing="2")


@rx.page(route="/admin/config", title="INSEVIG — Configuración", on_load=AuthState.cargar_sesion)
def config() -> rx.Component:
    s = get_settings()

    def mask(x: str) -> str:
        return "•••• configurado" if x else "(vacío)"

    return pagina(
        page_heading("Configuración", "Valores efectivos (desde .env). Los secretos van enmascarados."),
        card(
            rx.vstack(
                _fila("SQL Server", f"{s.sqlserver_host} / {s.sqlserver_db}"),
                _fila("Filtro SQL", s.sqlserver_filter),
                _fila("Drivers ODBC", ", ".join(s.driver_list)),
                _fila("SQL Server user RO", s.sqlserver_user_ro),
                _fila("SQL Server pwd RO", mask(s.sqlserver_pwd_ro)),
                _fila("SQL Server user RW", s.sqlserver_user_rw or "(no configurado)"),
                _fila("Supabase URL", s.supabase_url or "(no configurado)"),
                _fila("Supabase key", mask(s.supabase_key)),
                _fila("BD de la app", s.app_db_url.split("://")[0] + "://…"),
                _fila("Email backend", s.email_backend),
                _fila("IA proveedor", s.ia_provider),
                _fila("Feature flags", ", ".join(sorted(s.flags)) or "(ninguno)"),
                _fila("STORAGE_DIR", str(s.storage_dir)),
                spacing="2",
                align="start",
                width="100%",
            ),
            width="100%",
        ),
        requiere=("admin", "ver"),
    )
