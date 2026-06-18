#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE REGISTRO DE PRESTAMOS - VERSION UNIFICADA v7.0
=========================================================
Fusion: REGISTRAR_PRESTAMO_6_GUI.pyw + REGISTRAR_PRESTAMOS_MASIVO_SEGURO.pyw
Guia: INTERFAZ_GRAFICA_RRHH.txt + INFRAESTRUCTURA_RRHH.txt

MEJORAS:
- Toda operacion BD en threads (sin congelar UI)
- Barra de estado con feedback en tiempo real
- Cierre limpio con _running flag
- Calculo inteligente de cuotas (respeta prestamos existentes)
- Respaldo automatico antes de insertar
- Modo cuotas y modo valor mensual
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from datetime import datetime, timedelta
import calendar
import sys
import pyodbc
import pandas as pd
import os
import pyperclip
import threading
from concurrent.futures import ThreadPoolExecutor
import math
import json
import traceback

try:
    from modulo_seguridad_prestamos import (
        crear_respaldo_prestamo,
        log_operacion,
        CARPETA_RESPALDOS
    )
    SEGURIDAD_DISPONIBLE = True
except ImportError:
    SEGURIDAD_DISPONIBLE = False

# =============================================================================
# PALETA RRHH INSEVIG (INTERFAZ_GRAFICA_RRHH.txt seccion 10)
# =============================================================================
COL_BG      = '#F0F4F8'
COL_HEADER  = '#1976D2'
COL_ACCENT  = '#2196F3'
COL_PEND    = '#F57C00'
COL_OK      = '#2E7D32'
COL_DANGER  = '#C62828'
COL_WHITE   = '#FFFFFF'
COL_GRAY    = '#CFD8DC'

# =============================================================================
# CONSTANTES
# =============================================================================
CLASE_PRESTAMO = "205"
CONCEPTO_PRESTAMO = "PRESTAMOS COMPANIA"
CODIGO_PRESTAMO = "EGR"
CODSUC_FIJO = 10
CODEMP_FIJO = 10
APORTA_FIJO = 0
TIPO_PGO_FIJO = 3
TIPO_TRA_FIJO = 1

TIPOS_TRANSACCION = {
    "": "(Sin tipo)",
    "PRESTAMO_PRE01": "Préstamo",
    "DESCUENTO_DES02": "Descuento",
    "EGRESO_EGR03": "Egreso",
    "DEVOLUCION_DEV04": "Devolución",
    "CUADRE_CUA05": "Cuadre",
    "DES_LIQUIDACION_DLQ06": "Descuento Liquidación",
    "CRUZE_CRZ07": "Cruce"
}

