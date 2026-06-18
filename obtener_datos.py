"""
MÓDULO DE OBTENCIÓN DE DATOS - Reutilizable para todos los programas
Contiene la lógica de búsqueda de empleados y consolidación de datos de nómina
"""

import pyodbc
import pandas as pd

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
        Mucho más rápido que obtener_datos_bd para búsquedas individuales.

        Args:
            periodo: String 'YYYY-MM'
            cedula_o_nombre: Cédula o nombre del empleado a buscar

        Returns:
            pandas.Series con datos del empleado o None si no encontrado
        """
        try:
            print("⚡ Búsqueda rápida de empleado...")
            conn = self._get_connection()

            # 1. Buscar el empleado por EMPLEADO, CEDULA o nombre
            # Primero intenta por EMPLEADO (código corto como '1012')
            if len(str(cedula_o_nombre)) <= 6:
                # Probablemente es un EMPLEADO
                query_emp = f"""
                SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                       [CARGO], [DEPTO], [SECCION]
                FROM [insevig].[dbo].[RPEMPLEA]
                WHERE {self.sql_filter} AND [ESTADO]='ACT' AND [EMPLEADO] = ?
                """
                df_emp = pd.read_sql(query_emp, conn, params=[str(cedula_o_nombre)])

                # Si no encuentra por EMPLEADO, intenta por CEDULA o nombre
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
                # Probablemente es una CEDULA o nombre
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

            # 2. Obtener movimientos SOLO de este empleado
            año, mes = periodo.split('-')
            fecha_inicio = f'{año}-{mes}-01'
            if mes == '12':
                año_fin = int(año) + 1
                mes_fin = 1
            else:
                año_fin = int(año)
                mes_fin = int(mes) + 1
            fecha_fin = f'{año_fin}-{mes_fin:02d}-01'

            # RPINGDES
            # Usar CAST para comparar como DATE (sin hora) o usar CONVERT
            query_mov = f"""
            SELECT *
            FROM [insevig].[dbo].[RPINGDES]
            WHERE {self.sql_filter} AND [EMPLEADO] = ?
                  AND [FECHA_VEN] IS NOT NULL
                  AND CAST([FECHA_VEN] AS DATE) >= CAST(? AS DATE)
                  AND CAST([FECHA_VEN] AS DATE) < CAST(? AS DATE)
            """
            df_mov = pd.read_sql(query_mov, conn, params=[empleado_code, fecha_inicio, fecha_fin])

            # Si no hay en RPINGDES, buscar en RPHISTOR
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

            # 3. Consolidar movimientos usando la misma lógica que obtener_datos_bd
            conceptos = {}
            # Mapeo de códigos REALES de CLASE en RPINGDES
            mapeo_conceptos = {
                100: 'SUELDO', 102: 'BONIFICACION', 115: 'FONDO_RESERVA',
                104: 'DECIMO_TERCERA', 103: 'DECIMO_CUARTA',
                106: 'MANIOBRAS', 107: 'REEMBOLSOS',
                108: 'SOBRETIEMPO_25', 112: 'SOBRETIEMPO_50', 113: 'SOBRETIEMPO_100',
                114: 'MOVILIZACION',
                200: 'APORT_IESS', 202: 'PRESTAMOS_QUIROGRAFARIOS',
                203: 'PRESTAMOS_COMPANIA', 204: 'ANTICIPO_SUELDO',
                205: 'ANTICIPOS_OTROS', 250: 'ANTICIPOS_SURTIDOS',
                207: 'APORT_IESS_CONYUGE', 208: 'IMPUESTO_RENTA',
                209: 'MULTAS', 210: 'PENSION_ALIMENTICIA', 211: 'PRESTAMO_HIPOTECARIO'
            }

            for idx, row in df_mov.iterrows():
                clase = int(row['CLASE']) if pd.notna(row['CLASE']) else 0
                valor = float(row['VALOR']) if pd.notna(row['VALOR']) else 0

                if clase not in [105, 126, 199]:  # ignorar ciertos códigos
                    concepto = mapeo_conceptos.get(clase, f'CONCEPTO_{clase}')
                    conceptos[concepto] = conceptos.get(concepto, 0) + valor

            # 4. Obtener DIAS para SUELDO
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

            # Agregar todos los conceptos
            resultado.update(conceptos)

            conn.close()

            # Retornar como pandas Series para compatibilidad
            return pd.Series(resultado)

        except Exception as e:
            print(f"❌ Error en búsqueda rápida: {e}")
            import traceback
            traceback.print_exc()
            return None
