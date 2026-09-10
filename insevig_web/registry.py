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
        "empleados", "Gestión de empleados", "users",
        [NavItem("Fichas de empleados", "/empleados/buscar"),
         NavItem("Búsqueda avanzada", "/empleados/avanzada"),
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
        [NavItem("Préstamos y egresos/ingresos", "/registrador", "registrar_rpingdes")],
    ),
    ModuleSpec(
        "reportes", "Reportes", "file-bar-chart",
        [NavItem("Consolidado de nómina", "/reportes/consolidado")],
    ),
    ModuleSpec(
        "prestamos", "Préstamos", "hand-coins",
        [NavItem("Historial", "/prestamos/historial"),
         NavItem("Saldos", "/prestamos/saldos")],
    ),
    ModuleSpec(
        "observaciones", "Observaciones", "clipboard-list",
        [NavItem("Observaciones / Multas / Faltas", "/observaciones"),
         NavItem("Carga masiva", "/observaciones/carga-masiva", "crear")],
    ),
    ModuleSpec(
        "sanciones", "Sanciones", "gavel",
        [NavItem("Bandeja (aprobar / procesar)", "/sanciones/bandeja"),
         NavItem("Historial procesadas", "/sanciones/historial"),
         NavItem("Buscar", "/sanciones/buscar"),
         NavItem("Novedades de horario", "/sanciones/novedades"),
         NavItem("Estadísticas", "/sanciones/estadisticas")],
    ),
    ModuleSpec(
        "maniobras", "Maniobras / Multas", "truck",
        [NavItem("Registrar maniobras / multas", "/registrador", "registrar_rpingdes")],
    ),
    ModuleSpec(
        "faltas", "Gestión de faltas", "calendar-x",
        [NavItem("Ver / editar período", "/faltas/periodo"),
         NavItem("Registro uno a uno", "/faltas/individual", "crear"),
         NavItem("Registro masivo", "/faltas/masivo", "crear"),
         NavItem("Cargador de restas de horas", "/faltas/restas", "cargar_masivo")],
    ),
    ModuleSpec(
        "bitacora", "Agenda de liquidaciones", "calendar-clock",
        [NavItem("Agenda de cobro", "/bitacora")],
    ),
    ModuleSpec(
        "liquidaciones", "Liquidaciones", "file-check-2",
        [NavItem("Generar finiquitos", "/liquidaciones", "ver"),
         NavItem("Editor de liquidaciones", "/liquidaciones/editor", "ver"),
         NavItem("Gestión de liquidaciones", "/liquidaciones/guardadas", "ver"),
         NavItem("Descuentos pendientes", "/liquidaciones/descuentos-pendientes", "ver")],
    ),
    ModuleSpec(
        "vacaciones", "Vacaciones", "calendar-days",
        [NavItem("Gozadas y pagadas", "/vacaciones", "ver")],
    ),
    ModuleSpec(
        "carga_usuarios", "Usuarios de la app (sanciones)", "user-plus",
        [NavItem("Usuario individual", "/carga-usuarios/individual", "crear"),
         NavItem("Ver usuarios", "/carga-usuarios/listado"),
         NavItem("Resetear contraseñas", "/carga-usuarios/reset", "editar"),
         NavItem("Carga masiva", "/carga-usuarios/masivo", "cargar_masivo")],
    ),
    ModuleSpec(
        "admin", "Administración", "settings",
        [NavItem("Usuarios", "/admin/usuarios"),
         NavItem("Roles y permisos", "/admin/roles"),
         NavItem("Auditoría", "/admin/auditoria"),
         NavItem("Verificación de datos", "/reportes/comparador", "ver"),
         NavItem("Parámetros", "/admin/parametros", "editar"),
         NavItem("Configuración", "/admin/config")],
    ),
]

MODULES_POR_NOMBRE: dict[str, ModuleSpec] = {m.nombre: m for m in MODULES}
