"""
REPORTE DE ROL GENERAL - NOMINA 7
Lee desde Supabase (principal) y verifica contra SQL Server
Produce el mismo Excel que REPORTE_ROL_GENERAL_NOMINA_6_.pyw
"""
import os, hashlib, warnings, sys, io
from datetime import datetime, date
from decimal import Decimal
import pandas as pd
import numpy as np
import pyodbc
from supabase import create_client

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

warnings.filterwarnings('ignore', message='.*SQLAlchemy.*')

# ── Credenciales ───────────────────────────────────────────────
SQL_CONN = "DRIVER={SQL Server};SERVER=SERVER\server;DATABASE=insevig;UID=sa;PWD=puntosoft123*"
SUPABASE_URL = "https://buzcapcwmksasrtjofae.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1emNhcGN3bWtzYXNydGpvZmFlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTk5NjgzNywiZXhwIjoyMDY1NTcyODM3fQ.gD_Qz6i2WzFqofBclS8BERVN-mALCzhFFS83IsKi1Rg"

# ── Mapeo de conceptos (idéntico al original) ─────────────────
CODIGOS_IGNORAR = {105, 126, 199}

MAPEO_CONCEPTOS = {
    100: 'SUELDO',
    102: 'BONIFICACION',
    104: 'FONDO_RESERVA',
    107: 'DECIMO_TERCERA',
    108: 'DECIMO_CUARTA',
    110: 'MANIOBRAS',
    111: 'REEMBOLSOS',
    113: 'SOBRETIEMPO_25',
    114: 'SOBRETIEMPO_50',
    115: 'SOBRETIEMPO_100',
    120: 'MOVILIZACION',
    200: 'APORT_IESS',
    201: 'ANTICIPOS_OTROS',
    202: 'ANTICIPO_SUELDO',
    203: 'MULTAS',
    204: 'PRESTAMOS_QUIROGRAFARIOS',
    205: 'PRESTAMOS_COMPANIA',
    206: 'PENSION_ALIMENTICIA',
    207: 'PRESTAMO_HIPOTECARIO',
    217: 'ANTICIPOS_OTROS',
    218: 'APORT_IESS_CONYUGE',
    219: 'IMPUESTO_RENTA',
    250: 'ANTICIPOS_SURTIDOS',
}

CONCEPTOS_INGRESOS = [
    'SUELDO', 'BONIFICACION', 'FONDO_RESERVA',
    'DECIMO_TERCERA', 'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS',
    'SOBRETIEMPO_25', 'SOBRETIEMPO_50', 'SOBRETIEMPO_100',
    'MOVILIZACION'
]

CONCEPTOS_EGRESOS = [
    'APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
    'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
    'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
    'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO'
]

COLUMNAS_NUMERICAS = CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS + [
    'TOTAL_INGRESOS', 'TOTAL_EGRESOS', 'TOTAL_RECIBIR', 'SUELDO_BASE'
]

COLUMNAS_ORDENADAS = (
    ['PERIODO', 'EMPLEADO', 'APELLIDOS_NOMBRES', 'CARGO', 'SUELDO_BASE',
     'DEPTO', 'CEDULA', 'CTA_AHO', 'SECCION', 'FECHA_ING', 'FECHA_SAL', 'DIAS'] +
    CONCEPTOS_INGRESOS + ['TOTAL_INGRESOS'] +
    CONCEPTOS_EGRESOS + ['TOTAL_EGRESOS', 'TOTAL_RECIBIR']
)

# ── Conexiones ──────────────────────────────────────────────────
_conexiones = {}

def conectar_sql():
    if 'sql' not in _conexiones:
        _conexiones['sql'] = pyodbc.connect(SQL_CONN)
    return _conexiones['sql']

def conectar_supabase():
    if 'supa' not in _conexiones:
        _conexiones['supa'] = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _conexiones['supa']

def cerrar_conexiones():
    if 'sql' in _conexiones:
        _conexiones['sql'].close()
    _conexiones.clear()

# ── Lectura de datos ────────────────────────────────────────────

