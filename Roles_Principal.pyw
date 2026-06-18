#!/usr/bin/env python3
"""
ROLES DE PAGO - SISTEMA INTEGRADO INSEVIG
Combina Visualizador + Generador en una sola aplicación con pestañas
- Pestaña 1: Visualizador de Roles (búsqueda individual)
- Pestaña 2: Generador de Roles (batch)
"""

import pyodbc
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import threading
from datetime import datetime
import calendar
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image
import tempfile
import warnings

warnings.filterwarnings('ignore', message='.*SQLAlchemy.*')

try:
    import fitz  # PyMuPDF
    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False


# ════════════════════════════════════════════════════════════════════════════
# CLASE DE OBTENCIÓN DE DATOS (módulo reutilizable)
# ════════════════════════════════════════════════════════════════════════════

class ObtenerDatos:
    """Clase para obtener datos de empleados desde SQL Server"""

    def __init__(self, server='192.168.2.115', database='insevig', username='sa', password='puntosoft123*'):
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.sql_filter = "CODEMP='10' AND CODSUC='10'"

    def _get_connection(self):
        """Crear conexión a SQL Server"""
        conn_str = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={self.server};'
            f'DATABASE={self.database};'
            f'UID={self.username};'
            f'PWD={self.password};'
            f'Encrypt=No;'
            f'TrustServerCertificate=yes;'
            f'ApplicationIntent=ReadOnly;'
        )
        return pyodbc.connect(conn_str)

    def obtener_datos_empleado_rapido(self, periodo, cedula_o_nombre):
        """
        MÉTODO RÁPIDO: Obtiene datos de UN SOLO empleado sin cargar todo el período.
        """
        try:
            print("⚡ Búsqueda rápida de empleado...")
            conn = self._get_connection()

            # 1. Buscar el empleado
            if len(str(cedula_o_nombre)) <= 6:
                query_emp = f"""
                SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                       [CARGO], [DEPTO], [SECCION]
                FROM [insevig].[dbo].[RPEMPLEA]
                WHERE {self.sql_filter} AND [ESTADO]='ACT' AND [EMPLEADO] = ?
                """
                df_emp = pd.read_sql(query_emp, conn, params=[str(cedula_o_nombre)])

                if df_emp is None or df_emp.empty:
                    try:
                        cedula_num = int(cedula_o_nombre)
                        query_emp = f"""
                        SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                               [CARGO], [DEPTO], [SECCION]
                        FROM [insevig].[dbo].[RPEMPLEA]
                        WHERE {self.sql_filter} AND [ESTADO]='ACT' AND [CEDULA] = ?
                        """
                        df_emp = pd.read_sql(query_emp, conn, params=[cedula_num])
                    except:
                        query_emp = f"""
                        SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                               [CARGO], [DEPTO], [SECCION]
                        FROM [insevig].[dbo].[RPEMPLEA]
                        WHERE {self.sql_filter} AND [ESTADO]='ACT' AND
                              ([NOMBRES] LIKE ? OR [APELLIDOS] LIKE ?)
                        """
                        filtro = f'%{cedula_o_nombre}%'
                        df_emp = pd.read_sql(query_emp, conn, params=[filtro, filtro])
            else:
                try:
                    cedula_num = int(cedula_o_nombre)
                    query_emp = f"""
                    SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                           [CARGO], [DEPTO], [SECCION]
                    FROM [insevig].[dbo].[RPEMPLEA]
                    WHERE {self.sql_filter} AND [ESTADO]='ACT' AND [CEDULA] = ?
                    """
                    df_emp = pd.read_sql(query_emp, conn, params=[cedula_num])
                except:
                    query_emp = f"""
                    SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                           [CARGO], [DEPTO], [SECCION]
                    FROM [insevig].[dbo].[RPEMPLEA]
                    WHERE {self.sql_filter} AND [ESTADO]='ACT' AND
                          ([NOMBRES] LIKE ? OR [APELLIDOS] LIKE ? OR [CEDULA] LIKE ?)
                    """
                    filtro = f'%{cedula_o_nombre}%'
                    df_emp = pd.read_sql(query_emp, conn, params=[filtro, filtro, filtro])

            if df_emp.empty:
                print("❌ Empleado no encontrado")
                conn.close()
                return None

            emp = df_emp.iloc[0]
            empleado_code = emp['EMPLEADO']

            print(f"✓ Empleado encontrado: {emp['APELLIDOS']} {emp['NOMBRES']}")

            # 2. Obtener movimientos
            año, mes = periodo.split('-')
            fecha_inicio = f'{año}-{mes}-01'
            if mes == '12':
                año_fin = int(año) + 1
                mes_fin = 1
            else:
                año_fin = int(año)
                mes_fin = int(mes) + 1
            fecha_fin = f'{año_fin}-{mes_fin:02d}-01'

            query_mov = f"""
            SELECT *
            FROM [insevig].[dbo].[RPINGDES]
            WHERE {self.sql_filter} AND [EMPLEADO] = ?
                  AND [FECHA_VEN] IS NOT NULL
                  AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                  AND CAST([FECHA_VEN] AS DATE) < CAST(? AS DATE)
            """
            df_mov = pd.read_sql(query_mov, conn, params=[empleado_code, fecha_inicio, fecha_fin])

            if df_mov is None or df_mov.empty:
                print("  → Buscando en RPHISTOR (períodos cerrados)...")
                query_hist = f"""
                SELECT *
                FROM [insevig].[dbo].[RPHISTOR]
                WHERE {self.sql_filter} AND [EMPLEADO] = ?
                      AND [FECHA_VEN] IS NOT NULL
                      AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                      AND CAST([FECHA_VEN] AS DATE) < CAST(? AS DATE)
                """
                df_mov = pd.read_sql(query_hist, conn, params=[empleado_code, fecha_inicio, fecha_fin])

            # 3. Consolidar movimientos
            conceptos = {}
            mapeo_conceptos = {
                100: 'SUELDO', 102: 'BONIFICACION', 104: 'FONDO_RESERVA',
                107: 'DECIMO_TERCERA', 108: 'DECIMO_CUARTA', 110: 'MANIOBRAS',
                111: 'REEMBOLSOS', 113: 'SOBRETIEMPO_25', 114: 'SOBRETIEMPO_50',
                115: 'SOBRETIEMPO_100', 120: 'MOVILIZACION', 200: 'APORT_IESS',
                201: 'ANTICIPOS_OTROS', 202: 'ANTICIPO_SUELDO', 203: 'MULTAS',
                204: 'PRESTAMOS_QUIROGRAFARIOS', 205: 'PRESTAMOS_COMPANIA',
                206: 'PENSION_ALIMENTICIA', 207: 'PRESTAMO_HIPOTECARIO',
                217: 'ANTICIPOS_OTROS', 218: 'APORT_IESS_CONYUGE', 219: 'IMPUESTO_RENTA',
                250: 'ANTICIPOS_SURTIDOS',
            }

            for idx, row in df_mov.iterrows():
                clase = int(row['CLASE']) if pd.notna(row['CLASE']) else 0
                valor = float(row['VALOR']) if pd.notna(row['VALOR']) else 0
                asentado = row.get('ASENTADO', False)

                if clase not in [105, 126, 199]:
                    concepto = mapeo_conceptos.get(clase, f'CONCEPTO_{clase}')
                    if concepto in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                        if asentado:
                            conceptos[concepto] = conceptos.get(concepto, 0) + valor
                    else:
                        conceptos[concepto] = conceptos.get(concepto, 0) + valor

            # 4. Obtener DIAS
            dias = 30.0
            if 'SUELDO' in conceptos and conceptos['SUELDO'] > 0:
                dias_query = f"""
                SELECT TOP 1 ISNULL(DIAS, 30) as DIAS
                FROM [insevig].[dbo].[RPINGDES]
                WHERE {self.sql_filter} AND [EMPLEADO] = ? AND [CLASE] = 101
                """
                df_dias = pd.read_sql(dias_query, conn, params=[empleado_code])
                if not df_dias.empty:
                    dias = float(df_dias.iloc[0]['DIAS'])

            # 5. Calcular totales
            campos_ingresos = ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA',
                              'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25',
                              'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION']
            campos_egresos = ['APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
                             'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                             'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                             'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO']

            ingresos = sum(conceptos.get(k, 0) for k in campos_ingresos)
            egresos = sum(conceptos.get(k, 0) for k in campos_egresos)

            # 6. Obtener nombres descriptivos
            df_dbt_fnc = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO='FNC' AND CODEMP='10'", conn)
            df_dbt_dpt = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO='DPT' AND CODEMP='10'", conn)

            dic_fnc = dict(zip(df_dbt_fnc['CODIGO'].astype(str).str.strip(), df_dbt_fnc['NOMBRE']))
            dic_dpt = dict(zip(df_dbt_dpt['CODIGO'].astype(str).str.strip(), df_dbt_dpt['NOMBRE']))

            cargo_nombre = dic_fnc.get(str(emp['CARGO']).strip(), str(emp['CARGO']))
            depto_nombre = dic_dpt.get(str(emp['DEPTO']).strip(), str(emp['DEPTO']))

            # 7. Armar resultado
            resultado = {
                'EMPLEADO': emp['EMPLEADO'],
                'APELLIDOS_NOMBRES': f"{emp['APELLIDOS']} {emp['NOMBRES']}".strip(),
                'CEDULA': emp['CEDULA'],
                'CARGO': cargo_nombre,
                'DEPTO': depto_nombre,
                'DIAS': dias,
                'TOTAL_INGRESOS': ingresos,
                'TOTAL_EGRESOS': egresos,
                'TOTAL_RECIBIR': ingresos - egresos,
            }

            resultado.update(conceptos)
            conn.close()

            return pd.Series(resultado)

        except Exception as e:
            print(f"❌ Error en búsqueda rápida: {e}")
            import traceback
            traceback.print_exc()
            return None


