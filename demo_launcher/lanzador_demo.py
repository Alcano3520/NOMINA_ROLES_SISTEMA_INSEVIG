"""Lanzador de demo INSEVIG — abre la app web (Reflex) en el navegador.

Uso: doble clic en el .exe (desplegado en `\\\\192.168.2.181\\Apps_Empresa$\\
Lanzadores\\` — unidad Y:). El personal de RRHH/general solo necesita esto:
si el servidor Reflex está corriendo como servicio en el NAS, abre el
navegador y listo.

Si el servidor NO responde y el .exe encuentra el proyecto de desarrollo
accesible (share oculto `\\\\192.168.2.181\\Sistemas_Dev$` — unidad X:, solo
GRP_DEVS), lo levanta con el mismo comando de `scripts/dev.sh`
(`reflex run --env prod --single-port --frontend-port 3000`).

Config opcional -- archivo `demo_config.ini` junto al .exe:

    [demo]
    url = http://192.168.2.181:3000
    proyecto = X:\\

Rutas siempre UNC (`\\\\192.168.2.181\\...`) o unidad de red mapeada
(X:, Y:); nunca rutas locales fijas tipo C:\\. Sin `demo_config.ini` se
asume la URL del NAS y se buscan las ubicaciones candidatas de abajo.
"""

from __future__ import annotations

import configparser
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

URL_DEFECTO = "http://192.168.2.181:3000"
PUERTO_DEFECTO = "3000"
SEGUNDOS_ESPERA_MAXIMOS = 60

# Ubicaciones candidatas del proyecto Reflex (share oculto de desarrollo).
# Solo GRP_DEVS puede leerlas; para el resto del personal fallan en silencio
# y el lanzador simplemente abre el navegador. UNC o unidad mapeada, jamás
# una ruta local fija.
RUTAS_PROYECTO_CANDIDATAS = (
    "X:\\",
    "X:\\web",
    "\\\\192.168.2.181\\Sistemas_Dev$",
    "\\\\192.168.2.181\\Sistemas_Dev$\\web",
)


def _directorio_exe() -> Path:
    """Carpeta donde vive el .exe (o el script, si corre sin empaquetar)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def _es_proyecto(ruta: Path) -> bool:
    try:
        return (ruta / "insevig_web").exists()
    except OSError:  # share no accesible (permisos) o ruta inválida
        return False


def _buscar_proyecto(base: Path) -> Path | None:
    for ruta in (base, *(Path(r) for r in RUTAS_PROYECTO_CANDIDATAS)):
        if _es_proyecto(ruta):
            return ruta
    return None


def _leer_config(base: Path) -> tuple[str, Path | None]:
    ini = base / "demo_config.ini"
    url = URL_DEFECTO
    proyecto: Path | None = None
    if ini.exists():
        cfg = configparser.ConfigParser()
        cfg.read(ini, encoding="utf-8")
        url = cfg.get("demo", "url", fallback=URL_DEFECTO)
        ruta = cfg.get("demo", "proyecto", fallback="")
        if ruta:
            proyecto = Path(ruta)
    if proyecto is None:
        proyecto = _buscar_proyecto(base)
    return url, proyecto


def _servidor_activo(url: str, timeout: float = 1.5) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)  # noqa: S310
        return True
    except Exception:  # noqa: BLE001 — cualquier fallo de red = "no está listo"
        return False


def _iniciar_servidor(proyecto: Path) -> None:
    reflex_venv = proyecto / ".venv" / "Scripts" / "reflex.exe"
    ejecutable = str(reflex_venv) if reflex_venv.exists() else "reflex"
    comando = [ejecutable, "run", "--env", "prod", "--single-port",
               "--frontend-port", PUERTO_DEFECTO]
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    # cwd puede ser UNC o unidad mapeada; CreateProcess acepta UNC como
    # directorio de trabajo (a diferencia de cmd.exe).
    subprocess.Popen(comando, cwd=str(proyecto), creationflags=flags)  # noqa: S603


def main() -> None:
    base = _directorio_exe()
    url, proyecto = _leer_config(base)

    print(f"INSEVIG — Demo\nBuscando el sistema en {url} ...")
    if not _servidor_activo(url):
        if proyecto is not None:
            print(f"No está corriendo. Iniciando desde: {proyecto}")
            _iniciar_servidor(proyecto)
            for _ in range(SEGUNDOS_ESPERA_MAXIMOS):
                if _servidor_activo(url):
                    print("Listo.")
                    break
                time.sleep(1)
            else:
                print("El sistema está tardando más de lo normal en arrancar; "
                      "se abrirá igual la página, reintente en unos segundos.")
        else:
            print("El servidor no responde y no se llegó al proyecto de "
                  "desarrollo (X: / Sistemas_Dev$). Se abrirá la URL igual; "
                  "si no carga, avise a Sistemas para que arranque el "
                  "servicio en el NAS.")

    webbrowser.open(url)
    time.sleep(2)


if __name__ == "__main__":
    main()
