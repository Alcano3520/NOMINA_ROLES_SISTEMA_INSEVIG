"""Selector SQL Server / Supabase para un módulo. Solo afecta lecturas."""

from __future__ import annotations

import reflex as rx

from insevig_web.states.datasource_state import ETIQUETA, DataSourceState


def data_source_selector(modulo: str, *, solo_escritura: bool = False) -> rx.Component:
    if solo_escritura:
        return rx.badge("Escrituras siempre a SQL Server", color_scheme="gray", size="1")
    return rx.hstack(
        rx.icon("database", size=14),
        rx.select(
            list(ETIQUETA.values()),
            value=DataSourceState.etiquetas_efectivas[modulo],
            on_change=lambda v: DataSourceState.set_fuente(modulo, v),
            size="1",
        ),
        rx.badge("solo lectura", color_scheme="amber", size="1"),
        spacing="2",
        align="center",
        on_mount=DataSourceState.detectar,
    )