# ════════════════════════════════════════════════════════════════════════════
# CLASE GENERADORA DE PDFs (compartida)
# ════════════════════════════════════════════════════════════════════════════

class GeneradorPDFs:
    """Clase para generar PDFs de roles de pago"""

    def __init__(self):
        self.server = '192.168.2.115'
        self.database = 'insevig'
        self.username = 'sa'
        self.password = 'puntosoft123*'
        self.sql_filter = "CODEMP='10' AND CODSUC='10'"

    def obtener_datos_bd(self, periodo):
        """Obtiene datos consolidados de la base de datos para batch"""
        try:
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password};'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
                f'ApplicationIntent=ReadOnly;'
            )

            print("Conectando a la base de datos...")
            conn = pyodbc.connect(conn_str)

            query_empleados = f"""
            SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                   [FECHA_ING], [FECHA_SAL], [CARGO], [CTA_AHO], [CTA_CTE],
                   [ESTADO], [ANTIQUINC], [DEPTO], [SECCION]
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE {self.sql_filter} AND [ESTADO] = 'ACT'
            """

            df_empleados = pd.read_sql(query_empleados, conn)
            print(f"Empleados ACTIVOS encontrados: {len(df_empleados)}")

            df_empleados['APELLIDOS_NOMBRES'] = (df_empleados['APELLIDOS'].fillna('').astype(str) + ' ' +
                                               df_empleados['NOMBRES'].fillna('').astype(str)).str.strip()

            def consolidar_cuenta(row):
                cta_aho = str(row['CTA_AHO']).strip() if pd.notna(row['CTA_AHO']) else ''
                cta_cte = str(row['CTA_CTE']).strip() if pd.notna(row['CTA_CTE']) else ''

                if cta_aho and cta_aho != 'nan':
                    return cta_aho
                elif cta_cte and cta_cte != 'nan':
                    return cta_cte
                else:
                    return ''

            df_empleados['CTA_AHO_CONSOLIDADA'] = df_empleados.apply(consolidar_cuenta, axis=1)

            # 2. Traer movimientos del período
            año, mes = periodo.split('-')
            fecha_inicio = pd.Timestamp(f'{año}-{mes}-01')
            if mes == '12':
                fecha_fin = pd.Timestamp(f'{int(año)+1}-01-01') - pd.Timedelta(days=1)
            else:
                fecha_fin = pd.Timestamp(f'{año}-{int(mes)+1:02d}-01') - pd.Timedelta(days=1)

            print(f"Buscando datos para el período: {periodo}")

            query_movimientos = f"""
            SELECT [NUMERO], [FECHA], [EMPLEADO], [CODSUC], [CODEMP], [CODIGO], [CLASE],
                   [SECUENCIA], [HORAS], [VALOR], [FECHA_VEN],
                   [CONCEPTO], [DIAS], [ASENTADO], [ACTUALIZA], [APORTA], [MONTO],
                   [DIVIDENDO], [ROL], [TIPO_PGO], [TIPO_TRA], [OBSERV]
            FROM [insevig].[dbo].[RPINGDES]
            WHERE {self.sql_filter}
              AND [FECHA_VEN] IS NOT NULL
              AND [FECHA_VEN] >= ?
              AND [FECHA_VEN] <= ?
            """
            df_movimientos = pd.read_sql(query_movimientos, conn, params=[fecha_inicio, fecha_fin])

            df_movimientos_periodo = df_movimientos
            movimiento_minimo_por_empleado = 10
            hay_pocos_movimientos = (
                len(df_movimientos_periodo) > 0 and
                len(df_movimientos_periodo) < len(df_empleados) * movimiento_minimo_por_empleado
            )

            hay_datos_rphistor = False
            try:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT COUNT(*) FROM [insevig].[dbo].[RPHISTOR] WITH (NOLOCK) "
                    f"WHERE {self.sql_filter} AND [FECHA_VEN] >= ? AND [FECHA_VEN] <= ?",
                    [fecha_inicio, fecha_fin]
                )
                count_rphistor = cursor.fetchone()[0]
                print(f"COUNT en RPHISTOR para {periodo}: {count_rphistor} filas")
                if count_rphistor > 0:
                    hay_datos_rphistor = True
            except Exception as e_count:
                print(f"Error al contar RPHISTOR: {e_count}")

            if df_movimientos_periodo.empty or hay_pocos_movimientos or (hay_datos_rphistor and len(df_movimientos_periodo) < count_rphistor):
                try:
                    query_columnas = """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'RPHISTOR'
                    ORDER BY ORDINAL_POSITION
                    """
                    df_columnas = pd.read_sql(query_columnas, conn)
                    columnas_histor = df_columnas['COLUMN_NAME'].tolist()

                    columnas_necesarias = ['NUMERO', 'FECHA', 'EMPLEADO', 'CODSUC', 'CODEMP', 'CODIGO', 'CLASE',
                                           'SECUENCIA', 'HORAS', 'VALOR', 'FECHA_VEN',
                                           'CONCEPTO', 'DIAS', 'ASENTADO', 'ACTUALIZA', 'APORTA', 'MONTO',
                                           'DIVIDENDO', 'ROL', 'TIPO_PGO', 'TIPO_TRA', 'OBSERV']

                    select_cols = []
                    for c in columnas_necesarias:
                        if c in columnas_histor:
                            select_cols.append(f"[{c}]")
                        else:
                            select_cols.append(f"NULL AS [{c}]")

                    query_histor = f"""
                    SELECT {', '.join(select_cols)}
                    FROM [insevig].[dbo].[RPHISTOR]
                    WHERE {self.sql_filter}
                      AND [FECHA_VEN] IS NOT NULL
                      AND [FECHA_VEN] >= ?
                      AND [FECHA_VEN] <= ?
                    """
                    df_histor = pd.read_sql(query_histor, conn, params=[fecha_inicio, fecha_fin])
                    df_movimientos_periodo = df_histor

                except Exception as e_hist:
                    print(f"Error al consultar RPHISTOR: {e_hist}")

            if df_movimientos_periodo.empty:
                print(f"No se encontraron movimientos para {periodo}")
                conn.close()
                return None

            mapeo_conceptos = {
                100: 'SUELDO', 102: 'BONIFICACION', 104: 'FONDO_RESERVA', 107: 'DECIMO_TERCERA',
                108: 'DECIMO_CUARTA', 110: 'MANIOBRAS', 111: 'REEMBOLSOS', 113: 'SOBRETIEMPO_25',
                114: 'SOBRETIEMPO_50', 115: 'SOBRETIEMPO_100', 120: 'MOVILIZACION',
                200: 'APORT_IESS', 201: 'ANTICIPOS_OTROS', 202: 'ANTICIPO_SUELDO', 203: 'MULTAS',
                204: 'PRESTAMOS_QUIROGRAFARIOS', 205: 'PRESTAMOS_COMPANIA', 206: 'PENSION_ALIMENTICIA',
                207: 'PRESTAMO_HIPOTECARIO', 217: 'ANTICIPOS_OTROS', 218: 'APORT_IESS_CONYUGE',
                219: 'IMPUESTO_RENTA', 250: 'ANTICIPOS_SURTIDOS',
            }

            codigos_ignorar = {105, 126, 199}

            df_movimientos_periodo['CLASE'] = pd.to_numeric(df_movimientos_periodo['CLASE'], errors='coerce')
            df_movimientos_periodo = df_movimientos_periodo.dropna(subset=['CLASE'])
            df_movimientos_periodo['CLASE'] = df_movimientos_periodo['CLASE'].astype(int)

            resultados = []
            grupos = df_movimientos_periodo.groupby('EMPLEADO')
            print(f"Procesando {len(grupos)} empleados...")

            conceptos_ingresos = ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA',
                                 'DECIMO_TERCERA', 'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS',
                                 'SOBRETIEMPO_25', 'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION']

            conceptos_egresos = ['APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
                                'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                                'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                                'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO']

            for empleado, grupo in grupos:
                fila = {
                    'EMPLEADO': empleado,
                    'APELLIDOS_NOMBRES': '',
                    'CEDULA': '',
                    'SUELDO_BASE': 0.0,
                    'FECHA_ING': '',
                    'FECHA_SAL': '',
                    'CARGO': '',
                    'CTA_AHO': '',
                    'PERIODO': periodo,
                    'DEPTO': '',
                    'SECCION': '',
                    'DIAS': 0
                }

                for concepto in conceptos_ingresos + conceptos_egresos:
                    fila[concepto] = 0.0

                for _, registro in grupo.iterrows():
                    clase_codigo = registro['CLASE']
                    tipo_movimiento = registro['CODIGO']

                    if clase_codigo in codigos_ignorar:
                        continue

                    valor = registro['VALOR'] if pd.notna(registro['VALOR']) else 0
                    asentado = registro['ASENTADO']

                    if clase_codigo in mapeo_conceptos:
                        concepto = mapeo_conceptos[clase_codigo]

                        if concepto in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                            if asentado:
                                fila[concepto] += round(valor, 2)
                        elif concepto == 'SUELDO':
                            fila[concepto] += round(valor, 2)
                            if pd.notna(registro['DIAS']):
                                fila['DIAS'] = registro['DIAS']
                        else:
                            if concepto in conceptos_ingresos + conceptos_egresos:
                                fila[concepto] += round(valor, 2)
                    else:
                        if tipo_movimiento == 'EGR':
                            fila['ANTICIPOS_SURTIDOS'] += round(valor, 2)

                total_ingresos = round(sum(fila[concepto] for concepto in conceptos_ingresos), 2)
                total_egresos = round(sum(fila[concepto] for concepto in conceptos_egresos), 2)

                fila['TOTAL_INGRESOS'] = total_ingresos
                fila['TOTAL_EGRESOS'] = total_egresos
                fila['TOTAL_RECIBIR'] = round(total_ingresos - total_egresos, 2)

                resultados.append(fila)

            df_consolidado = pd.DataFrame(resultados)
            print(f"Empleados procesados: {len(df_consolidado)}")

            df_empleados_renamed = df_empleados.rename(columns={
                'APELLIDOS_NOMBRES': 'APELLIDOS_NOMBRES_EMP',
                'CEDULA': 'CEDULA_EMP',
                'SUELDO': 'SUELDO_EMP',
                'FECHA_ING': 'FECHA_ING_EMP',
                'FECHA_SAL': 'FECHA_SAL_EMP',
                'CARGO': 'CARGO_EMP',
                'CTA_AHO_CONSOLIDADA': 'CTA_AHO_EMP',
                'ANTIQUINC': 'ANTIQUINC_EMP',
                'DEPTO': 'DEPTO_EMP',
                'SECCION': 'SECCION_EMP'
            })

            df_consolidado = df_consolidado.merge(
                df_empleados_renamed[['EMPLEADO', 'APELLIDOS_NOMBRES_EMP', 'CEDULA_EMP', 'SUELDO_EMP',
                                    'FECHA_ING_EMP', 'FECHA_SAL_EMP', 'CARGO_EMP', 'CTA_AHO_EMP',
                                    'ANTIQUINC_EMP', 'DEPTO_EMP', 'SECCION_EMP']],
                on='EMPLEADO',
                how='inner'
            )

            print(f"Empleados después del JOIN: {len(df_consolidado)}")

            df_consolidado['APELLIDOS_NOMBRES'] = df_consolidado['APELLIDOS_NOMBRES_EMP'].fillna('')

            def limpiar_cedula(x):
                if pd.isna(x):
                    return ''
                cedula_str = str(x)
                if '.' in cedula_str:
                    cedula_str = cedula_str.split('.')[0]
                return cedula_str

            df_consolidado['CEDULA'] = df_consolidado['CEDULA_EMP'].apply(limpiar_cedula)
            df_consolidado['SUELDO_BASE'] = df_consolidado['SUELDO_EMP'].fillna(0.0)
            df_consolidado['FECHA_ING'] = df_consolidado['FECHA_ING_EMP'].fillna('')
            df_consolidado['FECHA_SAL'] = df_consolidado['FECHA_SAL_EMP'].fillna('')
            df_consolidado['CARGO'] = df_consolidado['CARGO_EMP'].fillna('')
            df_consolidado['CTA_AHO'] = df_consolidado['CTA_AHO_EMP'].fillna('')
            df_consolidado['DEPTO'] = df_consolidado['DEPTO_EMP'].fillna('')
            df_consolidado['SECCION'] = df_consolidado['SECCION_EMP'].fillna('')

            print("Convirtiendo códigos a nombres descriptivos...")

            df_dbtablas_fnc = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'FNC' AND CODEMP = '10'", conn)
            df_dbtablas_dpt = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'DPT' AND CODEMP = '10'", conn)
            df_dbtablas_sec = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'SEC' AND CODEMP = '10'", conn)

            dic_fnc = dict(zip(df_dbtablas_fnc['CODIGO'].astype(str).str.strip(), df_dbtablas_fnc['NOMBRE']))
            dic_dpt = dict(zip(df_dbtablas_dpt['CODIGO'].astype(str).str.strip(), df_dbtablas_dpt['NOMBRE']))
            dic_sec = dict(zip(df_dbtablas_sec['CODIGO'].astype(str).str.strip(), df_dbtablas_sec['NOMBRE']))

            for idx in df_consolidado.index:
                cargo_codigo = str(df_consolidado.loc[idx, 'CARGO']).strip()
                df_consolidado.loc[idx, 'CARGO'] = dic_fnc.get(cargo_codigo, cargo_codigo)

                depto_codigo = str(df_consolidado.loc[idx, 'DEPTO']).strip()
                df_consolidado.loc[idx, 'DEPTO'] = dic_dpt.get(depto_codigo, depto_codigo)

                seccion_codigo = str(df_consolidado.loc[idx, 'SECCION']).strip()
                df_consolidado.loc[idx, 'SECCION'] = dic_sec.get(seccion_codigo, seccion_codigo)

            df_consolidado.loc[df_consolidado['ANTIQUINC_EMP'] == 0, 'FONDO_RESERVA'] = 0.00

            for idx in df_consolidado.index:
                total_ingresos_nuevo = round(sum(df_consolidado.loc[idx, concepto] for concepto in conceptos_ingresos), 2)
                df_consolidado.loc[idx, 'TOTAL_INGRESOS'] = total_ingresos_nuevo
                total_egresos = df_consolidado.loc[idx, 'TOTAL_EGRESOS']
                df_consolidado.loc[idx, 'TOTAL_RECIBIR'] = round(total_ingresos_nuevo - total_egresos, 2)

            conn.close()

            columnas_a_eliminar = [col for col in df_consolidado.columns if col.endswith('_EMP')]
            df_consolidado = df_consolidado.drop(columns=columnas_a_eliminar)

            print(f"✅ Datos consolidados obtenidos: {len(df_consolidado)} empleados")
            return df_consolidado

        except Exception as e:
            print(f"❌ Error al obtener datos de BD: {e}")
            import traceback
            traceback.print_exc()
            return None

    def crear_pdf_empleado_bd(self, filename, row, start_date, end_date, logo_path=None):
        """Crea el PDF para un empleado"""
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4
        self.dibujar_rol_en_posicion(c, row, start_date, end_date, width, height, y_offset=height/2, logo_path=logo_path)
        c.save()

    def crear_pdf_empleado_doble(self, filename, row, start_date, end_date, logo_path=None):
        """Crea el PDF con 2 roles en una hoja"""
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4

        self.dibujar_rol_en_posicion(c, row, start_date, end_date, width, height, y_offset=height/2, logo_path=logo_path)

        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.setDash(3, 3)
        c.line(30, height/2, width-30, height/2)

        c.setStrokeColorRGB(0, 0, 0)
        c.setDash()

        self.dibujar_rol_en_posicion(c, row, start_date, end_date, width, height, y_offset=0, logo_path=logo_path)

        c.save()

    def dibujar_rol_en_posicion(self, c, row, start_date, end_date, width, height, y_offset=0, logo_path=None):
        """Dibuja un rol en una posición específica"""
        margin = 40
        base_y = y_offset

        c.rect(margin-10, base_y + height/2 - 350, width-2*(margin-10), 310)

        if logo_path and os.path.exists(logo_path):
            try:
                img_original = Image.open(logo_path)
                img_bw = img_original.convert('L')

                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                img_bw.save(temp_file.name, 'PNG')
                temp_file.close()

                logo_width = 60
                logo_height = 60

                logo_x = width - (margin - 10) - logo_width - 10
                logo_y = base_y + height/2 - 350 + 310 - logo_height - 5

                c.drawImage(temp_file.name, logo_x, logo_y, width=logo_width, height=logo_height,
                           preserveAspectRatio=True, mask='auto')

                os.unlink(temp_file.name)
            except Exception as e:
                print(f"ERROR al cargar logo: {e}")

        c.setFont("Times-Bold", 14)
        title_y = base_y + height/2 - 60
        c.drawCentredString(width/2, title_y, "SOBRES DE PAGOS")
        c.drawCentredString(width/2, title_y-15, "INSEVIG CIA.LTDA.")

        c.setFont("Times-Roman", 11)
        y = base_y + height/2 - 95
        cedula = self._format_cedula(row['CEDULA'])
        c.drawString(margin, y, f"Cedula empleado: {cedula}")
        c.drawString(margin, y-12, f"Nombre del Empleado: {str(row['APELLIDOS_NOMBRES'])}     ({str(row['EMPLEADO'])})")
        c.drawString(margin, y-24, f"Periodo de pago: Desde {start_date} Hasta {end_date}")
        c.drawString(margin, y-36, f"Departamento: {str(row['DEPTO'])}     Cargo: {str(row['CARGO'])}")

        table_top = y-50
        table_bottom = table_top-200
        table_width = width - 2*margin

        c.rect(margin, table_bottom, table_width, table_top - table_bottom)

        col_concept = margin + 5
        col_income = margin + 205
        col_deduct = margin + 310
        col_net = margin + 415

        c.setFont("Times-Italic", 10)
        headers_y = table_top - 12

        c.drawString(col_concept, headers_y, "Concepto")
        c.drawString(col_income, headers_y, "Ingresos")
        c.drawString(col_deduct, headers_y, "Descuentos")
        c.drawString(col_net, headers_y, "Neto a Recibir")

        c.line(margin + 200, table_bottom, margin + 200, table_top)
        c.line(margin + 305, table_bottom, margin + 305, table_top)
        c.line(margin + 410, table_bottom, margin + 410, table_top)

        c.line(margin, headers_y - 5, margin + table_width, headers_y - 5)

        c.setFont("Times-Roman", 12)
        y = headers_y - 15
        line_height = 12

        total_income = 0
        total_deductions = 0

        sueldo = self._safe_get_bd(row, 'SUELDO')
        dias = self._safe_get_bd(row, 'DIAS')
        if sueldo > 0:
            c.drawString(col_concept, y, f"SUELDO                     {int(dias)} Dias")
            c.drawRightString(col_deduct - 10, y, f"{sueldo:.2f}")
            total_income += sueldo
            y -= line_height

        overtime = self._calculate_overtime_bd(row)
        if overtime > 0:
            c.drawString(col_concept, y, "HORAS EXTRAS(noct-suplem-extraor)")
            c.drawRightString(col_deduct - 10, y, f"{overtime:.2f}")
            total_income += overtime
            y -= line_height

        fondo_reserva = self._safe_get_bd(row, 'FONDO_RESERVA')
        if fondo_reserva == 0:
            base_calculo = self._calculate_reserve_fund_base_bd(row)
            fondo_reserva = base_calculo * 0.0833

            c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33%")
            c.drawRightString(col_deduct - 10, y, f"{fondo_reserva:.2f}")
            total_income += fondo_reserva
            y -= line_height

            total_deductions += fondo_reserva
        elif fondo_reserva > 0:
            c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33%")
            c.drawRightString(col_deduct - 10, y, f"{fondo_reserva:.2f}")
            total_income += fondo_reserva
            y -= line_height

        otros_ingresos = [
            ('REEMBOLSOS', "REEMBOLSOS"),
            ('DECIMO_TERCERA', "DECIMO TERCER SUELDO"),
            ('DECIMO_CUARTA', "DECIMO CUARTO SUELDO"),
            ('BONIFICACION', "BONIFICACION"),
            ('MANIOBRAS', "MANIOBRAS"),
            ('MOVILIZACION', "MOVILIZACION")
        ]

        for columna_bd, label in otros_ingresos:
            value = self._safe_get_bd(row, columna_bd)
            if value > 0:
                c.drawString(col_concept, y, label)
                c.drawRightString(col_deduct - 10, y, f"{value:.2f}")
                total_income += value
                y -= line_height

        if fondo_reserva > 0 and self._safe_get_bd(row, 'FONDO_RESERVA') == 0:
            c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33% EN IESS")
            c.drawRightString(col_net - 10, y, f"{fondo_reserva:.2f}")
            y -= line_height

        descuentos_bd = [
            ('APORT_IESS', "APORT.IESS"),
            ('PRESTAMOS_QUIROGRAFARIOS', "PRESTAMOS QUIROGRAFARIOS"),
            ('PRESTAMOS_COMPANIA', "PRESTAMOS COMPAÑIA"),
            ('ANTICIPO_SUELDO', "ANTICIPO DE SUELDO"),
            ('ANTICIPOS_OTROS', "ANTICIPOS OTROS"),
            ('ANTICIPOS_SURTIDOS', "ANTICIPOS SURTIDOS"),
            ('APORT_IESS_CONYUGE', "APORTE IESS CONYUGE"),
            ('IMPUESTO_RENTA', "IMPUESTO A LA RENTA"),
            ('MULTAS', "MULTAS"),
            ('PENSION_ALIMENTICIA', "PENSION ALIMENTICIA"),
            ('PRESTAMO_HIPOTECARIO', "PRESTAMO HIPOTECARIO")
        ]

        for columna_bd, label in descuentos_bd:
            value = self._safe_get_bd(row, columna_bd)
            if value > 0:
                c.drawString(col_concept, y, label)
                c.drawRightString(col_net - 10, y, f"{value:.2f}")
                total_deductions += value
                y -= line_height

        total_y = table_bottom + 25
        c.line(margin, total_y, margin + table_width, total_y)

        net_pay = total_income - total_deductions

        c.setFont("Times-Roman", 14)
        c.drawString(col_concept, total_y - 15, "Total a Pagar ===========>")
        c.drawRightString(col_deduct - 10, total_y - 15, f"{total_income:.2f}")
        c.drawRightString(col_net - 10, total_y - 15, f"{total_deductions:.2f}")
        c.drawRightString(margin + table_width - 10, total_y - 15, f"{net_pay:.2f}")

        firma_y = base_y + height/2 - 410
        c.drawCentredString(width/2, firma_y, "F I R M A")
        c.line(width/2 - 80, firma_y+10, width/2 + 80, firma_y+10)

    def _format_cedula(self, cedula):
        try:
            cedula_str = str(cedula)
            cedula_str = cedula_str.split('.')[0]
            return cedula_str.zfill(10)
        except:
            return str(cedula)

    def _safe_get_bd(self, row, column_name, default=0):
        try:
            value = row.get(column_name, default)
            if pd.isna(value):
                return 0.0
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').strip()
            return float(value) if value != '' else 0.0
        except:
            return 0.0

    def _calculate_overtime_bd(self, row):
        return (self._safe_get_bd(row, 'SOBRETIEMPO_25') +
                self._safe_get_bd(row, 'SOBRETIEMPO_50') +
                self._safe_get_bd(row, 'SOBRETIEMPO_100'))

    def _calculate_reserve_fund_base_bd(self, row):
        return (self._safe_get_bd(row, 'SUELDO') +
                self._safe_get_bd(row, 'BONIFICACION') +
                self._safe_get_bd(row, 'MANIOBRAS') +
                self._safe_get_bd(row, 'SOBRETIEMPO_25') +
                self._safe_get_bd(row, 'SOBRETIEMPO_50') +
                self._safe_get_bd(row, 'SOBRETIEMPO_100'))


