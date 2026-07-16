#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modulo de seguridad para REGISTRAR_PRESTAMOS_UNIFICADO.pyw
============================================================
Antes de cada UPDATE/DELETE sobre RPINGDES, crear_respaldo_prestamo() guarda
una copia JSON de las filas afectadas. log_operacion() deja un registro de
auditoria (quien, que, cuando) de cada INSERT/UPDATE/DELETE, exitoso o no.
"""

import os
import sys
import json
import getpass
import threading
from datetime import datetime, date

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CARPETA_RESPALDOS = os.path.join(BASE_DIR, 'respaldos_prestamos')
ARCHIVO_LOG = os.path.join(CARPETA_RESPALDOS, 'auditoria.log')

_lock = threading.Lock()


def _asegurar_carpeta():
    os.makedirs(CARPETA_RESPALDOS, exist_ok=True)


def _json_default(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return str(valor)


def crear_respaldo_prestamo(conn, empleado, numero, descripcion=""):
    """
    Guarda en un JSON el estado actual (antes de modificar) de las filas
    RPINGDES para EMPLEADO+NUMERO. Retorna (exito, ruta_archivo, error).
    """
    try:
        _asegurar_carpeta()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM RPINGDES WHERE EMPLEADO=? AND NUMERO=?",
            (empleado, numero)
        )
        columnas = [c[0] for c in cursor.description]
        filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

        ahora = datetime.now()
        contenido = {
            'fecha_respaldo': ahora.isoformat(),
            'usuario': getpass.getuser(),
            'empleado': str(empleado),
            'numero': str(numero),
            'descripcion': descripcion,
            'filas': filas,
        }

        nombre = f"respaldo_{empleado}_{numero}_{ahora.strftime('%Y%m%d_%H%M%S_%f')}.json"
        ruta = os.path.join(CARPETA_RESPALDOS, nombre)

        with _lock:
            with open(ruta, 'w', encoding='utf-8') as f:
                json.dump(contenido, f, ensure_ascii=False, indent=2, default=_json_default)

        return True, ruta, None
    except Exception as e:
        return False, None, str(e)


def log_operacion(tipo, empleado, numero, detalle="", exito=True):
    """Agrega una linea al log de auditoria. Nunca lanza excepciones."""
    try:
        _asegurar_carpeta()
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        usuario = getpass.getuser()
        estado = "OK" if exito else "ERROR"
        detalle = (detalle or "").replace("\n", " ").replace("\r", " ")
        linea = f"[{ahora}] usuario={usuario} tipo={tipo} empleado={empleado} numero={numero} estado={estado} detalle={detalle}\n"
        with _lock:
            with open(ARCHIVO_LOG, 'a', encoding='utf-8') as f:
                f.write(linea)
    except Exception:
        pass
