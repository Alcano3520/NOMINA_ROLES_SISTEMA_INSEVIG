"""Registro de módulos. La shell (`components/layout`, `sidebar`) y `insevig_web.py`
solo conocen los módulos a través de esto.

Añadir un módulo = crear su carpeta `pages/<mod>/`, `states/<mod>_state.py`, etc.
y registrar un `ModuleSpec` aquí. La shell no se toca.

★ CONGELADO (el contrato). El contenido de MODULES lo edita quien integra, no un
agente de módulo.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NavItem:
    label: str
    ruta: str
    permiso: str = "ver"  # acción requerida sobre el módulo


@dataclass(frozen=True)
class ModuleSpec:
    nombre: str  # id corto, == prefijo de archivos (reportes, prestamos, ...)
    titulo: str  # etiqueta visible
    icono: str  # nombre de icono lucide (rx.icon)
    items: list[NavItem] = field(default_factory=list)
    disponible: bool = True  # feature flag / fase no terminada

    @property
    def ruta_principal(self) -> str:
        return self.items[0].ruta if self.items else f"/{self.nombre}"


MODULES: list[ModuleSpec] = [
    ModuleSpec(
        "reportes", "Reportes", "file-bar-chart",
        [NavItem("Consolidado de nómina", "/reportes/consolidado"),
         NavItem("Comparador SQL vs Supabase", "/reportes/comparador", "exportar")],
    ),
    ModuleSpec(
        "prestamos", "Préstamos", "hand-coins",
        [NavItem("Historial", "/prestamos/historial"),
         NavItem("Saldos", "/prestamos/saldos")],
    ),
    ModuleSpec(
        "observaciones", "Observaciones", "clipboard-list",
        [NavItem("Observaciones / Multas / Faltas", "/observaciones")],
    ),
    ModuleSpec(
        "empleados", "Gestión de empleados", "users",
        [NavItem("Buscar", "/empleados/buscar"),
         NavItem("Historial de nómina", "/empleados/historial"),
         NavItem("Carga masiva", "/empleados/carga-masiva", "cargar_masivo")],
    ),
    ModuleSpec(
        "roles", "Roles de pago", "receipt-text",
        [NavItem("Generar", "/roles/generar", "generar_pdf"),
         NavItem("Lote", "/roles/lote", "generar_pdf"),
         NavItem("Envío por correo", "/envio", "enviar_email")],
    ),
    ModuleSpec(
        "registrador", "Registrar egresos/ingresos", "file-plus-2",
        [NavItem("Importar BIESS", "/registrador/biess", "registrar_rpingdes"),
         NavItem("Registro manual", "/registrador/manual", "registrar_rpingdes")],
    ),
    ModuleSpec(
        "bitacora", "Agenda de liquidaciones", "calendar-clock",
        [NavItem("Agenda de cobro", "/bitacora")],
    ),
    ModuleSpec(
        "admin", "Administración", "settings",
        [NavItem("Usuarios", "/admin/usuarios"),
         NavItem("Roles y permisos", "/admin/roles"),
         NavItem("Auditoría", "/admin/auditoria"),
         NavItem("Configuración", "/admin/config")],
    ),
]

MODULES_POR_NOMBRE: dict[str, ModuleSpec] = {m.nombre: m for m in MODULES}