# =============================================================================
# CLASES SIMPLIFICADAS — TODOS LOS TIPOS (EGR + ING)
# =============================================================================
CLASES_SIMPLIFICADAS = {
    "250": {"concepto": "ANTICIPOS SURTIDOS", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "219": {"concepto": "IMPUESTO A LA RENTA", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "218": {"concepto": "APORT.IESS CONYUGE", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 1},
    "206": {"concepto": "PENSION ALIMENTICIA", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "203": {"concepto": "MULTAS", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "202": {"concepto": "ANTICIPO DE SUELDO", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "204": {"concepto": "PRESTAMOS QUIROGRAFARIOS", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "207": {"concepto": "PRESTAMO HIPOTECARIO", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "217": {"concepto": "ANTICIPOS OTROS", "codigo": "EGR", "codsuc": 10, "codemp": 10, "tipo": "EGR", "aporta": 0},
    "102": {"concepto": "BONIFICACION OTROS INGRESOS", "codigo": "ING", "codsuc": 10, "codemp": 10, "tipo": "ING", "aporta": 1},
    "120": {"concepto": "MOVILIZACION", "codigo": "ING", "codsuc": 10, "codemp": 10, "tipo": "ING", "aporta": 0},
    "111": {"concepto": "REEMBOLSOS", "codigo": "ING", "codsuc": 10, "codemp": 10, "tipo": "ING", "aporta": 0},
    "110": {"concepto": "MANIOBRAS", "codigo": "ING", "codsuc": 10, "codemp": 10, "tipo": "ING", "aporta": 1},
}

# =============================================================================
# FUNCIONES BD (shared by both tabs)
# =============================================================================
def conectar_bd():
    try:
        conn_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=192.168.2.115;DATABASE=insevig;UID=sa;PWD=puntosoft123*'
        conn = pyodbc.connect(conn_string, timeout=10)
        return conn, None
    except Exception as e:
        return None, str(e)

def buscar_empleados_batch(conn, codigos_empleados, chunk_size=100):
    try:
        if not codigos_empleados:
            return {}, None
        empleados_dict = {}
        codigos_list = list(codigos_empleados)
        for i in range(0, len(codigos_list), chunk_size):
            chunk = codigos_list[i:i + chunk_size]
            placeholders = ','.join(['?' for _ in chunk])
            cursor = conn.cursor()
            query = f"""SELECT EMPLEADO, APELLIDOS, NOMBRES, DEPTO, SECCION
                       FROM RPEMPLEA WITH (NOLOCK) WHERE EMPLEADO IN ({placeholders})
                       AND RTRIM(LTRIM(APELLIDOS)) NOT IN ('.','0','00','000','0000')"""
            cursor.execute(query, chunk)
            for r in cursor.fetchall():
                empleados_dict[str(r.EMPLEADO)] = {
                    'id': r.EMPLEADO,
                    'nombre_completo': f"{str(r.APELLIDOS or '').strip()} {str(r.NOMBRES or '').strip()}".strip(),
                    'depto': r.DEPTO,
                    'seccion': r.SECCION
                }
        return empleados_dict, None
    except Exception as e:
        return {}, str(e)

def _cedula_variantes(c):
    """Genera todos los formatos posibles de una cedula ecuatoriana.
    Ejemplo: '912345678' → {'912345678', '0912345678'}
             '0912345678' → {'0912345678', '912345678'}
    Asi la query encuentra la cedula aunque este guardada con o sin cero inicial."""
    c = str(c).strip()
    variantes = {c}
    if c.isdigit():
        variantes.add(c.zfill(10))           # con cero(s) al frente hasta 10 digitos
        sin_ceros = c.lstrip('0') or '0'
        variantes.add(sin_ceros)             # sin ceros al frente
    return variantes

def _limpiar_cedula_bd(raw):
    """Limpia el valor de CEDULA tal como viene de pyodbc.
    La BD guarda cedulas como FLOAT → pyodbc lo convierte a '920725710.0'.
    Esta funcion devuelve solo los digitos ('920725710')."""
    if raw is None:
        return ""
    s = str(raw).strip()
    # Formato float: "920725710.0" → convertir a int → "920725710"
    if '.' in s:
        try:
            s = str(int(float(s)))
        except Exception:
            pass
    # Quedarme solo con dígitos
    digits = ''.join(c for c in s if c.isdigit())
    return digits

def buscar_empleados_por_cedula(conn, cedulas, chunk_size=100):
    """Busca empleados por cedula. Maneja cédulas con o sin cero inicial:
    '912345678' y '0912345678' se consideran equivalentes.
    NOTA: la BD guarda cedulas como FLOAT (ej: 920725710.0), pyodbc lo retorna
    como '920725710.0' — _limpiar_cedula_bd() normaliza eso a '920725710'."""
    try:
        if not cedulas:
            return {}, None

        # Para cada input del usuario, generar todas sus variantes de formato
        # formato_a_originales: cada variante apunta al set de inputs originales que la generaron
        formato_a_originales = {}
        for c in cedulas:
            c = str(c).strip()
            for v in _cedula_variantes(c):
                formato_a_originales.setdefault(v, set()).add(c)

        todos_formatos = list(formato_a_originales.keys())
        resultado = {}

        for i in range(0, len(todos_formatos), chunk_size):
            chunk = todos_formatos[i:i + chunk_size]
            placeholders = ','.join(['?' for _ in chunk])
            cursor = conn.cursor()
            query = f"""SELECT EMPLEADO, APELLIDOS, NOMBRES, DEPTO, SECCION, CEDULA
                       FROM RPEMPLEA WITH (NOLOCK) WHERE CEDULA IN ({placeholders})
                       AND RTRIM(LTRIM(APELLIDOS)) NOT IN ('.','0','00','000','0000')"""
            cursor.execute(query, chunk)
            for r in cursor.fetchall():
                # La BD guarda CEDULA como float → pyodbc retorna '920725710.0'
                # _limpiar_cedula_bd normaliza a '920725710'
                ced_db = _limpiar_cedula_bd(r.CEDULA)
                if not ced_db:
                    continue
                emp_data = {
                    'id': r.EMPLEADO,
                    'nombre_completo': f"{str(r.APELLIDOS or '').strip()} {str(r.NOMBRES or '').strip()}".strip(),
                    'depto': r.DEPTO,
                    'seccion': r.SECCION
                }
                # Indexar por todas las variantes del valor limpio en BD
                for v in _cedula_variantes(ced_db):
                    resultado[v] = emp_data
                    # Y por los inputs originales del usuario que podrian coincidir
                    for orig in formato_a_originales.get(v, set()):
                        resultado[orig] = emp_data

        return resultado, None
    except Exception as e:
        return {}, str(e)

def buscar_empleados(conn, filtro="", limite=100):
    try:
        cursor = conn.cursor()
        if filtro:
            query = """
                SELECT EMPLEADO, APELLIDOS, NOMBRES, DEPTO, SECCION
                FROM RPEMPLEA WITH (NOLOCK)
                WHERE (CAST(EMPLEADO AS VARCHAR) LIKE ? OR APELLIDOS LIKE ? OR NOMBRES LIKE ?)
                AND RTRIM(LTRIM(APELLIDOS)) NOT IN ('.','0','00','000','0000')
                ORDER BY APELLIDOS, NOMBRES
            """
            param = f'%{filtro}%'
            cursor.execute(query, (param, param, param))
        else:
            query = """
                SELECT EMPLEADO, APELLIDOS, NOMBRES, DEPTO, SECCION
                FROM RPEMPLEA WITH (NOLOCK)
                WHERE RTRIM(LTRIM(APELLIDOS)) != '.'
                ORDER BY APELLIDOS, NOMBRES
            """
            cursor.execute(query)
        rows = cursor.fetchmany(limite)
        return [{
            'id': r.EMPLEADO,
            'apellidos': str(r.APELLIDOS or '').strip(),
            'nombres': str(r.NOMBRES or '').strip(),
            'depto': r.DEPTO,
            'seccion': r.SECCION
        } for r in rows], None
    except Exception as e:
        return [], str(e)

def obtener_proximo_numero_egreso(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT ULT_EGR FROM RPCONTRL WITH (UPDLOCK, HOLDLOCK)")
        ultimo = cursor.fetchone()
        if ultimo and ultimo[0] is not None:
            return int(ultimo[0]) + 1, None
        return None, "No se pudo obtener numero"
    except Exception as e:
        return None, str(e)

def actualizar_ultimo_egreso(conn, nuevo_numero):
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE RPCONTRL SET ULT_EGR = ?", nuevo_numero)
        return True, None
    except Exception as e:
        return False, str(e)

def obtener_detalles_empleado(conn, empleado_id):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DEPTO, SECCION FROM RPEMPLEA WITH (NOLOCK) WHERE EMPLEADO = ?", empleado_id)
        r = cursor.fetchone()
        if r:
            return r.DEPTO, r.SECCION, None
        return None, None, f"Empleado {empleado_id} no existe"
    except Exception as e:
        return None, None, str(e)

def get_last_day_of_month(year, month):
    return datetime(year, month, calendar.monthrange(year, month)[1])

def get_next_month(year, month):
    if month == 12:
        return year + 1, 1
    return year, month + 1

def obtener_proyeccion_pagos_futuros_empleado(conn, empleado_id, fecha_referencia=None):
    cursor = conn.cursor()
    if fecha_referencia is None:
        fecha_referencia = datetime.now()
    primer_dia = fecha_referencia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    proyeccion = {}
    try:
        query = """
            SELECT FECHA_VEN, VALOR
            FROM RPINGDES WITH (NOLOCK)
            WHERE EMPLEADO = ? AND FECHA_VEN >= ? AND CLASE = '205' AND ASENTADO = 0
            ORDER BY FECHA_VEN
        """
        cursor.execute(query, empleado_id, primer_dia)
        for row in cursor.fetchall():
            if row.FECHA_VEN and row.VALOR is not None:
                fv = row.FECHA_VEN
                if isinstance(fv, str):
                    try:
                        fv = datetime.strptime(fv[:19], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            fv = datetime.strptime(fv[:10], '%Y-%m-%d')
                        except:
                            continue
                key = (fv.year, fv.month)
                proyeccion[key] = proyeccion.get(key, 0.0) + float(row.VALOR)
        return proyeccion, None
    except Exception as e:
        return {}, str(e)

def planificar_cuotas_inteligente(conn, empleado_id, valor_total, cuota_deseada, fecha_inicio):
    if valor_total <= 0 or cuota_deseada <= 0:
        return [], "Valores invalidos"
    proyeccion_existentes, err = obtener_proyeccion_pagos_futuros_empleado(conn, empleado_id, fecha_inicio)
    if err:
        return [], f"Error obteniendo proyeccion: {err}"
    saldo = round(float(valor_total), 2)
    cuota_deseada = round(float(cuota_deseada), 2)
    cuotas = []
    secuencia = 1
    year, month = fecha_inicio.year, fecha_inicio.month
    for _ in range(600):
        if saldo <= 0.005:
            break
        carga_existente = round(proyeccion_existentes.get((year, month), 0.0), 2)
        espacio = cuota_deseada - carga_existente
        if espacio < 0:
            espacio = 0.0
        vc = min(saldo, espacio)
        vc = round(vc, 2)
        if vc > 0.005:
            cuotas.append({
                "secuencia": secuencia,
                "fecha_vencimiento": get_last_day_of_month(year, month),
                "valor": vc
            })
            saldo -= vc
            saldo = round(saldo, 2)
            secuencia += 1
        year, month = get_next_month(year, month)
    if saldo > 0.005:
        return cuotas, f"Saldo restante: {saldo}. Cuota muy baja para deuda existente."
    if not cuotas and valor_total > 0:
        return [], "Cuota deseada cubierta por pagos existentes."
    return cuotas, None

def calcular_cuotas_tradicional(valor_total, num_cuotas, fecha_inicio):
    if valor_total <= 0 or num_cuotas <= 0:
        return [], "Valores invalidos"
    vc = round(valor_total / num_cuotas, 2)
    ajuste = round(valor_total - (vc * num_cuotas), 2)
    cuotas = []
    year, month = fecha_inicio.year, fecha_inicio.month
    for i in range(num_cuotas):
        val = vc + ajuste if i == 0 and ajuste != 0 else vc
        cuotas.append({"secuencia": i + 1, "fecha_vencimiento": get_last_day_of_month(year, month), "valor": round(val, 2)})
        year, month = get_next_month(year, month)
    return cuotas, None

def calcular_cuotas_valor(conn, empleado_id, valor_total, vcm, fecha_inicio):
    return planificar_cuotas_inteligente(conn, empleado_id, valor_total, vcm, fecha_inicio)

def insertar_prestamo(conn, empleado_id, numero_egreso, fecha_emision, observacion, cuotas, valor_total):
    cursor = conn.cursor()
    depto, seccion, err = obtener_detalles_empleado(conn, empleado_id)
    if err:
        return False, err
    if observacion and len(observacion) > 700:
        observacion = observacion[:700]
    num_cuotas = len(cuotas)
    try:
        for c in cuotas:
            cursor.execute("""INSERT INTO RPINGDES (
                NUMERO, EMPLEADO, SECUENCIA, CLASE, FECHA, FECHA_VEN, VALOR, OBSERV,
                CODSUC, CODEMP, DEPTO, SECCION, ASENTADO, ACTUALIZA, APORTA, TIPO_PGO, TIPO_TRA, CODIGO,
                CONCEPTO, MONTO, DIVIDENDO
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (numero_egreso, empleado_id, c["secuencia"], CLASE_PRESTAMO, fecha_emision, c["fecha_vencimiento"],
                 c["valor"], observacion, CODSUC_FIJO, CODEMP_FIJO, depto, seccion, 0, 0, APORTA_FIJO,
                 TIPO_PGO_FIJO, TIPO_TRA_FIJO, CODIGO_PRESTAMO, CONCEPTO_PRESTAMO, valor_total, num_cuotas))
        return True, f"{num_cuotas} cuotas"
    except Exception as e:
        return False, str(e)

def obtener_ultimos_egresos(conn, limite=100):
    try:
        cursor = conn.cursor()
        query = """
            SELECT g.NUMERO, g.EMPLEADO, MIN(g.FECHA) as FECHA_EMISION,
                   SUM(g.VALOR) as VALOR_TOTAL, MAX(g.OBSERV) as OBSERV,
                   COUNT(*) as CUOTAS, e.APELLIDOS, e.NOMBRES
            FROM RPINGDES g WITH (NOLOCK)
            LEFT JOIN RPEMPLEA e WITH (NOLOCK) ON g.EMPLEADO = e.EMPLEADO
            WHERE g.CLASE = '205'
            GROUP BY g.NUMERO, g.EMPLEADO, e.APELLIDOS, e.NOMBRES
            ORDER BY MAX(g.FECHA) DESC
        """
        cursor.execute(query)
        rows = cursor.fetchmany(limite)
        result = []
        for r in rows:
            nombre = f"{r.APELLIDOS}, {r.NOMBRES}" if r.APELLIDOS else f"Emp #{r.EMPLEADO}"
            result.append({
                'egreso': r.NUMERO,
                'empleado': nombre,
                'fecha': r.FECHA_EMISION.strftime('%d/%m/%Y') if r.FECHA_EMISION else '',
                'valor': f"${float(r.VALOR_TOTAL or 0):.2f}",
                'observacion': r.OBSERV or ''
            })
        result.sort(key=lambda x: x['egreso'], reverse=True)
        return result[:limite], None
    except Exception as e:
        return [], str(e)

def obtener_historial_todos(conn, filtro="", limite=200):
    """Devuelve egresos/ingresos de TODOS los tipos agrupados por NUMERO.
    Para CLASE 205 (prestamos) agrupa las cuotas en una sola fila con el total.
    Para otros tipos cada NUMERO tiene tipicamente una sola fila."""
    try:
        cursor = conn.cursor()
        params = []
        where_extra = ""
        if filtro:
            if filtro.isdigit():
                where_extra = " AND (CAST(r.NUMERO AS VARCHAR) LIKE ? OR CAST(r.EMPLEADO AS VARCHAR) LIKE ?)"
                like = f"%{filtro}%"
                params += [like, like]
            else:
                where_extra = " AND (e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ?)"
                like = f"%{filtro}%"
                params += [like, like]
        query = f"""
            SELECT TOP {limite}
                r.NUMERO, r.CLASE, r.EMPLEADO,
                MIN(r.FECHA) as FECHA_EMISION,
                SUM(r.VALOR) as VALOR_TOTAL,
                COUNT(*) as CUOTAS,
                MAX(r.OBSERV) as OBSERV,
                MAX(r.CONCEPTO) as CONCEPTO,
                e.APELLIDOS, e.NOMBRES
            FROM RPINGDES r WITH (NOLOCK)
            LEFT JOIN RPEMPLEA e WITH (NOLOCK) ON r.EMPLEADO = e.EMPLEADO
            WHERE r.ASENTADO = 0
            {where_extra}
            GROUP BY r.NUMERO, r.CLASE, r.EMPLEADO, e.APELLIDOS, e.NOMBRES
            ORDER BY MAX(r.FECHA) DESC, r.NUMERO DESC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            ape = str(r.APELLIDOS or '').strip()
            nom = str(r.NOMBRES  or '').strip()
            nombre = f"{ape} {nom}".strip() or f"Emp #{r.EMPLEADO}"
            concepto = str(r.CONCEPTO or '').strip() or str(r.OBSERV or '').strip()
            result.append({
                'numero':   r.NUMERO,
                'clase':    str(r.CLASE or '').strip(),
                'empleado': r.EMPLEADO,
                'nombre':   nombre,
                'fecha':    r.FECHA_EMISION.strftime('%d/%m/%Y') if r.FECHA_EMISION else '',
                'valor':    float(r.VALOR_TOTAL or 0),
                'cuotas':   int(r.CUOTAS or 1),
                'concepto': concepto,
            })
        return result, None
    except Exception as e:
        return [], str(e)

def obtener_cuotas_prestamo(conn, numero, empleado_id):
    """Devuelve todas las cuotas de un prestamo CLASE 205 ordenadas por secuencia."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SECUENCIA, FECHA_VEN, VALOR, ASENTADO, OBSERV, CONCEPTO
            FROM RPINGDES WITH (NOLOCK)
            WHERE NUMERO = ? AND EMPLEADO = ? AND CLASE = '205'
            ORDER BY SECUENCIA
        """, (numero, empleado_id))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                'secuencia': r.SECUENCIA,
                'fecha_ven': r.FECHA_VEN,
                'valor':     float(r.VALOR or 0),
                'asentado':  bool(r.ASENTADO),
                'observ':    str(r.OBSERV or '').strip(),
            })
        return result, None
    except Exception as e:
        return [], str(e)

def obtener_proximo_numero_tipo(conn, tipo_movimiento):
    cursor = conn.cursor()
    try:
        if tipo_movimiento == "ING":
            cursor.execute("SELECT ULT_ING FROM RPCONTRL WITH (UPDLOCK, HOLDLOCK)")
        else:
            cursor.execute("SELECT ULT_EGR FROM RPCONTRL WITH (UPDLOCK, HOLDLOCK)")
        ultimo = cursor.fetchone()
        if ultimo and ultimo[0] is not None:
            return int(ultimo[0]) + 1, None
        return None, f"No se pudo obtener ultimo numero de {tipo_movimiento}"
    except Exception as e:
        return None, str(e)

def actualizar_ultimo_numero_tipo(conn, numero, tipo_movimiento):
    cursor = conn.cursor()
    try:
        if tipo_movimiento == "ING":
            cursor.execute("UPDATE RPCONTRL SET ULT_ING = ?", numero)
        else:
            cursor.execute("UPDATE RPCONTRL SET ULT_EGR = ?", numero)
        return True, None
    except Exception as e:
        return False, str(e)

def insertar_movimiento_tipo(conn, empleado_id, numero_movimiento, fecha_dt, observacion, valor, clase_codigo, secuencia=1):
    if clase_codigo not in CLASES_SIMPLIFICADAS:
        return False, f"Clase '{clase_codigo}' no valida"
    config = CLASES_SIMPLIFICADAS[clase_codigo]
    try:
        valor = round(float(valor), 2)
        if valor <= 0:
            return False, "Valor debe ser > 0"
    except (ValueError, TypeError):
        return False, f"Valor no valido: {valor}"
    depto, seccion, err = obtener_detalles_empleado(conn, empleado_id)
    if err:
        return False, err
    if observacion and len(observacion) > 700:
        observacion = observacion[:700]
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO RPINGDES (
            NUMERO, EMPLEADO, SECUENCIA, CLASE, FECHA, FECHA_VEN, VALOR, OBSERV,
            CODSUC, CODEMP, DEPTO, SECCION, ASENTADO, ACTUALIZA, APORTA, TIPO_PGO, TIPO_TRA, CODIGO,
            CONCEPTO, MONTO, DIVIDENDO
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (numero_movimiento, empleado_id, secuencia, clase_codigo, fecha_dt, fecha_dt,
             valor, observacion, config["codsuc"], config["codemp"],
             depto, seccion, 0, 0, config["aporta"], 3, 1, config["codigo"],
             config["concepto"], valor, 1))
        return True, f"{'INGRESO' if config['tipo'] == 'ING' else 'EGRESO'} registrado"
    except Exception as e:
        return False, str(e)

# =============================================================================
# BIESS HELPERS  (Quirografarios / Hipotecarios)
# =============================================================================
def biess_limpiar_cedula(cedula_raw):
    """Limpia cedula del Excel BIESS (puede venir como float, con puntos, etc.)."""
    if cedula_raw is None:
        return None
    s = str(cedula_raw).strip()
    if s in ('', 'nan', 'None', 'NaN'):
        return None
    # pandas puede leer cedulas como float "1234567890.0"
    if '.' in s:
        try:
            s = str(int(float(s)))
        except Exception:
            pass
    digits = ''.join(c for c in s if c.isdigit())
    if not digits:
        return None
    if len(digits) >= 10:
        return digits[:10]
    return None

def biess_col_a_indice(col_str):
    """Convierte letra(s) de columna Excel a indice 0-based. 'A'->0, 'AA'->26."""
    col_str = col_str.upper().strip()
    result = 0
    for ch in col_str:
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result - 1

def biess_procesar_excel(archivo_path, fila_inicio, col_cedula_str, col_valor_str):
    """
    Lee el Excel BIESS y retorna (consolidado, descartados).
    consolidado = dict {cedula_10dig: valor_total_float}
    """
    col_ced = biess_col_a_indice(col_cedula_str)
    col_val = biess_col_a_indice(col_valor_str)
    fila_idx = max(0, fila_inicio - 1)
    df = pd.read_excel(archivo_path, header=None)
    consolidado = {}
    descartados = 0
    for idx in range(fila_idx, len(df)):
        try:
            cedula_raw = df.iloc[idx, col_ced]
            valor_raw  = df.iloc[idx, col_val]
            if pd.isna(cedula_raw) or pd.isna(valor_raw):
                descartados += 1
                continue
            cedula = biess_limpiar_cedula(cedula_raw)
            if not cedula:
                descartados += 1
                continue
            valor_str = str(valor_raw).strip().replace('$', '').replace(',', '').replace(' ', '')
            valor = float(valor_str)
            if not (0.01 <= valor <= 100_000):
                descartados += 1
                continue
            consolidado[cedula] = round(consolidado.get(cedula, 0.0) + valor, 2)
        except Exception:
            descartados += 1
    return consolidado, descartados

def biess_buscar_por_cedulas(conn, cedulas_set):
    """
    Busca empleados activos y liquidados por cedulas.
    Retorna dict {cedula_10dig: {'codigo', 'nombre', 'estado_biess'}}
    estado_biess: 'activo' | 'liquidado' | 'no_encontrado'
    """
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, ESTADO
            FROM RPEMPLEA WITH (NOLOCK)
            WHERE RTRIM(LTRIM(APELLIDOS)) NOT IN ('.','0','00','000','0000')
        """)
        rows = cursor.fetchall()
        bd_activos   = {}
        bd_liquidados = {}
        for r in rows:
            c = biess_limpiar_cedula(r.CEDULA)
            if not c:
                continue
            nombre = f"{(r.APELLIDOS or '').strip()} {(r.NOMBRES or '').strip()}".strip()
            estado = (r.ESTADO or '').strip()
            rec = {'codigo': str(r.EMPLEADO), 'nombre': nombre, 'cedula': c}
            if estado == 'LIQ':
                bd_liquidados[c] = rec
            else:
                bd_activos[c] = rec
        resultado = {}
        for ced in cedulas_set:
            c = biess_limpiar_cedula(ced) or ced
            if c in bd_activos:
                resultado[c] = {**bd_activos[c], 'estado_biess': 'activo'}
            elif c in bd_liquidados:
                resultado[c] = {**bd_liquidados[c], 'estado_biess': 'liquidado'}
            else:
                resultado[c] = {'codigo': '', 'nombre': 'NO ENCONTRADO', 'cedula': c, 'estado_biess': 'no_encontrado'}
        return resultado
    except Exception:
        return {}

# =============================================================================
# UI HELPERS
# =============================================================================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind('<Enter>', self.enter)
        widget.bind('<Leave>', self.leave)

    def enter(self, event):
        x = event.x_root + 15
        y = event.y_root + 10
        self.tipwindow = tk.Toplevel(self.widget)
        self.tipwindow.wm_overrideredirect(True)
        self.tipwindow.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self.tipwindow, text=self.text, background='lightyellow',
                         font=('', 8), relief='solid', borderwidth=1, wraplength=250, padx=5, pady=3)
        label.pack()

    def leave(self, event):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

# =============================================================================
# MAIN APP
# =============================================================================
class SistemaPrestamosUnificado:
    def __init__(self, master):
        self.master = master
        self._running = True
        self.master.title("Sistema de Prestamos v7.0 - Unificado")
        self.master.geometry("1400x800")
        self.master.minsize(1000, 650)
        self.master.configure(bg=COL_BG)
        self.master.protocol('WM_DELETE_WINDOW', self._on_close)
        self._set_icon()

        self.conn = None
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.cache_empleados = {}
        self.masivo_buscar_por = tk.StringVar(value="cedula")
        self.tt_buscar_por = tk.StringVar(value="cedula")

        # Estado
        self.status_var = tk.StringVar(value="Listo")
        self.progress_var = tk.DoubleVar(value=0)
        self.cuotas_calculadas = None
        self.numero_egreso_calculado = None
        self.ultimos_egresos_data = []

        # Grid data (batch tab)
        self.grid_data = {}
        self.visible_entries = {}
        self.selected_cell = None
        self.total_rows = 2500
        self.visible_start = 0
        self.visible_count = 20

        self._setup_styles()
        self._setup_ui()
        self._bind_shortcuts()

        self.master.after(100, self._conectar_bd)

    def _set_icon(self):
        base = os.path.dirname(os.path.abspath(__file__))
        ico = os.path.join(base, 'logo_insevig.ico')
        png = os.path.join(base, 'logo_insevig.png')
        try:
            # Windows / EXE: iconbitmap con ICO
            self.master.iconbitmap(ico)
        except Exception:
            try:
                # Linux: iconphoto con PNG via PIL
                from PIL import Image, ImageTk
                img = Image.open(png)
                photo = ImageTk.PhotoImage(img)
                self.master.iconphoto(True, photo)
                self._icon_ref = photo  # evitar garbage collection
            except Exception:
                pass

    def _on_close(self):
        self._running = False
        try:
            self.thread_pool.shutdown(wait=False)
        except Exception:
            pass
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        try:
            self.master.destroy()
        except Exception:
            pass

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background=COL_WHITE, fieldbackground=COL_WHITE,
                       foreground='#2C3E50', rowheight=26, font=('Segoe UI', 9))
        style.configure('Treeview.Heading', background=COL_HEADER, foreground=COL_WHITE,
                       font=('Segoe UI', 9, 'bold'), relief='flat')
        style.map('Treeview',
                  background=[('selected', COL_ACCENT)],
                  foreground=[('selected', COL_WHITE)])
        style.configure('TLabel', background=COL_BG, font=('Segoe UI', 9))
        style.configure('TFrame', background=COL_BG)
        style.configure('TLabelframe', background=COL_BG)
        style.configure('TLabelframe.Label', background=COL_BG, font=('Segoe UI', 9, 'bold'),
                        foreground=COL_HEADER)
        style.configure('TButton', padding=5, font=('Segoe UI', 9))
        style.configure('TEntry', font=('Segoe UI', 10))
        style.configure('TCombobox', font=('Segoe UI', 9))
        style.configure('TRadiobutton', background=COL_BG, font=('Segoe UI', 9))
        style.configure('TCheckbutton', background=COL_BG, font=('Segoe UI', 9))
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('TNotebook', background=COL_BG, tabmargins=[2, 4, 0, 0])
        style.configure('TNotebook.Tab', padding=[14, 6], font=('Segoe UI', 9, 'bold'),
                        background='#BBDEFB', foreground='#0D47A1')
        style.map('TNotebook.Tab',
                  background=[('selected', COL_HEADER)],
                  foreground=[('selected', COL_WHITE)])
        style.configure('Horizontal.TProgressbar', troughcolor='#BBDEFB',
                        background=COL_ACCENT, thickness=6)

    def _conectar_bd(self):
        self._set_status("Conectando al sistema...", COL_PEND)
        def bg():
            conn, err = conectar_bd()
            self.master.after(0, lambda: self._conectar_hecho(conn, err))
        threading.Thread(target=bg, daemon=True).start()

    def _conectar_hecho(self, conn, err):
        if err:
            self.conn = None
            self._set_status(f"Error de conexión: {err}", COL_DANGER)
            messagebox.showerror("Error de conexión", f"No se pudo conectar al sistema:\n{err}")
        else:
            self.conn = conn
            self._set_status("Conectado - Listo", COL_OK)
            self._cargar_ultimos_egresos()

    def _set_status(self, msg, color=COL_HEADER):
        self.status_var.set(msg)
        try:
            self.status_label.configure(foreground=color)
        except:
            pass
        try:
            self.master.update_idletasks()
        except:
            pass

    # === UI SETUP ===
    def _setup_ui(self):
        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self.master, bg=COL_HEADER, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        left_hdr = tk.Frame(header, bg=COL_HEADER)
        left_hdr.pack(side=tk.LEFT, padx=14, pady=6)
        tk.Label(left_hdr, text="SISTEMA DE PRESTAMOS", bg=COL_HEADER, fg=COL_WHITE,
                font=('Segoe UI', 15, 'bold')).pack(anchor=tk.W)
        tk.Label(left_hdr, text="INSEVIG  ·  v7.0",
                bg=COL_HEADER, fg='#BBDEFB', font=('Segoe UI', 8)).pack(anchor=tk.W)

        right_hdr = tk.Frame(header, bg=COL_HEADER)
        right_hdr.pack(side=tk.RIGHT, padx=14)
        sec_tag = "● SEGURIDAD ACTIVA" if SEGURIDAD_DISPONIBLE else "● SIN SEGURIDAD"
        sec_color = COL_OK if SEGURIDAD_DISPONIBLE else COL_DANGER
        tk.Label(right_hdr, text=sec_tag, bg=COL_HEADER, fg=sec_color,
                font=('Segoe UI', 9, 'bold')).pack(anchor=tk.E)

        # ── Progress bar ─────────────────────────────────────────────────
        prog = ttk.Progressbar(self.master, variable=self.progress_var,
                               maximum=100, style='Horizontal.TProgressbar')
        prog.pack(fill=tk.X, padx=0, pady=0)

        # ── Notebook ─────────────────────────────────────────────────────
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 2))

        self.tab_individual = ttk.Frame(self.notebook)
        self.tab_masiva = ttk.Frame(self.notebook)
        self.tab_todos_tipos = ttk.Frame(self.notebook)
        self.tab_tt_individual = ttk.Frame(self.notebook)
        self.tab_biess = ttk.Frame(self.notebook)
        self.tab_consulta = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_individual,    text="  Préstamo Individual  ")
        self.notebook.add(self.tab_masiva,        text="  Carga Masiva Préstamos  ")
        self.notebook.add(self.tab_todos_tipos,   text="  Egresos / Ingresos  ")
        self.notebook.add(self.tab_tt_individual, text="  Registro Individual  ")
        self.notebook.add(self.tab_biess,         text="  BIESS Quirografarios  ")
        self.notebook.add(self.tab_consulta,      text="  Consulta / Edición  ")

        self._build_tab_individual()
        self._build_tab_masiva()
        self._build_tab_todos_tipos()
        self._build_tt_individual_tab(self.tab_tt_individual)
        self._build_biess_tab()
        self._build_consulta_tab()

        # ── Status bar ───────────────────────────────────────────────────
        bar = tk.Frame(self.master, bg=COL_HEADER, height=28)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)
        self.status_label = tk.Label(bar, textvariable=self.status_var, bg=COL_HEADER,
                                     fg=COL_WHITE, font=('Consolas', 9), anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=12)
        self.conn_status_var = tk.StringVar(value="Conectando...")
        tk.Label(bar, textvariable=self.conn_status_var, bg=COL_HEADER,
                fg='#89AAC8', font=('Consolas', 9)).pack(side=tk.RIGHT, padx=12)

    def _dialogo_confirmar(self, titulo, descripcion, columnas, filas, on_ok):
        """Dialogo de confirmacion con tabla scrollable. on_ok se llama solo si el usuario confirma."""
        w, h = 900, 540
        dlg = tk.Toplevel(self.master)
        dlg.title(titulo)
        dlg.geometry(f"{w}x{h}")
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        dlg.resizable(True, True)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - w) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.focus_set()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except Exception:
            pass

        # Header
        hdr = tk.Frame(dlg, bg=COL_HEADER, height=44)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  ⚠  {titulo}", bg=COL_HEADER, fg=COL_WHITE,
                font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=12, pady=10)

        # Descripcion en banner amarillo
        desc_f = tk.Frame(dlg, bg='#FFF8E1', relief='groove', bd=1)
        desc_f.pack(fill=tk.X, padx=12, pady=(8, 2))
        tk.Label(desc_f, text=descripcion, font=('Segoe UI', 9), fg='#4E342E',
                bg='#FFF8E1', justify=tk.LEFT, wraplength=860).pack(anchor=tk.W, padx=10, pady=6)

        # Contador
        cnt_f = tk.Frame(dlg, bg=COL_BG)
        cnt_f.pack(fill=tk.X, padx=14)
        tk.Label(cnt_f, text=f"Registros a ingresar: {len(filas):,}",
                font=('Segoe UI', 9, 'bold'), fg=COL_HEADER, bg=COL_BG).pack(side=tk.LEFT, pady=4)

        # Tabla scrollable
        tf = ttk.Frame(dlg)
        tf.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
        col_names = [c[0] for c in columnas]
        tree = ttk.Treeview(tf, columns=col_names, show="headings", selectmode="none")
        for nombre, ancho in columnas:
            tree.heading(nombre, text=nombre, anchor=tk.W)
            tree.column(nombre, width=ancho, minwidth=30, stretch=True, anchor=tk.W)
        tree.tag_configure('par',   background='#E3F2FD')
        tree.tag_configure('impar', background=COL_WHITE)
        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL,   command=tree.yview)
        hsb = ttk.Scrollbar(tf, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for idx, fila in enumerate(filas):
            tree.insert("", tk.END, values=fila, tags=('par' if idx % 2 == 0 else 'impar',))

        # Botones
        bf = tk.Frame(dlg, bg=COL_BG)
        bf.pack(fill=tk.X, padx=12, pady=10)

        def _confirmar():
            dlg.destroy()
            on_ok()

        tk.Button(bf, text="  CONFIRMAR E INGRESAR  ", command=_confirmar,
                 bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 10, 'bold'),
                 relief='flat', cursor='hand2', padx=8, pady=5).pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="  Cancelar  ", command=dlg.destroy,
                 bg=COL_DANGER, fg=COL_WHITE, font=('Segoe UI', 10),
                 relief='flat', cursor='hand2', pady=5).pack(side=tk.LEFT, padx=3)
        tk.Label(bf, text="Revise la lista antes de confirmar",
                font=('Segoe UI', 8, 'italic'), fg='#888', bg=COL_BG).pack(side=tk.RIGHT, padx=6)
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    def _bind_shortcuts(self):
        self.master.bind('<Control-n>', lambda e: (self._limpiar_campos(), self.notebook.select(0)))
        self.master.bind('<Control-f>', lambda e: self._buscar_empleado())
        self.master.bind('<Control-q>', lambda e: self._on_close())
        def _ctrl_v(e):
            tab = self.notebook.index("current")
            if tab == 1:    # Tab 2 Carga Masiva Prestamos
                self._handle_paste(e)
                return "break"
            elif tab == 2:  # Tab 3 Todos los Tipos (masivo)
                self._tt_paste()
                return "break"
            # Tab 0 (individual), Tab 3 (tt_ind), Tab 4 (BIESS): comportamiento normal
        self.master.bind('<Control-v>', _ctrl_v)
        self.master.bind('<Control-V>', _ctrl_v)
        self.master.bind('<F5>', lambda e: self._cargar_ultimos_egresos())
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    def _on_tab_changed(self, event=None):
        tab = self.notebook.index("current")
        if tab == 0:
            self._cargar_ultimos_egresos()
        elif tab == 2:
            self._tt_historial_buscar()
        elif tab == 3:
            self._ind_historial_buscar()

    # ===================================================================
    # TAB INDIVIDUAL
    # ===================================================================
    def _build_tab_individual(self):
        p = ttk.PanedWindow(self.tab_individual, orient=tk.HORIZONTAL)
        p.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: form
        left = ttk.Frame(p)
        p.add(left, weight=2)

        fdata = ttk.LabelFrame(left, text="Datos del Prestamo", padding=10)
        fdata.pack(fill=tk.X, pady=5)

        ttk.Label(fdata, text="ID Empleado:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.emp_entry = ttk.Entry(fdata, width=14, font=('Segoe UI', 10))
        self.emp_entry.grid(row=0, column=1, sticky=tk.W, pady=4, ipady=4)
        self.emp_entry.bind('<KeyRelease>', lambda e: self._debounced('emp', 400, self._buscar_empleado_nombre))
        tk.Button(fdata, text="  Buscar  ", command=self._buscar_empleado,
                 bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2').grid(row=0, column=2, padx=6)

        self.emp_name_var = tk.StringVar()
        tk.Label(fdata, textvariable=self.emp_name_var, fg=COL_ACCENT,
                font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(fdata, text="Valor Total ($):").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.valor_entry = ttk.Entry(fdata, width=16, font=('Segoe UI', 10))
        self.valor_entry.grid(row=1, column=1, sticky=tk.W, pady=4, ipady=4)

        self.planif_inteligente = tk.BooleanVar(value=True)
        ttk.Checkbutton(fdata, text="Planificacion inteligente (respeta cuotas existentes)",
                       variable=self.planif_inteligente).grid(row=2, column=0, columnspan=4, sticky=tk.W, pady=4)

        self.label_cuota = ttk.Label(fdata, text="Valor cuota mensual ($):")
        self.label_cuota.grid(row=3, column=0, sticky=tk.W, pady=4)
        self.cuota_entry = ttk.Entry(fdata, width=16, font=('Segoe UI', 10))
        self.cuota_entry.grid(row=3, column=1, sticky=tk.W, pady=4, ipady=4)

        ttk.Label(fdata, text="Fecha (DD/MM/AAAA):").grid(row=4, column=0, sticky=tk.W, pady=4)
        self.fecha_entry = ttk.Entry(fdata, width=14, font=('Segoe UI', 10))
        self.fecha_entry.insert(0, datetime.now().strftime('%d/%m/%Y'))
        self.fecha_entry.grid(row=4, column=1, sticky=tk.W, pady=4, ipady=4)

        ttk.Label(fdata, text="Observacion:").grid(row=5, column=0, sticky=tk.W+tk.N, pady=4)
        self.obs_text = tk.Text(fdata, width=50, height=3, wrap=tk.WORD,
                               font=('Segoe UI', 9), relief='solid', borderwidth=1)
        self.obs_text.grid(row=5, column=1, columnspan=3, sticky=tk.W, pady=4)

        ttk.Label(fdata, text="Tipo Transaccion:").grid(row=6, column=0, sticky=tk.W, pady=4)
        self.tipo_trans_var = tk.StringVar()
        t = ttk.Combobox(fdata, textvariable=self.tipo_trans_var, width=28, state="readonly")
        t['values'] = list(TIPOS_TRANSACCION.keys())
        t.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=4)

        # ── Botones de accion ─────────────────────────────────────────
        btnf = tk.Frame(left, bg=COL_BG)
        btnf.pack(fill=tk.X, pady=8)
        self.btn_calcular = tk.Button(btnf, text="  Calcular  ", command=self._calcular_prestamo,
                                      bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 10, 'bold'),
                                      relief='flat', cursor='hand2', padx=4, pady=3)
        self.btn_calcular.pack(side=tk.LEFT, padx=3)
        self.btn_ingresar = tk.Button(btnf, text="  Ingresar Prestamo  ",
                                      command=self._ingresar_prestamo,
                                      bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 10, 'bold'),
                                      relief='flat', cursor='hand2', padx=4, pady=3,
                                      state=tk.DISABLED)
        self.btn_ingresar.pack(side=tk.LEFT, padx=3)
        tk.Button(btnf, text="  Limpiar  ", command=self._limpiar_campos,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2', pady=3).pack(side=tk.LEFT, padx=3)
        tk.Button(btnf, text="  Exportar  ", command=self._exportar_resumen,
                 bg='#8E44AD', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2', pady=3).pack(side=tk.LEFT, padx=3)

        # Summary
        sf = ttk.LabelFrame(left, text="Resumen", padding=5)
        sf.pack(fill=tk.BOTH, expand=True, pady=5)
        self.summary = scrolledtext.ScrolledText(sf, height=10, wrap=tk.WORD)
        self.summary.pack(fill=tk.BOTH, expand=True)
        self.summary.config(state=tk.DISABLED)

        # Right: historial de préstamos con buscador
        right = ttk.Frame(p)
        p.add(right, weight=1)

        ef = tk.Frame(right, bg=COL_BG)
        ef.pack(fill=tk.BOTH, expand=True)

        hdr_ef = tk.Frame(ef, bg=COL_HEADER, height=36)
        hdr_ef.pack(fill=tk.X); hdr_ef.pack_propagate(False)
        tk.Label(hdr_ef, text="  Historial de Préstamos",
                 bg=COL_HEADER, fg=COL_WHITE,
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=8, pady=8)

        # Buscador
        sf_e = tk.Frame(ef, bg=COL_BG)
        sf_e.pack(fill=tk.X, padx=4, pady=4)
        self._ind_prest_filtro_var = tk.StringVar()
        ttk.Entry(sf_e, textvariable=self._ind_prest_filtro_var, width=16,
                  font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0,3), ipady=3,
                                              fill=tk.X, expand=True)
        tk.Button(sf_e, text="Buscar", command=self._cargar_ultimos_egresos,
                  bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(sf_e, text="↺",
                  command=lambda: (self._ind_prest_filtro_var.set(""),
                                   self._cargar_ultimos_egresos()),
                  bg='#78909C', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2', width=2).pack(side=tk.LEFT, padx=2)
        self._ind_prest_filtro_var.trace_add("write",
            lambda *a: self.master.after(600, self._cargar_ultimos_egresos))

        tk.Label(sf_e, text="  N° o nombre", bg=COL_BG,
                 fg='gray', font=('Segoe UI', 7)).pack(side=tk.LEFT)

        # Treeview
        tf_e = ttk.Frame(ef)
        tf_e.pack(fill=tk.BOTH, expand=True, padx=4)
        cols = ("Egreso", "Empleado", "Fecha", "Valor")
        self.egresos_tree = ttk.Treeview(tf_e, columns=cols, show="headings", height=20)
        self.egresos_tree.heading("Egreso",   text="#",        anchor=tk.CENTER)
        self.egresos_tree.heading("Empleado", text="Empleado", anchor=tk.W)
        self.egresos_tree.heading("Fecha",    text="Fecha",    anchor=tk.CENTER)
        self.egresos_tree.heading("Valor",    text="Valor",    anchor=tk.E)
        self.egresos_tree.column("Egreso",   width=60,  anchor=tk.CENTER, stretch=False)
        self.egresos_tree.column("Empleado", width=200, anchor=tk.W,      stretch=True)
        self.egresos_tree.column("Fecha",    width=85,  anchor=tk.CENTER, stretch=False)
        self.egresos_tree.column("Valor",    width=80,  anchor=tk.E,      stretch=False)
        self.egresos_tree.tag_configure('par',   background='#FFF8E1')
        self.egresos_tree.tag_configure('impar', background='#FFF3E0')
        vsb = ttk.Scrollbar(tf_e, orient=tk.VERTICAL, command=self.egresos_tree.yview)
        self.egresos_tree.configure(yscrollcommand=vsb.set)
        self.egresos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.egresos_tree.bind("<Double-1>", self._prest_ind_ver_detalle)

        # Botón
        bot_ef = tk.Frame(ef, bg=COL_BG)
        bot_ef.pack(fill=tk.X, padx=4, pady=(3, 0))
        tk.Button(bot_ef, text="  Ver / Editar  ",
                  command=self._prest_ind_ver_detalle,
                  bg=COL_PEND, fg=COL_WHITE, font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT)
        self._prest_ind_info_var = tk.StringVar(value="")
        tk.Label(bot_ef, textvariable=self._prest_ind_info_var,
                 bg=COL_BG, fg='gray', font=('Segoe UI', 8)).pack(side=tk.RIGHT)

        self._debounce_timers = {}

    def _debounced(self, key, ms, fn):
        if key in self._debounce_timers:
            self.master.after_cancel(self._debounce_timers[key])
        self._debounce_timers[key] = self.master.after(ms, fn)

    def _buscar_empleado_nombre(self):
        val = self.emp_entry.get().strip()
        if not val:
            return
        if val.isdigit():
            self._buscar_empleado_por_id(int(val))
        else:
            self._set_status("Usar ID numerico", COL_PEND)

    def _buscar_empleado_por_id(self, emp_id):
        def bg():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                cursor = conn2.cursor()
                cursor.execute("SELECT APELLIDOS, NOMBRES FROM RPEMPLEA WITH (NOLOCK) WHERE EMPLEADO = ?", emp_id)
                r = cursor.fetchone()
                self.master.after(0, lambda: self._nombre_hecho(r))
            finally:
                conn2.close()
        threading.Thread(target=bg, daemon=True).start()

    def _nombre_hecho(self, r):
        if r:
            self.emp_name_var.set(f"{str(r.APELLIDOS or '').strip()} {str(r.NOMBRES or '').strip()}".strip())
        else:
            self.emp_name_var.set("(No encontrado)")

    def _buscar_empleado(self):
        if not self.conn:
            return
        dlg = tk.Toplevel(self.master)
        dlg.title("Buscar Empleado")
        dlg.geometry("640x460")
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 640) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 460) // 2
        dlg.geometry(f"640x460+{x}+{y}")
        dlg.focus_set()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except:
            pass

        # Header del diálogo
        hdr = tk.Frame(dlg, bg=COL_HEADER, height=36)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Buscar Empleado", bg=COL_HEADER, fg=COL_WHITE,
                font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=12, pady=6)

        sf = tk.Frame(dlg, bg=COL_BG)
        sf.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(sf, text="Filtro:", bg=COL_BG, font=('Segoe UI', 9)).pack(side=tk.LEFT)
        filtro_var = tk.StringVar()
        ttk.Entry(sf, textvariable=filtro_var, width=40, font=('Segoe UI', 10)).pack(
            side=tk.LEFT, padx=8, ipady=3)

        tree = ttk.Treeview(dlg, columns=("ID", "Apellidos", "Nombres", "Depto"), show="headings", height=15)
        tree.heading("ID", text="ID")
        tree.heading("Apellidos", text="Apellidos")
        tree.heading("Nombres", text="Nombres")
        tree.heading("Depto", text="Depto")
        tree.column("ID", width=65, anchor=tk.CENTER)
        tree.column("Apellidos", width=210)
        tree.column("Nombres", width=210)
        tree.column("Depto", width=75, anchor=tk.CENTER)
        tree.tag_configure('par',   background='#F0F4F8')
        tree.tag_configure('impar', background=COL_WHITE)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def buscar():
            filtro = filtro_var.get().strip()
            def bg():
                conn2, err = conectar_bd()
                if err:
                    return
                try:
                    rows, err = buscar_empleados(conn2, filtro, 200)
                    self.master.after(0, lambda: _mostrar(rows))
                finally:
                    conn2.close()
            threading.Thread(target=bg, daemon=True).start()

        def _mostrar(rows):
            for i in tree.get_children():
                tree.delete(i)
            for idx, r in enumerate(rows):
                tag = 'par' if idx % 2 == 0 else 'impar'
                tree.insert("", tk.END, values=(r['id'], r['apellidos'], r['nombres'], r['depto']), tags=(tag,))

        def seleccionar():
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0], 'values')
                self.emp_entry.delete(0, tk.END)
                self.emp_entry.insert(0, str(vals[0]))
                self._buscar_empleado_por_id(int(vals[0]))
                dlg.destroy()

        tree.bind("<Double-1>", lambda e: seleccionar())

        bf = tk.Frame(dlg, bg=COL_BG)
        bf.pack(fill=tk.X, padx=10, pady=6)
        tk.Button(bf, text="  Buscar  ", command=buscar,
                 bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="  Seleccionar  ", command=seleccionar,
                 bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="  Cerrar  ", command=dlg.destroy,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2').pack(side=tk.RIGHT, padx=3)

        filtro_var.trace_add("write", lambda *a: self.master.after(500, buscar))
        buscar()

    def _validar_campos_individuales(self):
        emp_str = self.emp_entry.get().strip()
        if not emp_str or not emp_str.isdigit():
            return False, None, None, None, None
        emp_id = int(emp_str)
        try:
            valor = float(self.valor_entry.get().strip())
        except:
            self._set_status("Valor total invalido", COL_DANGER)
            return False, None, None, None, None
        if valor <= 0:
            self._set_status("Valor total debe ser > 0", COL_DANGER)
            return False, None, None, None, None
        cuota_str = self.cuota_entry.get().strip()
        usar_planif = self.planif_inteligente.get()
        try:
            if usar_planif:
                cv = float(cuota_str)
            else:
                cv = int(cuota_str)
        except:
            self._set_status("Valor/Nro de cuotas invalido", COL_DANGER)
            return False, None, None, None, None
        if cv <= 0:
            self._set_status("Valor/Nro cuotas debe ser > 0", COL_DANGER)
            return False, None, None, None, None
        fecha_str = self.fecha_entry.get().strip()
        try:
            if '-' in fecha_str:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
            else:
                fecha = datetime.strptime(fecha_str, '%d/%m/%Y')
        except:
            fecha = datetime.now()
        return True, emp_id, valor, cv, fecha

    def _calcular_prestamo(self):
        valido, emp_id, valor, cv, fecha = self._validar_campos_individuales()
        if not valido:
            return
        self.btn_calcular.config(state=tk.DISABLED)
        self._set_status("Calculando...", COL_PEND)
        usar_planif = self.planif_inteligente.get()
        tipo_trans = self.tipo_trans_var.get()
        obs = self.obs_text.get("1.0", tk.END).strip()
        if tipo_trans:
            obs = f"{obs} {tipo_trans}" if obs else tipo_trans

        def bg():
            conn2, err2 = conectar_bd()
            if err2:
                self.master.after(0, lambda: self._mostrar_error_calculo(f"Error BD: {err2}"))
                return
            try:
                num, err_num = obtener_proximo_numero_egreso(conn2)
                if err_num:
                    self.master.after(0, lambda: self._mostrar_error_calculo(f"Error egreso: {err_num}"))
                    return
                egreso_num = num

                if usar_planif:
                    cuotas, error = planificar_cuotas_inteligente(conn2, emp_id, valor, cv, fecha)
                else:
                    cuotas, error = calcular_cuotas_tradicional(valor, int(cv), fecha)

                if error:
                    self.master.after(0, lambda: self._mostrar_error_calculo(error))
                    return

                depto, secc, _ = obtener_detalles_empleado(conn2, emp_id)
                self.master.after(0, lambda: self._mostrar_resumen(emp_id, valor, cuotas, egreso_num, depto, secc))
            except Exception as e:
                self.master.after(0, lambda: self._mostrar_error_calculo(str(e)))
            finally:
                conn2.close()

        threading.Thread(target=bg, daemon=True).start()

    def _mostrar_error_calculo(self, msg):
        if not self._running:
            return
        self._set_status(f"Error: {msg}", COL_DANGER)
        self.btn_calcular.config(state=tk.NORMAL)
        self.cuotas_calculadas = None
        self.numero_egreso_calculado = None
        self.btn_ingresar.config(state=tk.DISABLED)
        messagebox.showerror("Error", msg)

    def _mostrar_resumen(self, emp_id, valor_total, cuotas, egreso_num, depto, secc):
        if not self._running:
            return
        self.cuotas_calculadas = cuotas
        self.numero_egreso_calculado = egreso_num
        self.summary.config(state=tk.NORMAL)
        self.summary.delete("1.0", tk.END)

        total_calc = sum(c['valor'] for c in cuotas)
        lines = []
        lines.append(f"Empleado: {emp_id} - {self.emp_name_var.get()}")
        lines.append(f"Valor Total: ${valor_total:.2f}")
        lines.append(f"Nro Egreso: {egreso_num}")
        lines.append(f"Cuotas: {len(cuotas)}")
        lines.append(f"Total calculado: ${total_calc:.2f}")
        lines.append(f"Depto: {depto}  Seccion: {secc}")
        lines.append("")
        lines.append(f"{'Cuota':<8} {'Vencimiento':<15} {'Valor':<12}")
        lines.append("-"*35)
        for i, c in enumerate(cuotas, 1):
            fv = c['fecha_vencimiento']
            if isinstance(fv, datetime):
                fv_str = fv.strftime('%d/%m/%Y')
            else:
                fv_str = str(fv)[:10]
            lines.append(f"{i:<8} {fv_str:<15} ${c['valor']:<8.2f}")

        self.summary.insert(tk.END, "\n".join(lines))
        self.summary.config(state=tk.DISABLED)
        self.btn_calcular.config(state=tk.NORMAL)
        self.btn_ingresar.config(state=tk.NORMAL)
        self._set_status(f"Calculado: {len(cuotas)} cuotas, Total: ${total_calc:.2f}", COL_OK)

    def _ingresar_prestamo(self):
        if not self.cuotas_calculadas or self.numero_egreso_calculado is None:
            self._set_status("Calcule el prestamo primero", COL_PEND)
            return
        if not self.conn:
            self._set_status("Sin conexión al sistema", COL_DANGER)
            return

        emp_str = self.emp_entry.get().strip()
        if not emp_str.isdigit():
            return
        emp_id = int(emp_str)
        try:
            valor = float(self.valor_entry.get().strip())
        except:
            return

        fecha_str = self.fecha_entry.get().strip()
        try:
            if '-' in fecha_str:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
            else:
                fecha = datetime.strptime(fecha_str, '%d/%m/%Y')
        except:
            fecha = datetime.now()

        obs = self.obs_text.get("1.0", tk.END).strip()
        tipo_trans = self.tipo_trans_var.get()
        if tipo_trans:
            obs = f"{obs} {tipo_trans}" if obs else tipo_trans

        total_cuotas = sum(c['valor'] for c in self.cuotas_calculadas)
        cuotas = self.cuotas_calculadas
        egreso = self.numero_egreso_calculado

        filas_dlg = []
        for i, c in enumerate(cuotas, 1):
            fv = c['fecha_vencimiento']
            fv_str = fv.strftime('%d/%m/%Y') if isinstance(fv, datetime) else str(fv)[:10]
            filas_dlg.append((i, fv_str, f"${c['valor']:,.2f}"))

        desc = (f"Empleado: {emp_id} — {self.emp_name_var.get()}\n"
                f"Nro Egreso: #{egreso}   Valor: ${valor:,.2f}   Total cuotas: ${total_cuotas:,.2f}")

        def proceder():
            self.btn_ingresar.config(state=tk.DISABLED)
            self._set_status("Ingresando prestamo...", COL_PEND)
            def bg():
                try:
                    exito, msg = insertar_prestamo(self.conn, emp_id, egreso, fecha,
                                                   obs or "Prestamo", cuotas, valor)
                    if exito:
                        ok2, err_upd = actualizar_ultimo_egreso(self.conn, egreso)
                        if ok2:
                            self.conn.commit()
                            log_operacion('INSERT', emp_id, egreso,
                                          f"Ingresado prestamo ${valor:.2f}, {len(cuotas)} cuotas")
                            self.master.after(0, lambda: self._ingreso_ok())
                        else:
                            self.conn.rollback()
                            self.master.after(0, lambda: self._ingreso_error(f"Error contador: {err_upd}"))
                    else:
                        self.conn.rollback()
                        self.master.after(0, lambda: self._ingreso_error(f"INSERT fallo: {msg}"))
                except Exception as e:
                    try:
                        self.conn.rollback()
                    except:
                        pass
                    self.master.after(0, lambda: self._ingreso_error(str(e)))
            threading.Thread(target=bg, daemon=True).start()

        self._dialogo_confirmar(
            "Confirmar Prestamo",
            desc,
            [("Cuota", 70), ("Vencimiento", 130), ("Valor", 110)],
            filas_dlg,
            proceder
        )

    def _ingreso_ok(self):
        if not self._running:
            return
        self._set_status("Prestamo ingresado exitosamente", COL_OK)
        self.btn_ingresar.config(state=tk.NORMAL)
        self.btn_calcular.config(state=tk.NORMAL)
        self.cuotas_calculadas = None
        self.numero_egreso_calculado = None
        messagebox.showinfo("Exito", "Prestamo ingresado correctamente")
        self._cargar_ultimos_egresos()
        self._limpiar_campos()

    def _ingreso_error(self, msg):
        if not self._running:
            return
        self._set_status(f"Error: {msg}", COL_DANGER)
        self.btn_ingresar.config(state=tk.NORMAL)
        self.btn_calcular.config(state=tk.NORMAL)
        messagebox.showerror("Error", msg)

    def _limpiar_campos(self):
        self.emp_entry.delete(0, tk.END)
        self.emp_name_var.set("")
        self.valor_entry.delete(0, tk.END)
        self.cuota_entry.delete(0, tk.END)
        self.fecha_entry.delete(0, tk.END)
        self.fecha_entry.insert(0, datetime.now().strftime('%d/%m/%Y'))
        self.obs_text.delete("1.0", tk.END)
        self.tipo_trans_var.set("")
        self.summary.config(state=tk.NORMAL)
        self.summary.delete("1.0", tk.END)
        self.summary.config(state=tk.DISABLED)
        self.cuotas_calculadas = None
        self.numero_egreso_calculado = None
        self.btn_ingresar.config(state=tk.DISABLED)

    def _exportar_resumen(self):
        if not self.cuotas_calculadas:
            messagebox.showwarning("Sin datos", "Calcule un prestamo primero")
            return
        fn = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv"), ("Texto", "*.txt")]
        )
        if not fn:
            return
        try:
            df = pd.DataFrame(self.cuotas_calculadas)
            if fn.endswith('.xlsx'):
                df.to_excel(fn, index=False)
            elif fn.endswith('.csv'):
                df.to_csv(fn, index=False)
            else:
                with open(fn, 'w') as f:
                    for c in self.cuotas_calculadas:
                        f.write(f"{c['secuencia']}\t{c['fecha_vencimiento']}\t{c['valor']}\n")
            self._set_status(f"Exportado a {fn}", COL_OK)
        except Exception as e:
            self._set_status(f"Error exportando: {e}", COL_DANGER)

    def _cargar_ultimos_egresos(self):
        if not self.conn:
            return
        filtro = getattr(self, '_ind_prest_filtro_var', None)
        filtro = filtro.get().strip() if filtro else ""
        def bg(f=filtro):
            conn2, err = conectar_bd()
            if err:
                return
            try:
                if f:
                    # Búsqueda por filtro: usar obtener_historial_todos filtrado a CLASE 205
                    rows, _ = obtener_historial_todos(conn2, f, 200)
                    egresos = [r for r in rows if r['clase'] == '205']
                    # Convertir al formato esperado por _mostrar_egresos
                    egresos_fmt = [{
                        'egreso':      r['numero'],
                        'empleado':    r['nombre'],
                        'fecha':       r['fecha'],
                        'valor':       f"${r['valor']:,.2f}",
                        'observacion': r['concepto'],
                    } for r in egresos]
                else:
                    egresos_fmt, _ = obtener_ultimos_egresos(conn2, 200)
                self.master.after(0, lambda e=egresos_fmt: self._mostrar_egresos(e, None))
            finally:
                conn2.close()
        threading.Thread(target=bg, daemon=True).start()

    def _mostrar_egresos(self, egresos, err):
        if not self._running:
            return
        if err:
            return
        self.ultimos_egresos_data = egresos
        for item in self.egresos_tree.get_children():
            self.egresos_tree.delete(item)
        for idx, e in enumerate(egresos):
            tag = 'par' if idx % 2 == 0 else 'impar'
            egreso_str = f"{int(e['egreso']):05d}" if e['egreso'] else ''
            self.egresos_tree.insert("", tk.END, values=(
                egreso_str, e['empleado'], e['fecha'], e['valor']
            ), tags=(tag,))
        if hasattr(self, '_prest_ind_info_var'):
            aviso = " (máx 200)" if len(egresos) == 200 else ""
            self._prest_ind_info_var.set(f"{len(egresos)}{aviso}")

    def _mostrar_obs_egreso(self, event):
        sel = self.egresos_tree.selection()
        if not sel:
            return
        vals = self.egresos_tree.item(sel[0], 'values')
        egreso_num_str = str(vals[0]).strip()

        # Buscar observacion en los datos cargados (igual que el original)
        observacion = "Sin observacion"
        for e in self.ultimos_egresos_data:
            if f"{int(e['egreso']):05d}" == egreso_num_str:
                observacion = e.get('observacion', '') or "Sin observacion"
                break

        dlg = tk.Toplevel(self.master)
        dlg.title(f"Observacion — Egreso #{egreso_num_str}")
        dlg.geometry("580x380")
        dlg.configure(bg=COL_BG)
        dlg.transient(self.master)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 580) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 380) // 2
        dlg.geometry(f"580x380+{x}+{y}")
        dlg.focus_set()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except:
            pass

        hdr = tk.Frame(dlg, bg=COL_HEADER, height=36)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"Egreso #{egreso_num_str}  —  {vals[1]}",
                bg=COL_HEADER, fg=COL_WHITE, font=('Segoe UI', 10, 'bold')).pack(
                side=tk.LEFT, padx=12, pady=6)

        info_f = ttk.LabelFrame(dlg, text="Informacion del Egreso", padding=8)
        info_f.pack(fill=tk.X, padx=12, pady=(8, 4))
        tk.Label(info_f, text=f"Egreso: {egreso_num_str}  |  Empleado: {vals[1]}  |  Fecha: {vals[2]}  |  Valor: {vals[3]}",
                font=('Segoe UI', 9, 'bold'), fg=COL_HEADER).pack(anchor=tk.W)

        obs_f = ttk.LabelFrame(dlg, text="Observacion Completa", padding=8)
        obs_f.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
        t = scrolledtext.ScrolledText(obs_f, wrap=tk.WORD, height=8,
                                      font=('Segoe UI', 10), relief='flat', bg='#F8F9FA')
        t.pack(fill=tk.BOTH, expand=True)
        t.insert("1.0", observacion)
        t.config(state=tk.NORMAL)  # editable para poder seleccionar/copiar

        bf = tk.Frame(dlg, bg=COL_BG)
        bf.pack(fill=tk.X, padx=12, pady=8)

        def _copiar():
            dlg.clipboard_clear()
            dlg.clipboard_append(observacion)
            messagebox.showinfo("Copiado", "Observacion copiada al portapapeles", parent=dlg)

        def _sel_todo():
            t.tag_add("sel", "1.0", "end")
            t.mark_set("insert", "1.0")
            t.see("insert")

        tk.Button(bf, text="  Copiar  ", command=_copiar,
                 bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="  Sel. Todo  ", command=_sel_todo,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf, text="  Cerrar  ", command=dlg.destroy,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2').pack(side=tk.RIGHT, padx=3)

    def _prest_ind_ver_detalle(self, event=None):
        """Doble-clic en el historial de Tab 1: abre cuotas del préstamo."""
        sel = self.egresos_tree.selection()
        if not sel:
            return
        vals = self.egresos_tree.item(sel[0], 'values')
        egreso_num_str = str(vals[0]).strip()
        empleado_nombre = str(vals[1]).strip()
        valor_str = str(vals[3]).strip()

        # Buscar en datos cargados
        for e in self.ultimos_egresos_data:
            if f"{int(e['egreso']):05d}" == egreso_num_str:
                # Necesitamos el ID del empleado — buscarlo por nombre en BD
                def _bg(num=e['egreso'], emp_nombre=e['empleado'], val_str=valor_str):
                    conn2, err = conectar_bd()
                    if err:
                        return
                    try:
                        cursor = conn2.cursor()
                        # Obtener EMPLEADO ID desde RPINGDES directamente
                        cursor.execute("""
                            SELECT TOP 1 EMPLEADO FROM RPINGDES WITH (NOLOCK)
                            WHERE NUMERO = ? AND CLASE = '205'
                        """, (num,))
                        row = cursor.fetchone()
                        if row:
                            emp_id = row[0]
                            r_hist = {
                                'numero':   num,
                                'clase':    '205',
                                'empleado': emp_id,
                                'nombre':   emp_nombre,
                                'valor':    float(str(val_str).replace('$','').replace(',','')),
                                'cuotas':   1,
                                'concepto': '',
                                'fecha':    '',
                            }
                            self.master.after(0, lambda r=r_hist: self._tt_hist_dlg_prestamo(r))
                    finally:
                        conn2.close()
                threading.Thread(target=_bg, daemon=True).start()
                return

    # ===================================================================
    # TAB CARGA MASIVA
    # ===================================================================
    def _build_tab_masiva(self):
        main = ttk.Frame(self.tab_masiva, padding=5)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="CARGA MASIVA DE PRESTAMOS — CLASE 205", font=("Segoe UI", 14, "bold"),
                fg=COL_HEADER).pack(pady=3)

        # Config
        cf = ttk.Frame(main)
        cf.pack(fill=tk.X, pady=3)

        modo_frame = ttk.LabelFrame(cf, text="Modo de Calculo", padding=3)
        modo_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        self.modo_calculo = tk.StringVar(value="cuotas")
        ttk.Radiobutton(modo_frame, text="CUOTAS: Nro de cuotas", variable=self.modo_calculo, value="cuotas").pack(anchor=tk.W)
        ttk.Radiobutton(modo_frame, text="VALOR: Valor cuota mensual", variable=self.modo_calculo, value="valor").pack(anchor=tk.W)

        tipo_frame = ttk.LabelFrame(cf, text="Tipo Transaccion", padding=3)
        tipo_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5,0))
        self.masivo_tipo_trans = tk.StringVar(value="PRESTAMO_PRE01")
        tc = ttk.Combobox(tipo_frame, textvariable=self.masivo_tipo_trans, width=25, state="readonly")
        tc['values'] = list(TIPOS_TRANSACCION.keys())
        tc.pack(anchor=tk.W, pady=2)

        buscar_frame = ttk.LabelFrame(cf, text="Buscar Empleado Por", padding=3)
        buscar_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5,0))
        ttk.Radiobutton(buscar_frame, text="Codigo empleado", variable=self.masivo_buscar_por, value="codigo").pack(anchor=tk.W)
        ttk.Radiobutton(buscar_frame, text="Cedula", variable=self.masivo_buscar_por, value="cedula").pack(anchor=tk.W)

        # Instructions — cambia segun modo cedula/codigo
        self.masivo_instruc_var = tk.StringVar()
        self.masivo_instruc_frame = tk.LabelFrame(main, text="", padx=3, pady=3)
        self.masivo_instruc_frame.pack(fill=tk.X, pady=3)
        self.masivo_instruc_ej = tk.Label(self.masivo_instruc_frame, font=("Consolas", 9), fg=COL_ACCENT)
        self.masivo_instruc_ej.pack(anchor=tk.W)
        self.masivo_instruc_var.trace_add("write", lambda *a: self.masivo_instruc_frame.config(text=self.masivo_instruc_var.get()))
        self.masivo_buscar_por.trace_add("write", lambda *a: self._masivo_update_instruc())
        self._masivo_update_instruc()

        # Grid
        self._build_masivo_grid(main)

        # Nav
        nav = ttk.Frame(main)
        nav.pack(fill=tk.X, pady=3)
        ttk.Button(nav, text="-50", command=lambda: self._nav_masivo(-50)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="-20", command=lambda: self._nav_masivo(-20)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="+20", command=lambda: self._nav_masivo(20)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="+50", command=lambda: self._nav_masivo(50)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="INICIO", command=self._ir_inicio_masivo).pack(side=tk.LEFT, padx=10)

        # Action buttons
        btnf = ttk.Frame(main)
        btnf.pack(fill=tk.X, pady=3)
        tk.Button(btnf, text="  PEGAR (Ctrl+V)  ", command=self._paste_data,
                 bg=COL_PEND, fg="white", font=("Segoe UI", 10, "bold"),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        ttk.Button(btnf, text="Validar", command=self._validar_todos_masivo).pack(side=tk.LEFT, padx=3)
        ttk.Button(btnf, text="Limpiar", command=self._limpiar_masivo).pack(side=tk.LEFT, padx=3)
        self._btn_procesar_masivo = tk.Button(btnf, text="  PROCESAR  ", command=self._procesar_masivo,
                 bg=COL_OK, fg="white", font=("Segoe UI", 12, "bold"),
                 relief='flat', cursor='hand2')
        self._btn_procesar_masivo.pack(side=tk.LEFT, padx=10)

        # Log
        lf = ttk.LabelFrame(main, text="Log", padding=3)
        lf.pack(fill=tk.X, pady=3)
        self.log_text = scrolledtext.ScrolledText(lf, height=4, font=("Consolas", 9))
        self.log_text.pack(fill=tk.X)

        self._inicializar_grid_masivo()

    def _build_masivo_grid(self, parent):
        gf = ttk.LabelFrame(parent, text="Datos", padding=3)
        gf.pack(fill=tk.BOTH, expand=True, pady=3)
        container = ttk.Frame(gf)
        container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(container, height=280, bg=COL_WHITE)
        vsb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        hsb = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.grid_frame = ttk.Frame(self.canvas)
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        headers = ["#", "Codigo", "Nombre", "Valor Total", "Cuotas/Valor", "Fecha", "Observacion"]
        for col, h in enumerate(headers):
            tk.Label(self.grid_frame, text=h, font=("Arial", 9, "bold"),
                    relief="ridge", bg=COL_HEADER, fg="white", width={0:5,1:10,2:25,3:12,4:10,5:12,6:30}.get(col, 15)
                    ).grid(row=0, column=col, sticky="ew", padx=1, pady=1)

    def _inicializar_grid_masivo(self):
        self.grid_data = {}
        for i in range(50):
            self.grid_data[i] = {'codigo': '', 'nombre': '', 'valor_total': '',
                                 'cuotas_valor': '', 'fecha': '', 'observacion': '', 'procesado': False}
        self.visible_start = 0
        self._crear_filas_visibles()

    def _crear_filas_visibles(self):
        for wd in self.visible_entries.values():
            for w in wd.values():
                if w and w.winfo_exists():
                    w.destroy()
        self.visible_entries.clear()
        for i in range(self.visible_count):
            fila = self.visible_start + i
            if fila >= self.total_rows:
                break
            if fila not in self.grid_data:
                self.grid_data[fila] = {'codigo': '', 'nombre': '', 'valor_total': '',
                                        'cuotas_valor': '', 'fecha': '', 'observacion': '', 'procesado': False}
            self._crear_fila_masivo(fila, i+1)

    def _crear_fila_masivo(self, fila, fila_vis):
        d = self.grid_data[fila]
        w = {}
        tk.Label(self.grid_frame, text=str(fila+1), relief="ridge", bg="#f0f0f0", width=5).grid(row=fila_vis, column=0, sticky="ew", padx=1, pady=1)

        e = tk.Entry(self.grid_frame, width=10, justify="center")
        e.grid(row=fila_vis, column=1, sticky="ew", padx=1, pady=1)
        e.insert(0, d['codigo'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=0: self._select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._on_change(r, 'codigo', ev.widget.get()))
        w[0] = e

        e = tk.Entry(self.grid_frame, width=25, state="readonly", bg="#e8e8e8")
        e.grid(row=fila_vis, column=2, sticky="ew", padx=1, pady=1)
        if d['nombre']:
            e.config(state="normal")
            e.insert(0, d['nombre'])
            e.config(state="readonly")
        w[1] = e

        e = tk.Entry(self.grid_frame, width=12, justify="right")
        e.grid(row=fila_vis, column=3, sticky="ew", padx=1, pady=1)
        e.insert(0, d['valor_total'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=2: self._select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._on_change(r, 'valor_total', ev.widget.get()))
        w[2] = e

        e = tk.Entry(self.grid_frame, width=10, justify="center")
        e.grid(row=fila_vis, column=4, sticky="ew", padx=1, pady=1)
        e.insert(0, d['cuotas_valor'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=3: self._select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._on_change(r, 'cuotas_valor', ev.widget.get()))
        w[3] = e

        e = tk.Entry(self.grid_frame, width=12, justify="center")
        e.grid(row=fila_vis, column=5, sticky="ew", padx=1, pady=1)
        e.insert(0, d['fecha'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=4: self._select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._on_change(r, 'fecha', ev.widget.get()))
        w[4] = e

        e = tk.Entry(self.grid_frame, width=30)
        e.grid(row=fila_vis, column=6, sticky="ew", padx=1, pady=1)
        e.insert(0, d['observacion'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=5: self._select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._on_change(r, 'observacion', ev.widget.get()))
        w[5] = e

        if d.get('procesado'):
            for w2 in w.values():
                try:
                    w2.config(bg="#90EE90")
                except:
                    pass

        self.visible_entries[fila] = w

    def _select_cell(self, row, col):
        self.selected_cell = (row, col)

    def _on_change(self, row, field, value):
        if row in self.grid_data:
            self.grid_data[row][field] = value

    def _handle_paste(self, event):
        try:
            self._paste_data()
        except Exception as e:
            messagebox.showerror("Error", str(e))
        return "break"

    def _paste_data(self):
        if self.selected_cell is None:
            messagebox.showwarning("Aviso", "Seleccione una celda primero")
            return
        clipboard = pyperclip.paste()
        if not clipboard:
            messagebox.showinfo("Vacio", "Portapapeles vacio")
            return
        lines = clipboard.strip().replace('\r', '').split('\n')
        if len(lines) > 2500:
            lines = lines[:2500]
        start_row, start_col = self.selected_cell
        self._log_masivo(f"Pegando {len(lines)} lineas desde fila {start_row+1}")
        codigos = set()
        for i, line in enumerate(lines):
            row = start_row + i
            if row >= self.total_rows:
                break
            line = line.strip()
            if not line:
                continue
            if row not in self.grid_data:
                self.grid_data[row] = {'codigo': '', 'nombre': '', 'valor_total': '',
                                       'cuotas_valor': '', 'fecha': '', 'observacion': '', 'procesado': False}
            valores = self._parse_linea(line)
            count = self._pegar_en_fila(row, start_col, valores)
            if start_col == 0 and valores:
                codigos.add(valores[0])
        self._crear_filas_visibles()
        if codigos:
            self._validar_async(codigos)
        messagebox.showinfo("OK", f"Pegados datos en {len(lines)} filas")

    def _parse_linea(self, line):
        if '\t' in line:
            return [v.strip() for v in line.split('\t')]
        elif ';' in line:
            return [v.strip() for v in line.split(';')]
        elif '|' in line:
            return [v.strip() for v in line.split('|')]
        elif ',' in line and line.count(',') >= 2:
            return [v.strip() for v in line.split(',')]
        return [line.strip()]

    def _pegar_en_fila(self, row, start_col, valores):
        col_to_field = {0: 'codigo', 2: 'valor_total', 3: 'cuotas_valor', 4: 'fecha', 5: 'observacion'}
        count = 0
        for j, val in enumerate(valores):
            if not val:
                continue
            if start_col == 0:
                target_col = 0 if j == 0 else j + 1
            else:
                target_col = start_col + j
            if target_col in col_to_field:
                self.grid_data[row][col_to_field[target_col]] = val
                count += 1
        return count

    def _validar_async(self, codigos):
        # Separar cedulas (7+ digitos) de codigos de empleado (numeros cortos)
        cedulas_set = {c for c in codigos if str(c).strip().isdigit() and len(str(c).strip()) >= 7}
        codigos_set = codigos - cedulas_set
        modo_radio  = self.masivo_buscar_por.get()
        if modo_radio == "cedula":
            cedulas_set = set(codigos)
            codigos_set = set()

        def bg():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                encontrados = {}
                if cedulas_set:
                    r, _ = buscar_empleados_por_cedula(conn2, cedulas_set)
                    encontrados.update(r)
                if codigos_set:
                    r, _ = buscar_empleados_batch(conn2, codigos_set)
                    encontrados.update(r)
            finally:
                conn2.close()
            if encontrados:
                self.cache_empleados.update(encontrados)
                for fila, d in self.grid_data.items():
                    clave = d['codigo']
                    if clave in encontrados:
                        emp = encontrados[clave]
                        d['nombre'] = emp['nombre_completo']
                        parece_cedula = str(clave).strip().isdigit() and len(str(clave).strip()) >= 7
                        if modo_radio == "cedula" or parece_cedula:
                            d['codigo'] = str(emp['id'])
                    elif d['codigo']:
                        d['nombre'] = "NO ENCONTRADO"
                self.master.after(0, self._crear_filas_visibles)
        self.thread_pool.submit(bg)

    def _validar_todos_masivo(self):
        codigos = {d['codigo'] for d in self.grid_data.values() if d['codigo']}
        if codigos:
            self._log_masivo(f"Validando {len(codigos)} empleados...")
            self._validar_async(codigos)

    def _limpiar_masivo(self):
        if messagebox.askyesno("Confirmar", "Limpiar todos los datos?"):
            self._inicializar_grid_masivo()
            self._log_masivo("Datos limpiados")

    def _nav_masivo(self, delta):
        self.visible_start = max(0, min(self.visible_start + delta, self.total_rows - self.visible_count))
        self._crear_filas_visibles()

    def _ir_inicio_masivo(self):
        self.visible_start = 0
        self._crear_filas_visibles()

    def _log_masivo(self, msg):
        try:
            self.log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.log_text.see(tk.END)
        except:
            pass

    def _procesar_masivo(self):
        if not self.conn:
            messagebox.showerror("Error", "Sin conexión al sistema")
            return
        usar_valor = self.modo_calculo.get() == "valor"
        filas = [(i, d) for i, d in self.grid_data.items()
                 if d['codigo'] and d['valor_total'] and d['cuotas_valor'] and not d.get('procesado')]
        if not filas:
            messagebox.showwarning("Vacio", "Sin datos para procesar")
            return
        try:
            total = sum(float(d['valor_total']) for _, d in filas)
        except ValueError:
            messagebox.showerror("Error", "Valores no numericos en 'Valor Total'")
            return
        modo = "VALOR CUOTA" if usar_valor else "NUM CUOTAS"

        filas_dlg = []
        for idx, (i, d) in enumerate(filas, 1):
            nombre = d.get('nombre') or self.cache_empleados.get(d['codigo'], {}).get('nombre_completo', '')
            try:
                val_fmt = f"${float(d['valor_total']):,.2f}"
            except Exception:
                val_fmt = d.get('valor_total', '')
            filas_dlg.append((
                idx,
                d['codigo'],
                nombre or '',
                val_fmt,
                d.get('cuotas_valor', ''),
                d.get('fecha', ''),
                (d.get('observacion', '') or '')[:60],
            ))

        desc = f"Modo: {modo}   Total: ${total:,.2f}   Prestamos: {len(filas)}"

        def proceder():
            self.progress_var.set(0)
            self._set_status("Procesando lote...", COL_PEND)
            self._btn_procesar_masivo.config(state=tk.DISABLED)
            self._log_masivo(f"Procesando {len(filas)} prestamos...")
            ok, err = 0, 0

            def bg():
                nonlocal ok, err
                for i, (fila, d) in enumerate(filas):
                    if not self._running:
                        break
                    try:
                        emp = int(d['codigo'])
                        valor = float(d['valor_total'])
                        cv = float(d['cuotas_valor'])
                        fecha_str = d.get('fecha', '').strip()
                        fecha = None
                        for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                            try:
                                fecha = datetime.strptime(fecha_str, fmt)
                                break
                            except:
                                pass
                        if fecha is None:
                            fecha = datetime.now()
                        obs = d.get('observacion', '') or "Prestamo masivo"
                        tipo_trans = self.masivo_tipo_trans.get()
                        if tipo_trans:
                            obs = f"{obs} {tipo_trans}"

                        if usar_valor:
                            cuotas, error = calcular_cuotas_valor(self.conn, emp, valor, cv, fecha)
                        else:
                            cuotas, error = calcular_cuotas_tradicional(valor, int(cv), fecha)

                        if error or not cuotas:
                            self.master.after(0, lambda e=emp, m=error: self._log_masivo(f"Error Emp {e}: {m or 'Sin cuotas'}"))
                            err += 1
                            continue

                        num_egr, error = obtener_proximo_numero_egreso(self.conn)
                        if error:
                            self.master.after(0, lambda e=emp, m=error: self._log_masivo(f"Error Emp {e}: Nro egreso - {m}"))
                            err += 1
                            continue

                        exito, msg = insertar_prestamo(self.conn, emp, num_egr, fecha, obs, cuotas, valor)

                        if exito:
                            ok2, err_upd = actualizar_ultimo_egreso(self.conn, num_egr)
                            if ok2:
                                self.conn.commit()
                                if SEGURIDAD_DISPONIBLE:
                                    log_operacion('INSERT', emp, num_egr,
                                                  f"Prestamo masivo ${valor:.2f}, {len(cuotas)} cuotas")
                                d['procesado'] = True
                                ok += 1
                                self.master.after(0, lambda e=emp, ne=num_egr, nc=len(cuotas): self._log_masivo(f"OK Emp {e}: Egr {ne}, {nc} cuotas"))
                            else:
                                self.conn.rollback()
                                self.master.after(0, lambda e=emp, m=err_upd: self._log_masivo(f"Error Emp {e}: Contador - {m}"))
                                err += 1
                        else:
                            self.conn.rollback()
                            self.master.after(0, lambda e=emp, m=msg: self._log_masivo(f"Error Emp {e}: INSERT - {m}"))
                            err += 1
                    except Exception as e:
                        try:
                            self.conn.rollback()
                        except:
                            pass
                        err += 1
                        self.master.after(0, lambda f=fila, m=str(e): self._log_masivo(f"Error fila {f}: {m}"))

                    self.master.after(0, lambda v=(i+1)/len(filas)*100: self.progress_var.set(v))

                self.master.after(0, lambda: self._masivo_fin(ok, err))

            threading.Thread(target=bg, daemon=True).start()

        self._dialogo_confirmar(
            "Confirmar Carga Masiva",
            desc,
            [("#", 40), ("Empleado", 80), ("Nombre", 180),
             ("Valor", 100), ("Cuotas", 70), ("Fecha", 100), ("Observacion", 200)],
            filas_dlg,
            proceder
        )

    def _masivo_fin(self, ok, err):
        if not self._running:
            return
        self._crear_filas_visibles()
        self._btn_procesar_masivo.config(state=tk.NORMAL)
        self.progress_var.set(0)
        color = COL_OK if err == 0 else COL_PEND
        self._set_status(f"Lote: {ok} exitosos, {err} errores", color)
        self._log_masivo(f"Fin: {ok} ok, {err} errores")
        messagebox.showinfo("Resultado del lote", f"Exitosos: {ok}\nErrores: {err}")
        self._cargar_ultimos_egresos()

    # ===================================================================
    # PANEL HISTORIAL (lado derecho de Tab 3 - Egresos/Ingresos)
    # ===================================================================

    def _build_tt_historial_panel(self, parent):
        self._tt_hist_rows = {}  # iid → dict con datos del registro

        main = ttk.Frame(parent, padding=4)
        main.pack(fill=tk.BOTH, expand=True)

        hdr = tk.Frame(main, bg=COL_HEADER, height=36)
        hdr.pack(fill=tk.X, pady=(0, 4))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Historial de Registros",
                 bg=COL_HEADER, fg=COL_WHITE,
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=8, pady=8)

        # Buscador
        sf = tk.Frame(main, bg=COL_BG)
        sf.pack(fill=tk.X, pady=(0, 4))
        self._tt_hist_filtro_var = tk.StringVar()
        ttk.Entry(sf, textvariable=self._tt_hist_filtro_var, width=18,
                  font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 4), ipady=3, fill=tk.X, expand=True)
        tk.Button(sf, text="Buscar", command=self._tt_historial_buscar,
                  bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(sf, text="↺", command=lambda: (self._tt_hist_filtro_var.set(""), self._tt_historial_buscar()),
                  bg='#78909C', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2', width=2).pack(side=tk.LEFT, padx=2)
        tk.Label(sf, text="  N° o nombre", bg=COL_BG,
                 fg='gray', font=('Segoe UI', 7)).pack(side=tk.LEFT)
        self._tt_hist_filtro_var.trace_add("write",
            lambda *a: self.master.after(600, self._tt_historial_buscar))

        # Treeview
        tf = ttk.Frame(main)
        tf.pack(fill=tk.BOTH, expand=True)

        cols = ("Tipo", "N°", "Empleado", "Fecha", "Total")
        self._tt_hist_tree = ttk.Treeview(tf, columns=cols, show="headings",
                                          selectmode="browse", height=20)
        self._tt_hist_tree.heading("Tipo",     text="Tipo",     anchor=tk.W)
        self._tt_hist_tree.heading("N°",       text="N°",       anchor=tk.CENTER)
        self._tt_hist_tree.heading("Empleado", text="Empleado", anchor=tk.W)
        self._tt_hist_tree.heading("Fecha",    text="Fecha",    anchor=tk.CENTER)
        self._tt_hist_tree.heading("Total",    text="Total",    anchor=tk.E)
        self._tt_hist_tree.column("Tipo",     width=55,  anchor=tk.W,      stretch=False)
        self._tt_hist_tree.column("N°",       width=60,  anchor=tk.CENTER, stretch=False)
        self._tt_hist_tree.column("Empleado", width=130, anchor=tk.W,      stretch=True)
        self._tt_hist_tree.column("Fecha",    width=80,  anchor=tk.CENTER, stretch=False)
        self._tt_hist_tree.column("Total",    width=78,  anchor=tk.E,      stretch=False)

        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self._tt_hist_tree.yview)
        self._tt_hist_tree.configure(yscrollcommand=vsb.set)
        self._tt_hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tt_hist_tree.tag_configure('par',      background='#F0F4F8')
        self._tt_hist_tree.tag_configure('impar',    background=COL_WHITE)
        self._tt_hist_tree.tag_configure('prestamo', background='#FFF3E0')
        self._tt_hist_tree.tag_configure('ingreso',  background='#E8F5E9')

        self._tt_hist_tree.bind("<Double-1>", self._tt_historial_ver_detalle)

        # Botones
        bot = tk.Frame(main, bg=COL_BG)
        bot.pack(fill=tk.X, pady=(4, 0))
        tk.Button(bot, text="Ver / Editar", command=self._tt_historial_ver_detalle,
                  bg=COL_PEND, fg=COL_WHITE, font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)

        self._tt_hist_info_var = tk.StringVar(value="")
        tk.Label(bot, textvariable=self._tt_hist_info_var,
                 bg=COL_BG, fg='gray', font=('Segoe UI', 8)).pack(side=tk.RIGHT, padx=4)

    def _tt_historial_buscar(self):
        filtro = self._tt_hist_filtro_var.get().strip()

        def _thread():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                rows, _ = obtener_historial_todos(conn2, filtro, 200)
                self.master.after(0, lambda r=rows: self._tt_historial_mostrar(r))
            finally:
                conn2.close()

        threading.Thread(target=_thread, daemon=True).start()

    def _tt_historial_mostrar(self, rows):
        for iid in self._tt_hist_tree.get_children():
            self._tt_hist_tree.delete(iid)
        self._tt_hist_rows.clear()

        NOMBRE_CLASE = {
            '205': 'Préstamo', '202': 'Anticipo', '203': 'Multa',
            '204': 'Quirogr.', '206': 'Alimentos', '207': 'Hipotec.',
            '217': 'Ant.Otros', '218': 'IESS Cón.', '219': 'Imp.Renta',
            '250': 'Ant.Surt.', '102': 'Bonific.', '110': 'Maniobras',
            '111': 'Reembolso', '120': 'Moviliz.',
        }

        for idx, r in enumerate(rows):
            clase = r['clase']
            tipo_label = NOMBRE_CLASE.get(clase, clase)
            cuotas = r['cuotas']
            if clase == '205' and cuotas > 1:
                tipo_label = f"Prést.({cuotas}c)"

            nombre_corto = r['nombre']

            if clase == '205':
                tag = 'prestamo'
            elif clase in ('102', '110', '111', '120'):
                tag = 'ingreso'
            else:
                tag = 'par' if idx % 2 == 0 else 'impar'

            iid = self._tt_hist_tree.insert("", tk.END, tags=(tag,),
                values=(tipo_label,
                        f"{int(r['numero']):05d}",
                        nombre_corto,
                        r['fecha'],
                        f"${r['valor']:,.2f}"))
            self._tt_hist_rows[iid] = r

        total = len(rows)
        aviso = " (máx 200)" if total == 200 else ""
        self._tt_hist_info_var.set(f"{total}{aviso} registros")

    def _tt_historial_ver_detalle(self, event=None):
        sel = self._tt_hist_tree.selection()
        if not sel:
            return
        r = self._tt_hist_rows.get(sel[0])
        if not r:
            return

        if r['clase'] == '205':
            self._tt_hist_dlg_prestamo(r)
        else:
            self._tt_hist_dlg_egreso(r)

    def _tt_hist_dlg_prestamo(self, r):
        """Diálogo interactivo para préstamos CLASE 205: editar cuotas individualmente
        o mover todas las pendientes a partir de una fecha nueva."""
        dlg = tk.Toplevel(self.master)
        dlg.title(f"Préstamo N° {int(r['numero']):05d}  —  {r['nombre']}")
        dlg.geometry("960x580")
        dlg.minsize(800, 480)
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        dlg.resizable(True, True)
        self.master.update_idletasks()
        x = self.master.winfo_x() + max(0, (self.master.winfo_width()  - 960) // 2)
        y = self.master.winfo_y() + max(0, (self.master.winfo_height() - 580) // 2)
        dlg.geometry(f"960x580+{x}+{y}")
        try:
            dlg.wait_visibility(); dlg.grab_set()
        except Exception:
            dlg.focus_set()

        # ── Header ───────────────────────────────────────────────────────
        hdr = tk.Frame(dlg, bg='#E65100', height=42)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  \U0001f4b3  Préstamo N° {int(r['numero']):05d}  —  {r['nombre']}",
                 bg='#E65100', fg=COL_WHITE,
                 font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT, padx=12, pady=8)

        # ── Info banda superior ───────────────────────────────────────────
        inf = tk.Frame(dlg, bg='#FFF8E1', relief='groove', bd=1)
        inf.pack(fill=tk.X, padx=8, pady=(6, 2))
        resumen_var = tk.StringVar(value="Cargando cuotas...")
        tk.Label(inf, text=f"Empleado: {r['empleado']}  |  Total préstamo: ${r['valor']:,.2f}",
                 bg='#FFF8E1', font=('Segoe UI', 9, 'bold'), fg='#4E342E').pack(side=tk.LEFT, padx=10, pady=4)
        tk.Label(inf, textvariable=resumen_var, bg='#FFF8E1',
                 fg=COL_HEADER, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=10, pady=4)

        # ── Cuerpo principal: izquierda=tabla, derecha=panel edición ─────
        body = tk.Frame(dlg, bg=COL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # ─ Tabla de cuotas ───────────────────────────────────────────────
        tf = ttk.LabelFrame(body, text="Cuotas del préstamo  (clic para seleccionar)", padding=4)
        tf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        cols = ("#", "Fecha Vencimiento", "Valor", "Estado")
        cuotas_tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="browse")
        cuotas_tree.heading("#",                text="#",       anchor=tk.CENTER)
        cuotas_tree.heading("Fecha Vencimiento",text="Vencimiento",  anchor=tk.W)
        cuotas_tree.heading("Valor",            text="Valor",   anchor=tk.E)
        cuotas_tree.heading("Estado",           text="Estado",  anchor=tk.CENTER)
        cuotas_tree.column("#",                width=42,  anchor=tk.CENTER, stretch=False)
        cuotas_tree.column("Fecha Vencimiento",width=130, anchor=tk.W,      stretch=True)
        cuotas_tree.column("Valor",            width=95,  anchor=tk.E,      stretch=False)
        cuotas_tree.column("Estado",           width=90,  anchor=tk.CENTER, stretch=False)
        cuotas_tree.tag_configure('pendiente', background='#FFF9C4')
        cuotas_tree.tag_configure('procesado', background='#E8F5E9', foreground='#2E7D32')
        cuotas_tree.tag_configure('selec',     background='#BBDEFB')

        vsb2 = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=cuotas_tree.yview)
        cuotas_tree.configure(yscrollcommand=vsb2.set)
        cuotas_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)

        cuotas_data = {}   # iid → dict de la cuota

        # ─ Panel de edición (derecha) ────────────────────────────────────
        ep = tk.Frame(body, bg=COL_BG, width=310)
        ep.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))
        ep.pack_propagate(False)

        # Sección 1 — Editar cuota seleccionada
        sec1 = tk.LabelFrame(ep, text="Editar cuota seleccionada",
                              bg=COL_BG, fg='#E65100',
                              font=('Segoe UI', 9, 'bold'), padx=10, pady=8)
        sec1.pack(fill=tk.X, pady=(0, 8))

        cuota_lbl_var = tk.StringVar(value="— Seleccione una cuota —")
        tk.Label(sec1, textvariable=cuota_lbl_var, bg=COL_BG,
                 fg=COL_HEADER, font=('Segoe UI', 9, 'bold')).grid(
                 row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))

        tk.Label(sec1, text="Fecha (dd/mm/aaaa):", bg=COL_BG,
                 font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=3)
        edit_fecha_var = tk.StringVar()
        edit_fecha_entry = ttk.Entry(sec1, textvariable=edit_fecha_var,
                                     width=14, font=('Segoe UI', 10))
        edit_fecha_entry.grid(row=1, column=1, sticky='w', padx=6, ipady=3)

        tk.Label(sec1, text="Valor ($):", bg=COL_BG,
                 font=('Segoe UI', 9)).grid(row=2, column=0, sticky='w', pady=3)
        edit_valor_var = tk.StringVar()
        edit_valor_entry = ttk.Entry(sec1, textvariable=edit_valor_var,
                                     width=14, font=('Segoe UI', 10))
        edit_valor_entry.grid(row=2, column=1, sticky='w', padx=6, ipady=3)

        edit_msg_var = tk.StringVar()
        tk.Label(sec1, textvariable=edit_msg_var, bg=COL_BG,
                 font=('Segoe UI', 8), fg=COL_OK, wraplength=260).grid(
                 row=3, column=0, columnspan=2, sticky='w')

        btn_guardar = tk.Button(sec1, text="  Guardar cuota  ",
                                bg=COL_OK, fg=COL_WHITE,
                                font=('Segoe UI', 9, 'bold'),
                                relief='flat', cursor='hand2',
                                state=tk.DISABLED)
        btn_guardar.grid(row=4, column=0, columnspan=2, sticky='w', pady=(8, 2))

        # Sección 2 — Mover cuotas pendientes
        sec2 = tk.LabelFrame(ep, text="Mover cuotas pendientes",
                              bg=COL_BG, fg=COL_HEADER,
                              font=('Segoe UI', 9, 'bold'), padx=10, pady=8)
        sec2.pack(fill=tk.X, pady=(0, 8))

        tk.Label(sec2,
                 text="Mueve TODAS las cuotas pendientes\npara que empiecen desde el mes que elijas.",
                 bg=COL_BG, fg='#455A64',
                 font=('Segoe UI', 8), justify=tk.LEFT).grid(
                 row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))

        tk.Label(sec2, text="Iniciar desde (mm/aaaa):", bg=COL_BG,
                 font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=3)
        mover_fecha_var = tk.StringVar(value=datetime.now().strftime('%m/%Y'))
        mover_fecha_entry = ttk.Entry(sec2, textvariable=mover_fecha_var,
                                      width=10, font=('Segoe UI', 10))
        mover_fecha_entry.grid(row=1, column=1, sticky='w', padx=6, ipady=3)

        mover_msg_var = tk.StringVar()
        tk.Label(sec2, textvariable=mover_msg_var, bg=COL_BG,
                 font=('Segoe UI', 8), fg='#455A64', wraplength=260).grid(
                 row=2, column=0, columnspan=2, sticky='w', pady=2)

        def _preview_mover(*_):
            """Calcula y muestra el preview al cambiar la fecha de inicio."""
            pendientes = [c for c in cuotas_data.values() if not c['asentado']]
            pendientes.sort(key=lambda c: c['secuencia'])
            if not pendientes:
                mover_msg_var.set("No hay cuotas pendientes.")
                return
            try:
                m, y = mover_fecha_var.get().strip().split('/')
                mes, anio = int(m), int(y)
                if not (1 <= mes <= 12) or anio < 2000:
                    raise ValueError
            except Exception:
                mover_msg_var.set("Formato inválido. Use mm/aaaa")
                return
            lineas = []
            for i, c in enumerate(pendientes):
                ultimo = get_last_day_of_month(anio, mes)
                lineas.append(f"  C#{c['secuencia']} → {ultimo.strftime('%d/%m/%Y')}  ${c['valor']:,.2f}")
                anio, mes = get_next_month(anio, mes)
            mover_msg_var.set(f"Vista previa ({len(pendientes)} cuotas):\n" + "\n".join(lineas[:6])
                              + (f"\n  ...y {len(lineas)-6} más" if len(lineas) > 6 else ""))

        mover_fecha_var.trace_add("write", lambda *a: self.master.after(400, _preview_mover))

        btn_mover = tk.Button(sec2, text="  Aplicar movimiento  ",
                              bg=COL_ACCENT, fg=COL_WHITE,
                              font=('Segoe UI', 9, 'bold'),
                              relief='flat', cursor='hand2')
        btn_mover.grid(row=3, column=0, columnspan=2, sticky='w', pady=(8, 2))

        tk.Button(ep, text="  Cerrar  ", command=dlg.destroy,
                  bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(anchor='s', pady=4)

        # ── Lógica de carga y refresco ────────────────────────────────────
        def _cargar_cuotas():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                cuotas, _ = obtener_cuotas_prestamo(conn2, r['numero'], r['empleado'])
                self.master.after(0, lambda c=cuotas: _mostrar_cuotas(c))
            finally:
                conn2.close()

        def _mostrar_cuotas(cuotas):
            for iid2 in cuotas_tree.get_children():
                cuotas_tree.delete(iid2)
            cuotas_data.clear()
            total_pend = 0.0
            for c in cuotas:
                fv = c['fecha_ven'].strftime('%d/%m/%Y') if c['fecha_ven'] else '-'
                estado = "Procesada" if c['asentado'] else "Pendiente"
                tag2 = 'procesado' if c['asentado'] else 'pendiente'
                iid2 = cuotas_tree.insert("", tk.END, tags=(tag2,),
                    values=(f"#{c['secuencia']}", fv, f"${c['valor']:,.2f}", estado))
                cuotas_data[iid2] = c
                if not c['asentado']:
                    total_pend += c['valor']
            n_pend = sum(1 for c in cuotas_data.values() if not c['asentado'])
            n_proc = len(cuotas_data) - n_pend
            resumen_var.set(f"Pendiente: ${total_pend:,.2f}  |  {n_pend} pendiente/s  |  {n_proc} procesada/s")
            _preview_mover()

        # Selección de cuota → rellenar panel edición
        def _on_select(event=None):
            sel2 = cuotas_tree.selection()
            if not sel2:
                return
            c = cuotas_data.get(sel2[0])
            if not c:
                return
            fv = c['fecha_ven'].strftime('%d/%m/%Y') if c['fecha_ven'] else ''
            cuota_lbl_var.set(f"Cuota #{c['secuencia']}  —  {'Procesada' if c['asentado'] else 'Pendiente'}")
            edit_fecha_var.set(fv)
            edit_valor_var.set(f"{c['valor']:.2f}")
            edit_msg_var.set("")
            st = tk.DISABLED if c['asentado'] else tk.NORMAL
            btn_guardar.config(state=st)
            edit_fecha_entry.config(state=('readonly' if c['asentado'] else 'normal'))
            edit_valor_entry.config(state=('readonly' if c['asentado'] else 'normal'))

        cuotas_tree.bind("<<TreeviewSelect>>", _on_select)

        # Guardar cambios de cuota individual
        def _guardar_cuota():
            sel2 = cuotas_tree.selection()
            if not sel2:
                return
            c = cuotas_data.get(sel2[0])
            if not c or c['asentado']:
                return
            # Validar fecha
            try:
                nueva_fecha = datetime.strptime(edit_fecha_var.get().strip(), '%d/%m/%Y')
            except Exception:
                edit_msg_var.set("Fecha inválida. Use dd/mm/aaaa")
                return
            # Validar valor
            try:
                nuevo_valor = float(edit_valor_var.get().replace(',', '.'))
                if nuevo_valor <= 0:
                    raise ValueError
            except Exception:
                edit_msg_var.set("Valor inválido.")
                return

            cambios = []
            if nueva_fecha != c['fecha_ven']:
                cambios.append(f"fecha {c['fecha_ven'].strftime('%d/%m/%Y') if c['fecha_ven'] else '-'} → {nueva_fecha.strftime('%d/%m/%Y')}")
            if abs(nuevo_valor - c['valor']) > 0.001:
                cambios.append(f"valor ${c['valor']:,.2f} → ${nuevo_valor:,.2f}")
            if not cambios:
                edit_msg_var.set("Sin cambios.")
                return

            edit_msg_var.set("Guardando...")
            btn_guardar.config(state=tk.DISABLED)

            def _thread():
                conn2, err = conectar_bd()
                if err:
                    self.master.after(0, lambda: edit_msg_var.set(f"Error: {err}"))
                    self.master.after(0, lambda: btn_guardar.config(state=tk.NORMAL))
                    return
                conn2.autocommit = False
                try:
                    exito, _, _ = crear_respaldo_prestamo(
                        conn2, r['empleado'], r['numero'],
                        f"Edicion cuota #{c['secuencia']}: {', '.join(cambios)}"
                    )
                    if not exito:
                        self.master.after(0, lambda: edit_msg_var.set("Error: no se pudo crear respaldo."))
                        return
                    cursor = conn2.cursor()
                    cursor.execute("""
                        UPDATE RPINGDES SET FECHA_VEN=?, VALOR=?
                        WHERE EMPLEADO=? AND NUMERO=? AND CLASE='205' AND SECUENCIA=?
                    """, (nueva_fecha, nuevo_valor,
                          r['empleado'], r['numero'], c['secuencia']))
                    conn2.commit()
                    log_operacion("EDITAR_CUOTA", r['empleado'], r['numero'],
                                  f"Cuota #{c['secuencia']}: {', '.join(cambios)}", exito=True)
                    self.master.after(0, lambda: edit_msg_var.set(f"✓ Guardado: {', '.join(cambios)}"))
                    self.master.after(0, lambda: btn_guardar.config(state=tk.NORMAL))
                    self.master.after(0, lambda: threading.Thread(target=_cargar_cuotas, daemon=True).start())
                except Exception as ex:
                    conn2.rollback()
                    log_operacion("EDITAR_CUOTA", r['empleado'], r['numero'], str(ex), exito=False)
                    err_msg = str(ex)
                    self.master.after(0, lambda m=err_msg: edit_msg_var.set(f"Error: {m}"))
                    self.master.after(0, lambda: btn_guardar.config(state=tk.NORMAL))
                finally:
                    conn2.close()

            threading.Thread(target=_thread, daemon=True).start()

        btn_guardar.config(command=_guardar_cuota)

        # Mover todas las cuotas pendientes desde una fecha
        def _aplicar_mover():
            pendientes = [c for c in cuotas_data.values() if not c['asentado']]
            pendientes.sort(key=lambda c: c['secuencia'])
            if not pendientes:
                messagebox.showinfo("Sin pendientes",
                    "No hay cuotas pendientes para mover.", parent=dlg)
                return
            try:
                m_str, y_str = mover_fecha_var.get().strip().split('/')
                mes, anio = int(m_str), int(y_str)
                if not (1 <= mes <= 12) or anio < 2000:
                    raise ValueError
            except Exception:
                messagebox.showerror("Fecha inválida",
                    "Ingrese mes/año en formato mm/aaaa (ej: 07/2026)", parent=dlg)
                return

            # Calcular nuevas fechas
            nuevas = []
            m_tmp, y_tmp = mes, anio
            for c in pendientes:
                nueva_fv = get_last_day_of_month(y_tmp, m_tmp)
                nuevas.append((c, nueva_fv))
                y_tmp, m_tmp = get_next_month(y_tmp, m_tmp)

            # Confirmación con preview
            preview = "\n".join(
                f"  Cuota #{c['secuencia']}:  "
                f"{c['fecha_ven'].strftime('%d/%m/%Y') if c['fecha_ven'] else '-'}"
                f"  →  {nf.strftime('%d/%m/%Y')}"
                for c, nf in nuevas[:10]
            )
            if len(nuevas) > 10:
                preview += f"\n  ... y {len(nuevas)-10} cuotas más"

            if not messagebox.askyesno(
                "Confirmar movimiento de cuotas",
                f"Se moverán {len(nuevas)} cuota/s pendientes a partir de "
                f"{pendientes[0]['secuencia'] and ''}{mes:02d}/{anio}:\n\n{preview}\n\n"
                "Se creará un respaldo antes de aplicar.\n¿Continuar?",
                parent=dlg
            ):
                return

            mover_msg_var.set("Aplicando cambios...")
            btn_mover.config(state=tk.DISABLED)

            def _thread_mover():
                conn2, err = conectar_bd()
                if err:
                    self.master.after(0, lambda: mover_msg_var.set(f"Error: {err}"))
                    self.master.after(0, lambda: btn_mover.config(state=tk.NORMAL))
                    return
                conn2.autocommit = False
                try:
                    exito, _, _ = crear_respaldo_prestamo(
                        conn2, r['empleado'], r['numero'],
                        f"Mover cuotas desde {mes:02d}/{anio} ({len(nuevas)} cuotas)"
                    )
                    if not exito:
                        self.master.after(0, lambda: mover_msg_var.set("Error: no se pudo crear respaldo."))
                        return
                    cursor = conn2.cursor()
                    for c, nueva_fv in nuevas:
                        cursor.execute("""
                            UPDATE RPINGDES SET FECHA_VEN=?
                            WHERE EMPLEADO=? AND NUMERO=? AND CLASE='205' AND SECUENCIA=?
                        """, (nueva_fv, r['empleado'], r['numero'], c['secuencia']))
                    conn2.commit()
                    log_operacion("MOVER_CUOTAS", r['empleado'], r['numero'],
                                  f"Desde {mes:02d}/{anio}, {len(nuevas)} cuotas", exito=True)
                    self.master.after(0, lambda: mover_msg_var.set(
                        f"✓ {len(nuevas)} cuota/s movidas correctamente"))
                    self.master.after(0, lambda: btn_mover.config(state=tk.NORMAL))
                    self.master.after(0, lambda: threading.Thread(
                        target=_cargar_cuotas, daemon=True).start())
                except Exception as ex:
                    conn2.rollback()
                    log_operacion("MOVER_CUOTAS", r['empleado'], r['numero'], str(ex), exito=False)
                    err_msg = str(ex)
                    self.master.after(0, lambda m=err_msg: mover_msg_var.set(f"Error: {m}"))
                    self.master.after(0, lambda: btn_mover.config(state=tk.NORMAL))
                finally:
                    conn2.close()

            threading.Thread(target=_thread_mover, daemon=True).start()

        btn_mover.config(command=_aplicar_mover)

        threading.Thread(target=_cargar_cuotas, daemon=True).start()

    def _tt_hist_dlg_egreso(self, r):
        """Diálogo detalle para egresos/ingresos simples (una sola fila)."""
        NOMBRE_CLASE = {
            '202': 'Anticipo de Sueldo', '203': 'Multas',
            '204': 'Prést. Quirografario', '206': 'Pensión Alimenticia',
            '207': 'Prést. Hipotecario', '217': 'Anticipos Otros',
            '218': 'Aport. IESS Cónyuge', '219': 'Impuesto a la Renta',
            '250': 'Anticipos Surtidos', '102': 'Bonific. Otros Ingresos',
            '110': 'Maniobras', '111': 'Reembolsos', '120': 'Movilización',
        }
        tipo_nombre = NOMBRE_CLASE.get(r['clase'], r['clase'])
        es_ing = r['clase'] in ('102', '110', '111', '120')
        col_hdr = '#1565C0' if es_ing else COL_PEND

        dlg = tk.Toplevel(self.master)
        dlg.title(f"N° {int(r['numero']):05d}  —  {tipo_nombre}  —  {r['nombre']}")
        dlg.geometry("580x390")
        dlg.minsize(500, 360)
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        dlg.resizable(True, False)
        self.master.update_idletasks()
        x = self.master.winfo_x() + max(0, (self.master.winfo_width()  - 580) // 2)
        y = self.master.winfo_y() + max(0, (self.master.winfo_height() - 390) // 2)
        dlg.geometry(f"580x390+{x}+{y}")
        try:
            dlg.wait_visibility(); dlg.grab_set()
        except Exception:
            dlg.focus_set()

        # Header
        hdr = tk.Frame(dlg, bg=col_hdr, height=40)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  N° {int(r['numero']):05d}  —  {tipo_nombre}  —  {r['nombre']}",
                 bg=col_hdr, fg=COL_WHITE,
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        # Datos info (solo lectura)
        inf = tk.Frame(dlg, bg='#F5F5F5', relief='groove', bd=1)
        inf.pack(fill=tk.X, padx=10, pady=(6, 2))
        tk.Label(inf,
                 text=f"Empleado: {r['empleado']}  |  {r['nombre']}  |  Tipo: {tipo_nombre}",
                 bg='#F5F5F5', font=('Segoe UI', 9), fg='#424242').pack(
                 anchor='w', padx=10, pady=4)

        # Campos editables
        edit_f = tk.LabelFrame(dlg, text="Editar registro",
                               bg=COL_BG, fg=col_hdr,
                               font=('Segoe UI', 9, 'bold'), padx=14, pady=10)
        edit_f.pack(fill=tk.X, padx=10, pady=6)

        # Fecha
        tk.Label(edit_f, text="Fecha (dd/mm/aaaa):", bg=COL_BG,
                 font=('Segoe UI', 9), width=20, anchor='w').grid(
                 row=0, column=0, sticky='w', pady=4)
        fecha_var = tk.StringVar(value=r['fecha'])
        ttk.Entry(edit_f, textvariable=fecha_var, width=16,
                  font=('Segoe UI', 10)).grid(row=0, column=1, sticky='w', padx=6, ipady=3)

        # Valor
        tk.Label(edit_f, text="Valor ($):", bg=COL_BG,
                 font=('Segoe UI', 9), width=20, anchor='w').grid(
                 row=1, column=0, sticky='w', pady=4)
        valor_var = tk.StringVar(value=f"{r['valor']:.2f}")
        ttk.Entry(edit_f, textvariable=valor_var, width=16,
                  font=('Segoe UI', 10)).grid(row=1, column=1, sticky='w', padx=6, ipady=3)

        # Observación
        tk.Label(edit_f, text="Observación:", bg=COL_BG,
                 font=('Segoe UI', 9), width=20, anchor='w').grid(
                 row=2, column=0, sticky='w', pady=4)
        obs_var = tk.StringVar(value=r['concepto'] or '')
        ttk.Entry(edit_f, textvariable=obs_var, width=38,
                  font=('Segoe UI', 9)).grid(row=2, column=1, sticky='w', padx=6, ipady=3)

        # Mensaje de estado inline
        msg_var = tk.StringVar()
        tk.Label(edit_f, textvariable=msg_var, bg=COL_BG,
                 font=('Segoe UI', 8), fg=COL_OK,
                 wraplength=480).grid(row=3, column=0, columnspan=2, sticky='w', pady=2)

        def _guardar():
            # Validar fecha
            try:
                nueva_fecha = datetime.strptime(fecha_var.get().strip(), '%d/%m/%Y')
            except Exception:
                msg_var.set("Fecha inválida — use dd/mm/aaaa")
                return
            # Validar valor
            try:
                nuevo_val = float(valor_var.get().replace(',', '.'))
                if nuevo_val <= 0:
                    raise ValueError
            except Exception:
                msg_var.set("Valor inválido — ingrese un número mayor que 0")
                return
            nueva_obs = obs_var.get().strip()
            msg_var.set("Guardando...")
            btn_guardar.config(state=tk.DISABLED)

            fila_cq = {
                'NUMERO':    r['numero'],
                'EMPLEADO':  r['empleado'],
                'SECUENCIA': 1,
                'CLASE':     r['clase'],
                'VALOR':     r['valor'],
            }
            def _after():
                btn_guardar.config(state=tk.NORMAL)
                # Refresca los paneles historial
                self._tt_historial_buscar()
                if hasattr(self, '_ind_historial_buscar'):
                    self._ind_historial_buscar()
                self._cargar_ultimos_egresos()

            def _ok(msg):
                msg_var.set(f"✓ {msg}")
                self.master.after(0, _after)

            def _err(msg):
                msg_var.set(f"Error: {msg}")
                self.master.after(0, lambda: btn_guardar.config(state=tk.NORMAL))

            self._tt_hist_aplicar_edicion(fila_cq, nuevo_val, nueva_obs,
                                          nueva_fecha, _ok, _err)

        def _eliminar():
            fila_cq = {
                'NUMERO':    r['numero'],
                'EMPLEADO':  r['empleado'],
                'CLASE':     r['clase'],
                'VALOR':     r['valor'],
            }
            dlg.destroy()
            self._tt_hist_eliminar_egreso(fila_cq, r)

        bf = tk.Frame(dlg, bg=COL_BG)
        bf.pack(fill=tk.X, padx=10, pady=8)
        btn_guardar = tk.Button(bf, text="  Guardar cambios  ", command=_guardar,
                                bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                                relief='flat', cursor='hand2')
        btn_guardar.pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="  Eliminar  ", command=_eliminar,
                  bg=COL_DANGER, fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="  Cerrar  ", command=dlg.destroy,
                  bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.RIGHT, padx=4)

    def _tt_hist_aplicar_edicion(self, fila, nuevo_valor, nueva_obs,
                                  nueva_fecha=None, on_ok=None, on_err=None):
        """Aplica edición de VALOR, OBS y FECHA a un egreso/ingreso simple."""
        if not SEGURIDAD_DISPONIBLE:
            messagebox.showerror("Seguridad requerida",
                "El módulo de seguridad no está disponible.")
            if on_err:
                on_err("Módulo de seguridad no disponible")
            return
        self._set_status("Guardando cambio...", COL_ACCENT)

        def _thread():
            conn2, err = conectar_bd()
            if err:
                self.master.after(0, lambda: (
                    messagebox.showerror("Error de conexión", err),
                    on_err(err) if on_err else None
                ))
                return
            conn2.autocommit = False
            try:
                desc = (f"Edicion clase={fila['CLASE']} "
                        f"valor {fila['VALOR']} → {nuevo_valor}")
                if nueva_fecha:
                    desc += f"  fecha → {nueva_fecha.strftime('%d/%m/%Y')}"
                exito, _, _ = crear_respaldo_prestamo(
                    conn2, fila['EMPLEADO'], fila['NUMERO'], desc)
                if not exito:
                    msg = "No se pudo crear el respaldo. Operación cancelada."
                    self.master.after(0, lambda: messagebox.showerror("Error respaldo", msg))
                    if on_err:
                        self.master.after(0, lambda: on_err(msg))
                    return

                cursor = conn2.cursor()
                if nueva_fecha:
                    cursor.execute("""
                        UPDATE RPINGDES SET VALOR=?, OBSERV=?, FECHA=?, FECHA_VEN=?
                        WHERE EMPLEADO=? AND NUMERO=? AND CLASE=? AND SECUENCIA=?
                    """, (nuevo_valor, nueva_obs, nueva_fecha, nueva_fecha,
                          fila['EMPLEADO'], fila['NUMERO'],
                          fila['CLASE'], fila['SECUENCIA']))
                else:
                    cursor.execute("""
                        UPDATE RPINGDES SET VALOR=?, OBSERV=?
                        WHERE EMPLEADO=? AND NUMERO=? AND CLASE=? AND SECUENCIA=?
                    """, (nuevo_valor, nueva_obs,
                          fila['EMPLEADO'], fila['NUMERO'],
                          fila['CLASE'], fila['SECUENCIA']))
                conn2.commit()
                log_operacion("EDITAR_EGRESO", fila['EMPLEADO'], fila['NUMERO'],
                              desc, exito=True)
                msg_ok = f"Guardado: ${nuevo_valor:,.2f}"
                if nueva_fecha:
                    msg_ok += f"  |  {nueva_fecha.strftime('%d/%m/%Y')}"
                self.master.after(0, lambda m=msg_ok: self._set_status(m, COL_OK))
                if on_ok:
                    self.master.after(0, lambda m=msg_ok: on_ok(m))
                else:
                    self.master.after(0, self._tt_historial_buscar)
            except Exception as ex:
                conn2.rollback()
                log_operacion("EDITAR_EGRESO", fila['EMPLEADO'], fila['NUMERO'],
                              str(ex), exito=False)
                err_msg = str(ex)
                if on_err:
                    self.master.after(0, lambda m=err_msg: on_err(m))
                else:
                    self.master.after(0, lambda m=err_msg: messagebox.showerror("Error", m))
            finally:
                conn2.close()

        threading.Thread(target=_thread, daemon=True).start()

    def _tt_hist_eliminar_egreso(self, fila, r):
        """Elimina todas las filas de un NUMERO+CLASE+EMPLEADO (con seguridad)."""
        if not SEGURIDAD_DISPONIBLE:
            messagebox.showerror("Seguridad requerida",
                "El módulo de seguridad no está disponible.")
            return
        desc = (f"N° {int(fila['NUMERO']):05d}  |  {r['nombre']}  |  "
                f"Tipo {fila['CLASE']}  |  ${fila['VALOR']:,.2f}")
        if not messagebox.askyesno("Confirmar eliminación",
            f"¿Eliminar este registro?\n\n{desc}\n\nSe creará un respaldo antes de eliminar."):
            return

        self._set_status("Eliminando registro...", COL_DANGER)

        def _thread():
            conn2, err = conectar_bd()
            if err:
                self.master.after(0, lambda: messagebox.showerror("Error de conexión", err))
                return
            conn2.autocommit = False
            try:
                exito, _, _ = crear_respaldo_prestamo(
                    conn2, fila['EMPLEADO'], fila['NUMERO'],
                    f"Eliminacion clase={fila['CLASE']}"
                )
                if not exito:
                    self.master.after(0, lambda: messagebox.showerror(
                        "Error respaldo", "No se pudo crear el respaldo. Operación cancelada."))
                    return
                cursor = conn2.cursor()
                cursor.execute("""
                    DELETE FROM RPINGDES
                    WHERE EMPLEADO=? AND NUMERO=? AND CLASE=? AND ASENTADO=0
                """, (fila['EMPLEADO'], fila['NUMERO'], fila['CLASE']))
                filas_afect = cursor.rowcount
                conn2.commit()
                log_operacion("ELIMINAR_EGRESO", fila['EMPLEADO'], fila['NUMERO'],
                              f"Clase {fila['CLASE']} eliminado ({filas_afect} fila/s)", exito=True)
                self.master.after(0, lambda: self._set_status(
                    f"Registro eliminado ({filas_afect} fila/s)", COL_OK))
                self.master.after(0, self._tt_historial_buscar)
            except Exception as ex:
                conn2.rollback()
                log_operacion("ELIMINAR_EGRESO", fila['EMPLEADO'], fila['NUMERO'], str(ex), exito=False)
                err_msg = str(ex)
                self.master.after(0, lambda m=err_msg: messagebox.showerror("Error", m))
            finally:
                conn2.close()

        threading.Thread(target=_thread, daemon=True).start()

    def _consulta_editar_cuota_directa(self, fila):
        """Edita el VALOR de una cuota de préstamo (desde el diálogo de préstamo)."""
        self._consulta_aplicar_edicion(fila, self._pedir_nuevo_valor(fila))

    def _pedir_nuevo_valor(self, fila):
        """Mini-diálogo para pedir nuevo valor. Retorna float o None."""
        resultado = [None]
        dlg = tk.Toplevel(self.master)
        dlg.title("Editar cuota")
        dlg.geometry("380x200")
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        dlg.resizable(False, False)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width()  - 380) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 200) // 2
        dlg.geometry(f"380x200+{x}+{y}")
        try:
            dlg.wait_visibility(); dlg.grab_set()
        except Exception:
            dlg.focus_set()

        hdr = tk.Frame(dlg, bg=COL_PEND, height=34)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        fv = fila['FECHA_VEN'].strftime('%d/%m/%Y') if fila['FECHA_VEN'] else '-'
        tk.Label(hdr, text=f"  Cuota #{fila['SECUENCIA']}  —  Vence {fv}",
                 bg=COL_PEND, fg=COL_WHITE, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=8, pady=6)

        f = tk.Frame(dlg, bg=COL_BG, padx=20, pady=12)
        f.pack(fill=tk.X)
        tk.Label(f, text=f"Valor actual: ${fila['VALOR']:,.2f}",
                 bg=COL_BG, font=('Segoe UI', 9), fg='gray').pack(anchor='w')
        tk.Label(f, text="Nuevo valor ($):", bg=COL_BG, font=('Segoe UI', 9, 'bold')).pack(anchor='w', pady=(6, 2))
        nv = tk.StringVar(value=f"{fila['VALOR']:.2f}")
        e = ttk.Entry(f, textvariable=nv, font=('Segoe UI', 11), width=16)
        e.pack(anchor='w', ipady=3)
        e.focus_set(); e.select_range(0, tk.END)

        def _ok():
            try:
                v = float(nv.get().replace(',', '.'))
                if v <= 0:
                    raise ValueError
                resultado[0] = v
                dlg.destroy()
            except Exception:
                messagebox.showerror("Valor inválido", "Ingrese un número mayor que 0.", parent=dlg)

        bf = tk.Frame(dlg, bg=COL_BG, pady=8, padx=20)
        bf.pack(fill=tk.X)
        tk.Button(bf, text="  Guardar  ", command=_ok,
                  bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="  Cancelar  ", command=dlg.destroy,
                  bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT)
        dlg.bind('<Return>', lambda e: _ok())
        dlg.bind('<Escape>', lambda e: dlg.destroy())
        dlg.wait_window()
        return resultado[0]

    # ===================================================================
    # TAB TODOS LOS TIPOS
    # ===================================================================
    def _build_tab_todos_tipos(self):
        pane = ttk.PanedWindow(self.tab_todos_tipos, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(pane)
        pane.add(left, weight=3)
        right = ttk.Frame(pane)
        pane.add(right, weight=1)
        self._build_tt_masivo_tab(left)
        self._build_tt_historial_panel(right)

    def _build_tt_individual_tab(self, parent):
        main = ttk.Frame(parent, padding=5)
        main.pack(fill=tk.BOTH, expand=True)

        p = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        p.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(p)
        p.add(left, weight=2)
        right_ind = ttk.Frame(p)
        p.add(right_ind, weight=1)
        # El panel historial se construye al final para no interferir con el left

        fdata = ttk.LabelFrame(left, text="Datos del Movimiento", padding=10)
        fdata.pack(fill=tk.X, pady=5)

        ttk.Label(fdata, text="Empleado:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.tt_ind_emp_entry = ttk.Entry(fdata, width=14, font=('Segoe UI', 10))
        self.tt_ind_emp_entry.grid(row=0, column=1, sticky=tk.W, pady=4, ipady=4)
        self.tt_ind_emp_entry.bind('<KeyRelease>', lambda e: self._debounced('tt_ind_emp', 400, self._tt_ind_buscar_nombre))
        tk.Button(fdata, text="  Buscar  ", command=self._tt_ind_buscar_empleado,
                 bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2').grid(row=0, column=2, padx=6)
        self.tt_ind_name_var = tk.StringVar()
        tk.Label(fdata, textvariable=self.tt_ind_name_var, fg=COL_ACCENT,
                font=('Segoe UI', 10, 'bold')).grid(row=0, column=3, sticky=tk.W, padx=5)

        bf = ttk.LabelFrame(fdata, text="Buscar por", padding=3)
        bf.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=4)
        self.tt_ind_buscar_por = tk.StringVar(value="cedula")
        ttk.Radiobutton(bf, text="Codigo empleado", variable=self.tt_ind_buscar_por, value="codigo").pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(bf, text="Cedula", variable=self.tt_ind_buscar_por, value="cedula").pack(side=tk.LEFT, padx=4)

        ttk.Label(fdata, text="Tipo:").grid(row=2, column=0, sticky=tk.W, pady=4)
        tipos_vals = [f"{k} - {v['concepto']}" for k, v in CLASES_SIMPLIFICADAS.items()]
        self.tt_ind_tipo_var = tk.StringVar()
        tc = ttk.Combobox(fdata, textvariable=self.tt_ind_tipo_var, width=42, state="readonly", values=tipos_vals)
        tc.set(tipos_vals[0])
        tc.grid(row=2, column=1, columnspan=3, sticky=tk.W, pady=4)

        ttk.Label(fdata, text="Fecha (DD/MM/AAAA):").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.tt_ind_fecha_entry = ttk.Entry(fdata, width=14, font=('Segoe UI', 10))
        self.tt_ind_fecha_entry.insert(0, datetime.now().strftime('%d/%m/%Y'))
        self.tt_ind_fecha_entry.grid(row=3, column=1, sticky=tk.W, pady=4, ipady=4)

        ttk.Label(fdata, text="Valor ($):").grid(row=4, column=0, sticky=tk.W, pady=4)
        self.tt_ind_valor_entry = ttk.Entry(fdata, width=16, font=('Segoe UI', 10))
        self.tt_ind_valor_entry.grid(row=4, column=1, sticky=tk.W, pady=4, ipady=4)

        ttk.Label(fdata, text="Observacion:").grid(row=5, column=0, sticky=tk.W+tk.N, pady=4)
        self.tt_ind_obs_text = tk.Text(fdata, width=50, height=3, wrap=tk.WORD,
                                       font=('Segoe UI', 9), relief='solid', borderwidth=1)
        self.tt_ind_obs_text.grid(row=5, column=1, columnspan=3, sticky=tk.W, pady=4)

        btnf = tk.Frame(left, bg=COL_BG)
        btnf.pack(fill=tk.X, pady=8)
        self.tt_ind_btn_ingresar = tk.Button(btnf, text="  Ingresar  ",
                                              command=self._tt_ind_ingresar,
                                              bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 10, 'bold'),
                                              relief='flat', cursor='hand2', padx=4, pady=3)
        self.tt_ind_btn_ingresar.pack(side=tk.LEFT, padx=3)
        tk.Button(btnf, text="  Limpiar  ", command=self._tt_ind_limpiar,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2', pady=3).pack(side=tk.LEFT, padx=3)

        sf = ttk.LabelFrame(left, text="Resultado", padding=5)
        sf.pack(fill=tk.BOTH, expand=True, pady=5)
        self.tt_ind_result = scrolledtext.ScrolledText(sf, height=8, wrap=tk.WORD, font=('Consolas', 9))
        self.tt_ind_result.pack(fill=tk.BOTH, expand=True)
        self.tt_ind_result.config(state=tk.DISABLED)

        # Panel historial en el lado derecho
        self._build_ind_historial_panel(right_ind)

    def _build_ind_historial_panel(self, parent):
        """Panel historial para Tab 4 - Registro Individual (todos los tipos)."""
        self._ind_hist_rows = {}

        main = ttk.Frame(parent, padding=4)
        main.pack(fill=tk.BOTH, expand=True)

        hdr = tk.Frame(main, bg=COL_HEADER, height=36)
        hdr.pack(fill=tk.X, pady=(0, 4))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Historial de Registros",
                 bg=COL_HEADER, fg=COL_WHITE,
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=8, pady=8)

        sf = tk.Frame(main, bg=COL_BG)
        sf.pack(fill=tk.X, pady=(0, 4))
        self._ind_hist_filtro_var = tk.StringVar()
        ttk.Entry(sf, textvariable=self._ind_hist_filtro_var, width=16,
                  font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 3), ipady=3,
                                              fill=tk.X, expand=True)
        tk.Button(sf, text="Buscar", command=self._ind_historial_buscar,
                  bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(sf, text="↺",
                  command=lambda: (self._ind_hist_filtro_var.set(""),
                                   self._ind_historial_buscar()),
                  bg='#78909C', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2', width=2).pack(side=tk.LEFT, padx=2)
        tk.Label(sf, text="  N° o nombre", bg=COL_BG,
                 fg='gray', font=('Segoe UI', 7)).pack(side=tk.LEFT)
        self._ind_hist_filtro_var.trace_add("write",
            lambda *a: self.master.after(600, self._ind_historial_buscar))

        tf = ttk.Frame(main)
        tf.pack(fill=tk.BOTH, expand=True)

        cols = ("Tipo", "N°", "Empleado", "Fecha", "Total")
        self._ind_hist_tree = ttk.Treeview(tf, columns=cols, show="headings",
                                           selectmode="browse", height=20)
        self._ind_hist_tree.heading("Tipo",     text="Tipo",     anchor=tk.W)
        self._ind_hist_tree.heading("N°",       text="N°",       anchor=tk.CENTER)
        self._ind_hist_tree.heading("Empleado", text="Empleado", anchor=tk.W)
        self._ind_hist_tree.heading("Fecha",    text="Fecha",    anchor=tk.CENTER)
        self._ind_hist_tree.heading("Total",    text="Total",    anchor=tk.E)
        self._ind_hist_tree.column("Tipo",     width=60,  anchor=tk.W,      stretch=False)
        self._ind_hist_tree.column("N°",       width=60,  anchor=tk.CENTER, stretch=False)
        self._ind_hist_tree.column("Empleado", width=150, anchor=tk.W,      stretch=True)
        self._ind_hist_tree.column("Fecha",    width=82,  anchor=tk.CENTER, stretch=False)
        self._ind_hist_tree.column("Total",    width=80,  anchor=tk.E,      stretch=False)

        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self._ind_hist_tree.yview)
        self._ind_hist_tree.configure(yscrollcommand=vsb.set)
        self._ind_hist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._ind_hist_tree.tag_configure('par',      background='#F0F4F8')
        self._ind_hist_tree.tag_configure('impar',    background=COL_WHITE)
        self._ind_hist_tree.tag_configure('prestamo', background='#FFF3E0')
        self._ind_hist_tree.tag_configure('ingreso',  background='#E8F5E9')
        self._ind_hist_tree.bind("<Double-1>", self._ind_historial_ver_detalle)

        bot = tk.Frame(main, bg=COL_BG)
        bot.pack(fill=tk.X, pady=(4, 0))
        tk.Button(bot, text="Ver / Editar", command=self._ind_historial_ver_detalle,
                  bg=COL_PEND, fg=COL_WHITE, font=('Segoe UI', 8, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)
        self._ind_hist_info_var = tk.StringVar(value="")
        tk.Label(bot, textvariable=self._ind_hist_info_var,
                 bg=COL_BG, fg='gray', font=('Segoe UI', 8)).pack(side=tk.RIGHT, padx=4)

    def _ind_historial_buscar(self):
        filtro = self._ind_hist_filtro_var.get().strip()
        def _thread():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                rows, _ = obtener_historial_todos(conn2, filtro, 200)
                self.master.after(0, lambda r=rows: self._ind_historial_mostrar(r))
            finally:
                conn2.close()
        threading.Thread(target=_thread, daemon=True).start()

    def _ind_historial_mostrar(self, rows):
        for iid in self._ind_hist_tree.get_children():
            self._ind_hist_tree.delete(iid)
        self._ind_hist_rows.clear()
        NOMBRE_CLASE = {
            '205': 'Préstamo', '202': 'Anticipo', '203': 'Multa',
            '204': 'Quirogr.', '206': 'Alimentos', '207': 'Hipotec.',
            '217': 'Ant.Otros', '218': 'IESS Cón.', '219': 'Imp.Renta',
            '250': 'Ant.Surt.', '102': 'Bonific.', '110': 'Maniobras',
            '111': 'Reembolso', '120': 'Moviliz.',
        }
        for idx, r in enumerate(rows):
            clase = r['clase']
            cuotas = r['cuotas']
            tipo_label = NOMBRE_CLASE.get(clase, clase)
            if clase == '205' and cuotas > 1:
                tipo_label = f"Prést.({cuotas}c)"
            if clase == '205':
                tag = 'prestamo'
            elif clase in ('102', '110', '111', '120'):
                tag = 'ingreso'
            else:
                tag = 'par' if idx % 2 == 0 else 'impar'
            iid = self._ind_hist_tree.insert("", tk.END, tags=(tag,),
                values=(tipo_label, f"{int(r['numero']):05d}",
                        r['nombre'], r['fecha'], f"${r['valor']:,.2f}"))
            self._ind_hist_rows[iid] = r
        aviso = " (máx 200)" if len(rows) == 200 else ""
        self._ind_hist_info_var.set(f"{len(rows)}{aviso}")

    def _ind_historial_ver_detalle(self, event=None):
        sel = self._ind_hist_tree.selection()
        if not sel:
            return
        r = self._ind_hist_rows.get(sel[0])
        if not r:
            return
        if r['clase'] == '205':
            self._tt_hist_dlg_prestamo(r)
        else:
            self._tt_hist_dlg_egreso(r)

    def _build_tt_masivo_tab(self, parent):
        main = ttk.Frame(parent, padding=5)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="EGRESOS E INGRESOS — TODOS LOS TIPOS", font=("Segoe UI", 14, "bold"),
                fg=COL_HEADER).pack(pady=3)

        # Config row
        cf = ttk.Frame(main)
        cf.pack(fill=tk.X, pady=3)

        tipo_frame = ttk.LabelFrame(cf, text="Tipo de Movimiento", padding=3)
        tipo_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        tipos_vals = []
        for codigo, cfg in CLASES_SIMPLIFICADAS.items():
            tipos_vals.append(f"{codigo} - {cfg['concepto']}")
        self.tt_tipo_var = tk.StringVar(value="110")
        tc = ttk.Combobox(tipo_frame, textvariable=self.tt_tipo_var, width=30, state="readonly", values=tipos_vals)
        tc.set("110 - MANIOBRAS")
        tc.pack(anchor=tk.W, pady=2)

        modo_frame = ttk.LabelFrame(cf, text="Modo de Numeracion", padding=3)
        modo_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5,0))
        self.tt_modo_var = tk.StringVar(value="individual")
        ttk.Radiobutton(modo_frame, text="Individual (un numero por empleado)",
                       variable=self.tt_modo_var, value="individual").pack(anchor=tk.W)
        ttk.Radiobutton(modo_frame, text="Agrupado (mismo numero para todos)",
                       variable=self.tt_modo_var, value="agrupado").pack(anchor=tk.W)

        tt_buscar_frame = ttk.LabelFrame(cf, text="Buscar Empleado Por", padding=3)
        tt_buscar_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5,0))
        ttk.Radiobutton(tt_buscar_frame, text="Codigo empleado", variable=self.tt_buscar_por, value="codigo").pack(anchor=tk.W)
        ttk.Radiobutton(tt_buscar_frame, text="Cedula", variable=self.tt_buscar_por, value="cedula").pack(anchor=tk.W)

        # Observacion comun (solo agrupado)
        self.tt_obs_frame = ttk.Frame(main)
        self.tt_obs_frame.pack(fill=tk.X, pady=3)
        ttk.Label(self.tt_obs_frame, text="Observacion Comun:").pack(side=tk.LEFT)
        self.tt_obs_comun_var = tk.StringVar()
        ttk.Entry(self.tt_obs_frame, textvariable=self.tt_obs_comun_var, width=60).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.tt_obs_frame.pack_forget()

        self.tt_tipo_var.trace_add("write", lambda *a: self._tt_update_instrucciones())
        self.tt_modo_var.trace_add("write", lambda *a: self._tt_toggle_obs())
        self.tt_buscar_por.trace_add("write", lambda *a: self._tt_update_instrucciones())

        # Instructions
        self.tt_instruc = tk.Label(main, text="Formato: Codigo | Fecha(DD/MM/AAAA) | Valor | Observacion",
                                   font=("Consolas", 9), fg=COL_ACCENT)
        self.tt_instruc.pack(anchor=tk.W, pady=2)

        # Grid
        self._tt_build_grid(main)

        # Nav
        nav = ttk.Frame(main)
        nav.pack(fill=tk.X, pady=3)
        ttk.Button(nav, text="-100", command=lambda: self._tt_nav(-100)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="-20", command=lambda: self._tt_nav(-20)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="+20", command=lambda: self._tt_nav(20)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="+100", command=lambda: self._tt_nav(100)).pack(side=tk.LEFT, padx=1)
        ttk.Button(nav, text="INICIO", command=self._tt_ir_inicio).pack(side=tk.LEFT, padx=10)
        ttk.Button(nav, text="FINAL", command=self._tt_ir_final).pack(side=tk.LEFT, padx=2)

        # Action buttons
        btnf = ttk.Frame(main)
        btnf.pack(fill=tk.X, pady=3)
        tk.Button(btnf, text="  PEGAR (Ctrl+V)  ", command=self._tt_paste,
                 bg=COL_PEND, fg="white", font=("Segoe UI", 10, "bold"),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        ttk.Button(btnf, text="Validar", command=self._tt_validar_todos).pack(side=tk.LEFT, padx=3)
        ttk.Button(btnf, text="Limpiar", command=self._tt_limpiar).pack(side=tk.LEFT, padx=3)
        ttk.Button(btnf, text="Resumen", command=self._tt_resumen).pack(side=tk.LEFT, padx=3)
        ttk.Button(btnf, text="Cargar Archivo", command=self._tt_cargar_archivo).pack(side=tk.LEFT, padx=3)
        self._tt_procesar_btn = tk.Button(btnf, text="  PROCESAR  ", command=self._tt_procesar,
                 bg=COL_OK, fg="white", font=("Segoe UI", 12, "bold"),
                 relief='flat', cursor='hand2')
        self._tt_procesar_btn.pack(side=tk.LEFT, padx=10)

        # Cancel btn
        self.tt_cancel_btn = ttk.Button(btnf, text="Cancelar", command=self._tt_cancelar, state=tk.DISABLED)
        self.tt_cancel_btn.pack(side=tk.LEFT, padx=3)

        # Stats
        self.tt_stats_var = tk.StringVar(value="Datos: 0 | Cache: 0 | Filas: 1-20 de 2500")
        tk.Label(main, textvariable=self.tt_stats_var, font=("Arial", 9), fg="darkgreen").pack(anchor=tk.W, pady=2)

        # Log
        lf = ttk.LabelFrame(main, text="Log", padding=3)
        lf.pack(fill=tk.X, pady=3)
        self.tt_log_text = scrolledtext.ScrolledText(lf, height=4, font=("Consolas", 9))
        self.tt_log_text.pack(fill=tk.X)

        self._tt_init_grid()

    # --- Individual EGR/ING helpers ---

    def _tt_ind_buscar_nombre(self):
        val = self.tt_ind_emp_entry.get().strip()
        if not val:
            self.tt_ind_name_var.set("")
            return
        por_cedula = self.tt_ind_buscar_por.get() == "cedula"
        if not por_cedula and val.isdigit():
            self._tt_ind_buscar_por_id(int(val))
        elif por_cedula and len(val) > 8:
            self._tt_ind_buscar_por_cedula(val)

    def _tt_ind_buscar_por_id(self, emp_id):
        def bg():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                cursor = conn2.cursor()
                cursor.execute("SELECT APELLIDOS, NOMBRES FROM RPEMPLEA WITH (NOLOCK) WHERE EMPLEADO = ?", emp_id)
                r = cursor.fetchone()
                if r:
                    nombre = f"{str(r.APELLIDOS or '').strip()} {str(r.NOMBRES or '').strip()}".strip()
                    self.master.after(0, lambda: self.tt_ind_name_var.set(nombre))
                else:
                    self.master.after(0, lambda: self.tt_ind_name_var.set("(No encontrado)"))
            finally:
                conn2.close()
        threading.Thread(target=bg, daemon=True).start()

    def _tt_ind_buscar_por_cedula(self, cedula):
        def bg():
            conn2, err = conectar_bd()
            if err:
                return
            try:
                encontrados, _ = buscar_empleados_por_cedula(conn2, [cedula])
                if encontrados and cedula in encontrados:
                    emp = encontrados[cedula]
                    self.master.after(0, lambda: self._tt_ind_set_empleado(str(emp['id']), emp['nombre_completo']))
                else:
                    self.master.after(0, lambda: self.tt_ind_name_var.set("(No encontrado)"))
            finally:
                conn2.close()
        threading.Thread(target=bg, daemon=True).start()

    def _tt_ind_set_empleado(self, emp_id_str, nombre):
        self.tt_ind_emp_entry.delete(0, tk.END)
        self.tt_ind_emp_entry.insert(0, emp_id_str)
        self.tt_ind_name_var.set(nombre)

    def _tt_ind_buscar_empleado(self):
        dlg = tk.Toplevel(self.master)
        dlg.title("Buscar Empleado")
        dlg.geometry("640x460")
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 640) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 460) // 2
        dlg.geometry(f"640x460+{x}+{y}")
        dlg.focus_set()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except:
            pass

        hdr = tk.Frame(dlg, bg=COL_HEADER, height=36)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Buscar Empleado", bg=COL_HEADER, fg=COL_WHITE,
                font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=12, pady=6)

        sf = tk.Frame(dlg, bg=COL_BG)
        sf.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(sf, text="Filtro:", bg=COL_BG, font=('Segoe UI', 9)).pack(side=tk.LEFT)
        filtro_var = tk.StringVar()
        ttk.Entry(sf, textvariable=filtro_var, width=40, font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=8, ipady=3)

        tree = ttk.Treeview(dlg, columns=("ID", "Apellidos", "Nombres", "Depto"), show="headings", height=15)
        tree.heading("ID", text="ID"); tree.heading("Apellidos", text="Apellidos")
        tree.heading("Nombres", text="Nombres"); tree.heading("Depto", text="Depto")
        tree.column("ID", width=65, anchor=tk.CENTER); tree.column("Apellidos", width=210)
        tree.column("Nombres", width=210); tree.column("Depto", width=75, anchor=tk.CENTER)
        tree.tag_configure('par', background='#F0F4F8')
        tree.tag_configure('impar', background=COL_WHITE)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        def buscar():
            filtro = filtro_var.get().strip()
            def bg():
                conn2, err = conectar_bd()
                if err:
                    return
                try:
                    rows, _ = buscar_empleados(conn2, filtro, 200)
                    self.master.after(0, lambda: _mostrar(rows))
                finally:
                    conn2.close()
            threading.Thread(target=bg, daemon=True).start()

        def _mostrar(rows):
            for i in tree.get_children():
                tree.delete(i)
            for idx, r in enumerate(rows):
                tag = 'par' if idx % 2 == 0 else 'impar'
                tree.insert("", tk.END, values=(r['id'], r['apellidos'], r['nombres'], r['depto']), tags=(tag,))

        def seleccionar():
            sel = tree.selection()
            if sel:
                vals = tree.item(sel[0], 'values')
                self.tt_ind_emp_entry.delete(0, tk.END)
                self.tt_ind_emp_entry.insert(0, str(vals[0]))
                self.tt_ind_name_var.set(f"{vals[1]} {vals[2]}")
                dlg.destroy()

        tree.bind("<Double-1>", lambda e: seleccionar())
        bf2 = tk.Frame(dlg, bg=COL_BG)
        bf2.pack(fill=tk.X, padx=10, pady=6)
        tk.Button(bf2, text="  Buscar  ", command=buscar,
                 bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf2, text="  Seleccionar  ", command=seleccionar,
                 bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                 relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf2, text="  Cerrar  ", command=dlg.destroy,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2').pack(side=tk.RIGHT, padx=3)
        filtro_var.trace_add("write", lambda *a: self.master.after(500, buscar))
        buscar()

    def _tt_ind_ingresar(self):
        emp_str = self.tt_ind_emp_entry.get().strip()
        if not emp_str or not emp_str.isdigit():
            messagebox.showwarning("Aviso", "Ingrese o busque un codigo de empleado valido")
            return
        emp_id = int(emp_str)
        tipo_str = self.tt_ind_tipo_var.get()
        if not tipo_str:
            messagebox.showwarning("Aviso", "Seleccione un tipo de movimiento")
            return
        tipo = tipo_str[:3]
        cfg = CLASES_SIMPLIFICADAS.get(tipo)
        if not cfg:
            messagebox.showwarning("Aviso", "Tipo no valido")
            return
        try:
            valor = float(self.tt_ind_valor_entry.get().strip().replace(',', '.'))
            if valor <= 0:
                raise ValueError
        except:
            messagebox.showwarning("Aviso", "Valor invalido (debe ser numero mayor que 0)")
            return
        fecha_str = self.tt_ind_fecha_entry.get().strip()
        fecha = None
        for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
            try:
                fecha = datetime.strptime(fecha_str, fmt)
                break
            except:
                pass
        if fecha is None:
            fecha = datetime.now()
        obs = self.tt_ind_obs_text.get("1.0", tk.END).strip() or cfg['concepto']
        nombre = self.tt_ind_name_var.get() or str(emp_id)
        tipo_texto = "INGRESO" if cfg['tipo'] == "ING" else "EGRESO"
        filas_dlg_ind = [
            ("Tipo",        tipo_texto),
            ("Empleado",    f"{emp_id} — {nombre}"),
            ("Concepto",    cfg['concepto']),
            ("Valor",       f"${valor:,.2f}"),
            ("Fecha",       fecha.strftime('%d/%m/%Y')),
            ("Observacion", (obs or '')[:100]),
        ]

        def proceder_ind():
            self.tt_ind_btn_ingresar.config(state=tk.DISABLED)
            self._set_status(f"Ingresando {tipo_texto}...", COL_PEND)

            def bg():
                conn2, err = conectar_bd()
                if err:
                    self.master.after(0, lambda: self._tt_ind_error(f"Error BD: {err}"))
                    return
                try:
                    numero, err_num = obtener_proximo_numero_tipo(conn2, cfg["tipo"])
                    if err_num:
                        self.master.after(0, lambda: self._tt_ind_error(f"Error numero: {err_num}"))
                        return
                    exito, msg = insertar_movimiento_tipo(conn2, emp_id, numero, fecha, obs, valor, tipo, 1)
                    if exito:
                        ok2, err_upd = actualizar_ultimo_numero_tipo(conn2, numero, cfg["tipo"])
                        if ok2:
                            conn2.commit()
                            if SEGURIDAD_DISPONIBLE:
                                log_operacion('INSERT', emp_id, numero,
                                              f"{cfg['concepto']} ${valor:.2f}")
                            self.master.after(0, lambda n=numero: self._tt_ind_ok(n, emp_id, valor, fecha, cfg, obs))
                        else:
                            conn2.rollback()
                            self.master.after(0, lambda: self._tt_ind_error(f"Error contador: {err_upd}"))
                    else:
                        conn2.rollback()
                        self.master.after(0, lambda: self._tt_ind_error(f"INSERT fallo: {msg}"))
                except Exception as e:
                    try:
                        conn2.rollback()
                    except:
                        pass
                    self.master.after(0, lambda: self._tt_ind_error(str(e)))
                finally:
                    conn2.close()
            threading.Thread(target=bg, daemon=True).start()

        self._dialogo_confirmar(
            f"Confirmar {tipo_texto}",
            f"Verifique los datos antes de confirmar el registro",
            [("Campo", 150), ("Valor", 500)],
            filas_dlg_ind,
            proceder_ind
        )

    def _tt_ind_ok(self, numero, emp_id, valor, fecha, cfg, obs):
        if not self._running:
            return
        tipo_texto = "INGRESO" if cfg['tipo'] == "ING" else "EGRESO"
        self.tt_ind_btn_ingresar.config(state=tk.NORMAL)
        self._set_status(f"{tipo_texto} #{numero} registrado exitosamente", COL_OK)
        self.tt_ind_result.config(state=tk.NORMAL)
        self.tt_ind_result.delete("1.0", tk.END)
        lines = [
            f"OK — {tipo_texto} REGISTRADO",
            "=" * 40,
            f"Numero     : #{numero}",
            f"Empleado   : {emp_id} — {self.tt_ind_name_var.get()}",
            f"Concepto   : {cfg['concepto']}",
            f"Valor      : ${valor:,.2f}",
            f"Fecha      : {fecha.strftime('%d/%m/%Y')}",
            f"Observacion: {obs}",
        ]
        self.tt_ind_result.insert(tk.END, "\n".join(lines))
        self.tt_ind_result.config(state=tk.DISABLED)
        messagebox.showinfo("Exito", f"{tipo_texto} #{numero} registrado correctamente")

    def _tt_ind_error(self, msg):
        if not self._running:
            return
        self.tt_ind_btn_ingresar.config(state=tk.NORMAL)
        self._set_status(f"Error: {msg}", COL_DANGER)
        messagebox.showerror("Error", msg)

    def _tt_ind_limpiar(self):
        self.tt_ind_emp_entry.delete(0, tk.END)
        self.tt_ind_name_var.set("")
        self.tt_ind_valor_entry.delete(0, tk.END)
        self.tt_ind_fecha_entry.delete(0, tk.END)
        self.tt_ind_fecha_entry.insert(0, datetime.now().strftime('%d/%m/%Y'))
        self.tt_ind_obs_text.delete("1.0", tk.END)
        self.tt_ind_result.config(state=tk.NORMAL)
        self.tt_ind_result.delete("1.0", tk.END)
        self.tt_ind_result.config(state=tk.DISABLED)

    def _tt_toggle_obs(self):
        if self.tt_modo_var.get() == "agrupado":
            self.tt_obs_frame.pack(fill=tk.X, pady=3, before=self.tt_instruc)
        else:
            self.tt_obs_frame.pack_forget()

    def _masivo_update_instruc(self):
        por_cedula = self.masivo_buscar_por.get() == "cedula"
        col1 = "Cedula" if por_cedula else "Cod.Emp"
        self.masivo_instruc_var.set(f"Formato: {col1} | Valor Total | Cuotas/Valor | Fecha(DD/MM/AAAA) | Observacion")
        ej_id = "0912345678" if por_cedula else "1234"
        try:
            self.masivo_instruc_ej.config(text=f"Ej: {ej_id}    5000    10    31/01/2026    Prestamo masivo")
        except Exception:
            pass

    def _tt_update_instrucciones(self):
        tipo = self.tt_tipo_var.get()[:3]
        cfg = CLASES_SIMPLIFICADAS.get(tipo, {})
        tipo_texto = "INGRESO" if cfg.get("tipo") == "ING" else "EGRESO"
        modo = self.tt_modo_var.get()
        por_cedula = self.tt_buscar_por.get() == "cedula"
        col1 = "Cedula" if por_cedula else "Codigo"
        if modo == "agrupado":
            self.tt_instruc.config(text=f"Formato: {col1} | Fecha(DD/MM/AAAA) | Valor  (Obs. comun) — {tipo_texto}: {cfg.get('concepto','')}")
        else:
            self.tt_instruc.config(text=f"Formato: {col1} | Fecha(DD/MM/AAAA) | Valor | Observacion — {tipo_texto}: {cfg.get('concepto','')}")

    def _tt_build_grid(self, parent):
        gf = ttk.LabelFrame(parent, text="Datos", padding=3)
        gf.pack(fill=tk.BOTH, expand=True, pady=3)
        container = ttk.Frame(gf)
        container.pack(fill=tk.BOTH, expand=True)
        self.tt_canvas = tk.Canvas(container, height=300, bg=COL_WHITE)
        vsb = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tt_canvas.yview)
        hsb = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.tt_canvas.xview)
        self.tt_grid_frame = ttk.Frame(self.tt_canvas)
        self.tt_grid_frame.bind("<Configure>", lambda e: self.tt_canvas.configure(scrollregion=self.tt_canvas.bbox("all")))
        self.tt_canvas.create_window((0, 0), window=self.tt_grid_frame, anchor="nw")
        self.tt_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        headers = ["#", "Codigo", "Nombre", "Fecha", "Valor", "Observacion"]
        widths = {0:5, 1:10, 2:25, 3:12, 4:12, 5:30}
        for col, h in enumerate(headers):
            tk.Label(self.tt_grid_frame, text=h, font=("Arial", 9, "bold"),
                    relief="ridge", bg=COL_HEADER, fg="white", width=widths.get(col, 15)
                    ).grid(row=0, column=col, sticky="ew", padx=1, pady=1)

    def _tt_init_grid(self):
        self.tt_grid_data = {}
        for i in range(50):
            self.tt_grid_data[i] = {'codigo': '', 'nombre': '', 'fecha': '', 'valor': '', 'observacion': '', 'procesado': False}
        self.tt_total_rows = 2500
        self.tt_visible_start = 0
        self.tt_visible_count = 20
        self.tt_visible_entries = {}
        self.tt_selected_cell = None
        self.tt_operation_cancelled = False
        self._tt_crear_filas()

    def _tt_crear_filas(self):
        for wd in self.tt_visible_entries.values():
            for w in wd.values():
                if w and w.winfo_exists():
                    w.destroy()
        self.tt_visible_entries.clear()
        for i in range(self.tt_visible_count):
            fila = self.tt_visible_start + i
            if fila >= self.tt_total_rows:
                break
            if fila not in self.tt_grid_data:
                self.tt_grid_data[fila] = {'codigo': '', 'nombre': '', 'fecha': '', 'valor': '', 'observacion': '', 'procesado': False}
            self._tt_crear_fila(fila, i+1)
        self._tt_update_stats()

    def _tt_crear_fila(self, fila, fila_vis):
        d = self.tt_grid_data[fila]
        w = {}
        tk.Label(self.tt_grid_frame, text=str(fila+1), relief="ridge", bg="#f0f0f0", width=5).grid(row=fila_vis, column=0, sticky="ew", padx=1, pady=1)

        e = tk.Entry(self.tt_grid_frame, width=10, justify="center")
        e.grid(row=fila_vis, column=1, sticky="ew", padx=1, pady=1)
        e.insert(0, d['codigo'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=0: self._tt_select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._tt_on_change(r, 'codigo', ev.widget.get()))
        w[0] = e

        e = tk.Entry(self.tt_grid_frame, width=25, state="readonly", bg="#e8e8e8")
        e.grid(row=fila_vis, column=2, sticky="ew", padx=1, pady=1)
        if d['nombre']:
            e.config(state="normal")
            e.insert(0, d['nombre'])
            e.config(state="readonly")
        w[1] = e

        e = tk.Entry(self.tt_grid_frame, width=12, justify="center")
        e.grid(row=fila_vis, column=3, sticky="ew", padx=1, pady=1)
        e.insert(0, d['fecha'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=2: self._tt_select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._tt_on_change(r, 'fecha', ev.widget.get()))
        w[2] = e

        e = tk.Entry(self.tt_grid_frame, width=12, justify="right")
        e.grid(row=fila_vis, column=4, sticky="ew", padx=1, pady=1)
        e.insert(0, d['valor'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=3: self._tt_select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._tt_on_change(r, 'valor', ev.widget.get()))
        w[3] = e

        e = tk.Entry(self.tt_grid_frame, width=30)
        e.grid(row=fila_vis, column=5, sticky="ew", padx=1, pady=1)
        e.insert(0, d['observacion'])
        e.bind("<FocusIn>", lambda ev, r=fila, c=4: self._tt_select_cell(r, c))
        e.bind("<KeyRelease>", lambda ev, r=fila: self._tt_on_change(r, 'observacion', ev.widget.get()))
        w[4] = e

        if d.get('procesado'):
            for w2 in w.values():
                try: w2.config(bg="#90EE90")
                except: pass

        self.tt_visible_entries[fila] = w

    def _tt_select_cell(self, row, col):
        self.tt_selected_cell = (row, col)

    def _tt_on_change(self, row, field, value):
        if row in self.tt_grid_data:
            self.tt_grid_data[row][field] = value
            if field == 'codigo' and value:
                # Auto-deteccion: 7+ digitos → siempre tratar como cedula
                parece_cedula = value.strip().isdigit() and len(value.strip()) >= 7
                por_cedula = (self.tt_buscar_por.get() == "cedula") or parece_cedula
                min_len = 8 if por_cedula else 2
                if len(value) > min_len:
                    self._tt_validar_individual(value, row)

    def _tt_validar_individual(self, codigo, fila):
        # Auto-deteccion: 7+ digitos → tratar como cedula aunque este en modo codigo
        parece_cedula = str(codigo).strip().isdigit() and len(str(codigo).strip()) >= 7
        por_cedula = (self.tt_buscar_por.get() == "cedula") or parece_cedula
        if not por_cedula and codigo in self.cache_empleados:
            return
        def bg():
            conn2, err = conectar_bd()
            if err: return
            try:
                if por_cedula:
                    encontrados, _ = buscar_empleados_por_cedula(conn2, [codigo])
                else:
                    encontrados, _ = buscar_empleados_batch(conn2, [codigo])
                if encontrados and codigo in encontrados:
                    emp = encontrados[codigo]
                    self.cache_empleados.update(encontrados)
                    self.tt_grid_data[fila]['nombre'] = emp['nombre_completo']
                    if por_cedula:
                        self.tt_grid_data[fila]['codigo'] = str(emp['id'])
                        self.master.after(0, self._tt_crear_filas)
                    else:
                        self.master.after(0, lambda: self._tt_actualizar_nombre_widget(fila))
                elif codigo:
                    self.tt_grid_data[fila]['nombre'] = "NO ENCONTRADO"
                    self.master.after(0, lambda: self._tt_actualizar_nombre_widget(fila))
            finally:
                conn2.close()
        self.thread_pool.submit(bg)

    def _tt_actualizar_nombre_widget(self, fila):
        if fila in self.tt_visible_entries and 1 in self.tt_visible_entries[fila]:
            entry = self.tt_visible_entries[fila][1]
            if entry and entry.winfo_exists():
                entry.config(state="normal")
                entry.delete(0, tk.END)
                entry.insert(0, self.tt_grid_data[fila]['nombre'])
                entry.config(state="readonly")

    def _tt_parse_linea(self, line):
        if '\t' in line: return [v.strip() for v in line.split('\t')]
        elif ';' in line: return [v.strip() for v in line.split(';')]
        elif '|' in line: return [v.strip() for v in line.split('|')]
        elif ',' in line and line.count(',') >= 2: return [v.strip() for v in line.split(',')]
        return [line.strip()]

    def _tt_paste(self):
        if self.tt_selected_cell is None:
            messagebox.showwarning("Aviso", "Seleccione una celda primero")
            return
        clipboard = pyperclip.paste()
        if not clipboard:
            messagebox.showinfo("Vacio", "Portapapeles vacio")
            return
        lines = clipboard.strip().replace('\r', '').split('\n')
        if len(lines) > 2500:
            lines = lines[:2500]
        start_row, start_col = self.tt_selected_cell
        self._tt_log(f"Pegando {len(lines)} lineas desde fila {start_row+1}")
        codigos = set()
        for i, line in enumerate(lines):
            row = start_row + i
            if row >= self.tt_total_rows: break
            line = line.strip()
            if not line: continue
            if row not in self.tt_grid_data:
                self.tt_grid_data[row] = {'codigo': '', 'nombre': '', 'fecha': '', 'valor': '', 'observacion': '', 'procesado': False}
            valores = self._tt_parse_linea(line)
            self._tt_pegar_en_fila(row, start_col, valores)
            if start_col == 0 and valores:
                codigos.add(valores[0])
        self._tt_crear_filas()
        if codigos:
            self._tt_validar_async(codigos)
        messagebox.showinfo("OK", f"Pegados datos en {len(lines)} filas")

    def _tt_pegar_en_fila(self, row, start_col, valores):
        col_to_field = {0: 'codigo', 2: 'fecha', 3: 'valor', 4: 'observacion'}
        for j, val in enumerate(valores):
            if not val: continue
            if start_col == 0:
                target_col = 0 if j == 0 else j + 1
            else:
                target_col = start_col + j
            if target_col in col_to_field:
                self.tt_grid_data[row][col_to_field[target_col]] = val

    def _tt_validar_async(self, codigos):
        # Separar cedulas (7+ digitos) de codigos (numeros cortos)
        cedulas_set  = {c for c in codigos if str(c).strip().isdigit() and len(str(c).strip()) >= 7}
        codigos_set  = codigos - cedulas_set
        modo_radio   = self.tt_buscar_por.get()
        # Si el radio dice cedula, todo pasa por cedula
        if modo_radio == "cedula":
            cedulas_set = set(codigos)
            codigos_set = set()

        def bg():
            conn2, err = conectar_bd()
            if err: return
            try:
                encontrados = {}
                if cedulas_set:
                    r, _ = buscar_empleados_por_cedula(conn2, cedulas_set)
                    encontrados.update(r)
                if codigos_set:
                    r, _ = buscar_empleados_batch(conn2, codigos_set)
                    encontrados.update(r)
                if encontrados:
                    self.cache_empleados.update(encontrados)
                    for fila, d in self.tt_grid_data.items():
                        clave = d['codigo']
                        if clave in encontrados:
                            emp = encontrados[clave]
                            d['nombre'] = emp['nombre_completo']
                            # Si es cedula → reemplazar por codigo de empleado
                            parece_cedula = str(clave).strip().isdigit() and len(str(clave).strip()) >= 7
                            if modo_radio == "cedula" or parece_cedula:
                                d['codigo'] = str(emp['id'])
                        elif d['codigo']:
                            d['nombre'] = "NO ENCONTRADO"
                    self.master.after(0, self._tt_crear_filas)
            finally:
                conn2.close()
        self.thread_pool.submit(bg)

    def _tt_validar_todos(self):
        codigos = {d['codigo'] for d in self.tt_grid_data.values() if d['codigo']}
        if codigos:
            self._tt_log(f"Validando {len(codigos)} empleados...")
            self._tt_validar_async(codigos)

    def _tt_limpiar(self):
        if messagebox.askyesno("Confirmar", "Limpiar todos los datos?"):
            for d in self.tt_grid_data.values():
                d['codigo'] = ''
                d['nombre'] = ''
                d['fecha'] = ''
                d['valor'] = ''
                d['observacion'] = ''
                d['procesado'] = False
            self._tt_crear_filas()
            self._tt_log("Datos limpiados")

    def _tt_nav(self, delta):
        self.tt_visible_start = max(0, min(self.tt_visible_start + delta, self.tt_total_rows - self.tt_visible_count))
        self._tt_crear_filas()

    def _tt_ir_inicio(self):
        self.tt_visible_start = 0
        self._tt_crear_filas()

    def _tt_ir_final(self):
        self.tt_visible_start = max(0, self.tt_total_rows - self.tt_visible_count)
        self._tt_crear_filas()

    def _tt_update_stats(self):
        filas_con = len([d for d in self.tt_grid_data.values() if d['codigo']])
        cache = len(self.cache_empleados)
        inicio = self.tt_visible_start + 1
        fin = min(self.tt_visible_start + self.tt_visible_count, self.tt_total_rows)
        self.tt_stats_var.set(f"Datos: {filas_con:,} | Cache: {cache} | Filas: {inicio:,}-{fin:,} de {self.tt_total_rows:,}")

    def _tt_log(self, msg):
        try:
            self.tt_log_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            self.tt_log_text.see(tk.END)
        except: pass

    def _tt_resumen(self):
        tipo = self.tt_tipo_var.get()[:3]
        cfg = CLASES_SIMPLIFICADAS.get(tipo, {})
        tipo_texto = "INGRESO" if cfg.get("tipo") == "ING" else "EGRESO"
        filas_validas = 0
        total_valor = 0
        for data in self.tt_grid_data.values():
            if data['codigo'] and data['valor'] and data['fecha'] and not data.get('procesado'):
                try:
                    v = float(data['valor'])
                    if v > 0:
                        filas_validas += 1
                        total_valor += v
                except: pass
        dlg = tk.Toplevel(self.master)
        dlg.title("Resumen de operacion")
        dlg.geometry("440x320")
        dlg.configure(bg=COL_BG)
        dlg.transient(self.master)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() - 440) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 320) // 2
        dlg.geometry(f"440x320+{x}+{y}")
        dlg.focus_set()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except:
            pass
        hdr2 = tk.Frame(dlg, bg=COL_HEADER, height=36)
        hdr2.pack(fill=tk.X)
        hdr2.pack_propagate(False)
        tk.Label(hdr2, text="Resumen del lote", bg=COL_HEADER, fg=COL_WHITE,
                font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=12, pady=6)
        t = scrolledtext.ScrolledText(dlg, wrap=tk.WORD, font=("Consolas", 9),
                                      bg='#F8F9FA', relief='flat')
        t.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        lines = [
            f"RESUMEN {tipo_texto}S",
            "=" * 40,
            f"Tipo: {cfg.get('concepto','')}",
            f"Filas con datos: {len([d for d in self.tt_grid_data.values() if d['codigo']]):,}",
            f"Filas procesables: {filas_validas:,}",
            f"Valor total: ${total_valor:,.2f}",
            f"Promedio: ${total_valor/filas_validas:,.2f}" if filas_validas > 0 else "",
        ]
        t.insert(tk.END, "\n".join(l for l in lines if l))
        t.config(state=tk.DISABLED)
        tk.Button(dlg, text="  Cerrar  ", command=dlg.destroy,
                 bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                 relief='flat', cursor='hand2').pack(pady=8)

    def _tt_cargar_archivo(self):
        filename = filedialog.askopenfilename(
            title="Archivo masivo",
            filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if not filename: return
        try:
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(filename, encoding='utf-8')
            else:
                df = pd.read_excel(filename)
            if len(df) > 2500:
                df = df.head(2500)
            self._tt_limpiar_silencioso()
            importados = 0
            codigos = set()
            for index, row in df.iterrows():
                if index >= self.tt_total_rows: break
                if index not in self.tt_grid_data:
                    self.tt_grid_data[index] = {'codigo': '', 'nombre': '', 'fecha': '', 'valor': '', 'observacion': '', 'procesado': False}
                if len(row) >= 1 and pd.notna(row.iloc[0]):
                    self.tt_grid_data[index]['codigo'] = str(row.iloc[0]).strip()
                    if self.tt_grid_data[index]['codigo']:
                        codigos.add(self.tt_grid_data[index]['codigo'])
                if len(row) >= 2 and pd.notna(row.iloc[1]):
                    self.tt_grid_data[index]['fecha'] = str(row.iloc[1]).strip()
                if len(row) >= 3 and pd.notna(row.iloc[2]):
                    self.tt_grid_data[index]['valor'] = str(row.iloc[2]).strip()
                if len(row) >= 4 and pd.notna(row.iloc[3]):
                    self.tt_grid_data[index]['observacion'] = str(row.iloc[3]).strip()
                importados += 1
            self._tt_crear_filas()
            self._tt_log(f"Importados {importados:,} registros")
            if codigos:
                self._tt_validar_async(codigos)
        except Exception as e:
            self._tt_log(f"Error cargando: {e}")

    def _tt_limpiar_silencioso(self):
        for d in self.tt_grid_data.values():
            d['codigo'] = ''
            d['nombre'] = ''
            d['fecha'] = ''
            d['valor'] = ''
            d['observacion'] = ''
            d['procesado'] = False

    def _tt_cancelar(self):
        self.tt_operation_cancelled = True
        self._tt_log("Cancelacion solicitada")

    def _tt_procesar(self):
        tipo = self.tt_tipo_var.get()[:3]
        cfg = CLASES_SIMPLIFICADAS.get(tipo)
        if not cfg:
            messagebox.showerror("Error", "Seleccione un tipo valido")
            return
        modo = self.tt_modo_var.get()
        filas_validas = []
        for i, d in self.tt_grid_data.items():
            if d['codigo'] and d['valor'] and d['fecha'] and not d.get('procesado'):
                try:
                    v = float(d['valor'])
                    if v > 0:
                        filas_validas.append((i, d))
                except: pass
        if not filas_validas:
            messagebox.showwarning("Sin datos", "No hay filas validas para procesar")
            return
        filas_dlg_tt = []
        for idx, (i, d) in enumerate(filas_validas, 1):
            try:
                val_fmt = f"${float(d['valor']):,.2f}"
            except Exception:
                val_fmt = d.get('valor', '')
            filas_dlg_tt.append((
                idx,
                d.get('codigo', ''),
                d.get('nombre', ''),
                d.get('fecha', ''),
                val_fmt,
                (d.get('observacion', '') or '')[:60],
            ))

        total_valor_tt = sum(float(d['valor']) for _, d in filas_validas)
        desc_tt = (f"Tipo: {cfg['concepto']}   Modo: {modo}   "
                   f"Registros: {len(filas_validas):,}   Total: ${total_valor_tt:,.2f}")

        def proceder_tt():
            self.tt_operation_cancelled = False
            self.tt_cancel_btn.config(state=tk.NORMAL)
            self._tt_procesar_btn.config(state=tk.DISABLED)
            self.progress_var.set(0)
            self._set_status("Procesando...", COL_PEND)
            self._tt_log(f"Procesando {len(filas_validas):,} registros...")

            def bg():
                conn2, err = conectar_bd()
                if err:
                    self.master.after(0, lambda: self._tt_log(f"Error BD: {err}"))
                    return
                try:
                    procesados = 0
                    errores = 0
                    numero_agrupado = None
                    secuencia_agrupado = 0

                    if modo == "agrupado":
                        numero_agrupado, err_num = obtener_proximo_numero_tipo(conn2, cfg["tipo"])
                        if err_num:
                            self.master.after(0, lambda: self._tt_log(f"Error numero: {err_num}"))
                            return
                        self.master.after(0, lambda: self._tt_log(f"Numero agrupado: {numero_agrupado}"))
                    else:
                        self.master.after(0, lambda: self._tt_log("Modo individual: un numero por empleado"))

                    total = len(filas_validas)
                    for idx, (fila_num, d) in enumerate(filas_validas):
                        if self.tt_operation_cancelled:
                            self.master.after(0, lambda: self._tt_log("Operacion cancelada"))
                            break
                        try:
                            emp = int(d['codigo'])
                            valor = float(d['valor'])
                            fecha_str = d['fecha'].strip()
                            fecha_dt = None
                            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                                try:
                                    fecha_dt = datetime.strptime(fecha_str, fmt)
                                    break
                                except: pass
                            if fecha_dt is None:
                                fecha_dt = datetime.now()
                                self.master.after(0, lambda f=fecha_str: self._tt_log(f"Fecha invalida '{f}', usando actual"))

                            if modo == "agrupado":
                                numero = numero_agrupado
                                secuencia_agrupado += 1
                                secuencia = secuencia_agrupado
                                obs = self.tt_obs_comun_var.get().strip() or "Procesamiento agrupado"
                            else:
                                numero, err_num = obtener_proximo_numero_tipo(conn2, cfg["tipo"])
                                if err_num:
                                    errores += 1
                                    self.master.after(0, lambda e=emp, m=err_num: self._tt_log(f"Error Emp {e}: {m}"))
                                    continue
                                secuencia = 1
                                obs = d.get('observacion', '') or cfg['concepto']

                            exito, msg = insertar_movimiento_tipo(conn2, emp, numero, fecha_dt, obs, valor, tipo, secuencia)
                            if exito:
                                if modo == "individual":
                                    ok2, err_upd = actualizar_ultimo_numero_tipo(conn2, numero, cfg["tipo"])
                                    if ok2:
                                        conn2.commit()
                                        d['procesado'] = True
                                        procesados += 1
                                        self.master.after(0, lambda e=emp, n=numero: self._tt_log(f"OK Emp {e}: #{n}"))
                                    else:
                                        try: conn2.rollback()
                                        except: pass
                                        errores += 1
                                        self.master.after(0, lambda e=emp, m=err_upd: self._tt_log(f"Error Emp {e}: Contador - {m}"))
                                else:
                                    d['procesado'] = True
                                    procesados += 1
                                    self.master.after(0, lambda e=emp, n=numero: self._tt_log(f"OK Emp {e}: #{n}"))
                            else:
                                if modo == "individual":
                                    try:
                                        conn2.rollback()
                                    except:
                                        pass
                                errores += 1
                                self.master.after(0, lambda e=emp, m=msg: self._tt_log(f"Error Emp {e}: {m}"))
                        except Exception as e:
                            errores += 1
                            self.master.after(0, lambda f=fila_num, m=str(e): self._tt_log(f"Error fila {f}: {m}"))

                        self.master.after(0, lambda v=(idx+1)/total*100: self.progress_var.set(v))

                    if modo == "agrupado" and procesados > 0:
                        ok2, err_upd = actualizar_ultimo_numero_tipo(conn2, numero_agrupado, cfg["tipo"])
                        if ok2:
                            conn2.commit()
                        else:
                            try: conn2.rollback()
                            except: pass
                            procesados = 0
                            self.master.after(0, lambda: self._tt_log(f"ERROR: no se pudo actualizar contador - {err_upd}"))

                    self.master.after(0, lambda: self._tt_fin(procesados, errores))
                finally:
                    conn2.close()

            threading.Thread(target=bg, daemon=True).start()

        self._dialogo_confirmar(
            "Confirmar Registro Masivo",
            desc_tt,
            [("#", 40), ("Empleado", 80), ("Nombre", 180),
             ("Fecha", 100), ("Valor", 100), ("Observacion", 200)],
            filas_dlg_tt,
            proceder_tt
        )

    def _tt_fin(self, ok, err):
        if not self._running:
            return
        self._tt_crear_filas()
        self.tt_cancel_btn.config(state=tk.DISABLED)
        self._tt_procesar_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        color = COL_OK if err == 0 else COL_PEND
        self._set_status(f"Todos Tipos: {ok} exitosos, {err} errores", color)
        self._tt_log(f"Fin: {ok} ok, {err} errores")
        messagebox.showinfo("Resultado", f"Exitosos: {ok}\nErrores: {err}")


    # ===================================================================
    # TAB BIESS QUIROGRAFARIOS / HIPOTECARIOS
    # ===================================================================

    def _build_biess_tab(self):
        parent = self.tab_biess
        main = ttk.Frame(parent, padding=6)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Header ───────────────────────────────────────────────────
        hdr = tk.Frame(main, bg=COL_HEADER, height=40)
        hdr.pack(fill=tk.X, pady=(0, 6))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  \U0001f3e6  BIESS — Quirografarios / Hipotecarios",
                 bg=COL_HEADER, fg=COL_WHITE,
                 font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        # ── Configuracion + parametros Excel ─────────────────────────
        top = tk.Frame(main, bg=COL_BG)
        top.pack(fill=tk.X)

        # Config frame
        cfg_frame = tk.LabelFrame(top, text="Configuración", bg=COL_BG, fg=COL_HEADER,
                                  font=('Segoe UI', 9, 'bold'), padx=8, pady=6)
        cfg_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        tipo_row = tk.Frame(cfg_frame, bg=COL_BG)
        tipo_row.pack(fill=tk.X, pady=3)
        tk.Label(tipo_row, text="Tipo:", bg=COL_BG, font=('Segoe UI', 9, 'bold'),
                 width=11, anchor='w').pack(side=tk.LEFT)
        self.biess_tipo_var = tk.StringVar(value="204")
        tk.Radiobutton(tipo_row, text="204 - Quirografario", variable=self.biess_tipo_var,
                       value="204", bg=COL_BG, font=('Segoe UI', 9),
                       command=self._biess_actualizar_obs).pack(side=tk.LEFT, padx=6)
        tk.Radiobutton(tipo_row, text="207 - Hipotecario", variable=self.biess_tipo_var,
                       value="207", bg=COL_BG, font=('Segoe UI', 9),
                       command=self._biess_actualizar_obs).pack(side=tk.LEFT, padx=6)

        fecha_row = tk.Frame(cfg_frame, bg=COL_BG)
        fecha_row.pack(fill=tk.X, pady=3)
        tk.Label(fecha_row, text="Fecha:", bg=COL_BG, font=('Segoe UI', 9),
                 width=11, anchor='w').pack(side=tk.LEFT)
        self.biess_fecha_var = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        ttk.Entry(fecha_row, textvariable=self.biess_fecha_var, width=14).pack(side=tk.LEFT, padx=2)
        self.biess_fecha_var.trace_add("write", lambda *a: self.master.after(300, self._biess_actualizar_obs))

        obs_row = tk.Frame(cfg_frame, bg=COL_BG)
        obs_row.pack(fill=tk.X, pady=3)
        tk.Label(obs_row, text="Observación:", bg=COL_BG, font=('Segoe UI', 9),
                 width=11, anchor='w').pack(side=tk.LEFT)
        self.biess_obs_var = tk.StringVar()
        ttk.Entry(obs_row, textvariable=self.biess_obs_var, width=52).pack(
            side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        # Excel params frame
        xls_frame = tk.LabelFrame(top, text="Parámetros Excel", bg=COL_BG, fg=COL_HEADER,
                                  font=('Segoe UI', 9, 'bold'), padx=8, pady=6)
        xls_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(4, 0))

        for lbl, attr, default in [
            ("Fila inicio:", 'biess_fila_var', "18"),
            ("Col. cédula:", 'biess_col_ced_var', "E"),
            ("Col. valor:",  'biess_col_val_var', "AA"),
        ]:
            r = tk.Frame(xls_frame, bg=COL_BG); r.pack(fill=tk.X, pady=3)
            tk.Label(r, text=lbl, bg=COL_BG, font=('Segoe UI', 9), width=12, anchor='w').pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            setattr(self, attr, var)
            ttk.Entry(r, textvariable=var, width=6).pack(side=tk.LEFT)

        # ── Archivo ──────────────────────────────────────────────────
        arch_frame = tk.LabelFrame(main, text="Archivo Excel BIESS", bg=COL_BG, fg=COL_HEADER,
                                   font=('Segoe UI', 9, 'bold'), padx=8, pady=4)
        arch_frame.pack(fill=tk.X, pady=4)

        self.biess_archivo_lbl = tk.Label(arch_frame, text="Ningún archivo seleccionado",
                                           fg='gray', bg=COL_BG, font=('Segoe UI', 9), anchor='w')
        self.biess_archivo_lbl.pack(fill=tk.X, pady=2)

        btn_arch = tk.Frame(arch_frame, bg=COL_BG)
        btn_arch.pack(fill=tk.X, pady=(2, 0))
        for txt, cmd, col in [
            ("📂 Seleccionar", self._biess_seleccionar_archivo, COL_ACCENT),
            ("⚙ Procesar",    self._biess_procesar,            COL_HEADER),
            ("🔍 Diagnóstico", self._biess_diagnostico,         '#7B1FA2'),
        ]:
            tk.Button(btn_arch, text=txt, command=cmd, bg=col, fg=COL_WHITE,
                      font=('Segoe UI', 9, 'bold'), relief='flat', cursor='hand2',
                      padx=6).pack(side=tk.LEFT, padx=3)

        # ── Tabla de resultados ───────────────────────────────────────
        res_frame = tk.LabelFrame(main, text="Datos consolidados", bg=COL_BG, fg=COL_HEADER,
                                  font=('Segoe UI', 9, 'bold'))
        res_frame.pack(fill=tk.BOTH, expand=True, pady=2)

        cols_b = ("Cédula", "Código", "Nombre", "Valor", "Estado")
        self.biess_tree = ttk.Treeview(res_frame, columns=cols_b, show="headings", height=10)
        col_w = {"Cédula": 105, "Código": 70, "Nombre": 230, "Valor": 105, "Estado": 200}
        col_a = {"Cédula": tk.CENTER, "Código": tk.CENTER, "Nombre": tk.W, "Valor": tk.E, "Estado": tk.W}
        for c in cols_b:
            self.biess_tree.heading(c, text=c, anchor=tk.W)
            self.biess_tree.column(c, width=col_w[c], anchor=col_a[c])
        self.biess_tree.tag_configure('ok',          background='#E8F5E9')
        self.biess_tree.tag_configure('liq',         background='#FFF9C4')
        self.biess_tree.tag_configure('noencontrado',background='#FFEBEE')
        vsb_b = ttk.Scrollbar(res_frame, orient=tk.VERTICAL,   command=self.biess_tree.yview)
        hsb_b = ttk.Scrollbar(res_frame, orient=tk.HORIZONTAL, command=self.biess_tree.xview)
        self.biess_tree.configure(yscrollcommand=vsb_b.set, xscrollcommand=hsb_b.set)
        vsb_b.pack(side=tk.RIGHT, fill=tk.Y)
        hsb_b.pack(side=tk.BOTTOM, fill=tk.X)
        self.biess_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Acciones ─────────────────────────────────────────────────
        act = tk.Frame(main, bg=COL_BG)
        act.pack(fill=tk.X, pady=4)

        self.biess_btn_subir = tk.Button(
            act, text="  💾 Subir a Base de Datos  ",
            command=self._biess_subir,
            bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 10, 'bold'),
            relief='flat', cursor='hand2', state=tk.DISABLED)
        self.biess_btn_subir.pack(side=tk.LEFT, padx=4)
        tk.Button(act, text="  📊 Exportar Excel  ", command=self._biess_exportar,
                  bg='#7B1FA2', fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=4)
        tk.Button(act, text="  🗑 Limpiar  ", command=self._biess_limpiar,
                  bg='#78909C', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=4)

        self.biess_resumen_var = tk.StringVar(value="")
        tk.Label(act, textvariable=self.biess_resumen_var, bg=COL_BG,
                 fg=COL_HEADER, font=('Segoe UI', 9, 'bold')).pack(side=tk.RIGHT, padx=8)

        # ── Estado interno ───────────────────────────────────────────
        self.biess_datos = []
        self.biess_archivo_path = None
        self._biess_actualizar_obs()

    def _biess_actualizar_obs(self):
        try:
            tipo = self.biess_tipo_var.get()
            fecha_str = self.biess_fecha_var.get().strip()
            fecha_dt = None
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                try:
                    fecha_dt = datetime.strptime(fecha_str, fmt); break
                except Exception:
                    pass
            if fecha_dt is None:
                fecha_dt = datetime.now()
            meses = {1:"ENERO",2:"FEBRERO",3:"MARZO",4:"ABRIL",5:"MAYO",6:"JUNIO",
                     7:"JULIO",8:"AGOSTO",9:"SEPTIEMBRE",10:"OCTUBRE",11:"NOVIEMBRE",12:"DICIEMBRE"}
            mes = meses[fecha_dt.month]
            anio = fecha_dt.year
            if tipo == "204":
                obs = f"PRESTAMOS QUIROGRAFARIOS MES: {mes} {anio}"
            else:
                obs = f"PRESTAMOS HIPOTECARIOS MES: {mes} {anio}"
            self.biess_obs_var.set(obs)
        except Exception:
            pass

    def _biess_seleccionar_archivo(self):
        fn = filedialog.askopenfilename(
            title="Archivo Excel BIESS",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")]
        )
        if fn:
            self.biess_archivo_path = fn
            nombre = os.path.basename(fn)
            self.biess_archivo_lbl.config(text=nombre, fg=COL_OK)
            self._set_status(f"Archivo BIESS: {nombre}", COL_OK)

    def _biess_procesar(self):
        if not self.biess_archivo_path:
            messagebox.showwarning("Aviso", "Seleccione un archivo primero")
            return
        try:
            fila = int(self.biess_fila_var.get())
        except Exception:
            fila = 18
        col_ced = self.biess_col_ced_var.get().strip() or "E"
        col_val = self.biess_col_val_var.get().strip() or "AA"
        archivo  = self.biess_archivo_path

        self._set_status("Procesando Excel BIESS...", COL_PEND)
        self.biess_btn_subir.config(state=tk.DISABLED)

        def bg():
            try:
                consolidado, descartados = biess_procesar_excel(archivo, fila, col_ced, col_val)
                if not consolidado:
                    self.master.after(0, lambda: self._set_status(
                        "Sin datos válidos. Verifique fila/columnas.", COL_DANGER))
                    self.master.after(0, lambda: messagebox.showwarning(
                        "Sin datos",
                        "No se encontraron datos válidos.\n"
                        "Use 🔍 Diagnóstico para verificar fila de inicio y columnas."))
                    return

                conn2, err = conectar_bd()
                if err:
                    self.master.after(0, lambda: self._set_status(f"Error de conexión: {err}", COL_DANGER))
                    return
                try:
                    emp_dict = biess_buscar_por_cedulas(conn2, set(consolidado.keys()))
                finally:
                    conn2.close()

                # Redistribucion de cedula especial (cedula excluida → empleado destino)
                CEDULAS_EXCLUIDAS = {"0704948983", "7049489830", "704948983"}
                DESTINOS_CEDULA   = ["1204563686", "1306343961", "1205800640"]
                cedula_excluida = next((c for c in CEDULAS_EXCLUIDAS if c in consolidado), None)
                if cedula_excluida:
                    valor_redir = consolidado.pop(cedula_excluida)
                    emp_dict.pop(cedula_excluida, None)
                    for dest in DESTINOS_CEDULA:
                        if dest in emp_dict and emp_dict[dest].get('estado_biess') in ('activo', 'liquidado'):
                            consolidado[dest] = round(consolidado.get(dest, 0.0) + valor_redir, 2)
                            break

                # Construir lista de datos
                datos = []
                for ced, valor in consolidado.items():
                    emp = emp_dict.get(ced, {})
                    eb  = emp.get('estado_biess', 'no_encontrado')
                    if eb == 'activo':
                        estado_txt = 'Listo para subir'
                    elif eb == 'liquidado':
                        estado_txt = 'LIQUIDADO — no procesar'
                    else:
                        estado_txt = 'No encontrado en BD'
                    datos.append({
                        'cedula':      ced,
                        'codigo':      emp.get('codigo', ''),
                        'nombre':      emp.get('nombre', ''),
                        'valor':       valor,
                        'estado':      estado_txt,
                        'estado_biess': eb,
                    })
                datos.sort(key=lambda x: x['nombre'].upper() if x['nombre'] else 'ZZZZZ')
                self.master.after(0, lambda d=datos, ds=descartados: self._biess_procesar_fin(d, ds))
            except Exception as ex:
                msg = str(ex)
                self.master.after(0, lambda: self._set_status(f"Error: {msg}", COL_DANGER))
                self.master.after(0, lambda: messagebox.showerror("Error al procesar", msg))

        threading.Thread(target=bg, daemon=True).start()

    def _biess_procesar_fin(self, datos, descartados):
        if not self._running:
            return
        self.biess_datos = datos
        self._biess_actualizar_tabla()
        activos  = sum(1 for d in datos if d['estado_biess'] == 'activo')
        liquidados = sum(1 for d in datos if d['estado_biess'] == 'liquidado')
        no_enc   = sum(1 for d in datos if d['estado_biess'] == 'no_encontrado')
        total_val = sum(d['valor'] for d in datos if d['estado_biess'] == 'activo')
        self.biess_resumen_var.set(
            f"Activos: {activos}   Liq: {liquidados}   No enc: {no_enc}   Total: ${total_val:,.2f}")
        self._set_status(
            f"Excel procesado — {len(datos)} registros ({descartados} descartados)", COL_OK)
        if activos > 0:
            self.biess_btn_subir.config(state=tk.NORMAL)
        else:
            messagebox.showwarning("Sin activos",
                                   "No hay empleados activos para subir.\n"
                                   "Revise el log de estados en la tabla.")

    def _biess_actualizar_tabla(self):
        for item in self.biess_tree.get_children():
            self.biess_tree.delete(item)
        for d in self.biess_datos:
            eb = d.get('estado_biess', '')
            tag = 'ok' if eb == 'activo' else ('liq' if eb == 'liquidado' else 'noencontrado')
            self.biess_tree.insert("", tk.END, values=(
                d['cedula'], d['codigo'], d['nombre'],
                f"${d['valor']:,.2f}", d['estado']
            ), tags=(tag,))

    def _biess_subir(self):
        if not self.biess_datos:
            messagebox.showwarning("Aviso", "No hay datos para subir")
            return
        if not self.conn:
            messagebox.showerror("Error", "Sin conexión al sistema")
            return
        obs = self.biess_obs_var.get().strip()
        if not obs:
            messagebox.showerror("Error", "La observación es obligatoria")
            return
        datos_validos = [d for d in self.biess_datos if d['estado_biess'] == 'activo']
        if not datos_validos:
            messagebox.showwarning("Aviso", "No hay empleados activos para subir")
            return

        tipo     = self.biess_tipo_var.get()
        cfg      = CLASES_SIMPLIFICADAS.get(tipo)
        fecha_str = self.biess_fecha_var.get().strip()
        fecha_dt  = None
        for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
            try:
                fecha_dt = datetime.strptime(fecha_str, fmt); break
            except Exception:
                pass
        if fecha_dt is None:
            fecha_dt = datetime.now()

        total_val = sum(d['valor'] for d in datos_validos)

        # Armar filas para el dialogo de confirmacion
        filas_dlg = []
        for i, d in enumerate(datos_validos, 1):
            filas_dlg.append((i, d['cedula'], d['codigo'], d['nombre'], f"${d['valor']:,.2f}"))

        desc = (f"Tipo: {cfg['concepto']}\n"
                f"Fecha: {fecha_dt.strftime('%d/%m/%Y')}   Observación: {obs[:70]}\n"
                f"Empleados activos: {len(datos_validos)}   Total: ${total_val:,.2f}\n"
                f"Todos recibirán el MISMO número de egreso (modo agrupado BIESS).")

        def proceder():
            self.biess_btn_subir.config(state=tk.DISABLED)
            self._set_status("Registrando...", COL_PEND)

            def bg():
                conn2, err = conectar_bd()
                if err:
                    self.master.after(0, lambda: self._set_status(f"Error de conexión: {err}", COL_DANGER))
                    self.master.after(0, lambda: messagebox.showerror("Error de conexión", err))
                    return
                try:
                    numero, err_num = obtener_proximo_numero_tipo(conn2, cfg['tipo'])
                    if err_num:
                        self.master.after(0, lambda: self._set_status(f"Error número: {err_num}", COL_DANGER))
                        self.master.after(0, lambda: messagebox.showerror("Error", err_num))
                        return

                    procesados = 0
                    errores    = 0
                    for d in datos_validos:
                        exito, msg = insertar_movimiento_tipo(
                            conn2, d['codigo'], numero, fecha_dt, obs, d['valor'], tipo, 1
                        )
                        if exito:
                            procesados += 1
                            d['estado']      = f'Subido #{numero}'
                            d['estado_biess'] = 'subido'
                        else:
                            errores += 1
                            d['estado'] = f'Error: {msg}'

                    if procesados > 0:
                        ok2, err_upd = actualizar_ultimo_numero_tipo(conn2, numero, cfg['tipo'])
                        if ok2:
                            conn2.commit()
                            if SEGURIDAD_DISPONIBLE:
                                log_operacion('INSERT', 'BIESS', numero,
                                              f"{cfg['concepto']} ${total_val:.2f}, {procesados} emp")
                        else:
                            conn2.rollback()
                            self.master.after(0, lambda: self._set_status(
                                "Error actualizando contador — operación revertida", COL_DANGER))
                            self.master.after(0, lambda: messagebox.showerror(
                                "Error", f"No se pudo actualizar el contador: {err_upd}"))
                            return
                    else:
                        conn2.rollback()

                    num_final = numero
                    self.master.after(0, lambda p=procesados, e=errores, n=num_final:
                                       self._biess_subir_fin(p, e, n))
                except Exception as ex:
                    try: conn2.rollback()
                    except Exception: pass
                    err_str = str(ex)
                    self.master.after(0, lambda: self._set_status(f"Error: {err_str}", COL_DANGER))
                    self.master.after(0, lambda: messagebox.showerror("Error", err_str))
                finally:
                    conn2.close()

            threading.Thread(target=bg, daemon=True).start()

        self._dialogo_confirmar(
            f"Confirmar BIESS — {cfg['concepto']}",
            desc,
            [("#", 40), ("Cédula", 105), ("Código", 70), ("Nombre", 210), ("Valor", 105)],
            filas_dlg,
            proceder
        )

    def _biess_subir_fin(self, procesados, errores, numero):
        if not self._running:
            return
        self._biess_actualizar_tabla()
        self.biess_btn_subir.config(state=tk.DISABLED)
        color = COL_OK if errores == 0 else COL_PEND
        self._set_status(f"BIESS #{numero}: {procesados} subidos, {errores} errores", color)
        messagebox.showinfo("Resultado BIESS",
                            f"Número de egreso: #{numero}\n"
                            f"✓ Procesados: {procesados}\n"
                            f"✗ Errores: {errores}")

    def _biess_exportar(self):
        if not self.biess_datos:
            messagebox.showwarning("Aviso", "No hay datos para exportar")
            return
        fn = filedialog.asksaveasfilename(
            title="Exportar datos BIESS",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")]
        )
        if fn:
            try:
                df_exp = pd.DataFrame([{
                    'Cedula': d['cedula'], 'Codigo': d['codigo'],
                    'Nombre': d['nombre'], 'Valor': d['valor'], 'Estado': d['estado']
                } for d in self.biess_datos])
                df_exp.to_excel(fn, index=False)
                messagebox.showinfo("Exportado", f"Guardado en:\n{fn}")
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

    def _biess_limpiar(self):
        if not self.biess_datos:
            return
        if messagebox.askyesno("Confirmar", "¿Limpiar todos los datos BIESS?"):
            self.biess_datos = []
            self._biess_actualizar_tabla()
            self.biess_btn_subir.config(state=tk.DISABLED)
            self.biess_resumen_var.set("")
            self._set_status("Datos BIESS limpiados", COL_OK)

    def _biess_diagnostico(self):
        if not self.biess_archivo_path:
            messagebox.showwarning("Aviso", "Seleccione un archivo primero")
            return
        try:
            fila = int(self.biess_fila_var.get())
        except Exception:
            fila = 18
        col_ced = self.biess_col_ced_var.get().strip() or "E"
        col_val = self.biess_col_val_var.get().strip() or "AA"
        try:
            col_ced_idx = biess_col_a_indice(col_ced)
            col_val_idx = biess_col_a_indice(col_val)
            df = pd.read_excel(self.biess_archivo_path, header=None)

            dlg = tk.Toplevel(self.master)
            dlg.title("Diagnóstico Excel BIESS")
            dlg.geometry("750x430")
            dlg.transient(self.master)
            dlg.configure(bg=COL_BG)
            try:
                dlg.wait_visibility(); dlg.grab_set()
            except Exception:
                dlg.focus_set()

            dhdr = tk.Frame(dlg, bg=COL_HEADER, height=36)
            dhdr.pack(fill=tk.X); dhdr.pack_propagate(False)
            tk.Label(dhdr, text="  \U0001f50d  Diagnóstico Excel BIESS", bg=COL_HEADER, fg=COL_WHITE,
                     font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

            t = scrolledtext.ScrolledText(dlg, wrap=tk.WORD, font=("Consolas", 9), bg='#F8F9FA')
            t.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

            t.insert(tk.END, f"Archivo : {os.path.basename(self.biess_archivo_path)}\n")
            t.insert(tk.END, f"Filas   : {len(df)}  |  Columnas totales: {len(df.columns)}\n")
            t.insert(tk.END, f"Config  : fila inicio={fila}  col_cedula={col_ced}(idx {col_ced_idx})"
                             f"  col_valor={col_val}(idx {col_val_idx})\n")
            t.insert(tk.END, "─" * 72 + "\n")
            t.insert(tk.END, f"{'Fila':>5}  {'Cédula raw':<22}  {'Limpia':>12}  {'Valor raw':<18}  Valor $\n")
            t.insert(tk.END, "─" * 72 + "\n")

            for idx in range(max(0, fila - 1), min(len(df), fila + 24)):
                try:
                    c_raw = df.iloc[idx, col_ced_idx]
                    v_raw = df.iloc[idx, col_val_idx]
                    if pd.isna(c_raw) and pd.isna(v_raw):
                        continue
                    c_limpia = biess_limpiar_cedula(c_raw) or "—"
                    try:
                        v_str = str(v_raw).replace('$','').replace(',','').strip()
                        v_fmt = f"${float(v_str):,.2f}"
                    except Exception:
                        v_fmt = str(v_raw)
                    t.insert(tk.END,
                             f"{idx+1:>5}  {str(c_raw):<22}  {c_limpia:>12}  {str(v_raw):<18}  {v_fmt}\n")
                except Exception:
                    pass

            t.insert(tk.END, f"\n→ mostrando hasta 25 filas desde fila {fila}\n")
            t.config(state=tk.DISABLED)

            tk.Button(dlg, text="  Cerrar  ", command=dlg.destroy,
                      bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                      relief='flat', cursor='hand2').pack(pady=6)
        except Exception as ex:
            messagebox.showerror("Error en diagnóstico", str(ex))

    # ===================================================================
    # TAB CONSULTA / EDICIÓN
    # ===================================================================

    def _build_consulta_tab(self):
        parent = self.tab_consulta
        self.cq_rows = {}   # iid → dict con campos clave del registro

        main = ttk.Frame(parent, padding=6)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Header ───────────────────────────────────────────────────
        hdr = tk.Frame(main, bg='#388E3C', height=40)
        hdr.pack(fill=tk.X, pady=(0, 6))
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  \U0001f50d  Consulta y Edición de Registros",
                 bg='#388E3C', fg=COL_WHITE,
                 font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        # ── Filtros ───────────────────────────────────────────────────
        fil = tk.LabelFrame(main, text="Filtros de búsqueda", bg=COL_BG, fg='#388E3C',
                            font=('Segoe UI', 9, 'bold'), padx=8, pady=6)
        fil.pack(fill=tk.X, pady=(0, 4))

        # Fila 1
        r1 = tk.Frame(fil, bg=COL_BG)
        r1.pack(fill=tk.X, pady=3)

        tk.Label(r1, text="Empleado:", bg=COL_BG, font=('Segoe UI', 9), width=10, anchor='w').pack(side=tk.LEFT)
        self.cq_emp_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.cq_emp_var, width=22, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=2, ipady=2)
        tk.Button(r1, text="Buscar...", command=self._consulta_buscar_empleado_dlg,
                  bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 8), relief='flat',
                  cursor='hand2').pack(side=tk.LEFT, padx=4)

        tk.Label(r1, text="Clase:", bg=COL_BG, font=('Segoe UI', 9), width=6, anchor='w').pack(side=tk.LEFT, padx=(12, 0))
        self.cq_clase_var = tk.StringVar(value="(Todas)")
        clases_opciones = [
            "(Todas)",
            "205 - Préstamos Compañía",
            "202 - Anticipo de Sueldo",
            "203 - Multas",
            "204 - Préstamos Quirografarios",
            "206 - Pensión Alimenticia",
            "207 - Préstamo Hipotecario",
            "217 - Anticipos Otros",
            "218 - Aport. IESS Cónyuge",
            "219 - Impuesto a la Renta",
            "250 - Anticipos Surtidos",
            "102 - Bonificación Otros Ingresos",
            "110 - Maniobras",
            "111 - Reembolsos",
            "120 - Movilización",
        ]
        ttk.Combobox(r1, textvariable=self.cq_clase_var, values=clases_opciones,
                     width=30, state='readonly').pack(side=tk.LEFT, padx=2)

        self.cq_pendientes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r1, text="Solo no procesados",
                        variable=self.cq_pendientes_var).pack(side=tk.LEFT, padx=(16, 0))

        # Fila 2
        r2 = tk.Frame(fil, bg=COL_BG)
        r2.pack(fill=tk.X, pady=3)

        tk.Label(r2, text="Fecha desde:", bg=COL_BG, font=('Segoe UI', 9), width=10, anchor='w').pack(side=tk.LEFT)
        self.cq_fecha_desde_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.cq_fecha_desde_var, width=13).pack(side=tk.LEFT, padx=2)
        tk.Label(r2, text="hasta:", bg=COL_BG, font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(6, 0))
        self.cq_fecha_hasta_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.cq_fecha_hasta_var, width=13).pack(side=tk.LEFT, padx=2)

        tk.Label(r2, text="N° Egreso:", bg=COL_BG, font=('Segoe UI', 9), width=9, anchor='w').pack(side=tk.LEFT, padx=(16, 0))
        self.cq_numero_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.cq_numero_var, width=12).pack(side=tk.LEFT, padx=2)

        tk.Button(r2, text="  Buscar  ", command=self._consulta_buscar,
                  bg='#388E3C', fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=(16, 4))
        tk.Button(r2, text="  Limpiar  ", command=self._consulta_limpiar_filtros,
                  bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=2)

        tk.Label(r2, text="(Formato fecha: dd/mm/yyyy)", bg=COL_BG,
                 fg='gray', font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=10)

        # ── Tabla de resultados ───────────────────────────────────────
        tf = ttk.Frame(main)
        tf.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        cols_def = [
            ("N°",        80),
            ("Emp",       65),
            ("Nombre",   200),
            ("Clase",     55),
            ("Concepto", 175),
            ("Observ",   140),
            ("Seq",       42),
            ("Vence",     98),
            ("Valor",     90),
            ("Estado",    75),
        ]
        col_names = [c[0] for c in cols_def]
        self.cq_tree = ttk.Treeview(tf, columns=col_names, show="headings",
                                    selectmode="browse")
        for nombre, ancho in cols_def:
            anchor = tk.E if nombre in ("Valor", "N°", "Emp", "Seq") else tk.W
            self.cq_tree.heading(nombre, text=nombre, anchor=tk.W,
                                 command=lambda c=nombre: self._consulta_sort(c))
            self.cq_tree.column(nombre, width=ancho, anchor=anchor, stretch=(nombre == "Nombre"))

        vsb = ttk.Scrollbar(tf, orient=tk.VERTICAL,   command=self.cq_tree.yview)
        hsb = ttk.Scrollbar(tf, orient=tk.HORIZONTAL, command=self.cq_tree.xview)
        self.cq_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.cq_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tf.grid_rowconfigure(0, weight=1)
        tf.grid_columnconfigure(0, weight=1)

        self.cq_tree.tag_configure('par',      background='#F0F4F8')
        self.cq_tree.tag_configure('impar',    background=COL_WHITE)
        self.cq_tree.tag_configure('asentado', background='#E8F5E9', foreground='#2E7D32')
        self.cq_tree.tag_configure('egr',      foreground='#B71C1C')
        self.cq_tree.tag_configure('ing',      foreground='#1A237E')

        self.cq_tree.bind('<<TreeviewSelect>>', self._consulta_on_select)
        self.cq_tree.bind('<Double-1>', self._consulta_editar_valor)

        # ── Barra de acciones ─────────────────────────────────────────
        bot = tk.Frame(main, bg=COL_BG)
        bot.pack(fill=tk.X)

        self.cq_btn_edit = tk.Button(bot, text="  Editar Valor  ",
                                     command=self._consulta_editar_valor,
                                     bg=COL_PEND, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                                     relief='flat', cursor='hand2', state=tk.DISABLED)
        self.cq_btn_edit.pack(side=tk.LEFT, padx=4)

        self.cq_btn_del = tk.Button(bot, text="  Eliminar Fila  ",
                                    command=self._consulta_eliminar,
                                    bg=COL_DANGER, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                                    relief='flat', cursor='hand2', state=tk.DISABLED)
        self.cq_btn_del.pack(side=tk.LEFT, padx=4)

        tk.Button(bot, text="  Exportar CSV  ", command=self._consulta_exportar_csv,
                  bg='#455A64', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=4)

        self.cq_info_var = tk.StringVar(value="0 registros")
        tk.Label(bot, textvariable=self.cq_info_var, bg=COL_BG,
                 fg='gray', font=('Segoe UI', 9)).pack(side=tk.RIGHT, padx=12)

        # ── Orden columnas (estado para toggle asc/desc) ──────────────
        self._cq_sort_col  = None
        self._cq_sort_desc = False

    def _consulta_limpiar_filtros(self):
        for v in (self.cq_emp_var, self.cq_fecha_desde_var,
                  self.cq_fecha_hasta_var, self.cq_numero_var):
            v.set("")
        self.cq_clase_var.set("(Todas)")
        self.cq_pendientes_var.set(False)

    def _consulta_on_select(self, event=None):
        sel = self.cq_tree.selection()
        state = tk.NORMAL if sel else tk.DISABLED
        self.cq_btn_edit.config(state=state)
        self.cq_btn_del.config(state=state)

    def _consulta_sort(self, col):
        if self._cq_sort_col == col:
            self._cq_sort_desc = not self._cq_sort_desc
        else:
            self._cq_sort_col  = col
            self._cq_sort_desc = False
        items = [(self.cq_tree.set(iid, col), iid) for iid in self.cq_tree.get_children()]
        try:
            items.sort(key=lambda x: float(x[0].replace('$','').replace(',',''))
                       if x[0].replace('$','').replace(',','').replace('.','',1).lstrip('-').isdigit()
                       else x[0].lower(),
                       reverse=self._cq_sort_desc)
        except Exception:
            items.sort(key=lambda x: x[0].lower(), reverse=self._cq_sort_desc)
        for idx, (_, iid) in enumerate(items):
            self.cq_tree.move(iid, '', idx)
            tag = 'par' if idx % 2 == 0 else 'impar'
            self.cq_tree.item(iid, tags=(tag,))

    def _consulta_buscar_empleado_dlg(self):
        w, h = 600, 440
        dlg = tk.Toplevel(self.master)
        dlg.title("Buscar Empleado")
        dlg.geometry(f"{w}x{h}")
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        dlg.resizable(True, True)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width()  - w) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - h) // 2
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        try:
            dlg.wait_visibility(); dlg.grab_set()
        except Exception:
            dlg.focus_set()

        hdr2 = tk.Frame(dlg, bg=COL_HEADER, height=36)
        hdr2.pack(fill=tk.X); hdr2.pack_propagate(False)
        tk.Label(hdr2, text="  Buscar Empleado", bg=COL_HEADER, fg=COL_WHITE,
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        sf = tk.Frame(dlg, bg=COL_BG)
        sf.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(sf, text="Filtro:", bg=COL_BG, font=('Segoe UI', 9)).pack(side=tk.LEFT)
        filtro_var = tk.StringVar()
        ttk.Entry(sf, textvariable=filtro_var, width=40).pack(side=tk.LEFT, padx=8, ipady=3)

        tree2 = ttk.Treeview(dlg, columns=("ID","Apellidos","Nombres","Depto"),
                              show="headings", height=14)
        for col2, w2 in [("ID",65),("Apellidos",200),("Nombres",200),("Depto",65)]:
            tree2.heading(col2, text=col2); tree2.column(col2, width=w2)
        tree2.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        def buscar2():
            f = filtro_var.get().strip()
            def bg2():
                c2, err2 = conectar_bd()
                if err2: return
                try:
                    rows2, _ = buscar_empleados(c2, f, 300)
                    self.master.after(0, lambda r=rows2: _mostrar2(r))
                finally:
                    c2.close()
            threading.Thread(target=bg2, daemon=True).start()

        def _mostrar2(rows2):
            for i in tree2.get_children(): tree2.delete(i)
            for idx, r in enumerate(rows2):
                tag = 'par' if idx % 2 == 0 else 'impar'
                tree2.insert("", tk.END,
                             values=(r['id'], r['apellidos'], r['nombres'], r['depto']),
                             tags=(tag,))

        def seleccionar2():
            sel2 = tree2.selection()
            if sel2:
                vals2 = tree2.item(sel2[0], 'values')
                self.cq_emp_var.set(str(vals2[0]))
                dlg.destroy()

        tree2.bind("<Double-1>", lambda e: seleccionar2())

        bf2 = tk.Frame(dlg, bg=COL_BG)
        bf2.pack(fill=tk.X, padx=10, pady=6)
        tk.Button(bf2, text="  Buscar  ", command=buscar2,
                  bg=COL_ACCENT, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf2, text="  Seleccionar  ", command=seleccionar2,
                  bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf2, text="  Cerrar  ", command=dlg.destroy,
                  bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.RIGHT, padx=3)

        filtro_var.trace_add("write", lambda *a: self.master.after(500, buscar2))
        buscar2()

    def _consulta_buscar(self):
        emp    = self.cq_emp_var.get().strip()
        clase  = self.cq_clase_var.get()
        fdesde = self.cq_fecha_desde_var.get().strip()
        fhasta = self.cq_fecha_hasta_var.get().strip()
        numero = self.cq_numero_var.get().strip()
        solo_pend = self.cq_pendientes_var.get()

        self._set_status("Consultando registros...", COL_ACCENT)
        self.cq_info_var.set("Buscando...")

        def _thread():
            conn2, err = conectar_bd()
            if err:
                self.master.after(0, lambda: self._set_status(f"Error de conexión: {err}", COL_DANGER))
                self.master.after(0, lambda: self.cq_info_var.set("Error de conexión"))
                return
            try:
                params = []
                where  = []

                if emp:
                    if emp.isdigit():
                        where.append("r.EMPLEADO = ?")
                        params.append(int(emp))
                    else:
                        where.append("(e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ?)")
                        like = f"%{emp}%"
                        params += [like, like]

                if clase and not clase.startswith("(Todas)"):
                    clase_code = clase.split(" - ")[0].strip()
                    where.append("r.CLASE = ?")
                    params.append(clase_code)

                if solo_pend:
                    where.append("r.ASENTADO = 0")

                if fdesde:
                    try:
                        fd = datetime.strptime(fdesde, "%d/%m/%Y")
                        where.append("r.FECHA_VEN >= ?")
                        params.append(fd)
                    except Exception:
                        pass

                if fhasta:
                    try:
                        fh = datetime.strptime(fhasta, "%d/%m/%Y")
                        where.append("r.FECHA_VEN <= ?")
                        params.append(fh)
                    except Exception:
                        pass

                if numero and numero.isdigit():
                    where.append("r.NUMERO = ?")
                    params.append(int(numero))

                w_clause = "WHERE " + " AND ".join(where) if where else ""

                sql = f"""
                    SELECT TOP 3000
                        r.NUMERO, r.EMPLEADO, r.SECUENCIA, r.CLASE,
                        r.FECHA, r.FECHA_VEN, r.VALOR,
                        r.OBSERV, r.CONCEPTO, r.ASENTADO,
                        e.APELLIDOS, e.NOMBRES
                    FROM RPINGDES r WITH (NOLOCK)
                    LEFT JOIN RPEMPLEA e WITH (NOLOCK) ON r.EMPLEADO = e.EMPLEADO
                    {w_clause}
                    ORDER BY r.FECHA_VEN DESC, r.NUMERO DESC, r.SECUENCIA
                """
                cursor = conn2.cursor()
                cursor.execute(sql, params)
                filas = cursor.fetchall()
                self.master.after(0, lambda f=filas: self._consulta_mostrar(f))
            except Exception as ex:
                err_msg = str(ex)
                self.master.after(0, lambda m=err_msg: self._set_status(f"Error: {m}", COL_DANGER))
                self.master.after(0, lambda: self.cq_info_var.set("Error en consulta"))
            finally:
                conn2.close()

        threading.Thread(target=_thread, daemon=True).start()

    def _consulta_mostrar(self, filas):
        for iid in self.cq_tree.get_children():
            self.cq_tree.delete(iid)
        self.cq_rows.clear()
        self.cq_btn_edit.config(state=tk.DISABLED)
        self.cq_btn_del.config(state=tk.DISABLED)

        for idx, r in enumerate(filas):
            numero, empleado, seq, clase, fecha, fecha_ven, valor, observ, concepto, asentado, ape, nom = r

            nombre = f"{str(ape or '').strip()} {str(nom or '').strip()}".strip() or f"Emp #{empleado}"

            fv_str = fecha_ven.strftime('%d/%m/%Y') if fecha_ven else ''
            val_str = f"${float(valor or 0):,.2f}"
            estado = "Procesado" if asentado else "Pendiente"
            concepto_str = str(concepto or '').strip()
            observ_str   = str(observ   or '').strip()

            tag = 'asentado' if asentado else ('par' if idx % 2 == 0 else 'impar')

            iid = self.cq_tree.insert("", tk.END, tags=(tag,),
                values=(numero, empleado, nombre, clase,
                        concepto_str, observ_str, seq,
                        fv_str, val_str, estado))

            self.cq_rows[iid] = {
                'NUMERO':    numero,
                'EMPLEADO':  empleado,
                'SECUENCIA': seq,
                'CLASE':     clase,
                'FECHA_VEN': fecha_ven,
                'VALOR':     float(valor or 0),
                'ASENTADO':  asentado,
            }

        total = len(filas)
        aviso = " (máx 3000)" if total == 3000 else ""
        self.cq_info_var.set(f"{total:,} registros{aviso}")
        self._set_status(f"Consulta: {total:,} registros encontrados", COL_OK)

    def _consulta_editar_valor(self, event=None):
        sel = self.cq_tree.selection()
        if not sel:
            return
        iid  = sel[0]
        fila = self.cq_rows.get(iid)
        if not fila:
            return

        if fila['ASENTADO']:
            messagebox.showwarning("Registro procesado",
                "Este registro ya fue procesado y no se puede modificar.")
            return

        if not SEGURIDAD_DISPONIBLE:
            messagebox.showerror("Seguridad requerida",
                "El módulo de seguridad no está disponible.")
            return

        # Préstamos CLASE 205: mostrar todas las cuotas juntas
        if fila['CLASE'] == '205':
            r_hist = {
                'numero':   fila['NUMERO'],
                'clase':    '205',
                'empleado': fila['EMPLEADO'],
                'nombre':   self.cq_tree.set(iid, 'Nombre'),
                'valor':    fila['VALOR'],
                'cuotas':   1,
                'concepto': '',
                'fecha':    '',
            }
            self._tt_hist_dlg_prestamo(r_hist)
            return

        # Diálogo de edición
        dlg = tk.Toplevel(self.master)
        dlg.title("Editar Valor")
        dlg.geometry("420x250")
        dlg.transient(self.master)
        dlg.configure(bg=COL_BG)
        dlg.resizable(False, False)
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width()  - 420) // 2
        y = self.master.winfo_y() + (self.master.winfo_height() - 250) // 2
        dlg.geometry(f"420x250+{x}+{y}")
        try:
            dlg.wait_visibility(); dlg.grab_set()
        except Exception:
            dlg.focus_set()

        hdr2 = tk.Frame(dlg, bg=COL_PEND, height=36)
        hdr2.pack(fill=tk.X); hdr2.pack_propagate(False)
        tk.Label(hdr2, text="  Editar Valor del Registro", bg=COL_PEND, fg=COL_WHITE,
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=8)

        inf = tk.Frame(dlg, bg=COL_BG, padx=16, pady=10)
        inf.pack(fill=tk.X)
        tk.Label(inf, text=f"Empleado: {fila['EMPLEADO']}  |  N°: {fila['NUMERO']}  "
                           f"|  Clase: {fila['CLASE']}  |  Seq: {fila['SECUENCIA']}",
                 bg=COL_BG, font=('Segoe UI', 9)).pack(anchor='w')
        if fila['FECHA_VEN']:
            tk.Label(inf, text=f"Fecha venc.: {fila['FECHA_VEN'].strftime('%d/%m/%Y')}",
                     bg=COL_BG, font=('Segoe UI', 9)).pack(anchor='w')

        vf = tk.Frame(dlg, bg=COL_BG, padx=16)
        vf.pack(fill=tk.X)
        tk.Label(vf, text=f"Valor actual: ${fila['VALOR']:,.2f}",
                 bg=COL_BG, font=('Segoe UI', 9), fg='gray').pack(anchor='w', pady=(0, 4))
        tk.Label(vf, text="Nuevo valor ($):", bg=COL_BG, font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        nuevo_var = tk.StringVar(value=f"{fila['VALOR']:.2f}")
        entry_nuevo = ttk.Entry(vf, textvariable=nuevo_var, font=('Segoe UI', 11), width=18)
        entry_nuevo.pack(anchor='w', ipady=4, pady=4)
        entry_nuevo.focus_set()
        entry_nuevo.select_range(0, tk.END)

        def _aplicar():
            try:
                nuevo_val = float(nuevo_var.get().replace(',', '.'))
            except Exception:
                messagebox.showerror("Valor inválido", "Ingrese un número válido.", parent=dlg)
                return
            if nuevo_val <= 0:
                messagebox.showerror("Valor inválido", "El valor debe ser mayor que 0.", parent=dlg)
                return
            dlg.destroy()
            self._consulta_aplicar_edicion(fila, nuevo_val)

        bf2 = tk.Frame(dlg, bg=COL_BG, pady=10)
        bf2.pack(fill=tk.X, padx=16)
        tk.Button(bf2, text="  Guardar  ", command=_aplicar,
                  bg=COL_OK, fg=COL_WHITE, font=('Segoe UI', 9, 'bold'),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)
        tk.Button(bf2, text="  Cancelar  ", command=dlg.destroy,
                  bg='#7F8C8D', fg=COL_WHITE, font=('Segoe UI', 9),
                  relief='flat', cursor='hand2').pack(side=tk.LEFT, padx=3)

        dlg.bind('<Return>', lambda e: _aplicar())
        dlg.bind('<Escape>', lambda e: dlg.destroy())

    def _consulta_aplicar_edicion(self, fila, nuevo_valor):
        self._set_status("Guardando cambio...", COL_ACCENT)

        def _thread():
            conn2, err = conectar_bd()
            if err:
                self.master.after(0, lambda: messagebox.showerror("Error de conexión", err))
                return
            conn2.autocommit = False
            try:
                exito, archivo, _ = crear_respaldo_prestamo(
                    conn2, fila['EMPLEADO'], fila['NUMERO'],
                    f"Edicion valor {fila['VALOR']} → {nuevo_valor}"
                )
                if not exito:
                    self.master.after(0, lambda: messagebox.showerror(
                        "Error respaldo", "No se pudo crear el respaldo. Operación cancelada."))
                    return

                cursor = conn2.cursor()
                cursor.execute("""
                    UPDATE RPINGDES
                    SET VALOR = ?
                    WHERE EMPLEADO = ? AND NUMERO = ? AND CLASE = ?
                      AND FECHA_VEN = ? AND SECUENCIA = ?
                """, (nuevo_valor, fila['EMPLEADO'], fila['NUMERO'],
                      fila['CLASE'], fila['FECHA_VEN'], fila['SECUENCIA']))
                filas_afectadas = cursor.rowcount
                conn2.commit()

                log_operacion("EDITAR_VALOR", fila['EMPLEADO'], fila['NUMERO'],
                              f"Valor {fila['VALOR']} → {nuevo_valor}  "
                              f"(clase={fila['CLASE']} seq={fila['SECUENCIA']})",
                              exito=True)

                self.master.after(0, lambda: self._set_status(
                    f"Valor actualizado: ${nuevo_valor:,.2f}  ({filas_afectadas} fila/s)", COL_OK))
                self.master.after(0, self._consulta_buscar)
            except Exception as ex:
                conn2.rollback()
                log_operacion("EDITAR_VALOR", fila['EMPLEADO'], fila['NUMERO'],
                              str(ex), exito=False)
                err_msg = str(ex)
                self.master.after(0, lambda m=err_msg: messagebox.showerror("Error", m))
                self.master.after(0, lambda: self._set_status("Error al editar valor", COL_DANGER))
            finally:
                conn2.close()

        threading.Thread(target=_thread, daemon=True).start()

    def _consulta_eliminar(self):
        sel = self.cq_tree.selection()
        if not sel:
            return
        iid  = sel[0]
        fila = self.cq_rows.get(iid)
        if not fila:
            return

        if fila['ASENTADO']:
            messagebox.showwarning("Registro procesado",
                "Este registro ya fue procesado y no se puede eliminar.")
            return

        if not SEGURIDAD_DISPONIBLE:
            messagebox.showerror("Seguridad requerida",
                "El módulo de seguridad no está disponible.")
            return

        # CLASE 205: advertir que se borra solo UNA cuota del préstamo
        if fila['CLASE'] == '205':
            fv = fila['FECHA_VEN'].strftime('%d/%m/%Y') if fila['FECHA_VEN'] else '-'
            if not messagebox.askyesno("Eliminar cuota de préstamo",
                f"Este registro es la cuota {fila['SECUENCIA']} de un préstamo.\n\n"
                f"Empleado: {fila['EMPLEADO']}  |  N° {fila['NUMERO']}  |  Vence {fv}  |  ${fila['VALOR']:,.2f}\n\n"
                "⚠  Solo se eliminará ESTA cuota, el resto del préstamo queda intacto.\n"
                "¿Continuar?"):
                return
        else:
            fv = fila['FECHA_VEN'].strftime('%d/%m/%Y') if fila['FECHA_VEN'] else '-'
            desc = (f"N° {fila['NUMERO']}  —  Empleado {fila['EMPLEADO']}  "
                    f"—  Vence {fv}  —  ${fila['VALOR']:,.2f}")
            if not messagebox.askyesno("Confirmar eliminación",
                    f"¿Eliminar este registro?\n\n{desc}\n\n"
                    "Se creará un respaldo antes de eliminar."):
                return

        self._set_status("Eliminando registro...", COL_DANGER)

        def _thread():
            conn2, err = conectar_bd()
            if err:
                self.master.after(0, lambda: messagebox.showerror("Error de conexión", err))
                return
            conn2.autocommit = False
            try:
                exito, archivo, _ = crear_respaldo_prestamo(
                    conn2, fila['EMPLEADO'], fila['NUMERO'],
                    f"Eliminacion fila clase={fila['CLASE']} seq={fila['SECUENCIA']}"
                )
                if not exito:
                    self.master.after(0, lambda: messagebox.showerror(
                        "Error respaldo", "No se pudo crear el respaldo. Operación cancelada."))
                    return

                cursor = conn2.cursor()
                cursor.execute("""
                    DELETE FROM RPINGDES
                    WHERE EMPLEADO = ? AND NUMERO = ? AND CLASE = ?
                      AND FECHA_VEN = ? AND SECUENCIA = ?
                """, (fila['EMPLEADO'], fila['NUMERO'], fila['CLASE'],
                      fila['FECHA_VEN'], fila['SECUENCIA']))
                filas_afectadas = cursor.rowcount
                conn2.commit()

                log_operacion("ELIMINAR_FILA", fila['EMPLEADO'], fila['NUMERO'],
                              f"Eliminada fila clase={fila['CLASE']} seq={fila['SECUENCIA']} "
                              f"valor={fila['VALOR']}",
                              exito=True)

                self.master.after(0, lambda: self._set_status(
                    f"Fila eliminada ({filas_afectadas} registro/s)", COL_OK))
                self.master.after(0, self._consulta_buscar)
            except Exception as ex:
                conn2.rollback()
                log_operacion("ELIMINAR_FILA", fila['EMPLEADO'], fila['NUMERO'],
                              str(ex), exito=False)
                err_msg = str(ex)
                self.master.after(0, lambda m=err_msg: messagebox.showerror("Error", m))
                self.master.after(0, lambda: self._set_status("Error al eliminar", COL_DANGER))
            finally:
                conn2.close()

        threading.Thread(target=_thread, daemon=True).start()

    def _consulta_exportar_csv(self):
        filas_iids = self.cq_tree.get_children()
        if not filas_iids:
            messagebox.showinfo("Sin datos", "No hay registros para exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            title="Exportar registros a CSV")
        if not path:
            return
        try:
            cols = ["N°","Emp","Nombre","Clase","Concepto","Observ","Seq","Vence","Valor","Estado"]
            import csv
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(cols)
                for iid in filas_iids:
                    w.writerow(self.cq_tree.item(iid, 'values'))
            messagebox.showinfo("Exportado",
                f"Exportados {len(filas_iids):,} registros a:\n{path}")
        except Exception as ex:
            messagebox.showerror("Error al exportar", str(ex))

def main():
    print("=== INICIANDO SISTEMA DE PRESTAMOS v7.0 ===")
    # Registrar AppUserModelID para icono correcto en barra de tareas Windows
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'insevig.prestamos.7.0'
        )
    except Exception:
        pass
    try:
        root = tk.Tk()
        app = SistemaPrestamosUnificado(root)
        root.mainloop()
    except Exception as e:
        print(f"ERROR CRITICO: {e}")
        traceback.print_exc()
        try:
            messagebox.showerror("Error Critico", str(e))
        except:
            pass

if __name__ == "__main__":
    main()
