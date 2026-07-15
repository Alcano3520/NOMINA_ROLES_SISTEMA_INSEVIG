"""
HISTORIAL DE NÓMINA POR EMPLEADO
Busca un empleado y muestra su nómina mes a mes apilada.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import threading
import platform
import subprocess
import os
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# ─── Credenciales ───────────────────────────────────────────────────────────
_SQL_BASE    = "SERVER=SERVER\\server;DATABASE=insevig;UID=sa;PWD=puntosoft123*"
SUPABASE_URL = "https://buzcapcwmksasrtjofae.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1emNhcGN3bWtzYXNydGpvZmFlIiwicm9sZSI6"
    "InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTk5NjgzNywiZXhwIjoyMDY1NTcyODM3fQ."
    "gD_Qz6i2WzFqofBclS8BERVN-mALCzhFFS83IsKi1Rg"
)

# ─── Constantes de negocio ──────────────────────────────────────────────────
CODIGOS_IGNORAR = {105, 126, 199}
MAPEO_CONCEPTOS = {
    100:'SUELDO',          102:'BONIFICACION',     104:'FONDO_RESERVA',
    107:'DECIMO_TERCERA',  108:'DECIMO_CUARTA',    110:'MANIOBRAS',
    111:'REEMBOLSOS',      113:'SOBRETIEMPO_25',   114:'SOBRETIEMPO_50',
    115:'SOBRETIEMPO_100', 120:'MOVILIZACION',
    200:'APORT_IESS',      201:'ANTICIPOS_OTROS',  202:'ANTICIPO_SUELDO',
    203:'MULTAS',          204:'PRESTAMOS_QUIROGRAFARIOS',
    205:'PRESTAMOS_COMPANIA', 206:'PENSION_ALIMENTICIA',
    207:'PRESTAMO_HIPOTECARIO', 217:'ANTICIPOS_OTROS',
    218:'APORT_IESS_CONYUGE', 219:'IMPUESTO_RENTA', 250:'ANTICIPOS_SURTIDOS',
}
CONCEPTOS_INGRESOS = [
    'SUELDO','BONIFICACION','FONDO_RESERVA','DECIMO_TERCERA','DECIMO_CUARTA',
    'MANIOBRAS','REEMBOLSOS','SOBRETIEMPO_25','SOBRETIEMPO_50','SOBRETIEMPO_100','MOVILIZACION',
]
CONCEPTOS_EGRESOS = [
    'APORT_IESS','PRESTAMOS_QUIROGRAFARIOS','PRESTAMOS_COMPANIA',
    'ANTICIPO_SUELDO','ANTICIPOS_OTROS','ANTICIPOS_SURTIDOS',
    'APORT_IESS_CONYUGE','IMPUESTO_RENTA','MULTAS',
    'PENSION_ALIMENTICIA','PRESTAMO_HIPOTECARIO',
]

COLS_FIJA  = ['PERIODO']               # columna(s) fijas (no se desplazan)
COLS_TABLA = [
    'PERIODO','CARGO','DEPTO','SECCION','FECHA_ING',
    'DIAS','SUELDO','BONIFICACION','FONDO_RESERVA',
    'DECIMO_TERCERA','DECIMO_CUARTA','MANIOBRAS','REEMBOLSOS',
    'SOBRETIEMPO_25','SOBRETIEMPO_50','SOBRETIEMPO_100','MOVILIZACION',
    'TOTAL_INGRESOS',
    'APORT_IESS','PRESTAMOS_QUIROGRAFARIOS','PRESTAMOS_COMPANIA',
    'ANTICIPO_SUELDO','ANTICIPOS_OTROS','ANTICIPOS_SURTIDOS',
    'APORT_IESS_CONYUGE','IMPUESTO_RENTA','MULTAS',
    'PENSION_ALIMENTICIA','PRESTAMO_HIPOTECARIO',
    'TOTAL_EGRESOS','TOTAL_RECIBIR',
]
HEADER_CORTO = {
    'PERIODO':'PERÍODO','CARGO':'CARGO','DEPTO':'DEPARTAMENTO',
    'SECCION':'SECCIÓN','FECHA_ING':'F.INGRESO',
    'DIAS':'DÍAS','SUELDO':'SUELDO','BONIFICACION':'BONIF',
    'FONDO_RESERVA':'F.RES','DECIMO_TERCERA':'13ro','DECIMO_CUARTA':'14to',
    'MANIOBRAS':'MANIOB','REEMBOLSOS':'REEMB','SOBRETIEMPO_25':'HE25%',
    'SOBRETIEMPO_50':'HE50%','SOBRETIEMPO_100':'HE100%','MOVILIZACION':'MOVIL',
    'TOTAL_INGRESOS':'T.INGR',
    'APORT_IESS':'IESS','PRESTAMOS_QUIROGRAFARIOS':'P.QUIRO',
    'PRESTAMOS_COMPANIA':'P.COMP','ANTICIPO_SUELDO':'ANT.SLD',
    'ANTICIPOS_OTROS':'ANT.OTR','ANTICIPOS_SURTIDOS':'ANT.SUR',
    'AORT_IESS_CONYUGE':'IESS.CON','APORT_IESS_CONYUGE':'IESS.CON',
    'IMPUESTO_RENTA':'IMP.RTA','MULTAS':'MULTAS','PENSION_ALIMENTICIA':'P.ALIM',
    'PRESTAMO_HIPOTECARIO':'P.HIP','TOTAL_EGRESOS':'T.EGR','TOTAL_RECIBIR':'T.RECIB',
}

OPCIONES_PERIODOS = {
    'Últimos 4 meses':  4,
    'Últimos 6 meses':  6,
    'Último año (12)': 12,
    'Todos':           999,
}

# ─── Utilidades ─────────────────────────────────────────────────────────────
def _sql_conn_str():
    try:
        import pyodbc
        avail = set(pyodbc.drivers())
        prefs = (['SQL Server Native Client 10.0','SQL Server',
                  'ODBC Driver 18 for SQL Server','ODBC Driver 17 for SQL Server']
                 if platform.system()=='Windows' else
                 ['ODBC Driver 18 for SQL Server','ODBC Driver 17 for SQL Server',
                  'ODBC Driver 13 for SQL Server','FreeTDS'])
        for d in prefs:
            if d in avail:
                return f'DRIVER={{{d}}};{_SQL_BASE}'
    except Exception:
        pass
    d = 'SQL Server' if platform.system()=='Windows' else 'ODBC Driver 17 for SQL Server'
    return f'DRIVER={{{d}}};{_SQL_BASE}'

def _fmt(val):
    """Formatea número para mostrar en tabla."""
    try:
        f = float(val)
        return f'{f:,.2f}' if f != 0 else ''
    except Exception:
        return str(val) if val else ''

def _fmt_fecha(val):
    """'YYYY-MM-DD' → 'DD/MM/YYYY'  |  'YYYY-MM' → 'MM/YYYY'"""
    s = str(val).strip()
    if len(s) == 10 and s[4] == '-' and s[7] == '-':
        return f'{s[8:10]}/{s[5:7]}/{s[:4]}'
    if len(s) == 7 and s[4] == '-':
        return f'{s[5:7]}/{s[:4]}'
    return '' if s in ('', 'nan', 'None', 'NaT') else s

def _periodos_recientes(n):
    """Retorna lista de 'YYYY-MM' de los últimos n meses (incluyendo el actual)."""
    from datetime import date
    hoy = date.today()
    periodos = []
    y, m = hoy.year, hoy.month
    for _ in range(n):
        periodos.append(f'{y}-{m:02d}')
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return periodos  # más reciente primero

# ─── Procesamiento ───────────────────────────────────────────────────────────
def procesar_empleado(df_mov, emp_info, catalogo_rows, campo_f='FECHA', etiqueta_periodo=None):
    """
    Procesa movimientos de UN empleado.
    campo_f: columna de fecha usada para agrupar por período
             ('FECHA' para rphistor_temp, 'FECHA_VEN' para rpingdesres)
    etiqueta_periodo: si se da, reemplaza el PERIODO generado (ej. '★ EN CURSO')
    Retorna DataFrame con una fila por período.
    """
    df = df_mov.copy()
    df.columns = [c.upper() for c in df.columns]

    campo_f = campo_f.upper()
    # rpingdesres puede no tener FECHA o tenerla vacía; usar FECHA_VEN en ese caso
    if campo_f not in df.columns:
        campo_f = 'FECHA_VEN' if 'FECHA_VEN' in df.columns else 'FECHA'
    df[campo_f] = pd.to_datetime(df[campo_f], errors='coerce')
    df = df.dropna(subset=[campo_f])           # eliminar filas con fecha nula
    df['PERIODO'] = df[campo_f].dt.strftime('%Y-%m')
    df['CLASE'] = pd.to_numeric(df['CLASE'], errors='coerce')
    df = df.dropna(subset=['CLASE'])
    df['CLASE'] = df['CLASE'].astype(int)

    cat = catalogo_rows.copy()
    cat.columns = [c.upper() for c in cat.columns]
    catalogo = {
        (str(r['TIPO']).strip(), str(r['CODIGO']).strip()): r['NOMBRE'] or r['CODIGO']
        for _, r in cat.iterrows()
    }

    filas = []
    for per, grupo in df.groupby('PERIODO'):
        fila = {'PERIODO': per, 'DIAS': 0}
        for c in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
            fila[c] = 0.0
        for _, reg in grupo.iterrows():
            clase = reg['CLASE']
            if clase in CODIGOS_IGNORAR:
                continue
            valor    = float(reg['VALOR'])    if pd.notna(reg.get('VALOR'))    else 0.0
            asentado = float(reg['ASENTADO']) if pd.notna(reg.get('ASENTADO')) else 0.0
            if clase in MAPEO_CONCEPTOS:
                concepto = MAPEO_CONCEPTOS[clase]
                if concepto in ('DECIMO_TERCERA','DECIMO_CUARTA'):
                    if asentado:
                        fila[concepto] += round(valor, 2)
                elif concepto == 'SUELDO':
                    fila[concepto] += round(valor, 2)
                    if pd.notna(reg.get('DIAS')):
                        fila['DIAS'] = reg['DIAS']
                elif concepto in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS:
                    fila[concepto] += round(valor, 2)
            elif str(reg.get('CODIGO','')).strip().upper() == 'EGR':
                fila['ANTICIPOS_SURTIDOS'] += round(valor, 2)
        fila['TOTAL_INGRESOS'] = round(sum(fila[c] for c in CONCEPTOS_INGRESOS), 2)
        fila['TOTAL_EGRESOS']  = round(sum(fila[c] for c in CONCEPTOS_EGRESOS),  2)
        fila['TOTAL_RECIBIR']  = round(fila['TOTAL_INGRESOS'] - fila['TOTAL_EGRESOS'], 2)
        filas.append(fila)

    if not filas:
        return pd.DataFrame()

    result = pd.DataFrame(filas).sort_values('PERIODO', ascending=False)

    # Resolver CARGO del empleado actual
    cargo_cod = str(emp_info.get('CARGO','')).strip()
    cargo_nom = catalogo.get(('FNC', cargo_cod), cargo_cod)
    depto_cod = str(emp_info.get('DEPTO','')).strip()
    depto_nom = catalogo.get(('DPT', depto_cod), depto_cod)
    secc_cod  = str(emp_info.get('SECCION','')).strip()
    secc_nom  = catalogo.get(('SEC', secc_cod), secc_cod)

    # Guardar nombres resueltos en emp_info para la cabecera de la UI
    emp_info['_CARGO_NOM'] = cargo_nom
    emp_info['_DEPTO_NOM'] = depto_nom
    emp_info['_SECC_NOM']  = secc_nom

    # Agregar columnas fijas del empleado a cada fila del historial
    result['CARGO']   = cargo_nom
    result['DEPTO']   = depto_nom
    result['SECCION'] = secc_nom
    fing = str(emp_info.get('FECHA_ING', '')).replace('T', ' ').strip()
    result['FECHA_ING'] = fing[:10] if fing not in ('', 'nan', 'None') else ''

    # Reemplazar etiqueta de período si se pidió (ej. EN CURSO)
    if etiqueta_periodo:
        result['PERIODO'] = etiqueta_periodo

    for c in CONCEPTOS_INGRESOS + CONCEPTOS_EGRESOS + ['TOTAL_INGRESOS','TOTAL_EGRESOS','TOTAL_RECIBIR']:
        if c in result.columns:
            result[c] = result[c].round(2)

    return result

# ─── Carga de datos ──────────────────────────────────────────────────────────
def cargar_empleados_supabase():
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    todos, offset = [], 0
    q = sb.table('rpemplea').select(
        'empleado,apellidos,nombres,cedula,cargo,depto,seccion,estado,sueldo,fecha_ing,fecha_sal'
    ).order('empleado')
    while True:
        r = q.range(offset, offset + 999).execute()
        if not r.data: break
        todos.extend(r.data)
        offset += 1000
        if len(r.data) < 1000: break
    df = pd.DataFrame(todos)
    df.columns = [c.upper() for c in df.columns]
    df['NOMBRE_COMPLETO'] = (df['APELLIDOS'].fillna('') + ' ' + df['NOMBRES'].fillna('')).str.strip()
    return df

def cargar_empleados_sql():
    import pyodbc
    conn = pyodbc.connect(_sql_conn_str(), timeout=10)
    df = pd.read_sql(
        "SELECT EMPLEADO,APELLIDOS,NOMBRES,CEDULA,CARGO,DEPTO,SECCION,ESTADO,SUELDO,FECHA_ING,FECHA_SAL FROM RPEMPLEA",
        conn
    )
    conn.close()
    df.columns = [c.upper() for c in df.columns]
    df['NOMBRE_COMPLETO'] = (df['APELLIDOS'].fillna('') + ' ' + df['NOMBRES'].fillna('')).str.strip()
    return df

def cargar_catalogo_supabase():
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    todos, offset = [], 0
    while True:
        r = (sb.table('dbtablas').select('tipo,codigo,nombre')
               .eq('codemp','10').order('tipo')
               .range(offset, offset+999).execute())
        if not r.data: break
        todos.extend(r.data)
        offset += 1000
        if len(r.data) < 1000: break
    return pd.DataFrame(todos)

def cargar_catalogo_sql():
    import pyodbc
    conn = pyodbc.connect(_sql_conn_str(), timeout=10)
    df = pd.read_sql("SELECT TIPO,CODIGO,NOMBRE FROM DBTABLAS WHERE CODEMP='10'", conn)
    conn.close()
    return df

def cargar_historial_supabase(emp_codigo, periodos=None):
    """Carga movimientos de rphistor_temp para un empleado. periodos=lista de 'YYYY-MM'."""
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        sb.postgrest.headers['Prefer'] = 'statement_timeout=60000'
    except Exception:
        pass

    todos, last_id, reintentos = [], 0, 0
    q_base = sb.table('rphistor_temp').select('*').eq('empleado', str(emp_codigo))
    if periodos:
        # Filtrar por rango: desde el más antiguo hasta el más reciente
        per_sorted = sorted(periodos)
        desde = f'{per_sorted[0]}-01'
        sig_y, sig_m = int(per_sorted[-1][:4]), int(per_sorted[-1][5:])
        sig_m += 1
        if sig_m > 12: sig_m = 1; sig_y += 1
        hasta = f'{sig_y}-{sig_m:02d}-01'
        q_base = q_base.gte('fecha', desde).lt('fecha', hasta)

    while True:
        try:
            r = q_base.gt('id', last_id).order('id').limit(2000).execute()
        except Exception as e:
            if reintentos < 3 and ('57014' in str(e) or 'timeout' in str(e).lower()):
                reintentos += 1
                time.sleep(reintentos * 3)
                continue
            raise
        reintentos = 0
        if not r.data: break
        todos.extend(r.data)
        last_id = r.data[-1]['id']
        if len(r.data) < 2000: break

    return pd.DataFrame(todos) if todos else pd.DataFrame()

def cargar_historial_sql(emp_codigo, periodos=None):
    import pyodbc
    conn = pyodbc.connect(_sql_conn_str(), timeout=10)
    if periodos:
        per_sorted = sorted(periodos)
        lista = ','.join(f"'{p}'" for p in per_sorted)
        query = f"""
            SELECT NUMERO,FECHA,EMPLEADO,CODSUC,CODEMP,CODIGO,CLASE,SECUENCIA,
                   DEPTO,SECCION,HORAS,VALOR,FECHA_VEN,CONCEPTO,DIAS,ASENTADO,
                   ACTUALIZA,APORTA,MONTO,DIVIDENDO,ROL,TIPO_PGO,TIPO_TRA,OBSERV
            FROM RPHISTOR
            WHERE EMPLEADO=? AND CONVERT(VARCHAR(7),FECHA,120) IN ({lista})
        """
    else:
        query = """
            SELECT NUMERO,FECHA,EMPLEADO,CODSUC,CODEMP,CODIGO,CLASE,SECUENCIA,
                   DEPTO,SECCION,HORAS,VALOR,FECHA_VEN,CONCEPTO,DIAS,ASENTADO,
                   ACTUALIZA,APORTA,MONTO,DIVIDENDO,ROL,TIPO_PGO,TIPO_TRA,OBSERV
            FROM RPHISTOR WHERE EMPLEADO=?
        """
    df = pd.read_sql(query, conn, params=[str(emp_codigo)])
    conn.close()
    return df

def _periodo_siguiente(periodo):
    """'2026-05' → '2026-06'"""
    y, m = int(periodo[:4]), int(periodo[5:])
    m += 1
    if m > 12:
        m, y = 1, y + 1
    return f'{y}-{m:02d}'

def cargar_actual_supabase(emp_codigo, periodo):
    """Carga rpingdesres para el empleado filtrado al período dado (fecha_ven)."""
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        sb.postgrest.headers['Prefer'] = 'statement_timeout=30000'
    except Exception:
        pass
    sig = _periodo_siguiente(periodo)
    todos, last_id = [], 0
    while True:
        r = (sb.table('rpingdesres').select('*')
               .eq('empleado', str(emp_codigo))
               .gte('fecha_ven', f'{periodo}-01')
               .lt('fecha_ven',  f'{sig}-01')
               .gt('id', last_id).order('id').limit(2000).execute())
        if not r.data:
            break
        todos.extend(r.data)
        last_id = r.data[-1]['id']
        if len(r.data) < 2000:
            break
    return pd.DataFrame(todos) if todos else pd.DataFrame()

def cargar_actual_sql(emp_codigo):
    """Trae TODOS los registros de RPINGDES para el empleado (sin filtro de fecha).
    El período más reciente se selecciona en el llamador."""
    import pyodbc
    COLS = ("NUMERO,FECHA,EMPLEADO,CODSUC,CODEMP,CODIGO,CLASE,SECUENCIA,"
            "DEPTO,SECCION,HORAS,VALOR,FECHA_VEN,CONCEPTO,DIAS,ASENTADO,"
            "ACTUALIZA,APORTA,MONTO,DIVIDENDO,ROL,TIPO_PGO,TIPO_TRA,OBSERV")
    conn = pyodbc.connect(_sql_conn_str(), timeout=10)
    df = pd.read_sql(
        f"SELECT {COLS} FROM RPINGDES WHERE EMPLEADO=?",
        conn, params=[str(emp_codigo)]
    )
    conn.close()
    return df

# ═══════════════════════════════════════════════════════════════════════════
#  VENTANA DE DETALLE (doble-clic en un período)
# ═══════════════════════════════════════════════════════════════════════════
class DetalleWindow(tk.Toplevel):
    """Muestra los registros individuales de un período para un empleado."""

    def __init__(self, parent, emp_sel, periodo, es_actual, fuente, df_catalogo):
        super().__init__(parent)
        self._emp_sel   = emp_sel
        self._periodo   = periodo    # 'YYYY-MM'
        self._es_actual = es_actual
        self._fuente    = fuente
        self._df_cat    = df_catalogo
        self._df_raw      = pd.DataFrame()
        self._observ_map  = {}   # iid → observación completa
        self._filtro_tipo    = tk.StringVar(value='Todos')
        self._filtro_concept = tk.StringVar(value='Todos')

        nombre  = str(emp_sel.get('NOMBRE_COMPLETO', '')).strip()
        cod     = str(emp_sel.get('EMPLEADO', '')).strip()
        per_fmt = _fmt_fecha(periodo)
        enc_txt = '  [EN CURSO]' if es_actual else ''

        self.title(f'Detalle {per_fmt}{enc_txt} — {nombre} (#{cod})')
        self.geometry('960x520')
        self.minsize(700, 380)

        F = 'Segoe UI'
        BG_BAR = '#1a73e8'

        # ── Encabezado ──────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_BAR, pady=8, padx=12)
        hdr.pack(fill='x')
        tk.Label(hdr,
                 text=f'Período: {per_fmt}{enc_txt}  │  {nombre}  (#{cod})',
                 font=(F, 12, 'bold'), bg=BG_BAR, fg='white').pack(side='left')

        # ── Barra de filtros ─────────────────────────────────────────────
        fbar = tk.Frame(self, bg='#f0f2f5', pady=7, padx=12)
        fbar.pack(fill='x')

        tk.Label(fbar, text='Mostrar:', bg='#f0f2f5',
                 font=(F, 11)).pack(side='left')
        for txt in ('Todos', 'Ingresos', 'Egresos'):
            tk.Radiobutton(fbar, text=txt, variable=self._filtro_tipo,
                           value=txt, bg='#f0f2f5', font=(F, 11),
                           command=self._aplicar_filtro).pack(side='left', padx=4)

        tk.Label(fbar, text='Concepto:', bg='#f0f2f5',
                 font=(F, 11)).pack(side='left', padx=(18, 4))
        self._cmb_concept = ttk.Combobox(fbar, textvariable=self._filtro_concept,
                                          values=['Todos'], width=24,
                                          state='readonly', font=(F, 11))
        self._cmb_concept.pack(side='left')
        self._cmb_concept.bind('<<ComboboxSelected>>',
                                lambda _: (self._tree.focus_set(),
                                           self._aplicar_filtro()))

        # ── Treeview con scroll ──────────────────────────────────────────
        cols = ('FECHA', 'TIPO', 'CLASE', 'CONCEPTO', 'VALOR', 'DIAS', 'OBSERV')
        frame_tree = tk.Frame(self, bg='white', padx=4, pady=4)
        frame_tree.pack(fill='both', expand=True)

        self._tree = ttk.Treeview(frame_tree, columns=cols,
                                   show='headings', selectmode='browse')

        widths  = {'FECHA': 88, 'TIPO': 72, 'CLASE': 52, 'CONCEPTO': 165,
                   'VALOR': 84, 'DIAS': 44, 'OBSERV': 220}
        anchors = {'VALOR': 'e', 'DIAS': 'e', 'CLASE': 'center', 'TIPO': 'center'}
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=widths.get(col, 80),
                              anchor=anchors.get(col, 'w'),
                              stretch=False, minwidth=30)

        self._tree.tag_configure('ingreso', background='#e8f5e9')
        self._tree.tag_configure('egreso',  background='#fce4ec')
        self._tree.tag_configure('otro',    background='#f8f9fa')

        sb_v = ttk.Scrollbar(frame_tree, orient='vertical',
                              command=self._tree.yview)
        sb_x = ttk.Scrollbar(frame_tree, orient='horizontal',
                              command=self._tree.xview)
        self._tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_x.set)
        sb_v.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        self._tree.pack(fill='both', expand=True)
        self._tree.bind('<<TreeviewSelect>>', self._on_row_select)

        # ── Panel observación (texto largo con wrap) ─────────────────────
        frame_obs = tk.Frame(self, bg='#f5f5f5', bd=1, relief='sunken')
        frame_obs.pack(fill='x', padx=4, pady=(0, 2))
        tk.Label(frame_obs, text='OBSERV:', font=(F, 9, 'bold'),
                 bg='#f5f5f5', fg='#555').pack(side='left', padx=(6, 4))
        self._txt_observ = tk.Text(frame_obs, height=2, wrap='word',
                                    font=(F, 10), bg='#f5f5f5', fg='#222',
                                    relief='flat', state='disabled',
                                    padx=4, pady=2)
        self._txt_observ.pack(side='left', fill='x', expand=True, pady=2)

        # ── Barra de resumen ─────────────────────────────────────────────
        self._lbl_resumen = tk.Label(
            self, text='Cargando...', anchor='w',
            font=('Courier New', 11), bg='#bbdefb', fg='#0d47a1',
            pady=5, padx=12)
        self._lbl_resumen.pack(fill='x')

        # ── Barra de estado ──────────────────────────────────────────────
        self._statusbar = tk.Label(
            self, text='Cargando datos...', anchor='w',
            font=(F, 10), bg='#dadce0', relief='sunken', padx=8, pady=3)
        self._statusbar.pack(fill='x', side='bottom')

        threading.Thread(target=self._cargar_datos, daemon=True).start()

    # ── Carga en hilo ────────────────────────────────────────────────────
    def _cargar_datos(self):
        try:
            emp_cod = str(self._emp_sel.get('EMPLEADO', ''))
            if self._es_actual:
                fn_supa = cargar_actual_supabase
                fn_sql  = cargar_actual_sql
                df = fn_supa(emp_cod, self._periodo) \
                     if self._fuente == 'Supabase' \
                     else fn_sql(emp_cod, self._periodo)
            else:
                df = cargar_historial_supabase(emp_cod, [self._periodo]) \
                     if self._fuente == 'Supabase' \
                     else cargar_historial_sql(emp_cod, [self._periodo])

            if df.empty:
                self.after(0, lambda: (
                    self._statusbar.config(text='Sin registros para este período'),
                    self._lbl_resumen.config(text='Sin datos')))
                return

            df = df.copy()
            df.columns = [c.upper() for c in df.columns]

            # Filtrar CODIGOS_IGNORAR
            def _int_clase(v):
                try: return int(float(v))
                except: return -1
            df = df[~df['CLASE'].apply(_int_clase).isin(CODIGOS_IGNORAR)]

            # Derivar TIPO y nombre de concepto
            def _tipo(clase):
                try:
                    c = int(float(clase))
                    nom = MAPEO_CONCEPTOS.get(c)
                    if nom in CONCEPTOS_INGRESOS:  return 'INGRESO'
                    if nom in CONCEPTOS_EGRESOS:   return 'EGRESO'
                except Exception:
                    pass
                return 'OTRO'

            def _concepto_nom(clase):
                try:
                    c = int(float(clase))
                    return MAPEO_CONCEPTOS.get(c, f'CLASE {c}')
                except Exception:
                    return str(clase)

            df['_TIPO']     = df['CLASE'].apply(_tipo)
            df['_CONCEPTO'] = df['CLASE'].apply(_concepto_nom)

            self._df_raw = df
            self.after(0, self._poblar_tabla)

        except Exception as ex:
            self.after(0, lambda e=ex: self._statusbar.config(text=f'Error: {e}'))

    # ── Observación completa al seleccionar fila ────────────────────────
    def _on_row_select(self, _=None):
        sel = self._tree.selection()
        iid = sel[0] if sel else None
        obs = self._observ_map.get(iid, '') if iid else ''
        self._txt_observ.config(state='normal')
        self._txt_observ.delete('1.0', 'end')
        if obs:
            self._txt_observ.insert('end', obs)
        self._txt_observ.config(state='disabled')

    # ── Poblar combobox y tabla ──────────────────────────────────────────
    def _poblar_tabla(self):
        conceptos = ['Todos'] + sorted(
            self._df_raw['_CONCEPTO'].dropna().unique().tolist())
        self._cmb_concept['values'] = conceptos
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        if self._df_raw.empty or '_TIPO' not in self._df_raw.columns:
            return
        df   = self._df_raw.copy()
        tipo = self._filtro_tipo.get()
        concepto = self._filtro_concept.get()

        if tipo == 'Ingresos':
            df = df[df['_TIPO'] == 'INGRESO']
        elif tipo == 'Egresos':
            df = df[df['_TIPO'] == 'EGRESO']

        if concepto != 'Todos':
            df = df[df['_CONCEPTO'] == concepto]

        # Limpiar treeview y forzar repintado antes de insertar nuevas filas
        for iid in self._tree.get_children():
            self._tree.delete(iid)
        self._tree.update()   # repintado real para evitar artefactos visuales

        self._observ_map.clear()
        total_ing = total_egr = 0.0

        campo_fecha = 'FECHA_VEN' if self._es_actual else 'FECHA'

        def _limpio(v):
            s = str(v).strip() if v is not None else ''
            return '' if s in ('nan', 'None', 'NaT', 'none') else s

        for idx, (_, row) in enumerate(df.iterrows()):
            tipo_row = row.get('_TIPO', 'OTRO')
            tag = ('ingreso' if tipo_row == 'INGRESO'
                   else 'egreso' if tipo_row == 'EGRESO'
                   else 'otro')

            fecha_val = row.get(campo_fecha, '')
            fecha_fmt = _fmt_fecha(str(fecha_val).replace('T', ' ')[:10])

            valor = 0.0
            try: valor = float(row.get('VALOR', 0) or 0)
            except: pass

            dias_raw = row.get('DIAS', '')
            try:
                dias = (int(float(dias_raw))
                        if pd.notna(dias_raw) and str(dias_raw) not in ('', 'nan')
                        else '')
            except Exception:
                dias = str(dias_raw) if dias_raw else ''

            observ_full = _limpio(row.get('OBSERV', ''))
            # Truncar en celda; texto completo se muestra en panel inferior al seleccionar
            observ_cell = (observ_full[:55] + '…') if len(observ_full) > 58 else observ_full

            iid = f'd{idx}'
            self._tree.insert('', 'end', iid=iid, values=(
                fecha_fmt, tipo_row, row.get('CLASE', ''),
                row.get('_CONCEPTO', ''), f'{valor:,.2f}',
                dias, observ_cell,
            ), tags=(tag,))
            self._observ_map[iid] = observ_full

            if tipo_row == 'INGRESO':
                total_ing += valor
            elif tipo_row == 'EGRESO':
                total_egr += valor

        n             = len(df)
        neto          = total_ing - total_egr
        total_filtrado = total_ing + total_egr   # suma de todos los VALOR visibles

        concepto_sel  = self._filtro_concept.get()
        tipo_sel      = self._filtro_tipo.get()
        filtro_activo = concepto_sel != 'Todos' or tipo_sel != 'Todos'

        if filtro_activo:
            # Con filtro activo: mostrar total de los valores filtrados de forma destacada
            partes = [f'Registros: {n}   │   TOTAL FILTRADO: ${total_filtrado:,.2f}']
            if tipo_sel == 'Todos':
                partes.append(f'Ingresos: ${total_ing:,.2f}')
                partes.append(f'Egresos: ${total_egr:,.2f}')
                partes.append(f'Neto: ${neto:,.2f}')
        else:
            partes = [
                f'Registros: {n}',
                f'Ingresos: ${total_ing:,.2f}',
                f'Egresos: ${total_egr:,.2f}',
                f'Neto: ${neto:,.2f}',
            ]

        self._lbl_resumen.config(text='   │   '.join(partes))
        self._statusbar.config(text=f'{n} registro(s) — período {_fmt_fecha(self._periodo)}')
        self.after(10, self.update)   # repintado real tras procesar eventos pendientes


# ═══════════════════════════════════════════════════════════════════════════
#  APLICACIÓN GUI
# ═══════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Historial de Nómina por Empleado')
        self.geometry('1280x720')
        self.minsize(900, 600)

        self._df_empleados = pd.DataFrame()  # todos los empleados cargados
        self._df_catalogo  = pd.DataFrame()
        self._df_historial = pd.DataFrame()  # historial del empleado seleccionado
        self._emp_sel      = {}              # info del empleado seleccionado
        self._fuente         = tk.StringVar(value='Supabase')
        self._n_periodos     = tk.StringVar(value='Últimos 4 meses')
        self._buscar_var     = tk.StringVar()
        self._filtro_estado  = tk.StringVar(value='Todos')
        self._periodo_enc    = tk.StringVar(value=_periodos_recientes(1)[0])
        self._cargando       = False
        self._sync_scroll    = False
        self._sel_syncing    = False
        self._iid_info       = {}    # iid → {'periodo': 'YYYY-MM', 'es_actual': bool}

        self._build_ui()
        self.after(200, self._iniciar_carga)

    # ── Construcción de la interfaz ─────────────────────────────────────────
    def _build_ui(self):
        # Colores
        BG    = '#f0f2f5'
        PANEL = '#ffffff'
        AZUL  = '#1a73e8'
        GRIS  = '#5f6368'
        F     = 'Segoe UI'   # familia de fuente

        self.configure(bg=BG)

        # Tema y estilos globales
        style = ttk.Style()
        try:
            style.theme_use('clam')   # da soporte de bordes/recuadros en tablas
        except Exception:
            pass
        style.configure('Treeview',
            font=(F, 11), rowheight=26,
            background='white', fieldbackground='white',
            bordercolor='#b8c8d8', borderwidth=1, relief='flat')
        style.configure('Treeview.Heading',
            font=(F, 11, 'bold'),
            background='#dde8f5', foreground='#1a237e',
            borderwidth=1, relief='groove')
        style.map('Treeview',
            background=[('selected', '#1a73e8')],
            foreground=[('selected', 'white')])

        # ── Barra superior ───────────────────────────────────────────────
        top = tk.Frame(self, bg=AZUL, pady=10, padx=14)
        top.pack(fill='x')

        tk.Label(top, text='📋 Historial de Nómina', font=(F, 14, 'bold'),
                 bg=AZUL, fg='white').pack(side='left')

        # Fuente
        tk.Label(top, text='Fuente:', bg=AZUL, fg='white',
                 font=(F, 11)).pack(side='left', padx=(20, 4))
        ttk.Combobox(top, textvariable=self._fuente,
                     values=['Supabase', 'SQL Server'], width=11,
                     state='readonly', font=(F, 11)).pack(side='left')
        self._fuente.trace_add('write', lambda *_: self._iniciar_carga())

        # Períodos
        tk.Label(top, text='Períodos:', bg=AZUL, fg='white',
                 font=(F, 11)).pack(side='left', padx=(16, 4))
        ttk.Combobox(top, textvariable=self._n_periodos,
                     values=list(OPCIONES_PERIODOS.keys()), width=16,
                     state='readonly', font=(F, 11)).pack(side='left')
        self._n_periodos.trace_add('write', lambda *_: self._recargar_historial_si_hay())

        # Filtro de estado de empleado
        tk.Label(top, text='Estado:', bg=AZUL, fg='white',
                 font=(F, 11)).pack(side='left', padx=(16, 4))
        ttk.Combobox(top, textvariable=self._filtro_estado,
                     values=['Todos', 'Activos', 'Liquidados'], width=10,
                     state='readonly', font=(F, 11)).pack(side='left')
        self._filtro_estado.trace_add('write', lambda *_: self._filtrar())

        # Período en curso (editable, por defecto el mes actual)
        tk.Label(top, text='Período actual:', bg=AZUL, fg='white',
                 font=(F, 11)).pack(side='left', padx=(16, 4))
        entry_enc = tk.Entry(top, textvariable=self._periodo_enc,
                             font=(F, 11), width=8)
        entry_enc.pack(side='left')
        entry_enc.bind('<Return>',    lambda _: self._recargar_historial_si_hay())
        entry_enc.bind('<FocusOut>',  lambda _: self._recargar_historial_si_hay())

        # Barra de búsqueda
        tk.Label(top, text='🔍', bg=AZUL, fg='white',
                 font=(F, 12)).pack(side='left', padx=(24, 4))
        self._entry_buscar = tk.Entry(top, textvariable=self._buscar_var,
                                      font=(F, 11), width=28)
        self._entry_buscar.pack(side='left')
        self._entry_buscar.bind('<Return>', lambda _: self._filtrar())
        self._buscar_var.trace_add('write', lambda *_: self._filtrar())

        tk.Button(top, text='Buscar', font=(F, 11),
                  command=self._filtrar, relief='flat',
                  bg='#0d47a1', fg='white', padx=10, pady=2).pack(side='left', padx=6)

        # ── Cuerpo principal ─────────────────────────────────────────────
        cuerpo = tk.PanedWindow(self, orient='horizontal', sashwidth=6,
                                bg=BG, relief='flat')
        cuerpo.pack(fill='both', expand=True, padx=14, pady=10)

        # ── Panel izquierdo: lista de empleados ──────────────────────────
        frame_izq = tk.Frame(cuerpo, bg=PANEL, relief='flat', bd=1)
        cuerpo.add(frame_izq, minsize=270, width=320)

        tk.Label(frame_izq, text='Empleados', font=(F, 11, 'bold'),
                 bg=PANEL, fg=GRIS, pady=8).pack(fill='x', padx=10)
        ttk.Separator(frame_izq).pack(fill='x')

        cols_emp = ('EMPLEADO', 'NOMBRE', 'ESTADO')
        self._tree_emp = ttk.Treeview(frame_izq, columns=cols_emp,
                                       show='headings', selectmode='browse')
        self._tree_emp.heading('EMPLEADO', text='Cód')
        self._tree_emp.heading('NOMBRE',   text='Nombre')
        self._tree_emp.heading('ESTADO',   text='Est')
        self._tree_emp.column('EMPLEADO', width=58,  anchor='center', stretch=False)
        self._tree_emp.column('NOMBRE',   width=210, anchor='w')
        self._tree_emp.column('ESTADO',   width=40,  anchor='center', stretch=False)

        sb_emp = ttk.Scrollbar(frame_izq, orient='vertical',
                               command=self._tree_emp.yview)
        self._tree_emp.configure(yscrollcommand=sb_emp.set)
        self._tree_emp.pack(side='left', fill='both', expand=True)
        sb_emp.pack(side='right', fill='y')
        self._tree_emp.bind('<<TreeviewSelect>>', self._on_seleccionar)
        self._tree_emp.tag_configure('inact', foreground='#aaa')

        # Contador
        self._lbl_conteo = tk.Label(frame_izq, text='', font=(F, 10),
                                     bg=PANEL, fg=GRIS)
        self._lbl_conteo.pack(pady=4)

        # ── Panel derecho: info + historial ──────────────────────────────
        frame_der = tk.Frame(cuerpo, bg=PANEL)
        cuerpo.add(frame_der, minsize=500)

        # Info del empleado seleccionado
        self._frame_info = tk.Frame(frame_der, bg='#e8f0fe', pady=10, padx=14)
        self._frame_info.pack(fill='x')

        self._lbl_nombre  = tk.Label(self._frame_info, text='— Selecciona un empleado —',
                                      font=(F, 12, 'bold'), bg='#e8f0fe', fg='#1a237e')
        self._lbl_nombre.pack(anchor='w')
        self._lbl_detalle = tk.Label(self._frame_info, text='',
                                      font=(F, 11), bg='#e8f0fe', fg='#37474f')
        self._lbl_detalle.pack(anchor='w', pady=(2, 0))

        ttk.Separator(frame_der).pack(fill='x')

        # Tabla historial: columna PERIODO fija + resto desplazable
        frame_tabla = tk.Frame(frame_der, bg=PANEL, padx=4, pady=4)
        frame_tabla.pack(fill='both', expand=True)

        TAGS = {'par': '#f8f9fa', 'impar': '#ffffff',
                'total': '#e3f2fd', 'encurso': '#fffde7'}

        def _cfg_tags(tree):
            tree.tag_configure('par',     background=TAGS['par'])
            tree.tag_configure('impar',   background=TAGS['impar'])
            tree.tag_configure('total',   background=TAGS['total'],
                               font=(F, 11, 'bold'))
            tree.tag_configure('encurso', background=TAGS['encurso'],
                               font=(F, 11, 'bold'))

        # ── Columna fija (PERIODO) ──────────────────────────────────────
        frame_fijo = tk.Frame(frame_tabla, bg=PANEL)
        self._tree_fijo = ttk.Treeview(frame_fijo, columns=COLS_FIJA,
                                        show='headings', selectmode='browse')
        self._tree_fijo.heading('PERIODO', text=HEADER_CORTO['PERIODO'],
                                anchor='center')
        self._tree_fijo.column('PERIODO', width=85, anchor='center',
                               stretch=False, minwidth=60)
        _cfg_tags(self._tree_fijo)
        self._tree_fijo.pack(fill='both', expand=True)

        # Borde visual entre fijo y móvil
        sep = tk.Frame(frame_tabla, width=2, bg='#b8c8d8')

        # ── Columnas móviles ────────────────────────────────────────────
        COLS_MOV = [c for c in COLS_TABLA if c not in COLS_FIJA]
        frame_movil = tk.Frame(frame_tabla, bg=PANEL)
        self._tree_hist = ttk.Treeview(frame_movil, columns=COLS_MOV,
                                        show='headings', selectmode='browse')
        for col in COLS_MOV:
            hdr = HEADER_CORTO.get(col, col)
            self._tree_hist.heading(col, text=hdr, anchor='e')
            self._tree_hist.column(col, width=60, anchor='e',
                                   stretch=False, minwidth=30)
        _cfg_tags(self._tree_hist)

        # Scrollbars
        sb_v = ttk.Scrollbar(frame_tabla, orient='vertical')
        sb_x = ttk.Scrollbar(frame_movil, orient='horizontal',
                              command=self._tree_hist.xview)
        self._tree_hist.configure(xscrollcommand=sb_x.set)

        # Scroll vertical: scrollbar controla ambos; yscrollcommand solo actualiza la barra
        def _yview_ambos(*args):
            self._tree_fijo.yview(*args)
            self._tree_hist.yview(*args)

        def _yscroll_sync(first, last):
            sb_v.set(first, last)
            if not self._sync_scroll:
                self._sync_scroll = True
                self._tree_fijo.yview_moveto(first)
                self._tree_hist.yview_moveto(first)
                self._sync_scroll = False

        self._tree_fijo.configure(yscrollcommand=_yscroll_sync)
        self._tree_hist.configure(yscrollcommand=_yscroll_sync)
        sb_v.configure(command=_yview_ambos)

        # Mousewheel en cualquiera de los dos paneles mueve ambos
        def _wheel(event):
            if event.num == 4 or event.delta > 0:
                self._tree_fijo.yview_scroll(-1, 'units')
                self._tree_hist.yview_scroll(-1, 'units')
            else:
                self._tree_fijo.yview_scroll(1, 'units')
                self._tree_hist.yview_scroll(1, 'units')
            return 'break'

        for w in (self._tree_fijo, self._tree_hist):
            w.bind('<MouseWheel>', _wheel)
            w.bind('<Button-4>',   _wheel)
            w.bind('<Button-5>',   _wheel)

        # Selección sincronizada entre columna fija y panel móvil
        self._tree_fijo.bind('<<TreeviewSelect>>', self._on_sel_fijo)
        self._tree_hist.bind('<<TreeviewSelect>>', self._on_sel_hist)

        # Doble-clic abre ventana de detalle
        self._tree_fijo.bind('<Double-Button-1>', self._ver_detalle)
        self._tree_hist.bind('<Double-Button-1>', self._ver_detalle)

        # Packing (sb_v debe ir antes que frame_movil para quedar a la derecha)
        frame_fijo.pack(side='left', fill='y')
        sep.pack(side='left', fill='y')
        sb_v.pack(side='right', fill='y')
        frame_movil.pack(side='left', fill='both', expand=True)
        sb_x.pack(side='bottom', fill='x')
        self._tree_hist.pack(fill='both', expand=True)

        # Fila de totales (fija al fondo)
        self._frame_totales = tk.Frame(frame_der, bg='#bbdefb', pady=5, padx=10)
        self._frame_totales.pack(fill='x')
        self._lbl_totales = tk.Label(self._frame_totales, text='',
                                      font=('Courier New', 11), bg='#bbdefb', fg='#0d47a1',
                                      anchor='w')
        self._lbl_totales.pack(fill='x')

        # Botón exportar
        bar_bot = tk.Frame(frame_der, bg=PANEL, pady=6, padx=10)
        bar_bot.pack(fill='x')
        tk.Button(bar_bot, text='⬇  Exportar a Excel',
                  command=self._exportar, font=(F, 11),
                  bg='#2e7d32', fg='white', relief='flat', padx=12, pady=4
                  ).pack(side='left')
        self._lbl_filas = tk.Label(bar_bot, text='', font=(F, 10),
                                    bg=PANEL, fg=GRIS)
        self._lbl_filas.pack(side='right', padx=8)

        # ── Barra de estado ──────────────────────────────────────────────
        self._statusbar = tk.Label(self, text='Iniciando...', anchor='w',
                                    font=(F, 10), bg='#dadce0',
                                    relief='sunken', padx=8, pady=3)
        self._statusbar.pack(fill='x', side='bottom')

    # ── Carga inicial ────────────────────────────────────────────────────────
    def _iniciar_carga(self):
        if self._cargando:
            return
        self._cargando = True
        self._statusbar.config(text=f'Cargando empleados desde {self._fuente.get()}...')
        self._tree_emp.delete(*self._tree_emp.get_children())
        self._lbl_conteo.config(text='')
        threading.Thread(target=self._thr_cargar_empleados, daemon=True).start()

    def _thr_cargar_empleados(self):
        try:
            fuente = self._fuente.get()
            if fuente == 'Supabase':
                df_e = cargar_empleados_supabase()
                df_c = cargar_catalogo_supabase()
            else:
                df_e = cargar_empleados_sql()
                df_c = cargar_catalogo_sql()
            self._df_empleados = df_e
            self._df_catalogo  = df_c
            self.after(0, lambda: self._post_carga(len(df_e)))
        except Exception as ex:
            self.after(0, lambda e=ex: self._error_carga(e))
        finally:
            self._cargando = False

    def _post_carga(self, n):
        self._statusbar.config(text=f'{n:,} empleados cargados — escribe para buscar')
        self._entry_buscar.focus_set()
        self._filtrar()

    def _error_carga(self, ex):
        self._statusbar.config(text=f'Error: {ex}')
        messagebox.showerror('Error de conexión', str(ex))

    # ── Búsqueda / filtro ────────────────────────────────────────────────────
    def _filtrar(self):
        if self._df_empleados.empty:
            return
        texto  = self._buscar_var.get().strip().upper()
        estado = self._filtro_estado.get()
        df = self._df_empleados

        # Filtro por estado
        if estado == 'Activos':
            df = df[df['ESTADO'].astype(str).str.strip().str.upper() == 'ACT']
        elif estado == 'Liquidados':
            df = df[df['ESTADO'].astype(str).str.strip().str.upper() != 'ACT']

        # Filtro por texto (nombre, código, cédula)
        if texto:
            mask = (df['NOMBRE_COMPLETO'].str.upper().str.contains(texto, na=False) |
                    df['EMPLEADO'].astype(str).str.contains(texto, na=False) |
                    df['CEDULA'].astype(str).str.contains(texto, na=False))
            df = df[mask]

        self._tree_emp.delete(*self._tree_emp.get_children())
        for _, r in df.head(200).iterrows():
            tag = 'inact' if str(r.get('ESTADO', '')).strip().upper() != 'ACT' else ''
            self._tree_emp.insert('', 'end',
                iid=str(r['EMPLEADO']),
                values=(r['EMPLEADO'], r['NOMBRE_COMPLETO'],
                        str(r.get('ESTADO', '')).strip()),
                tags=(tag,))
        total = len(df)
        self._lbl_conteo.config(
            text=f'{min(total, 200)} de {total} empleados'
            + ('  (mostrando 200)' if total > 200 else ''))

    # ── Selección de empleado ────────────────────────────────────────────────
    def _on_seleccionar(self, _event=None):
        sel = self._tree_emp.selection()
        if not sel:
            return
        emp_cod = sel[0]
        df_e = self._df_empleados
        fila = df_e[df_e['EMPLEADO'].astype(str) == str(emp_cod)]
        if fila.empty:
            return
        self._emp_sel = fila.iloc[0].to_dict()
        self._cargar_historial(emp_cod)

    def _on_sel_fijo(self, _=None):
        sel = self._tree_fijo.selection()
        if sel and set(sel) != set(self._tree_hist.selection()):
            self._tree_hist.selection_set(sel)
            self._tree_hist.see(sel[0])

    def _on_sel_hist(self, _=None):
        sel = self._tree_hist.selection()
        if sel and set(sel) != set(self._tree_fijo.selection()):
            self._tree_fijo.selection_set(sel)

    def _recargar_historial_si_hay(self):
        if self._emp_sel:
            emp_cod = str(self._emp_sel.get('EMPLEADO',''))
            if emp_cod:
                self._cargar_historial(emp_cod)

    def _ver_detalle(self, event):
        widget = event.widget
        iid = widget.identify_row(event.y)
        if not iid or iid not in self._iid_info:
            return
        info    = self._iid_info[iid]
        periodo = info.get('periodo', '')
        if not periodo or periodo in ('', 'nan', 'None', 'NaT'):
            return
        DetalleWindow(
            self,
            emp_sel=self._emp_sel,
            periodo=periodo,
            es_actual=info.get('es_actual', False),
            fuente=self._fuente.get(),
            df_catalogo=self._df_catalogo,
        )

    def _cargar_historial(self, emp_cod):
        n_per  = OPCIONES_PERIODOS[self._n_periodos.get()]
        periodos = None if n_per >= 999 else _periodos_recientes(n_per)
        self._statusbar.config(
            text=f'Cargando historial de emp {emp_cod}...')
        self._tree_fijo.delete(*self._tree_fijo.get_children())
        self._tree_hist.delete(*self._tree_hist.get_children())
        self._lbl_totales.config(text='')
        self._lbl_filas.config(text='')
        threading.Thread(
            target=self._thr_historial,
            args=(emp_cod, periodos),
            daemon=True
        ).start()

    def _thr_historial(self, emp_cod, periodos):
        try:
            fuente         = self._fuente.get()
            periodo_actual = self._periodo_enc.get().strip()

            if fuente == 'Supabase':
                df_mov    = cargar_historial_supabase(emp_cod, periodos)
                df_actual = cargar_actual_supabase(emp_cod, periodo_actual) if periodo_actual else pd.DataFrame()
            else:
                df_mov    = cargar_historial_sql(emp_cod, periodos)
                # SQL Server: traer todos los registros de RPINGDES sin filtro fecha
                df_actual = cargar_actual_sql(emp_cod)

            df_h = pd.DataFrame()
            if not df_mov.empty:
                df_h = procesar_empleado(df_mov, self._emp_sel, self._df_catalogo)
                if periodos:
                    df_h = df_h[df_h['PERIODO'].isin(periodos)]

            df_enc = pd.DataFrame()
            if not df_actual.empty:
                if fuente == 'Supabase':
                    # Supabase: las fechas son confiables — agrupar por FECHA_VEN
                    df_enc = procesar_empleado(
                        df_actual, self._emp_sel, self._df_catalogo,
                        campo_f='FECHA_VEN')
                else:
                    # SQL Server: RPINGDES puede tener FECHA_VEN/FECHA incorrectas.
                    # Forzar todos los registros al período indicado por el usuario.
                    dc = df_actual.copy()
                    dc.columns = [c.upper() for c in dc.columns]
                    mid = f'{periodo_actual}-15'
                    for col in ('FECHA_VEN', 'FECHA'):
                        if col in dc.columns:
                            dc[col] = mid
                    df_enc = procesar_empleado(
                        dc, self._emp_sel, self._df_catalogo,
                        campo_f='FECHA_VEN')

            if df_h.empty and df_enc.empty:
                self.after(0, lambda: self._statusbar.config(
                    text=f'Sin datos para emp {emp_cod}'))
                return

            self.after(0, lambda h=df_h, e=df_enc: self._mostrar_historial(h, e))
        except Exception as ex:
            self.after(0, lambda e=ex: self._statusbar.config(text=f'Error: {e}'))

    # ── Mostrar historial en tabla ───────────────────────────────────────────
    def _mostrar_historial(self, df, df_enc=None):
        if df_enc is None:
            df_enc = pd.DataFrame()

        # Combinar para exportar (EN CURSO primero)
        frames = []
        if not df_enc.empty:
            frames.append(df_enc)
        if not df.empty:
            frames.append(df)
        df_todo = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        self._df_historial = df_todo

        # Info del empleado
        emp = self._emp_sel
        nombre = str(emp.get('NOMBRE_COMPLETO','')).strip()
        cod    = str(emp.get('EMPLEADO','')).strip()
        cargo  = emp.get('_CARGO_NOM', str(emp.get('CARGO','')))
        depto  = emp.get('_DEPTO_NOM', str(emp.get('DEPTO','')))
        ci     = str(emp.get('CEDULA','')).strip()
        sueldo = emp.get('SUELDO', 0)
        estado = str(emp.get('ESTADO','')).strip()
        fing   = _fmt_fecha(str(emp.get('FECHA_ING','')).replace('T',' ')[:10])
        fsal   = _fmt_fecha(str(emp.get('FECHA_SAL','')).replace('T',' ')[:10])
        if fsal in ('', 'nan', 'None', 'NaT', ''): fsal = 'Activo'

        self._lbl_nombre.config(
            text=f'{nombre}  (#{cod})  [{estado}]')
        self._lbl_detalle.config(
            text=f'Cargo: {cargo[:35]}  │  Depto: {depto[:35]}  │  '
                 f'CI: {ci}  │  Sueldo base: ${float(sueldo or 0):,.2f}  │  '
                 f'Ingreso: {fing}  │  Sal: {fsal}')

        # Poblar tabla (columna fija + móviles, mismo iid para sincronizar selección)
        self._tree_fijo.delete(*self._tree_fijo.get_children())
        self._tree_hist.delete(*self._tree_hist.get_children())

        COLS_MOV = [c for c in COLS_TABLA if c not in COLS_FIJA]
        self._iid_info.clear()

        def _insert_fila(row, tag, iid, es_actual=False):
            per = _fmt_fecha(str(row.get('PERIODO', '')))
            self._tree_fijo.insert('', 'end', iid=iid, values=(per,), tags=(tag,))
            vals_mov = []
            for col in COLS_MOV:
                v = row.get(col, '')
                vals_mov.append(_fmt_fecha(str(v)) if col == 'FECHA_ING' else _fmt(v))
            self._tree_hist.insert('', 'end', iid=iid, values=vals_mov, tags=(tag,))
            self._iid_info[iid] = {
                'periodo': str(row.get('PERIODO', '')),
                'es_actual': es_actual,
            }

        n = 0
        # Período abierto al tope (fondo amarillo)
        if not df_enc.empty:
            for _, row in df_enc.iterrows():
                _insert_fila(row, 'encurso', f'r{n}', es_actual=True); n += 1

        # Filas históricas con colores alternos
        for i, (_, row) in enumerate(df.iterrows()):
            _insert_fila(row, 'par' if i % 2 == 0 else 'impar', f'r{n}', es_actual=False); n += 1

        # Fila de totales (suma todo incluyendo EN CURSO)
        num_cols = [c for c in COLS_TABLA if c != 'PERIODO']
        totales = {c: pd.to_numeric(df_todo[c], errors='coerce').sum()
                   if c in df_todo.columns else 0
                   for c in num_cols}
        n_hist   = len(df)
        enc_txt  = ' + EN CURSO' if not df_enc.empty else ''
        parts = [f"TOTAL {n_hist} período(s){enc_txt}: "]
        for c in ['SUELDO','TOTAL_INGRESOS','TOTAL_EGRESOS','TOTAL_RECIBIR']:
            if c in totales:
                lbl = HEADER_CORTO.get(c, c)
                parts.append(f'{lbl}=${totales[c]:,.2f}')
        self._lbl_totales.config(text='   │   '.join(parts))
        self._lbl_filas.config(text=f'{n_hist} período(s){enc_txt}')
        self._statusbar.config(
            text=f'Historial de {nombre} — {n_hist} período(s){enc_txt}')
        # Diferir autofit para que tkinter termine de renderizar primero
        self.after(80, self._autofit_columnas)

    # ── Autofit de columnas (como "Ajustar" en Excel) ────────────────────────
    def _autofit_columnas(self):
        """Ajusta cada columna al texto más ancho (encabezado o celda)."""
        # Fuente de celdas
        try:
            font_cell = tkfont.nametofont('TkDefaultFont')
        except Exception:
            return
        # Fuente de encabezados: igual que celda pero bold
        fa = font_cell.actual()
        try:
            font_hdr = tkfont.Font(family=fa['family'], size=fa['size'], weight='bold')
        except Exception:
            font_hdr = font_cell

        PAD      = 20
        COLS_MOV = [c for c in COLS_TABLA if c not in COLS_FIJA]

        # Auto-fit columna fija (PERIODO)
        for i, col in enumerate(COLS_FIJA):
            ancho = font_hdr.measure(HEADER_CORTO.get(col, col)) + PAD
            for iid in self._tree_fijo.get_children():
                vals = self._tree_fijo.item(iid, 'values')
                if i < len(vals) and vals[i]:
                    w = font_cell.measure(str(vals[i])) + PAD
                    if w > ancho: ancho = w
            self._tree_fijo.column(col, width=ancho, minwidth=50)

        # Auto-fit columnas móviles
        for i, col in enumerate(COLS_MOV):
            ancho = font_hdr.measure(HEADER_CORTO.get(col, col)) + PAD
            for iid in self._tree_hist.get_children():
                vals = self._tree_hist.item(iid, 'values')
                if i < len(vals) and vals[i]:
                    w = font_cell.measure(str(vals[i])) + PAD
                    if w > ancho: ancho = w
            self._tree_hist.column(col, width=ancho, minwidth=30)

    # ── Exportar ─────────────────────────────────────────────────────────────
    def _exportar(self):
        if self._df_historial.empty:
            messagebox.showinfo('Sin datos', 'Selecciona un empleado primero.')
            return
        emp = self._emp_sel
        nombre = str(emp.get('NOMBRE_COMPLETO','')).strip().replace(' ','_')[:25]
        cod    = str(emp.get('EMPLEADO','')).strip()
        ts     = datetime.now().strftime('%Y%m%d_%H%M%S')
        default = f'HISTORIAL_{cod}_{nombre}_{ts}.xlsx'

        ruta = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel','*.xlsx')],
            initialfile=default,
            title='Guardar historial')
        if not ruta:
            return

        try:
            with pd.ExcelWriter(ruta, engine='openpyxl') as w:
                # Info del empleado en primera hoja
                info = pd.DataFrame([
                    ['Empleado', cod],
                    ['Nombre',   emp.get('NOMBRE_COMPLETO','')],
                    ['Cédula',   emp.get('CEDULA','')],
                    ['Cargo',    emp.get('_CARGO_NOM', emp.get('CARGO',''))],
                    ['Depto',    emp.get('_DEPTO_NOM', emp.get('DEPTO',''))],
                    ['Sección',  emp.get('_SECC_NOM',  emp.get('SECCION',''))],
                    ['Sueldo base', emp.get('SUELDO',0)],
                    ['Estado',   emp.get('ESTADO','')],
                    ['Fecha ingreso', str(emp.get('FECHA_ING','')).replace('T',' ')[:10]],
                    ['Fecha salida',  str(emp.get('FECHA_SAL','')).replace('T',' ')[:10]],
                ], columns=['Campo','Valor'])
                info.to_excel(w, sheet_name='INFO_EMPLEADO', index=False)

                # Historial
                df_exp = self._df_historial[COLS_TABLA].copy()
                df_exp.to_excel(w, sheet_name='HISTORIAL_NOMINA', index=False)

                # Formato columnas
                for sheet in w.sheets.values():
                    for col in sheet.columns:
                        max_len = max((len(str(c.value or '')) for c in col), default=8)
                        sheet.column_dimensions[col[0].column_letter].width = min(max_len+2, 30)

            # Abrir archivo
            if platform.system() == 'Windows':
                os.startfile(ruta)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', ruta])
            else:
                subprocess.call(['xdg-open', ruta])

            self._statusbar.config(text=f'Exportado: {Path(ruta).name}')
        except Exception as ex:
            messagebox.showerror('Error al exportar', str(ex))

# ═══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    app = App()
    app.mainloop()
