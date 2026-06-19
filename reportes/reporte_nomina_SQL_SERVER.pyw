import pyodbc
import pandas as pd
import os
from datetime import datetime
import numpy as np
import warnings

warnings.filterwarnings('ignore', message='.*SQLAlchemy.*')

def obtener_nombre_cargo(conn, codigo_cargo):
    """
    Obtiene el nombre completo del cargo desde la tabla DBTABLAS
    """
    if not codigo_cargo:
        return ""
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT TOP 1 NOMBRE 
        FROM dbo.DBTABLAS 
        WHERE TIPO = 'FNC' AND CODIGO = ?
        """
        
        codigo_cargo_limpio = str(codigo_cargo).strip()
        
        cursor.execute(query, [codigo_cargo_limpio])
        resultado = cursor.fetchone()
        
        if resultado:
            return resultado[0]
        else:
            return codigo_cargo
    
    except Exception as e:
        print(f"Error al obtener nombre de cargo: {e}")
        return codigo_cargo

def obtener_nombre_departamento(conn, codigo_depto):
    """
    Obtiene el nombre completo del departamento desde la tabla DBTABLAS
    """
    if not codigo_depto:
        return ""
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT TOP 1 NOMBRE 
        FROM dbo.DBTABLAS 
        WHERE TIPO = 'DPT' AND CODIGO = ?
        """
        
        codigo_depto_limpio = str(codigo_depto).strip()
        
        cursor.execute(query, [codigo_depto_limpio])
        resultado = cursor.fetchone()
        
        if resultado:
            return resultado[0]
        else:
            return codigo_depto
    
    except Exception as e:
        print(f"Error al obtener nombre de departamento: {e}")
        return codigo_depto

def obtener_nombre_seccion(conn, codigo_seccion):
    """
    Obtiene el nombre completo de la sección desde la tabla DBTABLAS
    """
    if not codigo_seccion:
        return ""
    
    try:
        cursor = conn.cursor()
        query = """
        SELECT TOP 1 NOMBRE 
        FROM dbo.DBTABLAS 
        WHERE TIPO = 'SEC' AND CODIGO = ?
        """
        
        codigo_seccion_limpio = str(codigo_seccion).strip()
        
        cursor.execute(query, [codigo_seccion_limpio])
        resultado = cursor.fetchone()
        
        if resultado:
            return resultado[0]
        else:
            return codigo_seccion
    
    except Exception as e:
        print(f"Error al obtener nombre de sección: {e}")
        return codigo_seccion

