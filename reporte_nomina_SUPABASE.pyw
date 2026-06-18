"""
REPORTE DE ROL GENERAL - NOMINA 8
Lee unicamente desde Supabase y produce Excel
"""
import warnings, sys, io
from datetime import datetime
import pandas as pd
import numpy as np
from supabase import create_client

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
warnings.filterwarnings('ignore')

SUPABASE_URL = "https://buzcapcwmksasrtjofae.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1emNhcGN3bWtzYXNydGpvZmFlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTk5NjgzNywiZXhwIjoyMDY1NTcyODM3fQ.gD_Qz6i2WzFqofBclS8BERVN-mALCzhFFS83IsKi1Rg"

CODIGOS_IGNORAR = {105, 126, 199}

MAPEO_CONCEPTOS = {
    100: 'SUELDO', 102: 'BONIFICACION', 104: 'FONDO_RESERVA',
    107: 'DECIMO_TERCERA', 108: 'DECIMO_CUARTA', 110: 'MANIOBRAS',
    111: 'REEMBOLSOS', 113: 'SOBRETIEMPO_25', 114: 'SOBRETIEMPO_50',
    115: 'SOBRETIEMPO_100', 120: 'MOVILIZACION',
    200: 'APORT_IESS', 201: 'ANTICIPOS_OTROS', 202: 'ANTICIPO_SUELDO',
    203: 'MULTAS', 204: 'PRESTAMOS_QUIROGRAFARIOS', 205: 'PRESTAMOS_COMPANIA',
    206: 'PENSION_ALIMENTICIA', 207: 'PRESTAMO_HIPOTECARIO',
    217: 'ANTICIPOS_OTROS', 218: 'APORT_IESS_CONYUGE',
    219: 'IMPUESTO_RENTA', 250: 'ANTICIPOS_SURTIDOS',
}

CONCEPTOS_INGRESOS = [
    'SUELDO', 'BONIFICACION', 'FONDO_RESERVA',
    'DECIMO_TERCERA', 'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS',
    'SOBRETIEMPO_25', 'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION'
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


def conectar():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _paginar(tabla, cols, filtros=None, desde=None, hasta=None, campo_fecha=None):
    s = conectar()
    query = s.table(tabla).select(cols)
    if filtros:
        for f in filtros:
            query = query.eq(f[0], f[1])
    if desde and campo_fecha:
        query = query.gte(campo_fecha, desde)
    if hasta and campo_fecha:
        query = query.lte(campo_fecha, hasta)
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


def leer_empleados():
    print("Obteniendo empleados ACTIVOS...")
    data = _paginar('rpemplea', '*', [('estado', 'ACT')])
    df = pd.DataFrame(data)
    df.columns = [c.upper() for c in df.columns]
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS'].fillna('').astype(str) + ' ' + df['NOMBRES'].fillna('').astype(str)
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS_NOMBRES'].str.strip()
    def consolidar_cuenta(row):
        a = str(row['CTA_AHO']).strip() if pd.notna(row['CTA_AHO']) else ''
        c = str(row['CTA_CTE']).strip() if pd.notna(row['CTA_CTE']) else ''
        return a if a and a != 'nan' else (c if c and c != 'nan' else '')
    df['CTA_AHO_CONSOLIDADA'] = df.apply(consolidar_cuenta, axis=1)
    respaldos = len(df[(df['CTA_AHO'].isna() | (df['CTA_AHO'] == '')) & (df['CTA_CTE'].notna() & (df['CTA_CTE'] != ''))])
    print(f"  Empleados ACTIVOS: {len(df)} | Usan CTA_CTE respaldo: {respaldos}")
    return df


def leer_movimientos(periodo):
    print(f"Obteniendo movimientos para {periodo}...")
    año, mes = periodo.split('-')
    if mes == '12':
        fin = f'{int(año)+1}-01-01'
    else:
        fin = f'{año}-{int(mes)+1:02d}-01'
    desde = f'{periodo}-01'
    data = _paginar('rpingdes', '*', campo_fecha='fecha_ven', desde=desde, hasta=fin)
    df = pd.DataFrame(data)
    df.columns = [c.upper() for c in df.columns]
    print(f"  Movimientos: {len(df)}")
    return df


def precargar_catalogos():
    print("  Cargando catalogos...")
    data = _paginar('dbtablas', 'tipo,codigo,nombre')
    c = {}
    for d in data:
        c[(str(d['tipo']).strip(), str(d['codigo']).strip())] = d['nombre'] or d['codigo']
    print(f"    {len(c)} registros")
    return c


def procesar(df_mov, df_emp):
    df_mov['FECHA_VEN'] = pd.to_datetime(df_mov['FECHA_VEN'], errors='coerce')
    df_mov['PERIODO'] = df_mov['FECHA_VEN'].dt.strftime('%Y-%m')
    df_mov = df_mov.dropna(subset=['PERIODO', 'EMPLEADO'])
    df_mov['CLASE'] = pd.to_numeric(df_mov['CLASE'], errors='coerce')
    df_mov = df_mov.dropna(subset=['CLASE'])
    df_mov['CLASE'] = df_mov['CLASE'].astype(int)
    grupos = df_mov.groupby(['EMPLEADO', 'PERIODO'])
    print(f"  Procesando {len(grupos)} grupos...")
    resultados = []
    for p, (key, grupo) in enumerate(grupos):
        empleado, per = key
        if p % 100 == 0 or p < 5:
            print(f"    {p+1}/{len(grupos)}: {empleado}")
        fila = {
            'EMPLEADO': empleado, 'APELLIDOS_NOMBRES': '', 'CEDULA': '',
            'SUELDO_BASE': 0.0, 'FECHA_ING': '', 'FECHA_SAL': '', 'CARGO': '',
            'CTA_AHO': '', 'PERIODO': per,
            'DEPTO': grupo['DEPTO'].iloc[0] if pd.notna(grupo['DEPTO'].iloc[0]) else '',
            'SECCION': grupo['SECCION'].iloc[0] if pd.notna(grupo['SECCION'].iloc[0]) else '',
            'DIAS': 0
        }
        for c in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
            fila[c] = 0.0
        for _, reg in grupo.iterrows():
            clase = reg['CLASE']
            if clase in CODIGOS_IGNORAR:
                continue
            valor = reg['VALOR'] if pd.notna(reg['VALOR']) else 0
            asentado = reg['ASENTADO']
            if clase in MAPEO_CONCEPTOS:
                concepto = MAPEO_CONCEPTOS[clase]
                if concepto in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                    if asentado:
                        fila[concepto] += round(valor, 2)
                elif concepto == 'SUELDO':
                    fila[concepto] += round(valor, 2)
                    if pd.notna(reg['DIAS']):
                        fila['DIAS'] = reg['DIAS']
                elif concepto in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
                    fila[concepto] += round(valor, 2)
            elif reg['CODIGO'] == 'EGR':
                fila['ANTICIPOS_SURTIDOS'] += round(valor, 2)
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
    print(f"  Empleados activos con movimientos: {len(df)}")
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS_NOMBRES_EMP'].fillna('')
    df['CEDULA'] = df['CEDULA_EMP'].fillna('')
    df['SUELDO_BASE'] = df['SUELDO_EMP'].fillna(0.0)
    df['FECHA_ING'] = df['FECHA_ING_EMP'].fillna('')
    df['FECHA_SAL'] = df['FECHA_SAL_EMP'].fillna('')
    df['CARGO'] = df['CARGO_EMP'].fillna('')
    df['CTA_AHO'] = df['CTA_AHO_CONSOLIDADA'].fillna('')
    df.loc[df['ANTIQUINC'] == 0, 'FONDO_RESERVA'] = 0.0
    for idx in df.index:
        ti = round(sum(df.loc[idx, c] for c in CONCEPTOS_INGRESOS), 2)
        df.loc[idx, 'TOTAL_INGRESOS'] = ti
        df.loc[idx, 'TOTAL_RECIBIR'] = round(ti - df.loc[idx, 'TOTAL_EGRESOS'], 2)
    print("  Resolviendo nombres de cargo, depto, seccion...")
    catalogo = precargar_catalogos()
    for idx in df.index:
        for col, prefijo in [('CARGO','FNC'), ('DEPTO','DPT'), ('SECCION','SEC')]:
            val = str(df.loc[idx, col]).strip() if pd.notna(df.loc[idx, col]) else ''
            if val:
                df.loc[idx, col] = catalogo.get((prefijo, val), val)
    sufix = [c for c in df.columns if c.endswith('_EMP')]
    df = df.drop(columns=[c for c in sufix if c in df.columns])
    df = df.drop(columns=[c for c in ['ANTIQUINC', 'CTA_AHO_CONSOLIDADA'] if c in df.columns])
    for c in COLUMNAS_NUMERICAS:
        if c in df.columns:
            df[c] = df[c].round(2)
    cols = [c for c in COLUMNAS_ORDENADAS if c in df.columns]
    return df[cols]


def exportar_excel(df, periodo):
    sufijo = f"_{periodo}" if periodo else "_TODOS"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = f"REPORTE_NOMINA_8{sufijo}_{ts}.xlsx"
    print(f"Creando Excel: {archivo}")
    with pd.ExcelWriter(archivo, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Consolidado', index=False)
        wb = writer.book
        ws = writer.sheets['Consolidado']
        hdr = wb.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BC', 'border': 1})
        money = wb.add_format({'num_format': '0.00'})
        for i, v in enumerate(df.columns.values):
            ws.write(0, i, v, hdr)
        for i, name in enumerate(df.columns):
            if name in COLUMNAS_NUMERICAS:
                ws.set_column(i, i, 12, money)
            else:
                ws.set_column(i, i, 15)
    print(f"OK: {archivo}")
    return archivo


def main():
    periodo_default = datetime.now().strftime('%Y-%m')
    periodo = input(f"Ingrese periodo (YYYY-MM) [{periodo_default}]: ").strip()
    if not periodo:
        periodo = periodo_default
    print(f"\n{'='*60}")
    print(f"REPORTE DE ROL GENERAL - NOMINA 8 (Supabase)")
    print(f"Periodo: {periodo}")
    print(f"{'='*60}\n")
    df_emp = leer_empleados()
    df_mov = leer_movimientos(periodo)
    df = procesar(df_mov, df_emp)
    exportar_excel(df, periodo)
    print(f"\nReporte completado: {len(df)} registros")

if __name__ == "__main__":
    main()
