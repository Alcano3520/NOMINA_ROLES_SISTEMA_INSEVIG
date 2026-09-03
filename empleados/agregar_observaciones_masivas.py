#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lógica de inserción masiva en RPEMPOBSERV (7 campos refer1..refer7 por fila,
sin llave primaria). Ver TOTAL_OSERVACIONES/REPORTE_AGREGAR_OBSERVACIONES_MASIVAS.txt
para el diseño de la estructura de la tabla y la estrategia de anti-duplicado.

"Fila existente" se busca por mes+año de fecha_ven, no por fecha exacta —
mismo criterio que usa SISTEMA_GESTION_EMPLEADOS_10.pyw en _mostrar_obs()/
_guardar_obs(). Si el matching fuera por fecha exacta, dos cargas en el mismo
mes con fechas distintas creaban filas paralelas que el visor de mes+año
nunca encontraba (las observaciones "ya cargadas" quedaban invisibles ahí).
"""

MAX_CAMPOS = 7
MAX_CHARS = 256


def _fila_mes(cursor, empleado, fecha_ven):
    """Fila más reciente (por fecha_ven) del empleado en el mes/año de
    `fecha_ven`, o None si no hay ninguna."""
    cursor.execute("""
        SELECT refer1, refer2, refer3, refer4, refer5, refer6, refer7, fecha_ven
        FROM RPEMPOBSERV
        WHERE empleado = ? AND MONTH(fecha_ven) = MONTH(?) AND YEAR(fecha_ven) = YEAR(?)
        ORDER BY fecha_ven DESC
    """, (empleado, fecha_ven, fecha_ven))
    return cursor.fetchone()


def _siguiente_campo_vacio(fila):
    """Primer refer1..refer7 NULL en `fila`, o None si está llena."""
    for i in range(MAX_CAMPOS):
        if fila[i] is None:
            return i + 1
    return None


def _texto_ya_existe(cursor, empleado, fecha_ven, texto):
    """Duplicado exacto: mismo texto ya en algún referN de alguna fila del mes/año."""
    cursor.execute("""
        SELECT COUNT(*) FROM RPEMPOBSERV
        WHERE empleado = ? AND MONTH(fecha_ven) = MONTH(?) AND YEAR(fecha_ven) = YEAR(?)
          AND (refer1 = ? OR refer2 = ? OR refer3 = ? OR refer4 = ?
               OR refer5 = ? OR refer6 = ? OR refer7 = ?)
    """, (empleado, fecha_ven, fecha_ven, texto, texto, texto, texto, texto, texto, texto))
    return cursor.fetchone()[0] > 0


def _insertar_fragmento(cursor, conn, empleado, fecha_ven, texto, force_new_row):
    """Inserta `texto` (ya recortado a MAX_CHARS) en el primer refer disponible
    de la fila del mes; crea fila nueva si no hay ninguna fila ese mes, o si
    force_new_row y la fila del mes ya está llena."""
    fila = _fila_mes(cursor, empleado, fecha_ven)

    if fila is None:
        cursor.execute("""
            INSERT INTO RPEMPOBSERV (empleado, codemp, codsuc, fecha_ven, refer1)
            VALUES (?, ?, ?, ?, ?)
        """, (empleado, '10', '10', fecha_ven, texto))
        conn.commit()
        return True, 'refer1 (fila nueva)'

    campo = _siguiente_campo_vacio(fila)
    if campo is None:
        if not force_new_row:
            return False, None
        cursor.execute("""
            INSERT INTO RPEMPOBSERV (empleado, codemp, codsuc, fecha_ven, refer1)
            VALUES (?, ?, ?, ?, ?)
        """, (empleado, '10', '10', fecha_ven, texto))
        conn.commit()
        return True, 'refer1 (fila nueva)'

    columna = f'refer{campo}'
    fila_fecha_ven = fila[7]  # fecha real de la fila encontrada, puede diferir de fecha_ven pedida
    cursor.execute(f"""
        UPDATE TOP (1) RPEMPOBSERV SET {columna} = ?
        WHERE empleado = ? AND fecha_ven = ? AND {columna} IS NULL
    """, (texto, empleado, fila_fecha_ven))
    conn.commit()
    return True, columna


def procesar_carga(datos_validados, conn, force_new_row=True):
    """
    datos_validados: lista de dicts {'empleado', 'fecha_ven', 'texto_obs'} ya
    validados desde la plantilla Excel (ver ObservacionesMasivasFrame._validar_obs).
    conn: conexión pyodbc ya abierta (se reutiliza, no se crea una nueva).

    Retorna stats: {'insertados', 'duplicados', 'sin_espacio', 'errores', 'detalles'}
    """
    cursor = conn.cursor()
    stats = {'insertados': 0, 'duplicados': 0, 'sin_espacio': 0, 'errores': 0, 'detalles': []}

    for item in datos_validados:
        empleado = str(item['empleado']).strip()
        fecha_ven = item['fecha_ven']
        texto = str(item['texto_obs']).strip()
        if not empleado or not texto:
            continue

        try:
            if _texto_ya_existe(cursor, empleado, fecha_ven, texto):
                stats['duplicados'] += 1
                stats['detalles'].append({'tipo': 'DUPLICADO', 'empleado': empleado})
                continue

            fragmentos = [texto[i:i + MAX_CHARS] for i in range(0, len(texto), MAX_CHARS)] or [texto]
            for frag in fragmentos:
                ok, campo = _insertar_fragmento(cursor, conn, empleado, fecha_ven, frag, force_new_row)
                if ok:
                    stats['insertados'] += 1
                    stats['detalles'].append({'tipo': 'INSERTADO', 'empleado': empleado,
                                               'campo': campo, 'texto': frag})
                else:
                    stats['sin_espacio'] += 1
                    stats['detalles'].append({'tipo': 'ERROR', 'empleado': empleado,
                                               'error': 'Sin espacio disponible (7 campos llenos)'})
        except Exception as e:
            stats['errores'] += 1
            stats['detalles'].append({'tipo': 'ERROR', 'empleado': empleado, 'error': str(e)})

    return stats