def _paginar_supabase(tabla, cols, filtros=None):
    """Obtiene TODOS los registros de Supabase manejando paginacion (limite 1000)"""
    s = conectar_supabase()
    query = s.table(tabla).select(cols)
    if filtros:
        for f in filtros:
            query = query.eq(f[0], f[1])
    todos = []
    offset = 0
    while True:
        r = query.range(offset, offset + 999).execute()
        if not r.data:
            break
        todos.extend(r.data)
        offset += 1000
        if len(r.data) < 1000:
            break
    return todos

def _paginar_supabase_fechas(tabla, cols, campo_fecha, desde, hasta):
    """Obtiene TODOS los registros filtrando por rango de fechas"""
    s = conectar_supabase()
    query = s.table(tabla).select(cols).gte(campo_fecha, desde).lte(campo_fecha, hasta)
    todos = []
    offset = 0
    while True:
        r = query.range(offset, offset + 999).execute()
        if not r.data:
            break
        todos.extend(r.data)
        offset += 1000
        if len(r.data) < 1000:
            break
    return todos

def leer_empleados(origen='supabase'):
    """Lee empleados ACTIVOS con datos personales y bancarios"""
    print(f"Obteniendo empleados ACTIVOS desde {origen}...")
    
    if origen == 'supabase':
        data = _paginar_supabase('rpemplea', '*', [('estado', 'ACT')])
        df = pd.DataFrame(data)
    else:
        conn = conectar_sql()
        q = """
        SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
               [FECHA_ING], [FECHA_SAL], [CARGO], [CTA_AHO], [CTA_CTE],
               [ESTADO], [ANTIQUINC]
        FROM [insevig].[dbo].[RPEMPLEA]
        WHERE [ESTADO] = 'ACT'
        """
        df = pd.read_sql(q, conn)
    
    df.columns = [c.upper() for c in df.columns]
    
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS'].fillna('').astype(str) + ' ' + df['NOMBRES'].fillna('').astype(str)
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS_NOMBRES'].str.strip()
    
    def consolidar_cuenta(row):
        cta_aho = str(row['CTA_AHO']).strip() if pd.notna(row['CTA_AHO']) else ''
        cta_cte = str(row['CTA_CTE']).strip() if pd.notna(row['CTA_CTE']) else ''
        if cta_aho and cta_aho != 'nan':
            return cta_aho
        elif cta_cte and cta_cte != 'nan':
            return cta_cte
        return ''
    
    df['CTA_AHO_CONSOLIDADA'] = df.apply(consolidar_cuenta, axis=1)
    
    respaldos = len(df[
        (df['CTA_AHO'].isna() | (df['CTA_AHO'] == '')) &
        (df['CTA_CTE'].notna() & (df['CTA_CTE'] != ''))
    ])
    print(f"  Empleados ACTIVOS: {len(df)} | Usan CTA_CTE respaldo: {respaldos}")
    return df


def leer_movimientos(periodo, origen='supabase'):
    """Lee movimientos de RPINGDES/rpingdes para el periodo"""
    print(f"Obteniendo movimientos desde {origen} para {periodo}...")
    
    if origen == 'supabase':
        año, mes = periodo.split('-')
        ultimo_dia = pd.Timestamp(f'{año}-{int(mes)+1:02d}-01') - pd.Timedelta(days=1) if mes != '12' else pd.Timestamp(f'{int(año)+1}-01-01') - pd.Timedelta(days=1)
        data = _paginar_supabase_fechas('rpingdes', '*', 'fecha_ven', f'{periodo}-01', str(ultimo_dia.date()))
        df = pd.DataFrame(data)
    else:
        conn = conectar_sql()
        año, mes = periodo.split('-')
        q = f"""
        SELECT [NUMERO], [FECHA], [EMPLEADO], [CODSUC], [CODEMP], [CODIGO], [CLASE],
               [SECUENCIA], [DEPTO], [SECCION], [HORAS], [VALOR], [FECHA_VEN],
               [CONCEPTO], [DIAS], [ASENTADO], [ACTUALIZA], [APORTA], [MONTO],
               [DIVIDENDO], [ROL], [TIPO_PGO], [TIPO_TRA], [OBSERV]
        FROM [insevig].[dbo].[RPINGDES]
        WHERE [FECHA_VEN] IS NOT NULL
          AND YEAR([FECHA_VEN]) = {año} AND MONTH([FECHA_VEN]) = {int(mes)}
        """
        df = pd.read_sql(q, conn)
    
    df.columns = [c.upper() for c in df.columns]
    print(f"  Movimientos encontrados: {len(df)}")
    return df