def exportar_rpingdes_consolidado(periodo=None):
    """
    Exporta los registros de la tabla RPINGDES consolidados por empleado y período.
    VERSIÓN FINAL CORREGIDA con mapeo completo basado en análisis real de datos.
    """
    print("Exportando registros consolidados de la tabla RPINGDES...")
    
    try:
        # Parámetros de conexión
        server = 'SERVER\\server'
        database = 'insevig'
        username = 'sa'
        password = 'puntosoft123*'
        
        conn_str = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password};'
            f'Encrypt=No;'
            f'TrustServerCertificate=yes;'
            f'ApplicationIntent=ReadOnly;'
        )
        
        print("Conectando a la base de datos...")
        conn = pyodbc.connect(conn_str)
        
        # 1. Traer datos adicionales de empleados desde RPEMPLEA (solo empleados ACTIVOS)
        print("Obteniendo datos adicionales de empleados ACTIVOS...")
        query_empleados = """
        SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO], 
               [FECHA_ING], [FECHA_SAL], [CARGO], [CTA_AHO], [CTA_CTE], [ESTADO], [ANTIQUINC]
        FROM [insevig].[dbo].[RPEMPLEA]
        WHERE [ESTADO] = 'ACT'
        """
        
        df_empleados = pd.read_sql(query_empleados, conn)
        print(f"Empleados ACTIVOS obtenidos: {len(df_empleados)} registros")
        
        # Crear columna consolidada APELLIDOS + NOMBRES
        df_empleados['APELLIDOS_NOMBRES'] = df_empleados['APELLIDOS'].fillna('').astype(str) + ' ' + df_empleados['NOMBRES'].fillna('').astype(str)
        df_empleados['APELLIDOS_NOMBRES'] = df_empleados['APELLIDOS_NOMBRES'].str.strip()
        
        # LÓGICA CTA_AHO: Si no tiene CTA_AHO, usar CTA_CTE como respaldo
        print("Aplicando lógica de cuentas bancarias (CTA_AHO con respaldo CTA_CTE)...")
        def consolidar_cuenta(row):
            cta_aho = str(row['CTA_AHO']).strip() if pd.notna(row['CTA_AHO']) else ''
            cta_cte = str(row['CTA_CTE']).strip() if pd.notna(row['CTA_CTE']) else ''
            
            # Si CTA_AHO tiene valor, usarlo; sino usar CTA_CTE
            if cta_aho and cta_aho != 'nan':
                return cta_aho
            elif cta_cte and cta_cte != 'nan':
                return cta_cte
            else:
                return ''
        
        df_empleados['CTA_AHO_CONSOLIDADA'] = df_empleados.apply(consolidar_cuenta, axis=1)
        
        # Contar casos de respaldo
        respaldos = len(df_empleados[(df_empleados['CTA_AHO'].isna() | (df_empleados['CTA_AHO'] == '')) & 
                                    (df_empleados['CTA_CTE'].notna() & (df_empleados['CTA_CTE'] != ''))])
        print(f"Empleados usando CTA_CTE como respaldo: {respaldos}")
        
        # 2. Traer datos de movimientos desde RPINGDES
        print("Ejecutando consulta de movimientos...")
        query = """
        SELECT [NUMERO], [FECHA], [EMPLEADO], [CODSUC], [CODEMP], [CODIGO], [CLASE],
               [SECUENCIA], [DEPTO], [SECCION], [HORAS], [VALOR], [FECHA_VEN], 
               [CONCEPTO], [DIAS], [ASENTADO], [ACTUALIZA], [APORTA], [MONTO],
               [DIVIDENDO], [ROL], [TIPO_PGO], [TIPO_TRA], [OBSERV]
        FROM [insevig].[dbo].[RPINGDES]
        WHERE [FECHA_VEN] IS NOT NULL
        """
        
        df = pd.read_sql(query, conn)
        
        print(f"Registros encontrados: {len(df)}")
        
        if df.empty:
            print("No se encontraron datos.")
            conn.close()
            return None
        
        # Procesar fechas
        print("Procesando fechas...")
        df['FECHA_VEN'] = pd.to_datetime(df['FECHA_VEN'], errors='coerce')
        df['PERIODO'] = df['FECHA_VEN'].dt.strftime('%Y-%m')
        
        # Mostrar períodos disponibles
        periodos_disponibles = df['PERIODO'].dropna().value_counts().sort_index()
        print("Períodos disponibles:")
        for per, count in periodos_disponibles.tail(10).items():
            print(f"  {per}: {count} registros")
        
        # Filtrar por período exacto (día 1 al último día del mes)
        if periodo:
            # Crear rango de fechas exacto para el período
            año, mes = periodo.split('-')
            fecha_inicio = pd.Timestamp(f'{año}-{mes}-01')
            # Último día del mes
            if mes == '12':
                fecha_fin = pd.Timestamp(f'{int(año)+1}-01-01') - pd.Timedelta(days=1)
            else:
                fecha_fin = pd.Timestamp(f'{año}-{int(mes)+1:02d}-01') - pd.Timedelta(days=1)
            
            # Filtrar por rango exacto de fechas
            df_filtrado = df[(df['FECHA_VEN'] >= fecha_inicio) & (df['FECHA_VEN'] <= fecha_fin)]
            print(f"Registros para período EXACTO {periodo} ({fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}): {len(df_filtrado)}")
            
            if df_filtrado.empty:
                print(f"No se encontraron datos para el período exacto {periodo}")
                conn.close()
                return None
            df = df_filtrado
        
        # Filtrar registros válidos
        df = df.dropna(subset=['PERIODO', 'EMPLEADO'])
        print(f"Registros válidos para procesar: {len(df)}")
        
        # Limpiar campo CLASE
        df['CLASE'] = pd.to_numeric(df['CLASE'], errors='coerce')
        df = df.dropna(subset=['CLASE'])
        df['CLASE'] = df['CLASE'].astype(int)
        
        # Códigos que se IGNORAN COMPLETAMENTE (no se consideran para nada)
        codigos_ignorar = {105, 126, 199}  # VACACIONES, APORT.PATRONAL, IECE-SECAP
        
        # ¡MAPEO COMPLETO Y CORREGIDO basado en análisis real!
        mapeo_conceptos = {
            # INGRESOS
            100: 'SUELDO',                    # SUELDO
            102: 'BONIFICACION',              # BONIFICACION OTROS INGRESOS
            104: 'FONDO_RESERVA',             # FONDO DE RESERVA
            # 105: IGNORAR - VACACIONES ANUALES (no se considera)
            107: 'DECIMO_TERCERA',            # DECIMO TERCERA REMUNERACION
            108: 'DECIMO_CUARTA',             # DECIMO CUARTA REMUNERACION
            110: 'MANIOBRAS',                 # MANIOBRAS
            111: 'REEMBOLSOS',                # REEMBOLSOS
            113: 'SOBRETIEMPO_25',            # SOBRETIEMPO 25%
            114: 'SOBRETIEMPO_50',            # SOBRETIEMPO 50%
            115: 'SOBRETIEMPO_100',           # SOBRETIEMPO 100%
            120: 'MOVILIZACION',              # MOVILIZACION
            # 126: IGNORAR - APORT.PATRONAL SECAP (no se considera)
            # 199: IGNORAR - IECE-SECAP (no se considera)
            
            # EGRESOS
            200: 'APORT_IESS',                # APORT.IESS
            201: 'ANTICIPOS_OTROS',           # ANTICIPO MOV -> ANTICIPOS_OTROS
            202: 'ANTICIPO_SUELDO',           # ANTICIPO DE SUELDO
            203: 'MULTAS',                    # MULTAS
            204: 'PRESTAMOS_QUIROGRAFARIOS',  # PRESTAMOS QUIROGRAFARIOS
            205: 'PRESTAMOS_COMPANIA',        # PRESTAMOS COMPANIA
            206: 'PENSION_ALIMENTICIA',       # PENSION ALIMENTICIA
            207: 'PRESTAMO_HIPOTECARIO',      # PRESTAMO HIPOTECARIO
            217: 'ANTICIPOS_OTROS',           # ANTICIPOS OTROS
            218: 'APORT_IESS_CONYUGE',        # APORT.IESS CONYUGE
            219: 'IMPUESTO_RENTA',            # IMPUESTO A LA RENTA
            250: 'ANTICIPOS_SURTIDOS',        # ANTICIPOS SURTIDOS
        }
        
        print("Procesando empleados...")
        empleados_unicos = df['EMPLEADO'].nunique()
        print(f"Empleados a procesar: {empleados_unicos}")
        
        resultados = []
        
        # Agrupar por empleado y período
        grupos = df.groupby(['EMPLEADO', 'PERIODO'])
        print(f"Procesando {len(grupos)} combinaciones empleado-período...")
        
        procesados = 0
        for (empleado, periodo_val), grupo in grupos:
            procesados += 1
            if procesados % 100 == 0 or procesados <= 5:
                print(f"Procesando {procesados}/{len(grupos)}: {empleado}")
            
            fila = {
                'EMPLEADO': empleado,
                'APELLIDOS_NOMBRES': '',  # Se llenará después con el JOIN
                'CEDULA': '',
                'SUELDO_BASE': 0.0,  # Sueldo de RPEMPLEA
                'FECHA_ING': '',
                'FECHA_SAL': '',
                'CARGO': '',  # Se llenará con el nombre del cargo
                'CTA_AHO': '',
                'PERIODO': periodo_val,
                'DEPTO': grupo['DEPTO'].iloc[0],  # Se reemplazará por el nombre
                'SECCION': grupo['SECCION'].iloc[0],  # Se reemplazará por el nombre
                'DIAS': 0
            }
            
            # Definir conceptos (SIN OTROS_INGRESOS)
            conceptos_ingresos = [
                'SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 
                'DECIMO_TERCERA', 'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS',
                'SOBRETIEMPO_25', 'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 
                'MOVILIZACION'
            ]
            
            # Egresos en el orden especificado
            conceptos_egresos = [
                'APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
                'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO'
            ]
            
            # Inicializar todos los conceptos en 0
            for concepto in conceptos_ingresos + conceptos_egresos:
                fila[concepto] = 0.0
            
            # Procesar cada registro del grupo
            for _, registro in grupo.iterrows():
                clase_codigo = registro['CLASE']      # Código real (100, 102, etc.)
                tipo_movimiento = registro['CODIGO']  # Tipo ('ING' o 'EGR')
                
                # IGNORAR COMPLETAMENTE ciertos códigos
                if clase_codigo in codigos_ignorar:
                    continue  # Saltar este registro sin procesarlo
                
                valor = registro['VALOR'] if pd.notna(registro['VALOR']) else 0
                monto = registro['MONTO'] if pd.notna(registro['MONTO']) else 0
                asentado = registro['ASENTADO']
                
                # USAR SOLO VALOR del período específico (no MONTO que puede incluir saldos)
                cantidad = valor
                
                # Verificar si el código está mapeado
                if clase_codigo in mapeo_conceptos:
                    concepto = mapeo_conceptos[clase_codigo]
                    
                    # Aplicar reglas especiales
                    if concepto in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                        # Solo considerar si ASENTADO es verdadero
                        if asentado:
                            fila[concepto] += round(cantidad, 2)
                    elif concepto == 'SUELDO':
                        fila[concepto] += round(cantidad, 2)
                        # Para DIAS, tomar el valor del concepto SUELDO
                        if pd.notna(registro['DIAS']):
                            fila['DIAS'] = registro['DIAS']
                    else:
                        # Todos los demás conceptos se suman directamente
                        if concepto in conceptos_ingresos + conceptos_egresos:
                            fila[concepto] += round(cantidad, 2)
                else:
                    # Códigos no mapeados: solo egresos van a ANTICIPOS_SURTIDOS, ingresos se ignoran
                    if tipo_movimiento == 'EGR':
                        fila['ANTICIPOS_SURTIDOS'] += round(cantidad, 2)
                    # Los ingresos no mapeados se ignoran (no hay OTROS_INGRESOS)
            
            # Calcular totales (redondeados a 2 decimales)
            total_ingresos = round(sum(fila[concepto] for concepto in conceptos_ingresos), 2)
            total_egresos = round(sum(fila[concepto] for concepto in conceptos_egresos), 2)
            
            fila['TOTAL_INGRESOS'] = total_ingresos
            fila['TOTAL_EGRESOS'] = total_egresos
            fila['TOTAL_RECIBIR'] = round(total_ingresos - total_egresos, 2)
            
            resultados.append(fila)
        
        print(f"Procesamiento completado. {len(resultados)} registros consolidados generados.")
        
        # Convertir a DataFrame y redondear valores numéricos
        if not resultados:
            print("No se generaron resultados consolidados.")
            conn.close()
            return None
            
        df_consolidado = pd.DataFrame(resultados)
        
        # HACER JOIN con datos de empleados (solo empleados ACTIVOS)
        print("Combinando con datos adicionales de empleados ACTIVOS...")
        df_consolidado = df_consolidado.merge(
            df_empleados[['EMPLEADO', 'APELLIDOS_NOMBRES', 'CEDULA', 'SUELDO', 'FECHA_ING', 'FECHA_SAL', 'CARGO', 'CTA_AHO_CONSOLIDADA', 'ANTIQUINC']], 
            on='EMPLEADO', 
            how='inner',  # Solo empleados que existen en RPEMPLEA y están ACTIVOS
            suffixes=('', '_RPEMPLEA')
        )
        
        print(f"Empleados procesados después del filtro ACTIVOS: {len(df_consolidado)}")
        
        # Verificar columnas disponibles después del merge
        print("Columnas disponibles después del merge:", list(df_consolidado.columns))
        
        # Manejar ANTIQUINC correctamente (puede venir como ANTIQUINC o ANTIQUINC_RPEMPLEA)
        if 'ANTIQUINC_RPEMPLEA' in df_consolidado.columns:
            antiquinc_col = 'ANTIQUINC_RPEMPLEA'
        elif 'ANTIQUINC' in df_consolidado.columns:
            antiquinc_col = 'ANTIQUINC'
        else:
            print("⚠️ Columna ANTIQUINC no encontrada, usando valor por defecto 1")
            df_consolidado['ANTIQUINC'] = 1
            antiquinc_col = 'ANTIQUINC'
        
        # Manejar CTA_AHO_CONSOLIDADA correctamente (puede venir como CTA_AHO_CONSOLIDADA o CTA_AHO_CONSOLIDADA_RPEMPLEA)
        if 'CTA_AHO_CONSOLIDADA_RPEMPLEA' in df_consolidado.columns:
            cuenta_col = 'CTA_AHO_CONSOLIDADA_RPEMPLEA'
        elif 'CTA_AHO_CONSOLIDADA' in df_consolidado.columns:
            cuenta_col = 'CTA_AHO_CONSOLIDADA'
        else:
            print("⚠️ Columna CTA_AHO_CONSOLIDADA no encontrada")
            cuenta_col = None
        
        # Actualizar campos con datos de RPEMPLEA
        df_consolidado['APELLIDOS_NOMBRES'] = df_consolidado['APELLIDOS_NOMBRES_RPEMPLEA'].fillna('')
        df_consolidado['CEDULA'] = df_consolidado['CEDULA_RPEMPLEA'].fillna('')
        df_consolidado['SUELDO_BASE'] = df_consolidado['SUELDO_RPEMPLEA'].fillna(0.0)
        df_consolidado['FECHA_ING'] = df_consolidado['FECHA_ING_RPEMPLEA'].fillna('')
        df_consolidado['FECHA_SAL'] = df_consolidado['FECHA_SAL_RPEMPLEA'].fillna('')
        
        # Guardar los códigos originales para obtener los nombres
        codigo_cargo_temp = df_consolidado['CARGO'].copy()  # Guardar CARGO original
        df_consolidado['CARGO'] = df_consolidado['CARGO_RPEMPLEA'].fillna('')  # Actualizar con CARGO de RPEMPLEA
        
        # Usar cuenta consolidada si existe
        if cuenta_col:
            df_consolidado['CTA_AHO'] = df_consolidado[cuenta_col].fillna('')
        else:
            df_consolidado['CTA_AHO'] = ''
        
        # APLICAR LÓGICA DE ANTIQUINC para FONDO_RESERVA
        print("Aplicando lógica ANTIQUINC para FONDO_RESERVA...")
        df_consolidado.loc[df_consolidado[antiquinc_col] == 0, 'FONDO_RESERVA'] = 0.00
        antiguedad_ceros = len(df_consolidado[df_consolidado[antiquinc_col] == 0])
        print(f"Empleados con ANTIQUINC=0 (FONDO_RESERVA=0): {antiguedad_ceros}")
        
        # RECALCULAR TOTALES después de aplicar lógica ANTIQUINC
        print("Recalculando totales después de aplicar lógica ANTIQUINC...")
        for idx in df_consolidado.index:
            # Recalcular TOTAL_INGRESOS
            total_ingresos_nuevo = round(sum(df_consolidado.loc[idx, concepto] for concepto in conceptos_ingresos), 2)
            df_consolidado.loc[idx, 'TOTAL_INGRESOS'] = total_ingresos_nuevo
            
            # Recalcular TOTAL_RECIBIR (TOTAL_INGRESOS - TOTAL_EGRESOS)
            total_egresos = df_consolidado.loc[idx, 'TOTAL_EGRESOS']
            df_consolidado.loc[idx, 'TOTAL_RECIBIR'] = round(total_ingresos_nuevo - total_egresos, 2)
        
        print("Totales recalculados correctamente.")
        
        # Obtener nombres descriptivos para CARGO, DEPTO y SECCION
        print("Obteniendo nombres descriptivos para CARGO, DEPTO y SECCION...")
        
        # Obtener nombres descriptivos y reemplazar las columnas de código
        for idx in df_consolidado.index:
            # Obtener nombre de CARGO
            if pd.notna(df_consolidado.loc[idx, 'CARGO']) and df_consolidado.loc[idx, 'CARGO'] != '':
                df_consolidado.loc[idx, 'CARGO'] = obtener_nombre_cargo(conn, df_consolidado.loc[idx, 'CARGO'])
            else:
                df_consolidado.loc[idx, 'CARGO'] = ''
            
            # Obtener nombre de DEPTO
            if pd.notna(df_consolidado.loc[idx, 'DEPTO']) and df_consolidado.loc[idx, 'DEPTO'] != '':
                df_consolidado.loc[idx, 'DEPTO'] = obtener_nombre_departamento(conn, df_consolidado.loc[idx, 'DEPTO'])
            else:
                df_consolidado.loc[idx, 'DEPTO'] = ''
            
            # Obtener nombre de SECCION
            if pd.notna(df_consolidado.loc[idx, 'SECCION']) and df_consolidado.loc[idx, 'SECCION'] != '':
                df_consolidado.loc[idx, 'SECCION'] = obtener_nombre_seccion(conn, df_consolidado.loc[idx, 'SECCION'])
            else:
                df_consolidado.loc[idx, 'SECCION'] = ''
        
        # Cerrar la conexión a la base de datos
        conn.close()
        
        # Eliminar columnas duplicadas del merge
        columnas_a_eliminar = [col for col in df_consolidado.columns if col.endswith('_RPEMPLEA')] + [antiquinc_col]
        if cuenta_col and cuenta_col in df_consolidado.columns:
            columnas_a_eliminar.append(cuenta_col)
        df_consolidado = df_consolidado.drop(columns=columnas_a_eliminar)
        
        # Redondear todas las columnas numéricas a 2 decimales
        columnas_numericas = conceptos_ingresos + conceptos_egresos + ['TOTAL_INGRESOS', 'TOTAL_EGRESOS', 'TOTAL_RECIBIR', 'SUELDO_BASE']
        for col in columnas_numericas:
            if col in df_consolidado.columns:
                df_consolidado[col] = df_consolidado[col].round(2)
        
        # Ordenar columnas con el nuevo orden solicitado
        columnas_ordenadas = (
            ['PERIODO', 'EMPLEADO', 'APELLIDOS_NOMBRES', 'CARGO', 'SUELDO_BASE', 'DEPTO',
             'CEDULA', 'CTA_AHO', 'SECCION', 'FECHA_ING', 'FECHA_SAL', 'DIAS'] + 
            conceptos_ingresos + ['TOTAL_INGRESOS'] + 
            conceptos_egresos + ['TOTAL_EGRESOS', 'TOTAL_RECIBIR']
        )
        
        # Reordenar columnas (mantener solo las que existen)
        columnas_existentes = [col for col in columnas_ordenadas if col in df_consolidado.columns]
        df_consolidado = df_consolidado[columnas_existentes]
        
        # Crear archivo Excel
        sufijo_periodo = f"_{periodo}" if periodo else "_TODOS"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_excel = f"RPINGDES_CONSOLIDADO{sufijo_periodo}_{timestamp}.xlsx"
        
        print(f"Creando archivo Excel: {archivo_excel}")
        
        with pd.ExcelWriter(archivo_excel, engine='xlsxwriter') as writer:
            df_consolidado.to_excel(writer, sheet_name='Consolidado', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Consolidado']
            
            # Formatos
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # Formato para números con exactamente 2 decimales
            money_format = workbook.add_format({'num_format': '0.00'})
            
            # Aplicar formato a encabezados
            for col_num, value in enumerate(df_consolidado.columns.values):
                worksheet.write(0, col_num, value, header_format)
            
            # Aplicar formato monetario a columnas numéricas (excluyendo campos de texto)
            for col_num, col_name in enumerate(df_consolidado.columns):
                if col_name in columnas_numericas:
                    worksheet.set_column(col_num, col_num, 12, money_format)
                else:
                    worksheet.set_column(col_num, col_num, 15)
        
        print(f"Archivo Excel guardado exitosamente: {archivo_excel}")
        
        return df_consolidado
        
    except Exception as e:
        print(f"Error en exportar_rpingdes_consolidado: {e}")
        import traceback
        traceback.print_exc()
        return None

# Función principal
if __name__ == "__main__":
    # Solicitar período
    periodo = input("Ingrese el período (YYYY-MM) o deje en blanco para todos: ").strip()
    if not periodo:
        periodo = None
    
    # Exportar datos consolidados
    df_consolidado = exportar_rpingdes_consolidado(periodo)
    
    if df_consolidado is not None:
        print("Exportación completada exitosamente.")
        print(f"Registros procesados: {len(df_consolidado)}")
    else:
        print("No se pudo completar la exportación debido a errores.")