# ════════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL CON PESTAÑAS
# ════════════════════════════════════════════════════════════════════════════

class RolesPrincipal:
    """Aplicación integrada de Roles con pestañas"""

    def __init__(self, root):
        self.root = root
        self.root.title("ROLES DE PAGO - INSEVIG")
        self.root.geometry("1000x800")

        # Colores corporativos
        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"
        self.color_white = "#ffffff"

        # Icono
        try:
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
            else:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')

            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"No se pudo cargar el icono: {e}")

        self.root.configure(bg=self.color_bg)

        # Instancias compartidas
        self.obtener_datos = ObtenerDatos()
        self.generador_pdf = GeneradorPDFs()

        # Header
        self._crear_header()

        # Notebook (pestañas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Pestaña 1: Visualizador
        self.tab_visualizador = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_visualizador, text="Visualizador")
        self._crear_visualizador()

        # Pestaña 2: Generador
        self.tab_generador = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_generador, text="Generador")
        self._crear_generador()

    def _crear_header(self):
        """Crea el header con título"""
        header = tk.Frame(self.root, bg=self.color_primary, height=70)
        header.pack(fill=tk.X, padx=0, pady=0)
        header.pack_propagate(False)

        tk.Label(header, text="GENERADOR Y VISUALIZADOR DE ROLES DE PAGO",
                font=("Segoe UI", 16, "bold"), fg=self.color_white, bg=self.color_primary).pack(pady=8)
        tk.Label(header, text="INSEVIG CIA. LTDA. • Sistema de Gestión de Nómina",
                font=("Segoe UI", 9), fg=self.color_secondary, bg=self.color_primary).pack()

    def _crear_visualizador(self):
        """Pestaña 1: Visualizador de roles individual"""

        # Variables
        self.vis_periodo_var = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        self.vis_buscar_var = tk.StringVar()
        self.vis_datos_actual = None
        self.vis_photo_image = None

        # Frame de controles
        ctrl = ttk.Frame(self.tab_visualizador)
        ctrl.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(ctrl, text="Período:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(ctrl, textvariable=self.vis_periodo_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(ctrl, text="Nombre o Cédula:").grid(row=0, column=2, padx=5, pady=5)
        entry_buscar = ttk.Entry(ctrl, textvariable=self.vis_buscar_var, width=30)
        entry_buscar.grid(row=0, column=3, padx=5, pady=5)
        entry_buscar.bind("<Return>", lambda e: self._vis_buscar())

        ttk.Button(ctrl, text="🔍 Buscar", command=self._vis_buscar).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(ctrl, text="💾 Descargar PDF", command=self._vis_descargar).grid(row=0, column=5, padx=5, pady=5)

        self.vis_status = tk.Label(ctrl, text="Ingrese período y nombre", fg='#666666', bg=self.color_bg)
        self.vis_status.grid(row=1, column=0, columnspan=6, sticky="w", padx=5, pady=3)

        # Canvas para mostrar PDF
        scroll_frame = ttk.Frame(self.tab_visualizador)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scroll = ttk.Scrollbar(scroll_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.vis_canvas = tk.Canvas(scroll_frame, bg="white", yscrollcommand=scroll.set)
        self.vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.vis_canvas.yview)

    def _vis_buscar(self):
        """Buscar un empleado en visualizador"""
        periodo = self.vis_periodo_var.get().strip()
        filtro = self.vis_buscar_var.get().strip()

        if not periodo or not filtro:
            messagebox.showwarning("Advertencia", "Ingrese período y nombre/cédula")
            return

        self.vis_status.config(text="⏳ Buscando...", fg='#cc6600')
        threading.Thread(target=self._vis_buscar_thread, args=(periodo, filtro), daemon=True).start()

    def _vis_buscar_thread(self, periodo, filtro):
        """Búsqueda en thread"""
        try:
            self.root.after(0, lambda: self.vis_status.config(text="⏳ Buscando empleados...", fg='#cc6600'))

            emp = self.obtener_datos.obtener_datos_empleado_rapido(periodo, filtro)

            if emp is None:
                self.root.after(0, lambda: messagebox.showinfo("Sin resultados", f"No encontrado: {filtro}"))
                return

            self.vis_datos_actual = emp
            self.root.after(0, self._vis_mostrar)

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", err_msg))

    def _vis_mostrar(self):
        """Generar y mostrar PDF"""
        if self.vis_datos_actual is None:
            return

        try:
            emp = self.vis_datos_actual
            periodo = self.vis_periodo_var.get()

            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                ruta_pdf = tmp.name

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"

            from calendar import monthrange
            _, ultimo_dia = monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{int(mes):02d}-{ultimo_dia}"

            self.generador_pdf.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)

            if HAS_PDF_SUPPORT:
                self._vis_mostrar_pdf_como_imagen(ruta_pdf)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', ruta_pdf])
                messagebox.showinfo("PDF generado", "Se abrió en el visor PDF")

            self.vis_status.config(text=f"✓ {emp['APELLIDOS_NOMBRES']}", fg='#28a745')

        except Exception as e:
            messagebox.showerror("Error", f"Error generando PDF: {e}")

    def _vis_mostrar_pdf_como_imagen(self, ruta_pdf):
        """Mostrar PDF como imagen en canvas"""
        try:
            doc = fitz.open(ruta_pdf)
            page = doc[0]

            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_data = pix.tobytes("ppm")

            from io import BytesIO
            img = Image.open(BytesIO(img_data))

            self.vis_photo_image = ImageTk.PhotoImage(img)

            self.vis_canvas.delete("all")
            self.vis_canvas.create_image(0, 0, image=self.vis_photo_image, anchor="nw")
            self.vis_canvas.config(scrollregion=self.vis_canvas.bbox("all"))

            doc.close()

        except Exception as e:
            messagebox.showerror("Error", f"Error mostrando PDF: {e}")

    def _vis_descargar(self):
        """Descargar PDF del empleado actual"""
        if self.vis_datos_actual is None:
            messagebox.showwarning("Advertencia", "Busque primero un empleado")
            return

        carpeta = filedialog.askdirectory(title="Seleccione carpeta para descargar")
        if not carpeta:
            return

        try:
            emp = self.vis_datos_actual
            periodo = self.vis_periodo_var.get()

            cedula = str(emp['CEDULA']).split('.')[0]
            nombre = emp['APELLIDOS_NOMBRES'].replace(' ', '_')
            nombre_archivo = f"{cedula}_{nombre}.pdf"
            ruta_pdf = os.path.join(carpeta, nombre_archivo)

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"

            from calendar import monthrange
            _, ultimo_dia = monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{int(mes):02d}-{ultimo_dia}"

            self.generador_pdf.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)
            messagebox.showinfo("Éxito", f"PDF descargado en:\n{ruta_pdf}")

        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def _crear_generador(self):
        """Pestaña 2: Generador batch de roles"""

        # Variables
        self.gen_carpeta_base = tk.StringVar()
        self.gen_periodo_var = tk.StringVar()
        self.gen_filtro_var = tk.StringVar()
        self.gen_formato_nombre = tk.StringVar(value="cedula-nombre")
        self.gen_dos_por_hoja = tk.BooleanVar(value=False)
        self.gen_incluir_logo = tk.BooleanVar(value=False)
        self.gen_ruta_logo = tk.StringVar()

        # Crear canvas scrolleable
        canvas = tk.Canvas(self.tab_generador, bg=self.color_bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_generador, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        # Parámetros
        params_frame = ttk.LabelFrame(scrollable_frame, text="📋 Parámetros de Generación", padding="15")
        params_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        ttk.Label(params_frame, text="Período (YYYY-MM):").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(params_frame, textvariable=self.gen_periodo_var, width=20).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(params_frame, text="Seleccionar...", command=self._gen_seleccionar_periodo).grid(row=0, column=2, pady=5)

        ttk.Label(params_frame, text="Filtro de texto (ej: FENIX):").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(params_frame, textvariable=self.gen_filtro_var, width=20).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(params_frame, text="Formato del nombre:").grid(row=2, column=0, sticky="w", pady=5)
        formato_combo = ttk.Combobox(params_frame, textvariable=self.gen_formato_nombre, width=35, state="readonly")
        formato_combo['values'] = (
            "cedula-nombre", "nombre-cedula", "cedula-nombre-cargo",
            "cedula-nombre-depto", "nombre-cargo-cedula", "depto-nombre-cedula"
        )
        formato_combo.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(params_frame, text="Opciones:").grid(row=3, column=0, sticky="w", pady=5)
        opciones_frame = ttk.Frame(params_frame)
        opciones_frame.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        ttk.Checkbutton(opciones_frame, text="2 roles por hoja", variable=self.gen_dos_por_hoja).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(opciones_frame, text="Incluir logo", variable=self.gen_incluir_logo,
                       command=self._gen_toggle_logo).pack(side=tk.LEFT)

        logo_frame = ttk.Frame(params_frame)
        logo_frame.grid(row=3, column=2, sticky="w", padx=5, pady=5)
        self.gen_boton_logo = ttk.Button(logo_frame, text="Seleccionar logo...",
                                        command=self._gen_seleccionar_logo, state=tk.DISABLED)
        self.gen_boton_logo.pack()

        ttk.Label(params_frame, text="Carpeta padre:").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(params_frame, textvariable=self.gen_carpeta_base, width=50).grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(params_frame, text="Examinar...", command=self._gen_seleccionar_carpeta).grid(row=4, column=2, pady=5)

        # Cédulas específicas
        cedulas_frame = ttk.LabelFrame(scrollable_frame, text="🔍 Filtro por Cédulas Específicas (opcional)", padding="10")
        cedulas_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        ttk.Label(cedulas_frame, text="Pegue cédulas (una por línea o separadas por comas):").pack(anchor=tk.W, pady=2)

        text_scroll_frame = ttk.Frame(cedulas_frame)
        text_scroll_frame.pack(fill=tk.X, pady=2)

        cedulas_scrollbar = ttk.Scrollbar(text_scroll_frame)
        cedulas_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.gen_cedulas_text = tk.Text(text_scroll_frame, height=4, width=70, yscrollcommand=cedulas_scrollbar.set)
        self.gen_cedulas_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        cedulas_scrollbar.config(command=self.gen_cedulas_text.yview)

        # Estado
        status_frame = ttk.LabelFrame(scrollable_frame, text="📊 Estado del Proceso", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        self.gen_etiqueta_carpeta = tk.Label(status_frame, text="📁 Subcarpeta: Ninguna seleccionada",
                                            foreground=self.color_primary, font=("Segoe UI", 9),
                                            bg=self.color_white, anchor='w')
        self.gen_etiqueta_carpeta.pack(fill=tk.X, pady=2)

        prog_frame = ttk.Frame(status_frame)
        prog_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prog_frame, text="Progreso:", font=("Segoe UI", 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        self.gen_barra_progreso = ttk.Progressbar(prog_frame, length=400, mode='determinate')
        self.gen_barra_progreso.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.gen_etiqueta_estado = tk.Label(status_frame, text="✓ Listo para generar roles",
                                           font=("Segoe UI", 9), fg='#28a745',
                                           bg=self.color_white, anchor='w')
        self.gen_etiqueta_estado.pack(fill=tk.X, pady=2)

        # Botones
        botones_frame = ttk.Frame(scrollable_frame)
        botones_frame.pack(pady=15)

        self.gen_boton_generar = ttk.Button(botones_frame, text="🚀 Generar Roles", command=self._gen_iniciar)
        self.gen_boton_generar.pack(side=tk.LEFT, padx=5, ipadx=20)

    def _gen_seleccionar_periodo(self):
        """Seleccionar período con diálogo"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Seleccionar Periodo")
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        year_var = tk.IntVar(value=datetime.now().year)
        month_var = tk.IntVar(value=datetime.now().month)
        resultado = [None, None]

        def confirmar():
            resultado[0] = year_var.get()
            resultado[1] = month_var.get()
            dialog.destroy()

        frame = ttk.Frame(dialog, padding="20 20 20 20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Seleccione el periodo", font=("Arial", 12, "bold")).pack(pady=(0, 20))

        year_frame = ttk.Frame(frame)
        year_frame.pack(fill=tk.X, pady=5)
        ttk.Label(year_frame, text="Año:").pack(side=tk.LEFT)

        años = list(range(2000, 2100))
        year_combo = ttk.Combobox(year_frame, textvariable=year_var, values=años, width=10)
        year_combo.pack(side=tk.LEFT, padx=10)
        year_combo.set(datetime.now().year)

        month_frame = ttk.Frame(frame)
        month_frame.pack(fill=tk.X, pady=5)
        ttk.Label(month_frame, text="Mes:").pack(side=tk.LEFT)

        month_values = [f"{m} - {calendar.month_name[m]}" for m in range(1, 13)]
        month_combo = ttk.Combobox(month_frame, values=month_values, width=20)
        month_combo.current(datetime.now().month - 1)
        month_combo.pack(side=tk.LEFT, padx=10)

        def actualizar_mes(event):
            month_var.set(month_combo.current() + 1)

        month_combo.bind("<<ComboboxSelected>>", actualizar_mes)

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Aceptar", command=confirmar).pack(side=tk.RIGHT, padx=5)

        dialog.focus_set()
        self.root.wait_window(dialog)

        if resultado[0] is not None and resultado[1] is not None:
            periodo_str = f"{resultado[0]}-{resultado[1]:02d}"
            self.gen_periodo_var.set(periodo_str)

    def _gen_seleccionar_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta padre")
        if carpeta:
            self.gen_carpeta_base.set(carpeta)

    def _gen_toggle_logo(self):
        if self.gen_incluir_logo.get():
            self.gen_boton_logo.config(state=tk.NORMAL)
        else:
            self.gen_boton_logo.config(state=tk.DISABLED)

    def _gen_seleccionar_logo(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar logo INSEVIG",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif"), ("Todos", "*.*")]
        )
        if archivo:
            self.gen_ruta_logo.set(archivo)

    def _gen_iniciar(self):
        if not self.gen_periodo_var.get():
            messagebox.showwarning("Advertencia", "Por favor seleccione un período")
            return

        if not self.gen_carpeta_base.get():
            messagebox.showwarning("Advertencia", "Por favor seleccione una carpeta padre")
            return

        self.gen_boton_generar.config(state=tk.DISABLED)
        self.gen_etiqueta_estado.config(text="Iniciando proceso...")

        threading.Thread(target=self._gen_ejecutar, daemon=True).start()

    def _gen_ejecutar(self):
        """Ejecutar generación de PDFs"""
        try:
            periodo = self.gen_periodo_var.get()
            year, month = periodo.split('-')

            carpeta_destino = os.path.join(self.gen_carpeta_base.get(), f"{year}-{month}")
            os.makedirs(carpeta_destino, exist_ok=True)

            self.gen_etiqueta_carpeta.config(text=f"📁 Subcarpeta: {carpeta_destino}")

            self.gen_etiqueta_estado.config(text="🔄 Conectando a la base de datos...", fg='#ff8c00')
            self.gen_barra_progreso["value"] = 10

            df_consolidado = self.generador_pdf.obtener_datos_bd(periodo)

            if df_consolidado is None or df_consolidado.empty:
                messagebox.showwarning("Advertencia", f"No se encontraron datos para el período {periodo}")
                return

            # Aplicar filtros
            cedulas_text = self.gen_cedulas_text.get("1.0", tk.END).strip()
            if cedulas_text:
                cedulas_lista = []
                for linea in cedulas_text.split('\n'):
                    for cedula in linea.split(','):
                        cedula_limpia = cedula.strip()
                        if cedula_limpia:
                            cedula_normalizada = ''.join(filter(str.isdigit, cedula_limpia))
                            if cedula_normalizada:
                                cedulas_lista.append(cedula_normalizada)

                if cedulas_lista:
                    def normalizar_cedula(x):
                        return ''.join(filter(str.isdigit, str(x)))

                    cedulas_set = set()
                    for cedula in cedulas_lista:
                        cedulas_set.add(cedula)
                        if len(cedula) == 9:
                            cedulas_set.add('0' + cedula)
                        if len(cedula) == 10 and cedula.startswith('0'):
                            cedulas_set.add(cedula[1:])
                        cedulas_set.add(cedula.zfill(10))

                    mascara = df_consolidado['CEDULA'].apply(lambda x: normalizar_cedula(x) in cedulas_set)
                    df_consolidado = df_consolidado[mascara].copy()

                    if df_consolidado.empty:
                        messagebox.showwarning("Advertencia", "No se encontraron empleados con las cédulas especificadas")
                        return
            else:
                filtro = self.gen_filtro_var.get().strip()
                if filtro:
                    df_consolidado = df_consolidado[
                        df_consolidado['APELLIDOS_NOMBRES'].str.contains(filtro, case=False, na=False) |
                        df_consolidado['CEDULA'].astype(str).str.contains(filtro, case=False, na=False) |
                        df_consolidado['CARGO'].astype(str).str.contains(filtro, case=False, na=False) |
                        df_consolidado['DEPTO'].astype(str).str.contains(filtro, case=False, na=False)
                    ]

                    if df_consolidado.empty:
                        messagebox.showwarning("Advertencia", f"No se encontraron empleados con el filtro '{filtro}'")
                        return

            _, last_day = calendar.monthrange(int(year), int(month))
            start_date = f"01/{month}/{year}"
            end_date = f"{last_day:02d}/{month}/{year}"
            period_str = f"{year}{month}"

            self.gen_etiqueta_estado.config(text="📄 Generando PDFs...", fg='#ff8c00')
            self.gen_barra_progreso["value"] = 30

            total_empleados = len(df_consolidado)

            for contador, (index, row) in enumerate(df_consolidado.iterrows()):
                progreso = int(30 + (contador / max(total_empleados, 1)) * 70)
                self.gen_barra_progreso["value"] = progreso
                self.gen_etiqueta_estado.config(text=f"📄 Generando PDF {contador+1} de {total_empleados}...", fg='#ff8c00')
                try:
                    self.root.update_idletasks()
                except:
                    pass

                filename = self._gen_nombre_archivo(row, carpeta_destino, period_str)

                logo_path = self.gen_ruta_logo.get() if self.gen_incluir_logo.get() else None
                if self.gen_dos_por_hoja.get():
                    self.generador_pdf.crear_pdf_empleado_doble(filename, row, start_date, end_date, logo_path)
                else:
                    self.generador_pdf.crear_pdf_empleado_bd(filename, row, start_date, end_date, logo_path)

            messagebox.showinfo("✅ Éxito", f"Roles de pago generados correctamente en:\n{carpeta_destino}")
            self.gen_etiqueta_estado.config(text="✅ Roles de pago generados", fg='#28a745')
            self.gen_barra_progreso["value"] = 100

        except Exception as e:
            import traceback
            error_detalle = traceback.format_exc()
            messagebox.showerror("Error", f"Error al generar roles:\n{str(e)}")
            self.gen_etiqueta_estado.config(text=f"Error: {str(e)}")
            self.gen_barra_progreso["value"] = 0

        finally:
            self.gen_boton_generar.config(state=tk.NORMAL)

    def _gen_nombre_archivo(self, row, output_folder, period_str):
        """Generar nombre de archivo según formato"""
        cedula = self.generador_pdf._format_cedula(row['CEDULA'])
        nombre_limpio = str(row['APELLIDOS_NOMBRES']).replace('/', '_').replace('\\', '_').replace(' ', '_')
        cargo_limpio = str(row['CARGO']).replace('/', '_').replace('\\', '_').replace(' ', '_')
        depto_limpio = str(row['DEPTO']).replace('/', '_').replace('\\', '_').replace(' ', '_')

        formato = self.gen_formato_nombre.get()

        if formato == "nombre-cedula":
            nombre_archivo = f"{nombre_limpio}-{cedula}_{period_str}.pdf"
        elif formato == "cedula-nombre-cargo":
            nombre_archivo = f"{cedula}-{nombre_limpio}-{cargo_limpio}_{period_str}.pdf"
        elif formato == "cedula-nombre-depto":
            nombre_archivo = f"{cedula}-{nombre_limpio}-{depto_limpio}_{period_str}.pdf"
        elif formato == "nombre-cargo-cedula":
            nombre_archivo = f"{nombre_limpio}-{cargo_limpio}-{cedula}_{period_str}.pdf"
        elif formato == "depto-nombre-cedula":
            nombre_archivo = f"{depto_limpio}-{nombre_limpio}-{cedula}_{period_str}.pdf"
        else:
            nombre_archivo = f"{cedula}-{nombre_limpio}_{period_str}.pdf"

        return f"{output_folder}/{nombre_archivo}"


if __name__ == '__main__':
    if not HAS_PDF_SUPPORT:
        print("⚠️  Falta PyMuPDF para mostrar PDF en pantalla")
        print("Instala: pip install pymupdf pillow")

    root = tk.Tk()
    app = RolesPrincipal(root)
    root.mainloop()
