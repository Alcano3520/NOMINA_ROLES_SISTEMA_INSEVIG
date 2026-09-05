"""Lanzador de demo INSEVIG — abre la app web (Reflex) en el navegador.

Uso: doble clic en el .exe generado (ver .github/workflows/
build-demo-launcher-exe.yml). Si el servidor ya está corriendo en la URL
configurada, solo abre el navegador. Si no está corriendo y hay una
instalación local del proyecto junto al .exe (una carpeta con `insevig_web`
y `.venv` al lado, o la ruta indicada en `demo_config.ini`), lo levanta
primero con el mismo comando de `scripts/dev.sh`
(`reflex run --env prod --single-port --frontend-port 3000`).

Config opcional -- archivo `demo_config.ini` junto al .exe:

    [demo]
    url = http://192.168.2.50:3000
    proyecto = C:\\INSEVIG\\web

Sin ese archivo, se asume `http://localhost:3000` y se busca el proyecto
en la misma carpeta que el .exe.
"""

from __future__ import annotations

import configparser
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

URL_DEFECTO = "http://localhost:3000"
PUERTO_DEFECTO = "3000"
SEGUNDOS_ESPERA_MAXIMOS = 60


def _directorio_exe() -> Path:
    """Carpeta donde vive el .exe (o el script, si corre sin empaquetar)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


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
    if proyecto is None and (base / "insevig_web").exists():
        proyecto = base
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
            print("No se encontró una instalación local junto al lanzador "
                  "(ni demo_config.ini). Se abrirá la URL de todas formas.")

    webbrowser.open(url)
    time.sleep(2)


if __name__ == "__main__":
    main()