def prefijar_catalogos(origen):
    """Precarga todos los nombres de dbtablas en un dict para acceso O(1)"""
    print(f"  Precargando catalogos desde {origen}...")
    catalogo = {}
    if origen == 'supabase':
        data = _paginar_supabase('dbtablas', 'tipo,codigo,nombre')
    else:
        conn = conectar_sql()
        cursor = conn.cursor()
        cursor.execute("SELECT TIPO, CODIGO, NOMBRE FROM DBTABLAS")
        data = [{'tipo': r[0], 'codigo': r[1], 'nombre': r[2]} for r in cursor.fetchall()]
    for d in data:
        key = (str(d['tipo']).strip(), str(d['codigo']).strip())
        catalogo[key] = d['nombre'] or d['codigo']
    print(f"    {len(catalogo)} registros cargados")
    return catalogo


# ── Procesamiento (compartido ambos orígenes) ──────────────────

def procesar_reporte(df_mov, df_emp, origen):
    """Procesa movimientos y empleados → DataFrame consolidado"""
    resultados = []
    
    df_mov['FECHA_VEN'] = pd.to_datetime(df_mov['FECHA_VEN'], errors='coerce')
    df_mov['PERIODO'] = df_mov['FECHA_VEN'].dt.strftime('%Y-%m')
    df_mov = df_mov.dropna(subset=['PERIODO', 'EMPLEADO'])
    df_mov['CLASE'] = pd.to_numeric(df_mov['CLASE'], errors='coerce')
    df_mov = df_mov.dropna(subset=['CLASE'])
    df_mov['CLASE'] = df_mov['CLASE'].astype(int)
    
    grupos = df_mov.groupby(['EMPLEADO', 'PERIODO'])
    print(f"  Procesando {len(grupos)} grupos empleado-periodo...")
    
    procesados = 0
    for (empleado, periodo_val), grupo in grupos:
        procesados += 1
        if procesados % 100 == 0 or procesados <= 5:
            print(f"    {procesados}/{len(grupos)}: {empleado}")
        
        fila = {
            'EMPLEADO': empleado, 'APELLIDOS_NOMBRES': '', 'CEDULA': '',
            'SUELDO_BASE': 0.0, 'FECHA_ING': '', 'FECHA_SAL': '', 'CARGO': '',
            'CTA_AHO': '', 'PERIODO': periodo_val,
            'DEPTO': grupo['DEPTO'].iloc[0] if pd.notna(grupo['DEPTO'].iloc[0]) else '',
            'SECCION': grupo['SECCION'].iloc[0] if pd.notna(grupo['SECCION'].iloc[0]) else '',
            'DIAS': 0
        }
        
        for c in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
            fila[c] = 0.0
        
        for _, reg in grupo.iterrows():
            clase = reg['CLASE']
            tipo = reg['CODIGO']
            if clase in CODIGOS_IGNORAR:
                continue
            
            valor = reg['VALOR'] if pd.notna(reg['VALOR']) else 0
            cantidad = valor
            asentado = reg['ASENTADO']
            
            if clase in MAPEO_CONCEPTOS:
                concepto = MAPEO_CONCEPTOS[clase]
                if concepto in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                    if asentado:
                        fila[concepto] += round(cantidad, 2)
                elif concepto == 'SUELDO':
                    fila[concepto] += round(cantidad, 2)
                    if pd.notna(reg['DIAS']):
                        fila['DIAS'] = reg['DIAS']
                else:
                    if concepto in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
                        fila[concepto] += round(cantidad, 2)
            else:
                if tipo == 'EGR':
                    fila['ANTICIPOS_SURTIDOS'] += round(cantidad, 2)
        
        total_ing = round(sum(fila[c] for c in CONCEPTOS_INGRESOS), 2)
        total_egr = round(sum(fila[c] for c in CONCEPTOS_EGRESOS), 2)
        fila['TOTAL_INGRESOS'] = total_ing
        fila['TOTAL_EGRESOS'] = total_egr
        fila['TOTAL_RECIBIR'] = round(total_ing - total_egr, 2)
        resultados.append(fila)
    
    df = pd.DataFrame(resultados)
    
    df = df.merge(
        df_emp[['EMPLEADO', 'APELLIDOS_NOMBRES', 'CEDULA', 'SUELDO',
                'FECHA_ING', 'FECHA_SAL', 'CARGO', 'CTA_AHO_CONSOLIDADA', 'ANTIQUINC']],
        on='EMPLEADO', how='inner', suffixes=('', '_EMP')
    )
    print(f"  Despues de filtro ACTIVOS: {len(df)} empleados")
    
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS_NOMBRES_EMP'].fillna('')
    df['CEDULA'] = df['CEDULA_EMP'].fillna('')
    df['SUELDO_BASE'] = df['SUELDO'].fillna(0.0)
    df['FECHA_ING'] = df['FECHA_ING_EMP'].fillna('')
    df['FECHA_SAL'] = df['FECHA_SAL_EMP'].fillna('')
    df['CARGO'] = df['CARGO_EMP'].fillna('')
    df['CTA_AHO'] = df['CTA_AHO_CONSOLIDADA'].fillna('')
    
    df.loc[df['ANTIQUINC'] == 0, 'FONDO_RESERVA'] = 0.0
    
    for idx in df.index:
        ti = round(sum(df.loc[idx, c] for c in CONCEPTOS_INGRESOS), 2)
        te = df.loc[idx, 'TOTAL_EGRESOS']
        df.loc[idx, 'TOTAL_INGRESOS'] = ti
        df.loc[idx, 'TOTAL_RECIBIR'] = round(ti - te, 2)
    
    print("  Resolviendo nombres de CARGO, DEPTO, SECCION...")
    catalogo = prefijar_catalogos(origen)
    for idx in df.index:
        c = str(df.loc[idx, 'CARGO']).strip() if pd.notna(df.loc[idx, 'CARGO']) else ''
        d = str(df.loc[idx, 'DEPTO']).strip() if pd.notna(df.loc[idx, 'DEPTO']) else ''
        s = str(df.loc[idx, 'SECCION']).strip() if pd.notna(df.loc[idx, 'SECCION']) else ''
        if c:
            df.loc[idx, 'CARGO'] = catalogo.get(('FNC', c), c)
        if d:
            df.loc[idx, 'DEPTO'] = catalogo.get(('DPT', d), d)
        if s:
            df.loc[idx, 'SECCION'] = catalogo.get(('SEC', s), s)
    
    cols_sufix = [c for c in df.columns if c.endswith('_EMP')]
    df = df.drop(columns=[c for c in cols_sufix if c in df.columns])
    extras = [c for c in ['ANTIQUINC', 'SUELDO', 'CTA_AHO_CONSOLIDADA'] if c in df.columns]
    df = df.drop(columns=extras)
    
    for c in COLUMNAS_NUMERICAS:
        if c in df.columns:
            df[c] = df[c].round(2)
    
    cols_existentes = [c for c in COLUMNAS_ORDENADAS if c in df.columns]
    df = df[cols_existentes]
    
    return df


def exportar_excel(df, periodo, sufijo=''):
    sufijo_periodo = f"_{periodo}" if periodo else "_TODOS"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = f"REPORTE_NOMINA_7{sufijo_periodo}_{ts}{sufijo}.xlsx"
    
    print(f"Creando Excel: {archivo}")
    with pd.ExcelWriter(archivo, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Consolidado', index=False)
        wb = writer.book
        ws = writer.sheets['Consolidado']
        
        hdr_fmt = wb.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top',
            'fg_color': '#D7E4BC', 'border': 1
        })
        money_fmt = wb.add_format({'num_format': '0.00'})
        
        for col_num, val in enumerate(df.columns.values):
            ws.write(0, col_num, val, hdr_fmt)
        for col_num, name in enumerate(df.columns):
            if name in COLUMNAS_NUMERICAS:
                ws.set_column(col_num, col_num, 12, money_fmt)
            else:
                ws.set_column(col_num, col_num, 15)
    
    print(f"OK: {archivo}")
    return archivo


def comparar_dataframes(df_a, df_b, label_a='Supabase', label_b='SQL Server'):
    """Compara dos DataFrames y reporta diferencias"""
    print(f"\n{'='*60}")
    print(f"COMPARACION: {label_a} vs {label_b}")
    print(f"{'='*60}")
    
    iguales = True
    
    if len(df_a) != len(df_b):
        print(f"[!!] DIFERENCIA en filas: {label_a}={len(df_a)}, {label_b}={len(df_b)}")
        iguales = False
    else:
        print(f"[OK] Filas: {len(df_a)} = {len(df_b)}")
    
    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    if cols_a != cols_b:
        print(f"[!!] DIFERENCIA en columnas: faltan={cols_b-cols_a}, sobran={cols_a-cols_b}")
        iguales = False
    else:
        print(f"[OK] Columnas: coinciden ({len(cols_a)})")
    
    cols_num = ['TOTAL_INGRESOS', 'TOTAL_EGRESOS', 'TOTAL_RECIBIR']
    for c in cols_num:
        if c in df_a.columns and c in df_b.columns:
            suma_a = df_a[c].sum()
            suma_b = df_b[c].sum()
            diff = abs(suma_a - suma_b)
            if diff > 1.0:
                print(f"[!!] {c}: {label_a}={suma_a:.2f}, {label_b}={suma_b:.2f}, diff={diff:.2f}")
                iguales = False
            else:
                print(f"[OK] {c}: {suma_a:.2f} ≈ {suma_b:.2f}")
    
    if iguales:
        print(f"\n[OK] REPORTES COINCIDEN - SINCRONIZACION VERIFICADA")
    else:
        print(f"\n[!!] HAY DIFERENCIAS - Revisar")
    
    return iguales


