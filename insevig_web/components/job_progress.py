"""Panel de progreso de un Job. Recibe los Vars del state de cada módulo."""

from __future__ import annotations

import reflex as rx

from insevig_web.components.ui import card


def job_progress(
    *,
    status: rx.Var,
    progress: rx.Var,
    total: rx.Var,
    message: rx.Var,
    error: rx.Var,
    corriendo: rx.Var,
    tiene_resultado: rx.Var,
    on_cancelar: rx.EventHandler,
    on_descargar: rx.EventHandler,
) -> rx.Component:
    return card(
        rx.vstack(
            rx.hstack(
                rx.badge(status, color_scheme=rx.cond(error != "", "red", "blue")),
                rx.text(message, size="2", color_scheme="gray"),
                spacing="2",
                align="center",
            ),
            rx.cond(
                corriendo,
                rx.progress(
                    value=progress,
                    max=rx.cond(total > 0, total, 1),
                    width="100%",
                ),
            ),
            rx.cond(error != "", rx.callout(error, color_scheme="red", size="1")),
            rx.hstack(
                rx.cond(
                    corriendo,
                    rx.button("Cancelar", on_click=on_cancelar, variant="soft", color_scheme="red", size="2"),
                ),
                rx.cond(
                    tiene_resultado,
                    rx.button("Descargar Excel", on_click=on_descargar, size="2"),
                ),
                spacing="2",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )
