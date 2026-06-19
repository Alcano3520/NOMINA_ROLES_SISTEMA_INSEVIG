"""
REPORTE DE NOMINA - INTERFAZ GRAFICA
Genera reporte consolidado de nomina (actual o historica)
desde SQL Server o Supabase con un solo clic.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import sys
import io
import os
import platform
import subprocess
import calendar
from datetime import datetime
from pathlib import Path
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
#  CREDENCIALES
# ─────────────────────────────────────────────
_SQL_BASE = "SERVER=SERVER\\server;DATABASE=insevig;UID=sa;PWD=puntosoft123*"

def _sql_conn_str():
    """Devuelve connection string con el driver ODBC disponible en esta plataforma."""
    try:
        import pyodbc
        available = set(pyodbc.drivers())
        if platform.system() == 'Windows':
            prefs = ['SQL Server Native Client 10.0', 'SQL Server',
                     'ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server']
        else:
            prefs = ['ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server',
                     'ODBC Driver 13 for SQL Server', 'FreeTDS']
        for drv in prefs:
            if drv in available:
                return f'DRIVER={{{drv}}};{_SQL_BASE}'
    except Exception:
        pass
    # fallback por plataforma si pyodbc no está instalado aún
    driver = 'SQL Server' if platform.system() == 'Windows' else 'ODBC Driver 17 for SQL Server'
    return f'DRIVER={{{driver}}};{_SQL_BASE}'
SUPABASE_URL = "https://buzcapcwmksasrtjofae.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1emNhcGN3bWtzYXNydGpvZmFlIiwicm9sZSI6"
    "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTk5NjgzNywiZXhwIjoyMDY1NTcyODM3fQ."
    "gD_Qz6i2WzFqofBclS8BERVN-mALCzhFFS83IsKi1Rg"
)
MGMT_URL = "https://api.supabase.com/v1/projects/buzcapcwmksasrtjofae/database/query"
MGMT_KEY  = "Bearer sbp_090d84f4d291db0827e7350f1c919d6a8ad350d6"

# ─────────────────────────────────────────────
#  CONSTANTES DE NEGOCIO
# ─────────────────────────────────────────────
CODIGOS_IGNORAR = {105, 126, 199}

MAPEO_CONCEPTOS = {
    100: 'SUELDO',           102: 'BONIFICACION',    104: 'FONDO_RESERVA',
    107: 'DECIMO_TERCERA',   108: 'DECIMO_CUARTA',   110: 'MANIOBRAS',
    111: 'REEMBOLSOS',       113: 'SOBRETIEMPO_25',  114: 'SOBRETIEMPO_50',
    115: 'SOBRETIEMPO_100',  120: 'MOVILIZACION',
    200: 'APORT_IESS',       201: 'ANTICIPOS_OTROS', 202: 'ANTICIPO_SUELDO',
    203: 'MULTAS',           204: 'PRESTAMOS_QUIROGRAFARIOS',
    205: 'PRESTAMOS_COMPANIA', 206: 'PENSION_ALIMENTICIA',
    207: 'PRESTAMO_HIPOTECARIO', 217: 'ANTICIPOS_OTROS',
    218: 'APORT_IESS_CONYUGE', 219: 'IMPUESTO_RENTA', 250: 'ANTICIPOS_SURTIDOS',
}

CONCEPTOS_INGRESOS = [
    'SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA', 'DECIMO_CUARTA',
    'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25', 'SOBRETIEMPO_50',
    'SOBRETIEMPO_100', 'MOVILIZACION',
]
CONCEPTOS_EGRESOS = [
    'APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
    'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
    'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
    'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO',
]
COLUMNAS_NUMERICAS = CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS + [
    'TOTAL_INGRESOS', 'TOTAL_EGRESOS', 'TOTAL_RECIBIR', 'SUELDO_BASE',
]
COLUMNAS_ORDENADAS = (
    ['PERIODO', 'EMPLEADO', 'APELLIDOS_NOMBRES', 'CARGO', 'SUELDO_BASE',
     'DEPTO', 'CEDULA', 'CTA_AHO', 'SECCION', 'FECHA_ING', 'FECHA_SAL', 'DIAS'] +
    CONCEPTOS_INGRESOS + ['TOTAL_INGRESOS'] +
    CONCEPTOS_EGRESOS + ['TOTAL_EGRESOS', 'TOTAL_RECIBIR']
)


# ─────────────────────────────────────────────
#  UTILIDADES DE PERÍODO
# ─────────────────────────────────────────────
def periodo_siguiente(periodo):
    """Retorna 'YYYY-MM' del mes siguiente (para filtro exclusivo en Supabase)."""
    y, m = map(int, periodo.split('-'))
    if m == 12:
        return f'{y+1}-01'
    return f'{y}-{m+1:02d}'


# ─────────────────────────────────────────────
#  LECTURA SQL SERVER
# ─────────────────────────────────────────────
def leer_movimientos_sql(periodo, historico=False, log=print):
    import pyodbc
    conn = pyodbc.connect(_sql_conn_str())

    tabla   = 'RPHISTOR' if historico else 'RPINGDES'
    campo_f = 'FECHA'    if historico else 'FECHA_VEN'

    log(f"  Consultando {tabla} periodo {periodo}...")
    query = f"""
        SELECT NUMERO, FECHA, EMPLEADO, CODSUC, CODEMP, CODIGO, CLASE,
               SECUENCIA, DEPTO, SECCION, HORAS, VALOR, FECHA_VEN,
               CONCEPTO, DIAS, ASENTADO, ACTUALIZA, APORTA, MONTO,
               DIVIDENDO, ROL, TIPO_PGO, TIPO_TRA, OBSERV
        FROM {tabla}
        WHERE CONVERT(VARCHAR(7), {campo_f}, 120) = ?
    """
    df = pd.read_sql(query, conn, params=[periodo])
    log(f"  {len(df):,} movimientos encontrados")

    log("  Cargando empleados...")
    # Histórico: todos; Actual: solo activos
    where_emp = "" if historico else "WHERE ESTADO = 'ACT'"
    df_emp = pd.read_sql(
        f"SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, SUELDO, FECHA_ING, "
        f"FECHA_SAL, CARGO, DEPTO, SECCION, CTA_AHO, CTA_CTE, ANTIQUINC FROM RPEMPLEA {where_emp}",
        conn
    )
    catalogo_rows = pd.read_sql("SELECT TIPO, CODIGO, NOMBRE FROM DBTABLAS WHERE CODEMP = '10'", conn)
    conn.close()

    df_emp.columns = [c.upper() for c in df_emp.columns]
    return df, df_emp, catalogo_rows


def leer_movimientos_supabase(periodo, historico=False, log=print):
    from supabase import create_client
    import requests
    import time

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Aumentar statement_timeout a 60 s (default Supabase: 8 s).
    # rphistor_temp tiene ~900K filas; necesita índice + timeout generoso.
    try:
        sb.postgrest.headers['Prefer'] = 'statement_timeout=60000'
    except Exception:
        pass

    tabla   = 'rphistor_temp' if historico else 'rpingdesres'
    campo_f = 'fecha'         if historico else 'fecha_ven'
    sig     = periodo_siguiente(periodo)

    log(f"  Consultando {tabla} periodo {periodo}...")

    # Paginación cursor-based (WHERE id > last_id) — más eficiente que OFFSET
    # para tablas grandes. OFFSET n requiere saltar n filas; cursor no.
    # Índice en rphistor_temp(fecha, id) creado el 2026-05-27.
    todos = []
    last_id = 0
    reintentos = 0
    while True:
        try:
            r = (sb.table(tabla).select('*')
                   .gte(campo_f, f'{periodo}-01')
                   .lt(campo_f, f'{sig}-01')
                   .gt('id', last_id)
                   .order('id')
                   .limit(1000)
                   .execute())
        except Exception as e:
            # Reintento automático ante timeout (57014) u error de red transitorio
            if reintentos < 3 and ('57014' in str(e) or 'timeout' in str(e).lower()):
                reintentos += 1
                espera = reintentos * 5
                log(f"  Timeout pag id>{last_id}, reintento {reintentos}/3 en {espera}s...")
                time.sleep(espera)
                continue
            raise
        reintentos = 0
        if not r.data:
            break
        todos.extend(r.data)
        last_id = r.data[-1]['id']
        if len(todos) % 5000 == 0 and len(todos) > 0:
            log(f"  ...{len(todos):,} registros leidos")
        if len(r.data) < 1000:
            break

    df = pd.DataFrame(todos)
    if not df.empty and 'id' in df.columns:
        df = df.drop_duplicates(subset='id')
    log(f"  {len(df):,} movimientos encontrados")

    # Empleados
    log("  Cargando empleados...")
    todos_emp = []
    offset = 0
    q = sb.table('rpemplea').select('*').order('empleado')
    if not historico:
        q = q.eq('estado', 'ACT')
    while True:
        r = q.range(offset, offset + 999).execute()
        if not r.data:
            break
        todos_emp.extend(r.data)
        offset += 1000
        if len(r.data) < 1000:
            break
    df_emp = pd.DataFrame(todos_emp)
    df_emp.columns = [c.upper() for c in df_emp.columns]

    # Catálogo
    todos_cat = []
    offset = 0
    while True:
        r = (sb.table('dbtablas').select('tipo,codigo,nombre')
               .eq('codemp', '10').order('tipo')
               .range(offset, offset + 999).execute())
        if not r.data:
            break
        todos_cat.extend(r.data)
        offset += 1000
        if len(r.data) < 1000:
            break
    catalogo_rows = pd.DataFrame(todos_cat)

    return df, df_emp, catalogo_rows


# ─────────────────────────────────────────────
#  PROCESAMIENTO COMÚN
# ─────────────────────────────────────────────
def procesar(df_mov, df_emp, catalogo_rows, periodo, historico, log=print):
    # Normalizar columnas
    df_mov.columns = [c.upper() for c in df_mov.columns]
    df_emp.columns = [c.upper() for c in df_emp.columns]

    # Campo de fecha para el período
    campo_f = 'FECHA' if historico else 'FECHA_VEN'
    df_mov[campo_f] = pd.to_datetime(df_mov[campo_f], errors='coerce')
    df_mov['PERIODO'] = df_mov[campo_f].dt.strftime('%Y-%m')
    df_mov = df_mov.dropna(subset=['PERIODO', 'EMPLEADO'])
    df_mov['CLASE'] = pd.to_numeric(df_mov['CLASE'], errors='coerce')
    df_mov = df_mov.dropna(subset=['CLASE'])
    df_mov['CLASE'] = df_mov['CLASE'].astype(int)

    # Catálogo cargo/depto/sección
    catalogo_rows.columns = [c.upper() for c in catalogo_rows.columns]
    catalogo = {
        (str(r['TIPO']).strip(), str(r['CODIGO']).strip()): r['NOMBRE'] or r['CODIGO']
        for _, r in catalogo_rows.iterrows()
    }

    # Cuentas bancarias empleados
    def cuenta(row):
        a = str(row.get('CTA_AHO', '')).strip()
        c = str(row.get('CTA_CTE', '')).strip()
        a = '' if a in ('', 'nan', 'None') else a
        c = '' if c in ('', 'nan', 'None') else c
        return a or c
    df_emp['CTA_AHO_CONSOLIDADA'] = df_emp.apply(cuenta, axis=1)

    df_emp['APELLIDOS_NOMBRES'] = (
        df_emp['APELLIDOS'].fillna('').astype(str) + ' ' +
        df_emp['NOMBRES'].fillna('').astype(str)
    ).str.strip()

    grupos = df_mov.groupby(['EMPLEADO', 'PERIODO'])
    log(f"  Procesando {len(grupos):,} grupos empleado-periodo...")

    resultados = []
    for i, ((empleado, per), grupo) in enumerate(grupos):
        if i % 200 == 0 and i > 0:
            log(f"  ...{i:,}/{len(grupos):,}")

        fila = {
            'EMPLEADO': empleado,
            'PERIODO': per,
            'DEPTO':   grupo['DEPTO'].iloc[0]   if pd.notna(grupo['DEPTO'].iloc[0])   else '',
            'SECCION': grupo['SECCION'].iloc[0] if pd.notna(grupo['SECCION'].iloc[0]) else '',
            'DIAS': 0,
            'APELLIDOS_NOMBRES': '', 'CEDULA': '', 'SUELDO_BASE': 0.0,
            'FECHA_ING': '', 'FECHA_SAL': '', 'CARGO': '', 'CTA_AHO': '',
        }
        for c in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
            fila[c] = 0.0

        for _, reg in grupo.iterrows():
            clase = reg['CLASE']
            if clase in CODIGOS_IGNORAR:
                continue
            valor    = reg['VALOR']    if pd.notna(reg['VALOR'])    else 0
            asentado = reg['ASENTADO'] if pd.notna(reg['ASENTADO']) else 0
            if clase in MAPEO_CONCEPTOS:
                concepto = MAPEO_CONCEPTOS[clase]
                if concepto in ('DECIMO_TERCERA', 'DECIMO_CUARTA'):
                    if asentado:
                        fila[concepto] += round(valor, 2)
                elif concepto == 'SUELDO':
                    fila[concepto] += round(valor, 2)
                    if pd.notna(reg.get('DIAS', None)):
                        fila['DIAS'] = reg['DIAS']
                elif concepto in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
                    fila[concepto] += round(valor, 2)
            elif str(reg.get('CODIGO', '')).strip().upper() == 'EGR':
                fila['ANTICIPOS_SURTIDOS'] += round(valor, 2)

        ti = round(sum(fila[c] for c in CONCEPTOS_INGRESOS), 2)
        te = round(sum(fila[c] for c in CONCEPTOS_EGRESOS), 2)
        fila['TOTAL_INGRESOS'] = ti
        fila['TOTAL_EGRESOS']  = te
        fila['TOTAL_RECIBIR']  = round(ti - te, 2)
        resultados.append(fila)

    df = pd.DataFrame(resultados)

    # JOIN con empleados
    join_type = 'left' if historico else 'inner'
    # DEPTO y SECCION: usar columna de df_emp si existe, sino tomar del movimiento
    _emp_cols = ['EMPLEADO', 'APELLIDOS_NOMBRES', 'CEDULA', 'SUELDO',
                 'FECHA_ING', 'FECHA_SAL', 'CARGO', 'CTA_AHO_CONSOLIDADA', 'ANTIQUINC']
    for _c in ['DEPTO', 'SECCION']:
        if _c in df_emp.columns:
            _emp_cols.append(_c)
    df = df.merge(
        df_emp[_emp_cols],
        on='EMPLEADO', how=join_type, suffixes=('', '_EMP')
    )
    log(f"  Empleados con movimientos: {len(df):,}")

    # Rellenar campos del empleado
    df['APELLIDOS_NOMBRES'] = df['APELLIDOS_NOMBRES_EMP'].fillna(df['APELLIDOS_NOMBRES'])
    df['CEDULA']      = df.get('CEDULA_EMP',    pd.Series(dtype=str)).fillna('')
    df['SUELDO_BASE'] = df.get('SUELDO_EMP',    pd.Series(dtype=float)).fillna(0.0)
    df['FECHA_ING']   = df.get('FECHA_ING_EMP', pd.Series(dtype=str)).fillna('')
    df['FECHA_SAL']   = df.get('FECHA_SAL_EMP', pd.Series(dtype=str)).fillna('')
    df['CARGO']       = df.get('CARGO_EMP',     pd.Series(dtype=str)).fillna(df['CARGO'])
    df['CTA_AHO']     = df.get('CTA_AHO_CONSOLIDADA', pd.Series(dtype=str)).fillna('')
    # DEPTO y SECCION siempre del empleado actual (RPEMPLEA), no del movimiento
    df['DEPTO']   = df.get('DEPTO_EMP',   pd.Series(dtype=str)).fillna(df.get('DEPTO',   ''))
    df['SECCION'] = df.get('SECCION_EMP', pd.Series(dtype=str)).fillna(df.get('SECCION', ''))

    # ANTIQUINC: 0 => sin fondo de reserva
    if 'ANTIQUINC' in df.columns:
        df.loc[df['ANTIQUINC'] == 0, 'FONDO_RESERVA'] = 0.0
        for idx in df[df['ANTIQUINC'] == 0].index:
            ti = round(sum(df.loc[idx, c] for c in CONCEPTOS_INGRESOS), 2)
            df.loc[idx, 'TOTAL_INGRESOS'] = ti
            df.loc[idx, 'TOTAL_RECIBIR']  = round(ti - df.loc[idx, 'TOTAL_EGRESOS'], 2)

    # Resolver nombres catálogo
    log("  Resolviendo nombres cargo/depto/seccion...")
    for idx in df.index:
        for col, tipo in [('CARGO', 'FNC'), ('DEPTO', 'DPT'), ('SECCION', 'SEC')]:
            val = str(df.loc[idx, col]).strip() if pd.notna(df.loc[idx, col]) else ''
            if val and val not in ('', 'nan', 'None'):
                df.loc[idx, col] = catalogo.get((tipo, val), val)

    # Limpiar columnas extra del merge
    borrar = [c for c in df.columns if c.endswith('_EMP')]
    borrar += [c for c in ['ANTIQUINC', 'CTA_AHO_CONSOLIDADA'] if c in df.columns]
    df = df.drop(columns=[c for c in borrar if c in df.columns])

    for c in COLUMNAS_NUMERICAS:
        if c in df.columns:
            df[c] = df[c].round(2)

    cols = [c for c in COLUMNAS_ORDENADAS if c in df.columns]
    return df[cols]


# ─────────────────────────────────────────────
#  EXPORTAR EXCEL
# ─────────────────────────────────────────────
def exportar_excel(df, periodo, fuente, historico, destino_dir):
    tipo   = 'HISTORICO' if historico else 'NOMINA'
    origen = 'SQL' if fuente == 'sql' else 'SUPA'
    ts     = datetime.now().strftime('%Y%m%d_%H%M%S')
    nombre = f'REPORTE_{tipo}_{origen}_{periodo}_{ts}.xlsx'
    ruta   = os.path.join(destino_dir, nombre)

    with pd.ExcelWriter(ruta, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Consolidado', index=False)
        wb = writer.book
        ws = writer.sheets['Consolidado']

        hdr_fmt  = wb.add_format({'bold': True, 'text_wrap': True, 'valign': 'top',
                                   'fg_color': '#D7E4BC', 'border': 1})
        num_fmt  = wb.add_format({'num_format': '0.00'})
        neg_fmt  = wb.add_format({'num_format': '0.00', 'font_color': '#C00000'})

        for i, col in enumerate(df.columns):
            ws.write(0, i, col, hdr_fmt)
            if col in COLUMNAS_NUMERICAS:
                ws.set_column(i, i, 13, num_fmt)
            else:
                ws.set_column(i, i, 16)

        # Totales al final
        fila_tot = len(df) + 1
        for i, col in enumerate(df.columns):
            if col in COLUMNAS_NUMERICAS:
                col_letra = chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)
                ws.write_formula(fila_tot, i,
                    f'=SUM({col_letra}2:{col_letra}{len(df)+1})', num_fmt)
        total_fmt = wb.add_format({'bold': True, 'fg_color': '#BDD7EE', 'num_format': '0.00', 'border': 1})
        ws.write(fila_tot, 0, 'TOTALES', wb.add_format({'bold': True, 'fg_color': '#BDD7EE', 'border': 1}))

    return ruta


# ─────────────────────────────────────────────
#  INTERFAZ GRAFICA
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Reporte de Nómina')
        self.resizable(False, False)
        self._build_ui()
        self._archivo_generado = None

    # ── construcción de la UI ──────────────────
    def _build_ui(self):
        # Colores
        BG   = '#F0F4F8'
        AZUL = '#2563EB'
        GRIS = '#64748B'
        self.configure(bg=BG)

        # ── Título ──────────────────────────────
        tk.Label(self, text='📊  Reporte de Nómina', bg=BG,
                 font=('Segoe UI', 16, 'bold'), fg='#1E3A5F').grid(
            row=0, column=0, columnspan=2, pady=(18, 4), padx=24, sticky='w')

        tk.Label(self, text='SQL Server · Supabase  |  Nómina Actual · Histórico',
                 bg=BG, font=('Segoe UI', 9), fg=GRIS).grid(
            row=1, column=0, columnspan=2, padx=24, sticky='w', pady=(0, 10))

        sep = ttk.Separator(self, orient='horizontal')
        sep.grid(row=2, column=0, columnspan=2, sticky='ew', padx=16, pady=4)

        # ── Panel de opciones ───────────────────
        frame = tk.Frame(self, bg=BG)
        frame.grid(row=3, column=0, columnspan=2, padx=24, pady=8, sticky='ew')
        frame.columnconfigure(1, weight=1)

        # Fuente
        tk.Label(frame, text='Fuente de datos:', bg=BG,
                 font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        f_fr = tk.Frame(frame, bg=BG)
        f_fr.grid(row=0, column=1, sticky='w', padx=8)
        self.var_fuente = tk.StringVar(value='sql')
        ttk.Radiobutton(f_fr, text='SQL Server', variable=self.var_fuente, value='sql').pack(side='left', padx=(0, 16))
        ttk.Radiobutton(f_fr, text='Supabase',   variable=self.var_fuente, value='supa').pack(side='left')

        # Tipo
        tk.Label(frame, text='Tipo de nómina:', bg=BG,
                 font=('Segoe UI', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        t_fr = tk.Frame(frame, bg=BG)
        t_fr.grid(row=1, column=1, sticky='w', padx=8)
        self.var_tipo = tk.StringVar(value='actual')
        ttk.Radiobutton(t_fr, text='Nómina Actual (RPINGDES)',  variable=self.var_tipo, value='actual').pack(side='left', padx=(0, 16))
        ttk.Radiobutton(t_fr, text='Histórico (RPHISTOR)',       variable=self.var_tipo, value='historico').pack(side='left')

        # Período
        tk.Label(frame, text='Período (YYYY-MM):', bg=BG,
                 font=('Segoe UI', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        p_fr = tk.Frame(frame, bg=BG)
        p_fr.grid(row=2, column=1, sticky='w', padx=8)
        self.var_periodo = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        self.ent_periodo = ttk.Entry(p_fr, textvariable=self.var_periodo, width=12,
                                     font=('Segoe UI', 11))
        self.ent_periodo.pack(side='left')
        tk.Label(p_fr, text='  (ej: 2026-05  o  2025-12)', bg=BG,
                 font=('Segoe UI', 9), fg=GRIS).pack(side='left')

        # Carpeta destino
        tk.Label(frame, text='Guardar en:', bg=BG,
                 font=('Segoe UI', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
        d_fr = tk.Frame(frame, bg=BG)
        d_fr.grid(row=3, column=1, sticky='w', padx=8)
        self.var_destino = tk.StringVar(value=str(Path(__file__).parent.parent))
        ent_dest = ttk.Entry(d_fr, textvariable=self.var_destino, width=38,
                              font=('Segoe UI', 9))
        ent_dest.pack(side='left')
        ttk.Button(d_fr, text='...', width=3,
                   command=self._elegir_carpeta).pack(side='left', padx=4)

        sep2 = ttk.Separator(self, orient='horizontal')
        sep2.grid(row=4, column=0, columnspan=2, sticky='ew', padx=16, pady=6)

        # ── Botones ─────────────────────────────
        btn_fr = tk.Frame(self, bg=BG)
        btn_fr.grid(row=5, column=0, columnspan=2, pady=4)

        self.btn_generar = tk.Button(
            btn_fr, text='▶  Generar Reporte',
            bg=AZUL, fg='white', font=('Segoe UI', 11, 'bold'),
            relief='flat', padx=20, pady=8, cursor='hand2',
            activebackground='#1D4ED8', activeforeground='white',
            command=self._iniciar
        )
        self.btn_generar.pack(side='left', padx=8)

        self.btn_abrir = tk.Button(
            btn_fr, text='📂  Abrir Excel',
            bg='#16A34A', fg='white', font=('Segoe UI', 11, 'bold'),
            relief='flat', padx=20, pady=8, cursor='hand2',
            activebackground='#15803D', activeforeground='white',
            state='disabled',
            command=self._abrir_excel
        )
        self.btn_abrir.pack(side='left', padx=8)

        # ── Progreso ─────────────────────────────
        self.progress = ttk.Progressbar(self, mode='indeterminate', length=480)
        self.progress.grid(row=6, column=0, columnspan=2, padx=24, pady=(8, 2), sticky='ew')

        # ── Log ──────────────────────────────────
        self.log_text = scrolledtext.ScrolledText(
            self, width=68, height=14, state='disabled',
            font=('Consolas', 9), bg='#1E293B', fg='#E2E8F0',
            insertbackground='white'
        )
        self.log_text.grid(row=7, column=0, columnspan=2, padx=16, pady=(4, 16), sticky='nsew')

        # ── Estado ───────────────────────────────
        self.lbl_estado = tk.Label(self, text='Listo', bg=BG,
                                    font=('Segoe UI', 9), fg=GRIS)
        self.lbl_estado.grid(row=8, column=0, columnspan=2, pady=(0, 8))

    # ── acciones ──────────────────────────────
    def _elegir_carpeta(self):
        d = filedialog.askdirectory(initialdir=self.var_destino.get())
        if d:
            self.var_destino.set(d)

    def _abrir_excel(self):
        if self._archivo_generado and os.path.exists(self._archivo_generado):
            sistema = platform.system()
            if sistema == 'Windows':
                os.startfile(self._archivo_generado)
            elif sistema == 'Darwin':
                subprocess.call(['open', self._archivo_generado])
            else:
                subprocess.call(['xdg-open', self._archivo_generado])

    def _log(self, msg):
        """Escribe en el cuadro de log (thread-safe vía after)."""
        def _write():
            self.log_text.config(state='normal')
            ts = datetime.now().strftime('%H:%M:%S')
            self.log_text.insert('end', f'[{ts}] {msg}\n')
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        self.after(0, _write)

    def _set_estado(self, msg, color='#64748B'):
        self.after(0, lambda: self.lbl_estado.config(text=msg, fg=color))

    def _iniciar(self):
        periodo = self.var_periodo.get().strip()
        # Validar formato
        try:
            datetime.strptime(periodo, '%Y-%m')
        except ValueError:
            messagebox.showerror('Error', 'Formato de período inválido.\nUse YYYY-MM (ej: 2026-05)')
            return

        self.btn_generar.config(state='disabled')
        self.btn_abrir.config(state='disabled')
        self._archivo_generado = None
        self.progress.start(12)
        self._set_estado('Procesando...', '#2563EB')

        t = threading.Thread(target=self._generar, daemon=True)
        t.start()

    def _generar(self):
        fuente   = self.var_fuente.get()
        tipo     = self.var_tipo.get()
        periodo  = self.var_periodo.get().strip()
        historico = (tipo == 'historico')
        destino  = self.var_destino.get()

        fuente_txt = 'SQL Server' if fuente == 'sql' else 'Supabase'
        tipo_txt   = 'Histórico'  if historico else 'Nómina Actual'

        self._log(f'{"="*55}')
        self._log(f'Fuente:  {fuente_txt}')
        self._log(f'Tipo:    {tipo_txt}')
        self._log(f'Período: {periodo}')
        self._log(f'{"="*55}')

        try:
            # 1. Leer datos
            self._log('Conectando y leyendo datos...')
            if fuente == 'sql':
                df_mov, df_emp, catalogo = leer_movimientos_sql(periodo, historico, log=self._log)
            else:
                df_mov, df_emp, catalogo = leer_movimientos_supabase(periodo, historico, log=self._log)

            if df_mov.empty:
                self.after(0, lambda: messagebox.showwarning(
                    'Sin datos', f'No se encontraron movimientos para {periodo}.'))
                return

            # 2. Procesar
            self._log('Procesando y consolidando...')
            df = procesar(df_mov, df_emp, catalogo, periodo, historico, log=self._log)

            # 3. Exportar
            self._log('Exportando Excel...')
            ruta = exportar_excel(df, periodo, fuente, historico, destino)
            self._archivo_generado = ruta

            self._log(f'')
            self._log(f'[OK] {len(df):,} empleados procesados')
            self._log(f'[OK] Archivo: {os.path.basename(ruta)}')
            self._log(f'Guardado en: {destino}')
            self._set_estado(f'Listo — {len(df):,} registros  |  {os.path.basename(ruta)}', '#16A34A')
            self.after(0, lambda: self.btn_abrir.config(state='normal'))

        except Exception as e:
            import traceback
            self._log(f'[ERROR] {e}')
            self._log(traceback.format_exc())
            self._set_estado(f'Error: {e}', '#DC2626')
            self.after(0, lambda: messagebox.showerror('Error', str(e)))

        finally:
            self.after(0, self.progress.stop)
            self.after(0, lambda: self.btn_generar.config(state='normal'))


# ─────────────────────────────────────────────
#  PUNTO DE ENTRADA
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app = App()
    app.mainloop()