# ── Main ─────────────────────────────────────────────────────────

def ejecutar_reporte(periodo, origen_principal='supabase', verificar=True):
    print(f"\n{'='*60}")
    print(f"REPORTE DE ROL GENERAL - NOMINA 7 - {origen_principal.upper()}")
    print(f"Periodo: {periodo}")
    print(f"{'='*60}\n")
    
    df_emp = leer_empleados(origen_principal)
    df_mov = leer_movimientos(periodo, origen_principal)
    df_final = procesar_reporte(df_mov, df_emp, origen_principal)
    
    sufijo = ''
    
    if verificar:
        try:
            print(f"\n{'='*60}")
            print("VERIFICACION contra SQL Server...")
            print(f"{'='*60}")
            df_emp_sql = leer_empleados('sql')
            df_mov_sql = leer_movimientos(periodo, 'sql')
            df_sql = procesar_reporte(df_mov_sql, df_emp_sql, 'sql')
            comparar_dataframes(df_final, df_sql, 'Supabase', 'SQL Server')
            sufijo = '_VERIFICADO'
        except Exception as e:
            print(f"[XX] Error en verificacion: {e}")
    
    archivo = exportar_excel(df_final, periodo, sufijo)
    print(f"\nReporte completado: {len(df_final)} registros")
    return df_final


if __name__ == "__main__":
    periodo_default = datetime.now().strftime('%Y-%m')
    periodo = input(f"Ingrese periodo (YYYY-MM) [{periodo_default}]: ").strip()
    if not periodo:
        periodo = periodo_default
    
    df = ejecutar_reporte(periodo, origen_principal='supabase', verificar=True)
    cerrar_conexiones()
