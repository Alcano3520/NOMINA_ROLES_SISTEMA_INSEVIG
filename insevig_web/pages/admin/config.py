from __future__ import annotations

import reflex as rx

from core.config import get_settings
from insevig_web.components.layout import pagina
from insevig_web.components.ui import card, page_heading
from insevig_web.states.admin_state import AdminState
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
        card(
            rx.vstack(
                rx.heading("Actualizar el sistema", size="3"),
                rx.text(
                    "Trae la última versión del código y reinicia el servicio en el "
                    "servidor. Equivale a correr 'Actualizar-INSEVIG.bat' en el NAS. "
                    "Solo administradores.",
                    size="1", color_scheme="gray",
                ),
                rx.cond(
                    AuthState.es_admin,
                    rx.alert_dialog.root(
                        rx.alert_dialog.trigger(
                            rx.button(rx.icon("refresh-cw", size=15), "Actualizar sistema", size="2"),
                        ),
                        rx.alert_dialog.content(
                            rx.alert_dialog.title("Actualizar el sistema"),
                            rx.alert_dialog.description(
                                "El servidor va a traer el código nuevo y reiniciarse. "
                                "Durante ~1-2 minutos la app puede no responder. ¿Continuar?",
                            ),
                            rx.hstack(
                                rx.alert_dialog.cancel(rx.button("Cancelar", variant="soft")),
                                rx.alert_dialog.action(
                                    rx.button("Sí, actualizar", on_click=AdminState.actualizar_sistema),
                                ),
                                spacing="3", justify="end", margin_top="1rem",
                            ),
                        ),
                    ),
                    rx.text("(sin permiso)", size="1", color_scheme="gray"),
                ),
                rx.cond(AdminState.deploy_msg != "",
                        rx.callout(AdminState.deploy_msg, size="1", margin_top="0.5rem")),
                spacing="2", align="start", width="100%",
            ),
            width="100%",
        ),
        requiere=("admin", "ver"),
    )
