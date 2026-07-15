#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA GESTION EMPLEADOS v10.0 - INSEVIG
GUI Mejorada siguiendo estándares RRHH documentados.
Compatible Linux/Windows.
"""

import os, sys, threading, webbrowser, shutil, tempfile, calendar, logging
from pathlib import Path
from datetime import datetime

# Setup logging (archivo + terminal)
import sys
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app_debug.log'),
        logging.StreamHandler(sys.stderr)  # También a terminal
    ]
)
LOG = logging.getLogger(__name__)

_openssl = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openssl_legacy.cnf')
if os.path.exists(_openssl):
    os.environ['OPENSSL_CONF'] = _openssl

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import pyodbc

try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('insevig.empleados.10.0')
except Exception:
    pass

# ── Palette INSEVIG DARK MODE ──────────────────────────────────────
COL_BG       = '#1E1E1E'      # Fondo principal oscuro
COL_HEADER   = '#0D1B2A'      # Header muy oscuro
COL_ACCENT   = '#4A9EFF'      # Azul claro para acentos
COL_PEND     = '#FF9F43'      # Naranja claro
COL_OK       = '#2ED573'      # Verde claro
COL_DANGER   = '#FF6B6B'      # Rojo claro
COL_WHITE    = '#FFFFFF'      # Blanco para texto
COL_GRAY     = '#A0A0A0'      # Gris claro
COL_ENTRY_BG = '#2D2D2D'      # Fondo entrada oscuro
COL_CARD     = '#2D2D2D'      # Tarjetas oscuras
COL_TEXT     = '#E0E0E0'      # Texto claro
COL_BORDER   = '#404040'      # Borde oscuro

FONT_DEFAULT = ('Segoe UI', 10)
FONT_SMALL   = ('Segoe UI', 9)
FONT_LABEL   = ('Segoe UI', 10, 'bold')
FONT_HEAD    = ('Segoe UI', 11, 'bold')
FONT_TITLE   = ('Segoe UI', 14, 'bold')

# ── SQL Server ──────────────────────────────────────────────────────
SQL_CFG = {
    'driver':   'ODBC Driver 17 for SQL Server',
    'server':   '192.168.2.115',
    'database': 'insevig',
    'uid':      'sa',
    'pwd':      'puntosoft123*',
}
SQL_FILTER = "CODEMP='10' AND CODSUC='10'"


def _get_sql_conn():
    """Intenta drivers en orden de prioridad."""
    drivers = [
        'ODBC Driver 17 for SQL Server',
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 13 for SQL Server',
        'ODBC Driver 11 for SQL Server',
        'SQL Server',
    ]
    cfg = SQL_CFG.copy()
    for drv in drivers:
        try:
            cfg['driver'] = drv
            cs = (f"DRIVER={{{drv}}};SERVER={cfg['server']};DATABASE={cfg['database']};"
                  f"UID={cfg['uid']};PWD={cfg['pwd']};Encrypt=No;TrustServerCertificate=yes")
            return pyodbc.connect(cs, timeout=10)
        except Exception:
            continue
    raise RuntimeError("No se pudo conectar a SQL Server con ningún driver ODBC.")


# ── ToolTip ──────────────────────────────────────────────────────────
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)

    def _show(self, ev=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=self.text, font=FONT_SMALL, bg=COL_CARD,
                       fg=COL_ACCENT, wraplength=300, justify='left',
                       padx=8, pady=4, relief='solid', borderwidth=1)
        lbl.pack()

    def _hide(self, ev=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class SistemaGestionEmpleados10:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Gestión de Empleados - INSEVIG v10")
        self.root.geometry("1280x800")
        try:
            self.root.state('zoomed')
        except tk.TclError:
            self.root.attributes('-zoomed', True)
        self.root.configure(bg=COL_BG)

        self._running = True
        self._status_var = tk.StringVar(value="Iniciando...")
        self._tabs_dirty = set()
        self._debounce_id = None

        self.conn = None
        self.empleado_actual = None
        self.datos_originales = None
        self.datos_modificados = False
        self.modo_edicion = False

        self._catalogos_cargados = False
        self.cargos = {}
        self.secciones = {}
        self.departamentos = {}
        self.sexos = {}
        self.estados_civiles = {}
        self.tipos_trabajo = {}
        self.formas_pago = {}
        self.bancos = {}
        self._auditoria_data = {}
        self._combos_widgets = {}
        self._form_widgets = {}
        self._check_widgets = {}
        self._readonly_descs = set()

        self._configurar_estilo()
        self._build_layout()
        self._set_form_state('view')
        self._status("Conectando a BD...")
        self.root.after(100, self._conectar_bd)

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ── Estilo ──────────────────────────────────────────────────────
    def _configurar_estilo(self):
        s = ttk.Style()
        s.theme_use('alt')  # Tema alt soporta mejor dark mode
        s.configure('.', font=FONT_DEFAULT, background=COL_BG, foreground=COL_TEXT)

        # Configurar tk widgets (no ttk) - GLOBAL
        self.root.option_add('*background', COL_BG)
        self.root.option_add('*foreground', COL_TEXT)
        self.root.option_add('*Entry.background', COL_ENTRY_BG)
        self.root.option_add('*Entry.foreground', COL_TEXT)
        self.root.option_add('*Text.background', COL_ENTRY_BG)
        self.root.option_add('*Text.foreground', COL_TEXT)
        self.root.option_add('*Frame.background', COL_BG)
        self.root.option_add('*Label.background', COL_BG)
        self.root.option_add('*Label.foreground', COL_TEXT)
        self.root.option_add('*Button.background', COL_CARD)
        self.root.option_add('*Button.foreground', COL_TEXT)

        s.configure('Treeview', background=COL_CARD, fieldbackground=COL_CARD,
                    foreground=COL_TEXT, rowheight=30, font=FONT_DEFAULT)
        s.configure('Treeview.Heading', background=COL_HEADER, foreground=COL_WHITE,
                    font=FONT_HEAD)
        s.map('Treeview', background=[('selected', COL_ACCENT)])

        s.configure('TNotebook', background=COL_BG, borderwidth=1)
        s.configure('TNotebook.Tab', font=FONT_HEAD,
                    padding=[18, 8], background=COL_CARD, foreground=COL_TEXT)
        s.map('TNotebook.Tab', background=[('selected', COL_ACCENT)],
              foreground=[('selected', COL_WHITE)])

        s.configure('TButton', font=FONT_LABEL, padding=[14, 6], background=COL_CARD, foreground=COL_TEXT)
        s.map('TButton', background=[('active', '#404040')])

        s.configure('Accent.TButton', font=FONT_LABEL, padding=[16, 8],
                    background=COL_ACCENT, foreground=COL_WHITE)
        s.map('Accent.TButton', background=[('active', '#357ABD')])

        s.configure('TLabelframe', background=COL_BG, borderwidth=2, relief='solid')
        s.configure('TLabelframe.Label', font=FONT_LABEL,
                    foreground=COL_ACCENT, background=COL_BG)

        s.configure('TEntry', fieldbackground=COL_ENTRY_BG, foreground=COL_WHITE, font=FONT_DEFAULT)
        s.configure('TCombobox', fieldbackground=COL_ENTRY_BG, foreground=COL_WHITE, font=FONT_DEFAULT)
        s.map('TCombobox', fieldbackground=[('readonly', COL_ENTRY_BG)], foreground=[('readonly', COL_WHITE)])

    # ── Status ──────────────────────────────────────────────────────
    def _status(self, msg):
        self._status_var.set(msg)
        self.root.update_idletasks()

    # ── Layout ──────────────────────────────────────────────────────
    def _build_layout(self):
        # Barra superior
        top = tk.Frame(self.root, bg=COL_HEADER, height=54)
        top.pack(fill='x')
        top.pack_propagate(False)
        tk.Label(top, text="SISTEMA DE GESTIÓN DE EMPLEADOS — INSEVIG",
                 font=FONT_TITLE, fg=COL_WHITE, bg=COL_HEADER).pack(side='left', padx=20, pady=12)

        # Cuerpo
        body = tk.Frame(self.root, bg=COL_BG)
        body.pack(fill='both', expand=True)

        # Izquierda (320px fijo)
        left = tk.Frame(body, bg=COL_BG, width=320)
        left.pack(side='left', fill='y', padx=(8, 0), pady=8)
        left.pack_propagate(False)

        # Separador
        ttk.Separator(body, orient='vertical').pack(side='left', fill='y', padx=4)

        # Derecha (expansible)
        right = tk.Frame(body, bg=COL_BG)
        right.pack(side='left', fill='both', expand=True, padx=8, pady=8)

        self._build_left_panel(left)
        self._build_notebook(right)

        # Barra de botones inferior
        btn_bar = tk.Frame(self.root, bg=COL_CARD, height=44)
        btn_bar.pack(fill='x')
        btn_bar.pack_propagate(False)

        ttk.Button(btn_bar, text="💾 GUARDAR", command=self._guardar_cambios,
                   style='Accent.TButton').pack(side='left', padx=(10, 4), pady=5)
        ttk.Button(btn_bar, text="✖ CANCELAR", command=self._cancelar_cambios
                   ).pack(side='left', padx=4, pady=5)
        ttk.Button(btn_bar, text="📄 IMPRIMIR", command=self._imprimir_empleado
                   ).pack(side='left', padx=4, pady=5)
        ttk.Separator(btn_bar, orient='vertical').pack(side='left', fill='y', padx=10)
        self._lbl_empleado_actual = tk.Label(btn_bar, text="", font=FONT_LABEL,
                                              fg=COL_TEXT, bg=COL_CARD, anchor='w')
        self._lbl_empleado_actual.pack(side='left', fill='x', expand=True, padx=6)
        ttk.Button(btn_bar, text="SALIR", command=self._on_close).pack(side='right', padx=10, pady=5)

        # Barra de estado inferior
        bar = tk.Frame(self.root, bg=COL_HEADER, height=36)
        bar.pack(fill='x')
        bar.pack_propagate(False)
        tk.Label(bar, textvariable=self._status_var,
                 font=FONT_LABEL, fg=COL_WHITE, bg=COL_HEADER,
                 anchor='w').pack(side='left', padx=12, pady=5)

    # ── Panel izquierdo ─────────────────────────────────────────────
    def _build_left_panel(self, parent):
        # Búsqueda
        g = ttk.LabelFrame(parent, text="BÚSQUEDA", padding=10)
        g.pack(fill='x', pady=(0, 8))

        row = tk.Frame(g, bg=COL_BG)
        row.pack(fill='x', pady=3)
        tk.Label(row, text="Cédula:", font=FONT_LABEL,
                 bg=COL_BG).pack(side='left')
        self._cedula_var = tk.StringVar()
        e = ttk.Entry(row, textvariable=self._cedula_var, width=20)
        e.pack(side='left', padx=(6, 0))
        e.bind('<Return>', lambda ev: self._buscar_por_cedula())
        ttk.Button(row, text="Buscar", command=self._buscar_por_cedula,
                   style='Accent.TButton').pack(side='left', padx=(6, 0))

        row2 = tk.Frame(g, bg=COL_BG)
        row2.pack(fill='x', pady=3)
        tk.Label(row2, text="Código:", font=FONT_LABEL,
                 bg=COL_BG).pack(side='left')
        self._codigo_var = tk.StringVar()
        e2 = ttk.Entry(row2, textvariable=self._codigo_var, width=20)
        e2.pack(side='left', padx=(6, 0))
        e2.bind('<Return>', lambda ev: self._buscar_por_codigo())
        ttk.Button(row2, text="Buscar", command=self._buscar_por_codigo,
                   style='Accent.TButton').pack(side='left', padx=(6, 0))

        ttk.Button(g, text="🔍 Búsqueda Avanzada", command=self._abrir_buscador,
                   style='Accent.TButton').pack(fill='x', pady=(6, 0))

        # Botones de acción PRIMERO (para que no queden ocultos)
        act = tk.Frame(parent, bg=COL_BG)
        act.pack(fill='x', pady=(8, 6))
        ttk.Button(act, text="Nuevo", command=self._nuevo_empleado,
                   style='Accent.TButton').pack(fill='x', pady=2)
        ttk.Button(act, text="Modificar", command=self._modificar_empleado).pack(fill='x', pady=2)
        ttk.Button(act, text="Eliminar", command=self._eliminar_empleado).pack(fill='x', pady=2)
        ttk.Button(act, text="Edición Masiva (Excel)",
                   command=self._edicion_masiva).pack(fill='x', pady=2)
        ttk.Button(act, text="Agregar Observaciones",
                   command=self._agregar_observaciones).pack(fill='x', pady=2)
        ttk.Button(act, text="Vista Completa", command=self._abrir_vista_completa).pack(fill='x', pady=2)

        lf = ttk.LabelFrame(parent, text="EMPLEADOS", padding=6)
        lf.pack(fill='both', expand=True)

        ctrl = tk.Frame(lf, bg=COL_BG)
        ctrl.pack(fill='x', pady=(0, 4))
        tk.Label(ctrl, text="Mostrar:", font=FONT_LABEL,
                 bg=COL_BG).pack(side='left')
        self._filtro_var = tk.StringVar(value="ACTIVOS")
        cb = ttk.Combobox(ctrl, textvariable=self._filtro_var,
                          values=["ACTIVOS", "INACTIVOS", "TODOS"], width=10, state='readonly')
        cb.pack(side='left', padx=(6, 0))
        cb.bind('<<ComboboxSelected>>', lambda ev: self._cargar_lista())

        nav = tk.Frame(ctrl, bg=COL_BG)
        nav.pack(side='right')
        for txt, cmd in [('◀◀', self._primer_emp), ('◀', self._anterior_emp),
                         ('▶', self._siguiente_emp), ('▶▶', self._ultimo_emp)]:
            tk.Button(nav, text=txt, font=FONT_HEAD,
                      command=cmd, bg=COL_CARD, fg=COL_TEXT, relief='flat',
                      padx=6, pady=1).pack(side='left')

        cols = ('cod', 'ape', 'nom')
        self._tree = ttk.Treeview(lf, columns=cols, show='headings', height=14)
        self._tree.heading('cod', text='Cód.')
        self._tree.heading('ape', text='Apellidos')
        self._tree.heading('nom', text='Nombres')
        self._tree.column('cod', width=60, anchor='center')
        self._tree.column('ape', width=140)
        self._tree.column('nom', width=140)

        vsb = ttk.Scrollbar(lf, orient='vertical', command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self._tree.bind('<<TreeviewSelect>>', self._on_tree_select)

        bot = tk.Frame(lf, bg=COL_BG)
        bot.pack(fill='x', pady=(6, 0))
        self._orden_var = tk.StringVar(value="alfabetico")
        for txt, val in [("A-Z", "alfabetico"), ("Depto.", "departamento")]:
            tk.Radiobutton(bot, text=txt, variable=self._orden_var, value=val,
                           command=self._cargar_lista, font=FONT_LABEL,
                           bg=COL_BG, fg=COL_TEXT,
                           selectcolor=COL_ACCENT, activeforeground=COL_ACCENT,
                           activebackground=COL_BG).pack(side='left', padx=(0, 8))

        ttk.Button(bot, text="Actualizar", command=self._cargar_lista).pack(side='right')

    # ── Notebook ────────────────────────────────────────────────────
    def _build_notebook(self, parent):
        self._nb = ttk.Notebook(parent)
        self._nb.pack(fill='both', expand=True)

        self._tab_datos = ttk.Frame(self._nb)
        self._tab_ingresos = ttk.Frame(self._nb)
        self._tab_observaciones = ttk.Frame(self._nb)
        self._tab_otros = ttk.Frame(self._nb)
        self._tab_certificados = ttk.Frame(self._nb)
        self._tab_referencias = ttk.Frame(self._nb)

        self._nb.add(self._tab_datos, text="Datos Generales")
        self._nb.add(self._tab_ingresos, text="Ingresos / Dctos.")
        self._nb.add(self._tab_observaciones, text="Observaciones")
        self._nb.add(self._tab_otros, text="Otros Datos")
        self._nb.add(self._tab_certificados, text="Certificados")
        self._nb.add(self._tab_referencias, text="Referencias")

        self._build_tab_datos()
        self._build_tab_ingresos()
        self._build_tab_observaciones()
        self._build_tab_otros()
        self._build_tab_certificados()
        self._build_tab_referencias()

        self._nb.bind('<<NotebookTabChanged>>', self._on_tab_change)

    # ── Pestaña: Datos Generales ────────────────────────────────────
    def _build_tab_datos(self):
        self._dg_vars = {}
        canvas = tk.Canvas(self._tab_datos, bg=COL_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self._tab_datos, orient='vertical', command=canvas.yview)
        sf = ttk.Frame(canvas)
        sf.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=sf, anchor='nw')
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def field_set(container, row, label, col_key, width=20, is_combo=False, values=None, col=0):
            c = col * 2
            tk.Label(container, text=label, font=FONT_LABEL,
                     bg=COL_BG).grid(row=row, column=c, sticky='w', padx=4, pady=2)
            var = tk.StringVar()
            self._dg_vars[col_key] = var
            if is_combo:
                w = ttk.Combobox(container, textvariable=var, values=values, width=width, state='readonly')
                self._combos_widgets[col_key] = w
            else:
                w = ttk.Entry(container, textvariable=var, width=width)
            w.grid(row=row, column=c + 1, sticky='w', padx=4, pady=2)
            self._form_widgets[col_key] = w
            return w

        g1 = ttk.LabelFrame(sf, text="Información Personal", padding=8)
        g1.grid(row=0, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        field_set(g1, 0, 'Código:', 'EMPLEADO', 14, col=0)
        field_set(g1, 0, 'Cédula:', 'CEDULA', 18, col=1)
        field_set(g1, 0, 'Cód.Suc:', 'CODSUC', 10, col=2)
        field_set(g1, 0, 'Cód.Emp:', 'CODEMP', 10, col=3)
        field_set(g1, 1, 'Nombres:', 'NOMBRES', 48, col=0)
        field_set(g1, 2, 'Apellidos:', 'APELLIDOS', 48, col=0)
        w_sexo = field_set(g1, 3, 'Sexo:', 'SEXO', 14, is_combo=True, values=['1', '2'], col=0)
        ToolTip(w_sexo, "1=Masculino, 2=Femenino")
        w_ec = field_set(g1, 3, 'Estado Civil:', 'ESTADO_CI', 14, is_combo=True, values=['1', '2', '3', '4'], col=1)
        ToolTip(w_ec, "1=Soltero, 2=Casado, 3=Divorciado, 4=Viudo")
        w_nac = field_set(g1, 4, 'Lugar Nac.:', 'LUGAR_NAC', 32, col=0)
        field_set(g1, 4, 'Fecha Nac.:', 'FECHA_NAC', 18, col=1)

        g2 = ttk.LabelFrame(sf, text="Ubicación", padding=8)
        g2.grid(row=1, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        field_set(g2, 0, 'Dirección:', 'DIRECCION', 64, col=0)
        field_set(g2, 1, 'Provincia:', 'PROVINCIA', 22, col=0)
        field_set(g2, 1, 'Cantón:', 'CANTON', 22, col=1)
        field_set(g2, 2, 'Parroquia:', 'PARROQUIA', 22, col=0)
        field_set(g2, 2, 'Nacionalidad:', 'NACIONAL', 22, col=1)

        g3 = ttk.LabelFrame(sf, text="Información Laboral", padding=8)
        g3.grid(row=2, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        field_set(g3, 0, 'Fecha Ingreso:', 'FECHA_ING', 18, col=0)
        tk.Label(g3, text='Departamento:', font=FONT_LABEL,
                 bg=COL_BG).grid(row=0, column=4, sticky='w', padx=4, pady=2)
        self._dg_vars['DEPTO'] = tk.StringVar()
        self._combo_depto = ttk.Combobox(g3, textvariable=self._dg_vars['DEPTO'], width=10, state='readonly')
        self._combo_depto.grid(row=0, column=5, sticky='w', padx=(4,0), pady=2)
        self._form_widgets['DEPTO'] = self._combo_depto
        self._combos_widgets['DEPTO'] = self._combo_depto
        ToolTip(self._combo_depto, "Seleccione el departamento")
        self._ent_depto = ttk.Entry(g3, width=30, state='readonly')
        self._ent_depto.grid(row=0, column=6, sticky='w', padx=(2,4), pady=2)
        self._form_widgets['_ent_depto'] = self._ent_depto
        self._readonly_descs = set()
        self._readonly_descs.add('_ent_depto')
        self._combo_depto.bind('<<ComboboxSelected>>', lambda ev: self._actualizar_nombre_desc('DEPTO'))

        tk.Label(g3, text='Cargo:', font=FONT_LABEL,
                 bg=COL_BG).grid(row=1, column=0, sticky='w', padx=4, pady=2)
        self._dg_vars['CARGO'] = tk.StringVar()
        self._combo_cargo = ttk.Combobox(g3, textvariable=self._dg_vars['CARGO'], width=10, state='readonly')
        self._combo_cargo.grid(row=1, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['CARGO'] = self._combo_cargo
        self._combos_widgets['CARGO'] = self._combo_cargo
        ToolTip(self._combo_cargo, "Seleccione el cargo")
        self._ent_cargo = ttk.Entry(g3, width=30, state='readonly')
        self._ent_cargo.grid(row=1, column=2, sticky='w', padx=4, pady=2)
        self._form_widgets['_ent_cargo'] = self._ent_cargo
        self._readonly_descs.add('_ent_cargo')
        self._combo_cargo.bind('<<ComboboxSelected>>', lambda ev: self._actualizar_nombre_desc('CARGO'))

        tk.Label(g3, text='Sección:', font=FONT_LABEL,
                 bg=COL_BG).grid(row=2, column=0, sticky='w', padx=4, pady=2)
        self._dg_vars['SECCION'] = tk.StringVar()
        self._combo_seccion = ttk.Combobox(g3, textvariable=self._dg_vars['SECCION'], width=10, state='readonly')
        self._combo_seccion.grid(row=2, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['SECCION'] = self._combo_seccion
        self._combos_widgets['SECCION'] = self._combo_seccion
        ToolTip(self._combo_seccion, "Seleccione la sección")
        self._ent_seccion = ttk.Entry(g3, width=30, state='readonly')
        self._ent_seccion.grid(row=2, column=2, sticky='w', padx=4, pady=2)
        self._form_widgets['_ent_seccion'] = self._ent_seccion
        self._readonly_descs.add('_ent_seccion')
        self._combo_seccion.bind('<<ComboboxSelected>>', lambda ev: self._actualizar_nombre_desc('SECCION'))

        field_set(g3, 3, 'Estado:', 'ESTADO', 14, is_combo=True, values=['ACTIVO', 'INACTIVO'], col=0)
        w_tel = field_set(g3, 3, 'Teléfono:', 'TELEFONO', 20, col=1)
        ToolTip(w_tel, "Teléfono principal del empleado")
        field_set(g3, 4, 'Email:', 'emp_mail', 44, col=0)
        w_tel2 = field_set(g3, 5, '2do Teléfono:', 'RPCAM', 20, col=0)
        ToolTip(w_tel2, "Teléfono alternativo o celular")
        w_tt = field_set(g3, 5, 'Tipo Trabajo:', 'TIPO_TRA', 14, is_combo=True, values=['1', '2', '3'], col=1)
        ToolTip(w_tt, "1=Fijo, 2=Temporal, 3=Contrato")
        field_set(g3, 6, 'Actividad:', 'ACTIVIDAD', 34, col=0)
        field_set(g3, 7, 'Cónyugue:', 'CONYUGUE', 44, col=0)

        g4 = ttk.LabelFrame(sf, text="Auditoría", padding=6)
        g4.grid(row=3, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        self._lbl_audit = tk.Label(g4, text="", font=FONT_SMALL,
                                    fg=COL_GRAY, bg=COL_BG, anchor='w')
        self._lbl_audit.pack(fill='x', padx=4, pady=2)

    # ── Pestaña: Ingresos / Descuentos ───────────────────────────────
    def _build_tab_ingresos(self):
        self._ing_vars = {}
        f = self._tab_ingresos

        def field(frame, row, col, label, key, width=16):
            tk.Label(frame, text=label, font=FONT_LABEL,
                     bg=COL_BG).grid(row=row, column=col * 2, sticky='w', padx=4, pady=2)
            var = tk.StringVar()
            self._ing_vars[key] = var
            w = ttk.Entry(frame, textvariable=var, width=width)
            w.grid(row=row, column=col * 2 + 1, sticky='w', padx=4, pady=2)
            self._form_widgets[f'ing_{key}'] = w

        g1 = ttk.LabelFrame(f, text="Sueldo y Beneficios", padding=8)
        g1.pack(fill='x', padx=6, pady=4)
        field(g1, 0, 0, 'Sueldo:', 'SUELDO')
        field(g1, 0, 1, 'Bonificación:', 'BONIFI')
        field(g1, 0, 2, 'Compensación:', 'COMPEN')
        field(g1, 1, 0, 'Transporte:', 'TRANSP')
        field(g1, 1, 1, 'Lunch:', 'LUNCH')
        field(g1, 2, 0, 'Horas 25%:', 'HOR25')
        field(g1, 2, 1, 'Horas 50%:', 'HOR50')
        field(g1, 2, 2, 'Horas 100%:', 'HOR100')

        g2 = ttk.LabelFrame(f, text="Beneficios Sociales Acumulados", padding=8)
        g2.pack(fill='x', padx=6, pady=4)
        field(g2, 0, 0, 'Décimo 3ro:', 'DECIMO3')
        field(g2, 0, 1, 'Décimo 4to:', 'DECIMO4')
        field(g2, 0, 2, 'Vacaciones:', 'VACACION')
        field(g2, 1, 0, 'Fdo. Reserva:', 'FONRESER')
        field(g2, 1, 1, 'Anticipo ($):', 'ANTICIPO')
        field(g2, 2, 0, 'Concepto:', 'CONCEPTO', 34)

    # ── Pestaña: Observaciones ──────────────────────────────────────
    def _build_tab_observaciones(self):
        f = self._tab_observaciones
        top = ttk.Frame(f)
        top.pack(fill='x', padx=8, pady=8)

        tk.Label(top, text='Período:', font=FONT_LABEL,
                 bg=COL_BG).pack(side='left', padx=(0, 6))
        meses = ['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO',
                 'JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE']
        self._mes_var = tk.StringVar(value=meses[datetime.now().month - 1])
        ttk.Combobox(top, textvariable=self._mes_var, values=meses, width=12, state='readonly').pack(side='left', padx=6)
        self._anio_var = tk.StringVar(value=str(datetime.now().year))
        ttk.Combobox(top, textvariable=self._anio_var,
                     values=[str(y) for y in range(2020, 2031)],
                     width=8, state='readonly').pack(side='left', padx=6)
        ttk.Button(top, text="Mostrar", command=self._mostrar_obs).pack(side='left', padx=8)
        ttk.Button(top, text="💾 Guardar Obs.", command=self._guardar_obs,
                  style='Accent.TButton').pack(side='left', padx=4)

        self._lbl_fecha_fin = tk.Label(top, text='', font=FONT_DEFAULT,
                                       fg=COL_GRAY, bg=COL_BG)

        # Para almacenar referencias a los Text widgets de observaciones
        self._obs_widgets = []
        self._lbl_fecha_fin.pack(side='right')

        # Canvas con scroll para mostrar recuadros de observaciones
        self._obs_canvas = tk.Canvas(f, bg=COL_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(f, orient='vertical', command=self._obs_canvas.yview)
        self._obs_frame = tk.Frame(self._obs_canvas, bg=COL_BG)

        self._obs_canvas.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        vsb.pack(side='right', fill='y', padx=(0, 8), pady=8)

        self._obs_canvas.configure(yscrollcommand=vsb.set)
        self._obs_canvas_window = self._obs_canvas.create_window(0, 0, window=self._obs_frame, anchor='nw')

        # Bind para resize
        self._obs_frame.bind('<Configure>', lambda e: self._obs_canvas.configure(scrollregion=self._obs_canvas.bbox('all')))
        self._obs_canvas.bind('<MouseWheel>', lambda e: self._obs_canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        self._obs_canvas.bind('<Button-4>', lambda e: self._obs_canvas.yview_scroll(-1, 'units'))
        self._obs_canvas.bind('<Button-5>', lambda e: self._obs_canvas.yview_scroll(1, 'units'))

        # Placeholder
        lbl = tk.Label(self._obs_frame, text="Selecciona un período y presiona 'Mostrar'",
                      font=FONT_LABEL, bg=COL_BG, fg=COL_GRAY)
        lbl.pack(pady=20)

        self._form_widgets['OBSERV'] = self._obs_frame

    def _mostrar_obs(self):
        """Mostrar observaciones en recuadros"""
        if not self.empleado_actual:
            messagebox.showwarning("ATENCIÓN", "Seleccione un empleado primero")
            return

        m = self._mes_var.get()
        a = self._anio_var.get()

        meses = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
                'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}
        mes_num = meses.get(m, 6)
        ano_num = int(a) if a.isdigit() else 2026
        emp_cod = self.empleado_actual.get('EMPLEADO', '')

        # Limpiar frame anterior
        for widget in self._obs_frame.winfo_children():
            widget.destroy()
        self._obs_widgets = []  # Limpiar referencias anteriores

        try:
            cur = self.conn.cursor()
            cur.execute(f"""
                SELECT refer1, refer2, refer3, refer4, refer5, refer6, refer7, fecha_ven
                FROM RPEMPOBSERV
                WHERE empleado = ? AND MONTH(fecha_ven) = ? AND YEAR(fecha_ven) = ?
                  AND CODEMP='10' AND CODSUC='10'
                ORDER BY fecha_ven DESC
            """, (emp_cod, mes_num, ano_num))

            row = cur.fetchone()

            if not row:
                lbl = tk.Label(self._obs_frame, text=f"Sin observaciones para {m} {a}",
                             font=FONT_LABEL, bg=COL_BG, fg=COL_GRAY)
                lbl.pack(pady=20)
                self._lbl_fecha_fin.config(text='')
                return

            fecha_ven = row[7]

            # Encabezado
            header = tk.Frame(self._obs_frame, bg=COL_HEADER, height=60)
            header.pack(fill='x', padx=0, pady=(0, 10))

            tk.Label(header, text=f"📅 {m} {a}  |  📆 {fecha_ven.strftime('%d/%m/%Y')}",
                    font=FONT_HEAD, bg=COL_HEADER, fg=COL_WHITE).pack(pady=10)

            # Crear recuadro para cada observación
            campos_llenos = 0
            for i in range(7):
                if row[i]:
                    campos_llenos += 1

                    # Recuadro para cada campo (dark mode)
                    card = tk.Frame(self._obs_frame, bg=COL_CARD, relief='solid', borderwidth=2)
                    card.pack(fill='both', expand=False, padx=0, pady=(0, 8))

                    # Header del recuadro
                    card_header = tk.Frame(card, bg=COL_ACCENT, height=30)
                    card_header.pack(fill='x')

                    tk.Label(card_header, text=f"[CAMPO {i+1}]", font=FONT_LABEL,
                            bg=COL_ACCENT, fg=COL_WHITE).pack(pady=6)

                    # Contenido editable - Text widget oscuro
                    content = tk.Text(card, font=FONT_DEFAULT,
                                    bg=COL_CARD, fg=COL_TEXT,
                                    height=3, width=70, wrap='word',
                                    relief='flat', borderwidth=0)
                    content.pack(fill='both', expand=True, padx=12, pady=12)
                    content.insert(1.0, row[i])
                    content.config(state='normal')  # Permitir edición

                    # Almacenar referencia para guardar después
                    self._obs_widgets.append({
                        'campo': i + 1,
                        'widget': content,
                        'valor_original': row[i]
                    })

            # Footer
            footer = tk.Label(self._obs_frame, text=f"Total: {campos_llenos}/7 campos",
                            font=FONT_SMALL, bg=COL_BG, fg=COL_GRAY)
            footer.pack(pady=10)

            self._lbl_fecha_fin.config(text=f'Fecha: {fecha_ven.strftime("%d/%m/%Y")}')
            self._status("Observaciones cargadas correctamente")

        except Exception as e:
            lbl = tk.Label(self._obs_frame, text=f"Error: {str(e)}", font=FONT_LABEL,
                         bg=COL_BG, fg=COL_DANGER)
            lbl.pack(pady=20)
            messagebox.showerror("Error", str(e))

    def _guardar_obs(self):
        """Guardar observaciones modificadas en RPEMPOBSERV"""
        if not self.empleado_actual or not self._obs_widgets:
            messagebox.showwarning("ATENCIÓN", "Cargue observaciones primero con 'Mostrar'")
            return

        m = self._mes_var.get()
        a = self._anio_var.get()
        meses = {'ENERO': 1, 'FEBRERO': 2, 'MARZO': 3, 'ABRIL': 4, 'MAYO': 5, 'JUNIO': 6,
                'JULIO': 7, 'AGOSTO': 8, 'SEPTIEMBRE': 9, 'OCTUBRE': 10, 'NOVIEMBRE': 11, 'DICIEMBRE': 12}
        mes_num = meses.get(m, 6)
        ano_num = int(a) if a.isdigit() else 2026
        emp_cod = self.empleado_actual.get('EMPLEADO', '')

        try:
            cur = self.conn.cursor()

            # Obtener la fecha_ven de la observación actual
            cur.execute(f"""
                SELECT fecha_ven FROM RPEMPOBSERV
                WHERE empleado = ? AND MONTH(fecha_ven) = ? AND YEAR(fecha_ven) = ?
                  AND CODEMP='10' AND CODSUC='10'
                ORDER BY fecha_ven DESC
            """, (emp_cod, mes_num, ano_num))

            row = cur.fetchone()
            if not row:
                messagebox.showerror("Error", "No se encontró la observación")
                return

            fecha_ven = row[0]

            # Actualizar cada campo
            cambios = 0
            for widget_info in self._obs_widgets:
                campo_num = widget_info['campo']
                texto_nuevo = widget_info['widget'].get(1.0, 'end').strip()
                columna = f'refer{campo_num}'

                # Actualizar solo si cambió
                if texto_nuevo != widget_info['valor_original']:
                    cur.execute(f"""
                        UPDATE RPEMPOBSERV
                        SET {columna} = ?
                        WHERE empleado = ? AND fecha_ven = ? AND CODEMP='10' AND CODSUC='10'
                    """, (texto_nuevo, emp_cod, fecha_ven))
                    cambios += 1

            self.conn.commit()
            messagebox.showinfo("✅ Guardado", f"Se guardaron {cambios} cambios en observaciones")
            self._mostrar_obs()  # Recargar para confirmar

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {str(e)}")

    # ── Pestaña: Otros Datos ────────────────────────────────────────
    def _build_tab_otros(self):
        self._ot_vars = {}
        self._check_states = {'INCL_ROL': False, 'INCL_BAN': False}
        f = self._tab_otros

        g1 = ttk.LabelFrame(f, text="Datos Generales", padding=8)
        g1.pack(fill='x', padx=6, pady=4)

        self._ot_vars['INCL_ROL'] = tk.StringVar(value='N')
        self._ot_vars['INCL_BAN'] = tk.StringVar(value='N')
        check_frame = ttk.Frame(g1)
        check_frame.grid(row=0, column=0, columnspan=2, sticky='w', padx=4, pady=2)
        self._chk_rol = tk.Checkbutton(check_frame, text="Incluir en el Rol",
                                       variable=tk.BooleanVar(),
                                       font=FONT_LABEL,
                                       bg=COL_BG, fg=COL_TEXT,
                                       selectcolor=COL_ACCENT, activebackground=COL_BG,
                                       command=lambda: self._toggle_check('INCL_ROL'))
        self._chk_rol.pack(side='left', padx=(0, 24))
        self._check_widgets['INCL_ROL'] = self._chk_rol
        self._chk_ban = tk.Checkbutton(check_frame, text="Acreditar",
                                       variable=tk.BooleanVar(),
                                       font=FONT_LABEL,
                                       bg=COL_BG, fg=COL_TEXT,
                                       selectcolor=COL_ACCENT, activebackground=COL_BG,
                                       command=lambda: self._toggle_check('INCL_BAN'))
        self._chk_ban.pack(side='left')
        self._check_widgets['INCL_BAN'] = self._chk_ban

        def field(container, row, col, label, key, width=14, is_combo=False, values=None):
            tk.Label(container, text=label, font=FONT_LABEL,
                     bg=COL_BG).grid(row=row, column=col * 2, sticky='w', padx=4, pady=2)
            var = tk.StringVar()
            self._ot_vars[key] = var
            if is_combo:
                w = ttk.Combobox(container, textvariable=var, values=values, width=width, state='readonly')
                self._combos_widgets[key] = w
            else:
                w = ttk.Entry(container, textvariable=var, width=width)
            w.grid(row=row, column=col * 2 + 1, sticky='w', padx=4, pady=2)
            self._form_widgets[f'ot_{key}'] = w

        field(g1, 1, 0, 'Cargas:', 'CARGAS', 10)
        field(g1, 2, 0, 'Últ. Liquidación:', 'ULTLIQ', 16)
        field(g1, 3, 0, 'Días Trab.:', 'DIAS_TRA', 10)
        field(g1, 4, 0, 'Grupo Sang.:', 'TIP_SAN', 12, is_combo=True,
              values=['O+','O-','A+','A-','B+','B-','AB+','AB-'])
        field(g1, 5, 0, 'Forma Pago:', 'TIPO_PGO', 12, is_combo=True, values=['1','2','3','4'])

        g2 = ttk.LabelFrame(f, text="Cuentas Contables", padding=8)
        g2.pack(fill='x', padx=6, pady=4)
        field(g2, 0, 0, 'Código Cta.:', 'CODCTA')
        field(g2, 1, 0, 'Cta. Depto.:', 'CTADPT')
        field(g2, 2, 0, 'Cta. Auxiliar:', 'CTAAUX')

        g3 = ttk.LabelFrame(f, text="Información Bancaria", padding=8)
        g3.pack(fill='x', padx=6, pady=4)
        field(g3, 0, 0, 'Banco:', 'RUTA4', 18, is_combo=True,
              values=['PRODUBANCO','PICHINCHA','GUAYAQUIL','PACIFICO'])
        field(g3, 1, 0, 'Cta. Cte.:', 'CTA_CTE', 24)
        field(g3, 2, 0, 'Cta. Ahorros:', 'CTA_AHO', 24)

    def _toggle_check(self, field):
        cur = self._check_states.get(field, False)
        self._check_states[field] = not cur
        self._ot_vars[field].set('S' if not cur else 'N')
        chk = self._chk_rol if field == 'INCL_ROL' else self._chk_ban
        if not cur:
            chk.select()
        else:
            chk.deselect()
        self._marcar_modificado()

    def _actualizar_check_visual(self):
        for f, var in [('INCL_ROL', self._chk_rol), ('INCL_BAN', self._chk_ban)]:
            if self._ot_vars[f].get() == 'S':
                var.select()
                self._check_states[f] = True
            else:
                var.deselect()
                self._check_states[f] = False

    # ── Pestaña: Certificados ───────────────────────────────────────
    def _build_tab_certificados(self):
        self._cert_vars = {}
        f = self._tab_certificados

        cf = ttk.Frame(f)
        cf.pack(fill='x', padx=8, pady=8)
        for i, nombre in enumerate(['Cédula Identidad', 'Cert. Votación',
                                    'Record Policial', 'Libreta Militar']):
            bx = ttk.LabelFrame(cf, text=nombre, padding=10)
            bx.grid(row=0, column=i, padx=6, pady=6, sticky='n')
            cv = tk.Canvas(bx, width=120, height=90, bg=COL_CARD,
                           highlightbackground=COL_BORDER, highlightthickness=2)
            cv.pack(pady=6)
            cv.create_text(60, 45, text="Archivo", font=FONT_DEFAULT, fill=COL_GRAY)

        g1 = ttk.LabelFrame(f, text="Familiares", padding=8)
        g1.pack(fill='x', padx=6, pady=4)
        tk.Label(g1, text='Nombres:', font=FONT_LABEL, bg=COL_BG).grid(row=0, column=0, sticky='w', padx=4, pady=2)
        self._cert_vars['NOM_FAM'] = tk.StringVar()
        w = ttk.Entry(g1, textvariable=self._cert_vars['NOM_FAM'], width=44); w.grid(row=0, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['cert_NOM_FAM'] = w
        tk.Label(g1, text='Dirección:', font=FONT_LABEL, bg=COL_BG).grid(row=1, column=0, sticky='w', padx=4, pady=2)
        self._cert_vars['DIR_FAM'] = tk.StringVar()
        w = ttk.Entry(g1, textvariable=self._cert_vars['DIR_FAM'], width=44); w.grid(row=1, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['cert_DIR_FAM'] = w
        tk.Label(g1, text='Teléfonos:', font=FONT_LABEL, bg=COL_BG).grid(row=2, column=0, sticky='w', padx=4, pady=2)
        self._cert_vars['TEL_FAM'] = tk.StringVar()
        w = ttk.Entry(g1, textvariable=self._cert_vars['TEL_FAM'], width=22); w.grid(row=2, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['cert_TEL_FAM'] = w

        g2 = ttk.LabelFrame(f, text="No Familiares", padding=8)
        g2.pack(fill='x', padx=6, pady=4)
        tk.Label(g2, text='Nombres:', font=FONT_LABEL, bg=COL_BG).grid(row=0, column=0, sticky='w', padx=4, pady=2)
        self._cert_vars['NOM_NO_FAM'] = tk.StringVar()
        w = ttk.Entry(g2, textvariable=self._cert_vars['NOM_NO_FAM'], width=44); w.grid(row=0, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['cert_NOM_NO_FAM'] = w
        tk.Label(g2, text='Dirección:', font=FONT_LABEL, bg=COL_BG).grid(row=1, column=0, sticky='w', padx=4, pady=2)
        self._cert_vars['DIR_NO_FAM'] = tk.StringVar()
        w = ttk.Entry(g2, textvariable=self._cert_vars['DIR_NO_FAM'], width=44); w.grid(row=1, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['cert_DIR_NO_FAM'] = w
        tk.Label(g2, text='Teléfonos:', font=FONT_LABEL, bg=COL_BG).grid(row=2, column=0, sticky='w', padx=4, pady=2)
        self._cert_vars['TEL_NO_FAM'] = tk.StringVar()
        w = ttk.Entry(g2, textvariable=self._cert_vars['TEL_NO_FAM'], width=22); w.grid(row=2, column=1, sticky='w', padx=4, pady=2)
        self._form_widgets['cert_TEL_NO_FAM'] = w

    # ── Pestaña: Referencias ────────────────────────────────────────
    def _build_tab_referencias(self):
        self._ref_vars = {}
        f = self._tab_referencias
        canvas = tk.Canvas(f, bg=COL_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(f, orient='vertical', command=canvas.yview)
        sf = ttk.Frame(canvas)
        sf.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=sf, anchor='nw')
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def field(container, row, label, key, width=22):
            tk.Label(container, text=label, font=FONT_LABEL,
                     bg=COL_BG).grid(row=row, column=0, sticky='w', padx=4, pady=2)
            var = tk.StringVar()
            self._ref_vars[key] = var
            w = ttk.Entry(container, textvariable=var, width=width)
            w.grid(row=row, column=1, sticky='w', padx=4, pady=2)
            self._form_widgets[f'ref_{key}'] = w

        g1 = ttk.LabelFrame(sf, text="Datos Referenciales", padding=8)
        g1.grid(row=0, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        field(g1, 0, 'Cédula Militar:', 'CED_MIL', 20)
        tk.Label(g1, text='Edad:', font=FONT_LABEL, bg=COL_BG).grid(row=0, column=2, sticky='w', padx=4, pady=2)
        self._ref_vars['EDAD'] = tk.StringVar()
        w = ttk.Entry(g1, textvariable=self._ref_vars['EDAD'], width=10); w.grid(row=0, column=3, sticky='w', padx=4, pady=2)
        self._form_widgets['ref_EDAD'] = w
        field(g1, 1, 'Tipo Sangre:', 'TIP_SAN', 12)
        field(g1, 2, 'Nro Cert. Votación:', 'IDVOTA', 20)
        field(g1, 3, 'Licencia Conducir:', 'LICCOND', 16)
        field(g1, 4, 'Código IESS:', 'CODIESS', 20)

        g2 = ttk.LabelFrame(sf, text="Estudios", padding=8)
        g2.grid(row=1, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        self._ref_vars['PRIMARIA'] = tk.BooleanVar()
        chk = tk.Checkbutton(g2, text='Primaria', variable=self._ref_vars['PRIMARIA'],
                       font=FONT_LABEL, bg=COL_BG, fg=COL_TEXT,
                       selectcolor=COL_ACCENT, activebackground=COL_BG)
        chk.grid(row=0, column=0, sticky='w', padx=4, pady=2)
        self._check_widgets['PRIMARIA'] = chk
        self._ref_vars['SECUNDARIA'] = tk.BooleanVar()
        chk = tk.Checkbutton(g2, text='Secundaria', variable=self._ref_vars['SECUNDARIA'],
                       font=FONT_LABEL, bg=COL_BG, fg=COL_TEXT,
                       selectcolor=COL_ACCENT, activebackground=COL_BG)
        chk.grid(row=0, column=1, sticky='w', padx=4, pady=2)
        self._check_widgets['SECUNDARIA'] = chk
        self._ref_vars['EST_SUP'] = tk.BooleanVar()
        chk = tk.Checkbutton(g2, text='Universidad', variable=self._ref_vars['EST_SUP'],
                       font=FONT_LABEL, bg=COL_BG, fg=COL_TEXT,
                       selectcolor=COL_ACCENT, activebackground=COL_BG)
        chk.grid(row=0, column=2, sticky='w', padx=4, pady=2)
        self._check_widgets['EST_SUP'] = chk
        field(g2, 1, 'Título:', 'TITULO', 34)
        field(g2, 2, 'Años Estudio:', 'ANIO_EST', 10)

        g3 = ttk.LabelFrame(sf, text="Servicios", padding=8)
        g3.grid(row=2, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        field(g3, 0, 'Tipo:', 'RPCAM5', 30)
        field(g3, 1, 'Contrato Inspectoría:', 'CONTINS', 30)
        field(g3, 2, 'GIPASE:', 'RPCAM3', 38)
        field(g3, 3, 'AFIS:', 'RPCAM4', 38)
        field(g3, 4, 'Certificados:', 'certificados', 38)
        field(g3, 5, 'Reentrenamiento:', 'reentrenamiento', 38)
        field(g3, 6, 'Vacuna:', 'vacuna', 38)

        g4 = ttk.LabelFrame(sf, text="Información Adicional", padding=8)
        g4.grid(row=3, column=0, columnspan=2, sticky='ew', padx=4, pady=3)
        field(g4, 0, 'Cert. Violencia Intraf.:', 'CERTVINF', 50)
        field(g4, 1, 'Maniobras:', 'MANIOBRAS', 50)
        field(g4, 2, 'No. Afiliación IESS:', 'NUM_AFIL', 20)

    # ── Lazy Refresh ────────────────────────────────────────────────
    def _on_tab_change(self, ev=None):
        if not self._running:
            return
        tab = self._nb.select()
        mapping = {}
        for i, (name, key) in enumerate([
            ('Datos Generales', 'datos'), ('Ingresos / Dctos.', 'ingresos'),
            ('Observaciones', 'obs'), ('Otros Datos', 'otros'),
            ('Certificados', 'cert'), ('Referencias', 'ref')
        ]):
            mapping[str(self._nb.children.get(f'!frame{i+1 if i>0 else ""}', ''))] = key
        # Simpler: map by tab text
        txt = self._nb.tab(tab, 'text')
        txt_to_key = {
            'Datos Generales': 'datos', 'Ingresos / Dctos.': 'ingresos',
            'Observaciones': 'obs', 'Otros Datos': 'otros',
            'Certificados': 'cert', 'Referencias': 'ref'
        }
        key = txt_to_key.get(txt)
        if key and key in self._tabs_dirty:
            self._tabs_dirty.discard(key)

    def _marcar_dirty(self, *keys):
        for k in keys:
            self._tabs_dirty.add(k)

    # ── BD: Conexión ────────────────────────────────────────────────
    def _conectar_bd(self):
        def tarea():
            try:
                conn = _get_sql_conn()
                self.conn = conn
                self._cargar_catalogos()
                self.root.after(100, self._actualizar_combos_catalogos)
                self.root.after(200, self._cargar_lista)
                self.root.after(0, lambda: self._status("Conectado a SQL Server"))
            except Exception as e:
                self.root.after(0, lambda msg=f"Error BD: {str(e)}": self._status(msg))
                self.root.after(0, lambda msg=str(e): messagebox.showerror("Error BD", msg))
        threading.Thread(target=tarea, daemon=True).start()

    def _cargar_catalogos(self):
        if not self.conn or self._catalogos_cargados:
            return
        try:
            cur = self.conn.cursor()
            for tipo, dest in [('CAR', self.cargos), ('SEC', self.secciones), ('DPT', self.departamentos),
                               ('SEX', self.sexos), ('ECS', self.estados_civiles),
                               ('TTR', self.tipos_trabajo), ('FPA', self.formas_pago),
                               ('BCO', self.bancos)]:
                try:
                    cur.execute("SELECT CODIGO, NOMBRE FROM DBTABLAS WHERE TIPO = ? ORDER BY NOMBRE", (tipo,))
                    dest.clear()
                    for r in cur.fetchall():
                        dest[str(r[0]).strip()] = r[1]
                except Exception:
                    dest.clear()
            self._catalogos_cargados = True
        except Exception:
            pass

    def _obtener_nombre(self, codigo, catalogo):
        if not codigo:
            return ""
        return catalogo.get(str(codigo).strip(), "")

    def _extraer_codigo(self, val):
        if val and ' - ' in val:
            return val.split(' - ')[0].strip()
        return val

    def _match_combo_val(self, codigo, items):
        if not codigo:
            return ""
        cod = str(codigo).strip()
        for item in items:
            if item.startswith(cod + ' - ') or item == cod:
                return item
        return cod

    def _actualizar_combos_catalogos(self):
        mapa = {
            '_combo_depto': self.departamentos,
            '_combo_cargo': self.cargos,
            '_combo_seccion': self.secciones,
        }
        for attr, cat in mapa.items():
            combo = getattr(self, attr, None)
            if combo and cat:
                items = sorted([f"{k} - {v}" for k, v in cat.items()])
                combo['values'] = items
        for key, cat in [('SEXO', self.sexos), ('ESTADO_CI', self.estados_civiles),
                          ('TIPO_TRA', self.tipos_trabajo), ('TIPO_PGO', self.formas_pago),
                          ('RUTA4', self.bancos)]:
            combo = self._combos_widgets.get(key)
            if combo and cat:
                items = sorted([f"{k} - {v}" for k, v in cat.items()])
                combo['values'] = items

    def _actualizar_nombre_desc(self, campo):
        mapa = {'DEPTO': (self._dg_vars['DEPTO'], self.departamentos, self._ent_depto),
                'CARGO': (self._dg_vars['CARGO'], self.cargos, self._ent_cargo),
                'SECCION': (self._dg_vars['SECCION'], self.secciones, self._ent_seccion)}
        var, cat, ent = mapa.get(campo, (None, None, None))
        if var:
            cod = self._extraer_codigo(var.get())
            nombre = self._obtener_nombre(cod, cat)
            ent.configure(state='normal')
            ent.delete(0, 'end')
            ent.insert(0, nombre if nombre else "")
            ent.configure(state='readonly')

    # ── BD: Búsquedas ───────────────────────────────────────────────
    def _buscar_por_cedula(self):
        ced = self._cedula_var.get().strip()
        if not ced:
            messagebox.showwarning("Aviso", "Ingrese una cédula")
            return
        self._status("Buscando...")
        def tarea():
            try:
                cur = self.conn.cursor()
                cur.execute(f"SELECT * FROM RPEMPLEA WHERE CEDULA=? AND {SQL_FILTER}", (ced,))
                emp = cur.fetchone()
                cols = [c[0] for c in cur.description]
                self.root.after(0, lambda: self._procesar_busqueda(emp, cols, "cédula", ced))
            except Exception as e:
                self.root.after(0, lambda: self._status(f"Error: {e}"))
        threading.Thread(target=tarea, daemon=True).start()

    def _buscar_por_codigo(self):
        cod = self._codigo_var.get().strip()
        if not cod:
            messagebox.showwarning("Aviso", "Ingrese un código")
            return
        self._status("Buscando...")
        def tarea():
            try:
                cur = self.conn.cursor()
                cur.execute(f"SELECT * FROM RPEMPLEA WHERE EMPLEADO=? AND {SQL_FILTER}", (cod,))
                emp = cur.fetchone()
                cols = [c[0] for c in cur.description]
                self.root.after(0, lambda: self._procesar_busqueda(emp, cols, "código", cod))
            except Exception as e:
                self.root.after(0, lambda: self._status(f"Error: {e}"))
        threading.Thread(target=tarea, daemon=True).start()

    def _procesar_busqueda(self, emp, cols, tipo, valor):
        if emp:
            self._cargar_datos_empleado(emp, cols)
            self._status(f"Empleado encontrado por {tipo}: {valor}")
        else:
            messagebox.showinfo("No encontrado", f"No se encontró empleado con {tipo}: {valor}")
            self._status(f"No encontrado por {tipo}")

    # ── Cargar datos a la UI ────────────────────────────────────────
    def _cargar_datos_empleado(self, empleado, descripcion):
        cols = [c[0] for c in descripcion] if not isinstance(descripcion[0], str) else descripcion
        datos = dict(zip(cols, empleado))

        # Datos generales
        for k, v in self._dg_vars.items():
            val = datos.get(k)
            if val is not None:
                texto = str(val) if not isinstance(val, datetime) else val.strftime("%d/%m/%Y")
                combo = self._combos_widgets.get(k)
                if combo:
                    items = combo.cget('values')
                    match = self._match_combo_val(texto, items)
                    if match:
                        texto = match
                v.set(texto)
            else:
                v.set("")
        for campo in ['DEPTO', 'CARGO', 'SECCION']:
            self._actualizar_nombre_desc(campo)

        # Ingresos
        for k, v in self._ing_vars.items():
            val = datos.get(k)
            v.set(str(val) if val is not None else "")

        # Otros
        for k, v in self._ot_vars.items():
            val = datos.get(k)
            if k in ['INCL_ROL', 'INCL_BAN']:
                sv = str(val) if val is not None else 'N'
                v.set(sv)
                self._check_states[k] = (sv == 'S')
            else:
                texto = str(val) if val is not None else ""
                combo = self._combos_widgets.get(k)
                if combo and texto:
                    items = combo.cget('values')
                    match = self._match_combo_val(texto, items)
                    if match:
                        texto = match
                v.set(texto)
        self._actualizar_check_visual()

        # Certificados
        for k, v in self._cert_vars.items():
            val = datos.get(k)
            v.set(str(val) if val is not None else "")

        # Referencias
        for k, v in self._ref_vars.items():
            val = datos.get(k)
            if k in ['PRIMARIA', 'SECUNDARIA', 'EST_SUP']:
                if isinstance(v, tk.BooleanVar):
                    v.set(bool(val) if val else False)
            else:
                v.set(str(val) if val is not None else "")

        # Observaciones (se cargan con el botón "Mostrar" en la pestaña)
        # Las observaciones se muestran en RPEMPOBSERV mediante _mostrar_obs()

        self.empleado_actual = datos
        self.datos_originales = datos.copy()
        self.datos_modificados = False
        self.modo_edicion = False

        # Auditoría
        self._auditoria_data = {
            'creado_por': datos.get('creado_por', ''),
            'fecha_crea': datos.get('fecha_crea', ''),
            'mod_por': datos.get('mod_por', ''),
            'fecha_mod': datos.get('fecha_mod', ''),
        }
        self._actualizar_label_auditoria()

        self._set_form_state('view')
        self.modo_edicion = False
        self._actualizar_label_empleado()
        self._marcar_dirty('datos', 'ingresos', 'obs', 'otros', 'cert', 'ref')

    # ── BD: Lista de empleados ──────────────────────────────────────
    def _cargar_lista(self):
        if not self.conn:
            return
        self._status("Cargando lista...")
        def tarea():
            try:
                f = self._filtro_var.get()
                where = ""
                if f == "ACTIVOS":
                    where = "AND ESTADO = 'ACT'"
                elif f == "INACTIVOS":
                    where = "AND ESTADO != 'ACT'"
                order = "ORDER BY APELLIDOS, NOMBRES" if self._orden_var.get() == "alfabetico" else "ORDER BY DEPTO, APELLIDOS, NOMBRES"
                cur = self.conn.cursor()
                cur.execute(f"SELECT EMPLEADO, APELLIDOS, NOMBRES FROM RPEMPLEA WHERE {SQL_FILTER} {where} {order}")
                rows = cur.fetchall()
                self.root.after(0, lambda: self._mostrar_lista(rows))
            except Exception as e:
                self.root.after(0, lambda: self._status(f"Error lista: {e}"))
        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_lista(self, rows):
        self._tree.delete(*self._tree.get_children())
        for r in rows:
            self._tree.insert('', 'end', values=(r[0], (r[1] or '').upper(), (r[2] or '').upper()))
        self._status(f"Lista: {len(rows)} empleados")

    # ── Navegación lista ────────────────────────────────────────────
    def _on_tree_select(self, ev=None):
        sel = self._tree.selection()
        if not sel:
            return
        if self.datos_modificados:
            r = messagebox.askyesnocancel("Cambios sin guardar",
                                          "¿Guardar cambios antes de continuar?")
            if r is None:
                return
            elif r:
                if not self._guardar_cambios():
                    return
        item = self._tree.item(sel[0])
        self._codigo_var.set(str(item['values'][0]))
        self._buscar_por_codigo()

    def _primer_emp(self):
        ch = self._tree.get_children()
        if ch:
            self._tree.selection_set(ch[0])
            self._on_tree_select()

    def _ultimo_emp(self):
        ch = self._tree.get_children()
        if ch:
            self._tree.selection_set(ch[-1])
            self._on_tree_select()

    def _anterior_emp(self):
        sel = self._tree.selection()
        if not sel:
            return
        ch = self._tree.get_children()
        try:
            i = ch.index(sel[0])
            if i > 0:
                self._tree.selection_set(ch[i - 1])
                self._on_tree_select()
        except ValueError:
            pass

    def _siguiente_emp(self):
        sel = self._tree.selection()
        if not sel:
            return
        ch = self._tree.get_children()
        try:
            i = ch.index(sel[0])
            if i < len(ch) - 1:
                self._tree.selection_set(ch[i + 1])
                self._on_tree_select()
        except ValueError:
            pass

    # ── Nuevo ───────────────────────────────────────────────────────
    def _nuevo_empleado(self):
        for v in list(self._dg_vars.values()) + list(self._ing_vars.values()):
            v.set("")
        for k, v in self._ot_vars.items():
            if k in ['INCL_ROL', 'INCL_BAN']:
                v.set('N')
                self._check_states[k] = False
            else:
                v.set("")
        self._actualizar_check_visual()
        for v in list(self._cert_vars.values()):
            v.set("")
        for k, v in self._ref_vars.items():
            if k in ['PRIMARIA', 'SECUNDARIA', 'EST_SUP']:
                v.set(False)
            else:
                v.set("")
        # Limpiar frame de observaciones
        for widget in self._obs_frame.winfo_children():
            widget.destroy()
        for ent in [self._ent_depto, self._ent_cargo, self._ent_seccion]:
            ent.configure(state='normal')
            ent.delete(0, 'end')
            ent.configure(state='readonly')
        self.empleado_actual = None
        self.datos_originales = None
        self.datos_modificados = False
        self.modo_edicion = True
        self._set_form_state('edit')
        self._status("Nuevo empleado — modo edición activo")

    # ── Modificar ───────────────────────────────────────────────────
    def _modificar_empleado(self):
        if not self.empleado_actual:
            messagebox.showwarning(
                "ATENCIÓN — Sin empleado seleccionado",
                "═══════════════════════════════════════════════\n"
                "  NO HAY UN EMPLEADO SELECCIONADO\n\n"
                "  Por favor, primero seleccione un empleado\n"
                "  de la lista o búsquelo por cédula/código\n"
                "  antes de intentar modificarlo.\n"
                "═══════════════════════════════════════════════"
            )
            return
        cod = self.empleado_actual.get('EMPLEADO', '')
        nom = f"{self.empleado_actual.get('NOMBRES', '')} {self.empleado_actual.get('APELLIDOS', '')}"
        ced = self.empleado_actual.get('CEDULA', '')
        respuesta = messagebox.askyesno(
            "CONFIRMAR ACTIVACIÓN DE MODO EDICIÓN",
            "═══════════════════════════════════════════════════════════════\n"
            "  ¿DESEA ACTIVAR EL MODO EDICIÓN PARA ESTE EMPLEADO?\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            f"  • EMPLEADO:  {nom}\n"
            f"  • CÓDIGO:    {cod}\n"
            f"  • CÉDULA:    {ced}\n\n"
            "  Al activar el modo edición podrá:\n"
            "    ✓ Modificar todos los datos del empleado\n"
            "    ✓ Los cambios se aplicarán al presionar GUARDAR\n"
            "    ✓ Use CANCELAR para descartar los cambios\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "  ¿DESEA CONTINUAR CON LA ACTIVACIÓN DEL MODO EDICIÓN?\n"
            "═══════════════════════════════════════════════════════════════",
            icon='question'
        )
        if respuesta:
            self.modo_edicion = True
            self._set_form_state('edit')
            self._status(f"⚠ MODO EDICIÓN ACTIVADO — {nom}")

    # ── Eliminar ────────────────────────────────────────────────────
    def _eliminar_empleado(self):
        if not self.empleado_actual:
            messagebox.showwarning(
                "ATENCIÓN — Sin empleado seleccionado",
                "═══════════════════════════════════════════════\n"
                "  NO HAY UN EMPLEADO SELECCIONADO\n\n"
                "  Por favor, seleccione un empleado de la\n"
                "  lista o búsquelo antes de eliminarlo.\n"
                "═══════════════════════════════════════════════"
            )
            return
        cod = self.empleado_actual.get('EMPLEADO', '')
        nom = f"{self.empleado_actual.get('NOMBRES', '')} {self.empleado_actual.get('APELLIDOS', '')}"
        ced = self.empleado_actual.get('CEDULA', '')
        cargo = self.empleado_actual.get('CARGO', '')
        depto = self.empleado_actual.get('DEPTO', '')
        estado = self.empleado_actual.get('ESTADO', '')
        fecha_ing = self.empleado_actual.get('FECHA_ING', '')
        sueldo = self.empleado_actual.get('SUELDO', 0)

        # ═══ PRIMERA CONFIRMACIÓN ═══
        r1 = messagebox.askyesno(
            "⚠ ELIMINAR EMPLEADO — ADVERTENCIA INICIAL",
            "═══════════════════════════════════════════════════════════════\n"
            "  ¡ESTÁ A PUNTO DE ELIMINAR UN EMPLEADO!\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            f"  EMPLEADO:  {nom}\n"
            f"  CÓDIGO:    {cod}\n"
            f"  CÉDULA:    {ced}\n\n"
            "  CONSECUENCIAS:\n"
            "  ⚠ Esta acción ELIMINARÁ PERMANENTEMENTE al empleado\n"
            "  ⚠ Se perderán TODOS sus datos e historial\n"
            "  ⚠ Esta operación NO SE PUEDE DESHACER\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "  ¿ESTÁ SEGURO DE QUE DESEA CONTINUAR?\n"
            "═══════════════════════════════════════════════════════════════",
            icon='warning'
        )
        if not r1:
            self._status("Eliminación cancelada por el usuario")
            return

        # ═══ SEGUNDA CONFIRMACIÓN — datos críticos ═══
        advertencias = []
        try:
            if sueldo and float(str(sueldo)) > 0:
                advertencias.append(f"  • SUELDO ASIGNADO: ${float(str(sueldo)):,.2f}")
        except Exception:
            pass
        if estado and str(estado) in ('ACT', 'ACTIVO'):
            advertencias.append("  • EL EMPLEADO ESTÁ ACTIVO")
        if fecha_ing:
            advertencias.append(f"  • FECHA DE INGRESO: {fecha_ing}")
        if cargo:
            advertencias.append(f"  • CARGO ASIGNADO: {cargo}")
        if depto:
            advertencias.append(f"  • DEPARTAMENTO: {depto}")

        txt_advertencias = "\n".join(advertencias) if advertencias else "  • No se detectaron datos críticos adicionales"

        r2 = messagebox.askyesno(
            "⚠ VERIFICACIÓN DE SEGURIDAD — DATOS CRÍTICOS",
            "═══════════════════════════════════════════════════════════════\n"
            "  DATOS CRÍTICOS ASOCIADOS A ESTE EMPLEADO:\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            f"{txt_advertencias}\n\n"
            "  RECOMENDACIONES ANTES DE ELIMINAR:\n"
            "  • ¿Tiene un respaldo actualizado de la base de datos?\n"
            "  • ¿Ha verificado que no hay nóminas pendientes?\n"
            "  • ¿Ha consultado con el departamento de RRHH?\n"
            "  • ¿Está seguro de que no necesitará estos datos?\n\n"
            "  💡 SUGERENCIA: Considere marcar como INACTIVO\n"
            "     en lugar de eliminar permanentemente.\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "  ¿DESEA CONTINUAR CON LA ELIMINACIÓN?\n"
            "═══════════════════════════════════════════════════════════════",
            icon='error'
        )
        if not r2:
            self._status("Eliminación cancelada en verificación de seguridad")
            return

        # ═══ TERCERA CONFIRMACIÓN — escribir código ═══
        conf = simpledialog.askstring(
            "⚠ CONFIRMACIÓN FINAL — ESCRIBA EL CÓDIGO",
            "═══════════════════════════════════════════════════════════════\n"
            "  CONFIRMACIÓN FINAL DE ELIMINACIÓN\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            f"  Para confirmar que realmente desea ELIMINAR\n"
            f"  permanentemente a:\n\n"
            f"    {nom}\n"
            f"    Código: {cod}\n\n"
            "  Escríba exactamente el código del empleado\n"
            "  en el campo de abajo para confirmar:\n\n"
            "  ⚠ Esta es su ÚLTIMA OPORTUNIDAD de cancelar.\n"
            "  Después de esto NO HABRÁ VUELTA ATRÁS.\n"
            "═══════════════════════════════════════════════════════════════",
            parent=self.root
        )
        if not conf or conf.strip() != str(cod):
            if conf:
                messagebox.showwarning(
                    "CÓDIGO INCORRECTO",
                    "═══════════════════════════════════════════════\n"
                    f"  El código ingresado no coincide.\n\n"
                    f"  Se esperaba: {cod}\n"
                    f"  Se recibió:  {conf.strip()}\n\n"
                    "  La eliminación ha sido cancelada por seguridad.\n"
                    "═══════════════════════════════════════════════"
                )
            else:
                messagebox.showinfo(
                    "ELIMINACIÓN CANCELADA",
                    "═══════════════════════════════════════════════\n"
                    "  Eliminación cancelada por el usuario.\n"
                    "═══════════════════════════════════════════════"
                )
            self._status("Eliminación cancelada — código incorrecto")
            return

        # ═══ EJECUTAR ═══
        self._status(f"Eliminando empleado {cod}...")
        def tarea():
            try:
                cur = self.conn.cursor()
                cur.execute("DELETE FROM RPEMPLEA WHERE EMPLEADO=? AND " + SQL_FILTER, (cod,))
                if cur.rowcount == 0:
                    self.root.after(0, lambda: messagebox.showerror(
                        "ERROR AL ELIMINAR",
                        "═══════════════════════════════════════════════\n"
                        "  No se pudo eliminar el empleado.\n\n"
                        "  Posibles causas:\n"
                        "  • El empleado ya fue eliminado\n"
                        "    por otro usuario\n"
                        "  • Error de conexión a la BD\n"
                        "═══════════════════════════════════════════════"
                    ))
                    return
                self.conn.commit()
                self.root.after(0, lambda: messagebox.showinfo(
                    "ELIMINACIÓN EXITOSA",
                    "═══════════════════════════════════════════════\n"
                    f"  Empleado ELIMINADO correctamente:\n\n"
                    f"  {nom}\n"
                    f"  Código: {cod}\n\n"
                    "  El registro ha sido eliminado\n"
                    "  permanentemente de la base de datos.\n"
                    "═══════════════════════════════════════════════"
                ))
                self.root.after(0, lambda: self._status(f"Empleado {cod} eliminado"))
                self.root.after(0, self._cargar_lista)
                self.root.after(0, self._nuevo_empleado)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "ERROR CRÍTICO",
                    "═══════════════════════════════════════════════\n"
                    f"  Error al eliminar empleado:\n\n"
                    f"  {str(e)}\n\n"
                    "  El empleado NO ha sido eliminado.\n"
                    "  Contacte al administrador.\n"
                    "═══════════════════════════════════════════════"
                ))
        threading.Thread(target=tarea, daemon=True).start()

    # ── Guardar ─────────────────────────────────────────────────────
    def _guardar_cambios(self):
        if not self.conn:
            messagebox.showerror(
                "ERROR — Sin conexión",
                "═══════════════════════════════════════════════\n"
                "  No hay conexión a la base de datos.\n\n"
                "  Verifique que SQL Server esté disponible\n"
                "  en 192.168.2.115 e intente nuevamente.\n"
                "═══════════════════════════════════════════════"
            )
            return False
        if not self.modo_edicion and self.empleado_actual:
            messagebox.showwarning(
                "ATENCIÓN — Modo edición desactivado",
                "═══════════════════════════════════════════════════════════════\n"
                "  No se puede guardar porque el modo edición\n"
                "  no está activo.\n\n"
                "  Presione el botón MODIFICAR para habilitar\n"
                "  la edición de datos, luego vuelva a pulsar\n"
                "  GUARDAR.\n"
                "═══════════════════════════════════════════════════════════════"
            )
            return False
        cod = self._dg_vars['EMPLEADO'].get()
        nom = self._dg_vars['NOMBRES'].get()
        ape = self._dg_vars['APELLIDOS'].get()
        ced = self._dg_vars['CEDULA'].get()
        if not cod or not ced or not nom or not ape:
            messagebox.showerror(
                "ERROR — Campos obligatorios faltantes",
                "═══════════════════════════════════════════════════════════════\n"
                "  Los siguientes campos son OBLIGATORIOS:\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                f"  {'✓' if cod else '✗'} CÓDIGO DE EMPLEADO\n"
                f"  {'✓' if ced else '✗'} CÉDULA\n"
                f"  {'✓' if nom else '✗'} NOMBRES\n"
                f"  {'✓' if ape else '✗'} APELLIDOS\n\n"
                "  Complete todos los campos obligatorios\n"
                "  antes de guardar.\n"
                "═══════════════════════════════════════════════════════════════"
            )
            return False

        tipo_op = "ACTUALIZAR" if self.empleado_actual else "CREAR NUEVO"
        conf = messagebox.askyesno(
            f"⚠ CONFIRMAR — {tipo_op}",
            "═══════════════════════════════════════════════════════════════\n"
            f"  ¿ESTÁ SEGURO DE {tipo_op}?\n"
            "═══════════════════════════════════════════════════════════════\n\n"
            f"  EMPLEADO:  {nom} {ape}\n"
            f"  CÓDIGO:    {cod}\n"
            f"  CÉDULA:    {ced}\n\n"
            "  Esta acción:\n"
            f"  {'✓ Modificará los datos del empleado existente' if self.empleado_actual else '✓ Creará un nuevo registro de empleado'}\n"
            "  ✓ Los cambios son PERMANENTES en la base de datos\n"
            "  ✓ No se puede deshacer automáticamente\n\n"
            "═══════════════════════════════════════════════════════════════\n"
            "  ¿DESEA CONTINUAR?\n"
            "═══════════════════════════════════════════════════════════════",
            icon='warning'
        )
        if not conf:
            return False

        self._status("Guardando...")
        def tarea():
            try:
                datos = {}
                for k, v in self._dg_vars.items():
                    raw = v.get()
                    datos[k] = self._extraer_codigo(raw) if raw else None
                for k, v in self._ing_vars.items():
                    val = v.get()
                    if val:
                        try:
                            datos[k] = float(val)
                        except ValueError:
                            datos[k] = val
                    else:
                        datos[k] = None
                for k, v in self._ot_vars.items():
                    if k in ['INCL_ROL', 'INCL_BAN']:
                        datos[k] = v.get() if v.get() in ['S', 'N'] else 'N'
                    else:
                        raw = v.get()
                        datos[k] = self._extraer_codigo(raw) if raw else None
                for k, v in self._cert_vars.items():
                    datos[k] = v.get() if v.get() else None
                for k, v in self._ref_vars.items():
                    if k in ['PRIMARIA', 'SECUNDARIA', 'EST_SUP']:
                        datos[k] = 1 if v.get() else 0
                    else:
                        datos[k] = v.get() if v.get() else None
                # Las observaciones se guardan en RPEMPOBSERV, no en OBSERV de RPEMPLEA
                datos['OBSERV'] = None

                cur = self.conn.cursor()
                if self.empleado_actual:
                    campos = [f"{k}=?" for k in datos if k != 'EMPLEADO']
                    vals = [datos[k] for k in datos if k != 'EMPLEADO'] + [cod]
                    cur.execute(f"UPDATE RPEMPLEA SET {', '.join(campos)} WHERE EMPLEADO=? AND {SQL_FILTER}", vals)
                else:
                    # Verificar duplicados antes de INSERT
                    cur.execute(f"SELECT COUNT(*) FROM RPEMPLEA WHERE EMPLEADO=? AND {SQL_FILTER}", (cod,))
                    if cur.fetchone()[0] > 0:
                        self.root.after(0, lambda: messagebox.showerror("ERROR",
                            f"═══════════════════════════════════════════════\n"
                            f"  Ya existe un empleado con código {cod}.\n\n"
                            f"  Verifique que el código sea único.\n"
                            f"═══════════════════════════════════════════════"))
                        return
                    cur.execute(f"SELECT COUNT(*) FROM RPEMPLEA WHERE CEDULA=? AND {SQL_FILTER}", (ced,))
                    if cur.fetchone()[0] > 0:
                        self.root.after(0, lambda: messagebox.showerror("ERROR",
                            f"═══════════════════════════════════════════════\n"
                            f"  Ya existe un empleado con cédula {ced}.\n\n"
                            f"  Verifique que la cédula sea única.\n"
                            f"═══════════════════════════════════════════════"))
                        return
                    cols = list(datos.keys())
                    ph = ', '.join(['?'] * len(cols))
                    vals = [datos[k] for k in cols]
                    cur.execute(f"INSERT INTO RPEMPLEA ({', '.join(cols)}) VALUES ({ph})", vals)
                self.conn.commit()

                self.root.after(0, lambda: messagebox.showinfo(
                    "OPERACIÓN EXITOSA",
                    "═══════════════════════════════════════════════\n"
                    f"  Datos guardados correctamente.\n\n"
                    f"  EMPLEADO:  {nom} {ape}\n"
                    f"  CÓDIGO:    {cod}\n"
                    "═══════════════════════════════════════════════"
                ))
                self.root.after(0, lambda: self._status(f"Datos guardados: {cod}"))
                self.root.after(0, self._cargar_lista)
                self.root.after(0, lambda: setattr(self, 'datos_modificados', False))
                self.root.after(0, lambda: setattr(self, 'modo_edicion', False))
                self.root.after(0, lambda: self._set_form_state('view'))
                self.root.after(0, self._actualizar_label_empleado)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "ERROR AL GUARDAR",
                    "═══════════════════════════════════════════════\n"
                    f"  Ocurrió un error al guardar:\n\n"
                    f"  {str(e)}\n\n"
                    "  Los cambios NO han sido aplicados.\n"
                    "  Intente nuevamente.\n"
                    "═══════════════════════════════════════════════"
                ))
        threading.Thread(target=tarea, daemon=True).start()
        return True

    def _cancelar_cambios(self):
        if not self.modo_edicion:
            messagebox.showinfo(
                "INFORMACIÓN",
                "═══════════════════════════════════════════════\n"
                "  No hay cambios que cancelar.\n"
                "  El modo edición no está activo.\n"
                "═══════════════════════════════════════════════"
            )
            return
        if self.datos_modificados:
            r = messagebox.askyesno(
                "⚠ CANCELAR CAMBIOS",
                "═══════════════════════════════════════════════════════════════\n"
                "  ¿ESTÁ SEGURO DE CANCELAR LOS CAMBIOS?\n"
                "═══════════════════════════════════════════════════════════════\n\n"
                "  ADVERTENCIA:\n"
                "  • Se perderán TODAS las modificaciones\n"
                "    realizadas desde la última vez que guardó\n"
                "  • Los datos volverán a su estado original\n"
                "  • Esta acción NO se puede deshacer\n\n"
                "═══════════════════════════════════════════════════════════════\n"
                "  ¿DESCARTAR TODOS LOS CAMBIOS?\n"
                "═══════════════════════════════════════════════════════════════",
                icon='warning'
            )
            if not r:
                return
        if self.empleado_actual and self.datos_originales:
            self._cargar_datos_desde_dict(self.datos_originales)
            self.datos_modificados = False
            self.modo_edicion = False
            self._set_form_state('view')
            self._status("Cambios cancelados — datos originales restaurados")
        else:
            self._nuevo_empleado()
            self.modo_edicion = False
            self._set_form_state('view')
            self._status("Cancelado")

    def _cargar_datos_desde_dict(self, datos):
        for k, v in self._dg_vars.items():
            val = datos.get(k)
            texto = str(val) if val is not None else ""
            combo = self._combos_widgets.get(k)
            if combo and texto:
                match = self._match_combo_val(texto, combo.cget('values'))
                if match:
                    texto = match
            v.set(texto)
        for campo in ['DEPTO', 'CARGO', 'SECCION']:
            self._actualizar_nombre_desc(campo)
        for k, v in self._ing_vars.items():
            val = datos.get(k)
            v.set(str(val) if val is not None else "")
        for k, v in self._ot_vars.items():
            val = datos.get(k)
            if k in ['INCL_ROL', 'INCL_BAN']:
                sv = str(val) if val is not None else 'N'
                v.set(sv)
                self._check_states[k] = (sv == 'S')
            else:
                texto = str(val) if val is not None else ""
                combo = self._combos_widgets.get(k)
                if combo and texto:
                    match = self._match_combo_val(texto, combo.cget('values'))
                    if match:
                        texto = match
                v.set(texto)
        self._actualizar_check_visual()
        for k, v in self._cert_vars.items():
            val = datos.get(k)
            v.set(str(val) if val is not None else "")
        for k, v in self._ref_vars.items():
            val = datos.get(k)
            if k in ['PRIMARIA', 'SECUNDARIA', 'EST_SUP']:
                if isinstance(v, tk.BooleanVar):
                    v.set(bool(val) if val else False)
            else:
                v.set(str(val) if val is not None else "")
        # Las observaciones se cargan con el botón "Mostrar" en la pestaña
        # No se cargan automáticamente desde el campo OBSERV

    def _imprimir_empleado(self):
        if not self.empleado_actual:
            messagebox.showwarning(
                "ATENCIÓN",
                "═══════════════════════════════════════════════\n"
                "  No hay empleado seleccionado para imprimir.\n"
                "  Seleccione o busque un empleado primero.\n"
                "═══════════════════════════════════════════════"
            )
            return
        nom = f"{self.empleado_actual.get('NOMBRES', '')} {self.empleado_actual.get('APELLIDOS', '')}".strip()
        messagebox.showinfo(
            "IMPRESIÓN",
            "═══════════════════════════════════════════════\n"
            f"  Función de impresión no implementada.\n\n"
            f"  Empleado: {nom}\n"
            "═══════════════════════════════════════════════"
        )

    def _actualizar_label_empleado(self):
        if self.empleado_actual:
            nom = f"{self.empleado_actual.get('NOMBRES', '')} {self.empleado_actual.get('APELLIDOS', '')}".strip()
            cod = self.empleado_actual.get('EMPLEADO', '')
            self._lbl_empleado_actual.config(text=f"Empleado actual: {nom} (cód. {cod})")
        else:
            self._lbl_empleado_actual.config(text="")

    def _actualizar_label_auditoria(self):
        ad = self._auditoria_data
        parts = []
        if ad.get('creado_por'):
            parts.append(f"Creado por: {ad['creado_por']}")
        if ad.get('fecha_crea'):
            try:
                d = ad['fecha_crea']
                if isinstance(d, datetime):
                    parts.append(f"Fecha: {d.strftime('%d/%m/%Y %H:%M')}")
                else:
                    parts.append(f"Fecha: {d}")
            except Exception:
                parts.append(f"Fecha: {ad['fecha_crea']}")
        if ad.get('mod_por'):
            parts.append(f"Modificado por: {ad['mod_por']}")
        if ad.get('fecha_mod'):
            try:
                d = ad['fecha_mod']
                if isinstance(d, datetime):
                    parts.append(f"Últ. mod: {d.strftime('%d/%m/%Y %H:%M')}")
                else:
                    parts.append(f"Últ. mod: {d}")
            except Exception:
                parts.append(f"Últ. mod: {ad['fecha_mod']}")
        txt = " | ".join(parts) if parts else "Sin datos de auditoría"
        if hasattr(self, '_lbl_audit'):
            self._lbl_audit.config(text=txt)

    def _set_form_state(self, mode='view'):
        editable = (mode == 'edit')
        for key, w in self._form_widgets.items():
            if key in getattr(self, '_readonly_descs', set()):
                w.configure(state='readonly', foreground=COL_TEXT)
            elif isinstance(w, ttk.Combobox):
                w.configure(state='readonly', foreground=COL_TEXT)
            elif isinstance(w, ttk.Entry):
                w.configure(state='normal' if editable else 'readonly', foreground=COL_TEXT)
            elif isinstance(w, tk.Text):
                w.configure(state='normal' if editable else 'disabled', foreground=COL_TEXT)
            elif isinstance(w, tk.Entry):
                w.configure(state='normal' if editable else 'readonly', foreground=COL_TEXT)
        for key, w in self._check_widgets.items():
            w.configure(state='normal' if editable else 'disabled')
        if editable:
            self._status("✎ MODO EDICIÓN ACTIVO — Modifique los datos y presione GUARDAR")
        else:
            self._status("📖 MODO VISTA — Use MODIFICAR para editar los datos")

    def _marcar_modificado(self, *args):
        if self.modo_edicion and not self.datos_modificados:
            self.datos_modificados = True
            self._status("⚠ DATOS MODIFICADOS — Presione GUARDAR para aplicar")

    # ── Vista Completa ──────────────────────────────────────────────
    def _abrir_vista_completa(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Vista Completa — Todos los Empleados")
        dlg.geometry("1100x650")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=COL_BG)
        VistaCompletaWindow(dlg, self.conn)

    # ── Edición Masiva ──────────────────────────────────────────────
    def _edicion_masiva(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Edición Masiva — Excel")
        dlg.geometry("900x700")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=COL_BG)
        EdicionMasivaFrame(dlg, self)

    def _agregar_observaciones(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Agregar Observaciones Masivas — RPEMPOBSERV")
        dlg.geometry("950x750")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=COL_BG)
        ObservacionesMasivasFrame(dlg, self)

    def _abrir_buscador(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Búsqueda Avanzada")
        dlg.geometry("800x550")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=COL_BG)
        BuscadorAvanzadoFrame(dlg, self)

    # ── Cierre ──────────────────────────────────────────────────────
    def _on_close(self):
        if self.datos_modificados:
            r = messagebox.askyesnocancel(
                "⚠ SALIR DEL SISTEMA",
                "═══════════════════════════════════════════════════════════════\n"
                "  Hay cambios sin guardar.\n\n"
                "  • SÍ:  Guardar cambios y salir\n"
                "  • NO:  Salir sin guardar (se perderán)\n"
                "  • CANCELAR:  Volver al sistema\n"
                "═══════════════════════════════════════════════════════════════"
            )
            if r is None:
                return
            elif r:
                self._guardar_cambios()
                self.root.update_idletasks()
        self._running = False
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# Edición Masiva
# ═══════════════════════════════════════════════════════════════════
class EdicionMasivaFrame:
    def __init__(self, window, app):
        self.window = window
        self.app = app
        self.conn = app.conn
        self.datos_validados = None
        self._build()

    def _build(self):
        main = ttk.Frame(self.window)
        main.pack(fill='both', expand=True, padx=16, pady=16)

        tk.Label(main, text="📊 Edición Masiva por Plantilla Excel",
                 font=('Segoe UI', 14, 'bold'), fg=COL_HEADER, bg=COL_BG).pack(pady=(0, 8))

        # Instrucciones
        info = tk.Frame(main, bg=COL_CARD, relief='solid', borderwidth=1)
        info.pack(fill='x', padx=8, pady=(0, 8))
        tk.Label(info, text="ℹ️  INSTRUCCIONES:", font=FONT_LABEL, fg=COL_ACCENT, bg=COL_CARD).pack(anchor='w', padx=6, pady=(4, 2))
        txt_info = ("1. Selecciona los campos que quieres modificar en la pestaña 'Descargar'\n"
                   "2. Descarga la plantilla Excel con los datos actuales\n"
                   "3. Edita los valores en Excel (solo las celdas que cambiarán)\n"
                   "4. Sube el archivo en la pestaña 'Cargar y Aplicar'\n"
                   "5. Valida los cambios (muestra un resumen)\n"
                   "6. Aplica los cambios a la base de datos")
        tk.Label(info, text=txt_info, font=FONT_SMALL, fg=COL_TEXT, bg=COL_CARD,
                justify='left').pack(anchor='w', padx=6, pady=(2, 4))

        nb = ttk.Notebook(main)
        nb.pack(fill='both', expand=True)

        # Tab 1: Descargar
        t1 = ttk.Frame(nb)
        nb.add(t1, text="1. Descargar Plantilla")
        tk.Label(t1, text="Campos a incluir:", font=FONT_LABEL,
                 bg=COL_BG).pack(anchor='w', padx=8, pady=4)

        # Botones Seleccionar/Deseleccionar
        btn_bar = ttk.Frame(t1)
        btn_bar.pack(fill='x', padx=8, pady=4)
        ttk.Button(btn_bar, text="✓ Seleccionar Todo", command=self._seleccionar_todo).pack(side='left', padx=2)
        ttk.Button(btn_bar, text="✗ Deseleccionar Todo", command=self._deseleccionar_todo).pack(side='left', padx=2)

        self._campos_vars = {}
        cf = ttk.Frame(t1)
        cf.pack(fill='x', padx=8)
        # Campos expandidos con más opciones
        campos = [
            ('NOMBRES','Nombres'),('APELLIDOS','Apellidos'),('CEDULA','Cédula'),
            ('SEXO','Sexo'),('ESTADO_CI','E.Civil'),('LUGAR_NAC','Lugar Nac.'),
            ('FECHA_NAC','F.Nacimiento'),('DIRECCION','Dirección'),('PROVINCIA','Provincia'),
            ('CANTON','Cantón'),('PARROQUIA','Parroquia'),('NACIONAL','Nacionalidad'),
            ('TELEFONO','Teléfono'),('RPCAM','2do Teléfono'),('emp_mail','Email'),
            ('FECHA_ING','F.Ingreso'),('DEPTO','Depto'),('SECCION','Sección'),
            ('CARGO','Cargo'),('ESTADO','Estado'),('ACTIVIDAD','Actividad'),
            ('CONYUGUE','Cónyuge'),('TIPO_TRA','Tipo Trab.'),
            ('SUELDO','Sueldo'),('BONIFI','Bonif.'),('COMPEN','Compens.'),
            ('TRANSP','Transporte'),('LUNCH','Lunch'),('HOR25','H.25%'),
            ('HOR50','H.50%'),('HOR100','H.100%'),('DECIMO3','D3'),('DECIMO4','D4'),
            ('VACACION','Vacaciones'),('CARGAS','Cargas'),('ULTLIQ','Últ.Líq.'),
            ('DIAS_TRA','Días Trab.'),('TIP_SAN','T.Sangre'),('TIPO_PGO','T.Pago'),
            ('CODCTA','Cód.Cuenta'),('CTADPT','C.Depto'),('CTAAUX','C.Aux'),
            ('RUTA4','Ruta'),('CTA_CTE','C.Corriente'),('CTA_AHO','C.Ahorros'),
            ('INCL_ROL','Incl.Rol'),('INCL_BAN','Incl.Banco'),
            ('NOM_FAM','Familiares'),('DIR_FAM','Dir.Fam'),('TEL_FAM','Tel.Fam'),
            ('NOM_NO_FAM','No Familiares'),('DIR_NO_FAM','Dir.NoFam'),('TEL_NO_FAM','Tel.NoFam'),
            ('CED_MIL','C.Militar'),('EDAD','Edad'),('IDVOTA','C.Votación'),
            ('LICCOND','L.Conducir'),('CODIESS','C.IESS'),('TITULO','Título'),
            ('ANIO_EST','Años Est.'),('CERTVINF','Cert.Violencia'),('MANIOBRAS','Maniobras'),
            ('NUM_AFIL','Afil.IESS'),('OBSERV','Observaciones')
        ]
        for i, (k, n) in enumerate(campos):
            v = tk.BooleanVar(value=(i < 10))  # Primeros 10 por defecto
            self._campos_vars[k] = v
            tk.Checkbutton(cf, text=n, variable=v, font=FONT_SMALL,
                           bg=COL_BG, fg=COL_TEXT, selectcolor=COL_ACCENT).grid(row=i//6, column=i%6, sticky='w', padx=4, pady=1)

        btnf = ttk.Frame(t1)
        btnf.pack(pady=8)
        ttk.Button(btnf, text="⬇ Descargar Plantilla Excel",
                   command=self._descargar, style='Accent.TButton').pack(side='left', padx=4)

        # Tab 2: Cargar
        t2 = ttk.Frame(nb)
        nb.add(t2, text="2. Cargar y Aplicar")
        t2_content = ttk.Frame(t2)
        t2_content.pack(fill='both', expand=True, padx=8, pady=8)

        # Archivo
        tk.Label(t2_content, text="Archivo Excel:", font=FONT_LABEL, bg=COL_BG).pack(anchor='w', pady=(0, 4))
        self._archivo_var = tk.StringVar()
        rf = ttk.Frame(t2_content)
        rf.pack(fill='x', pady=(0, 4))
        ttk.Entry(rf, textvariable=self._archivo_var, width=50).pack(side='left', padx=(0, 4))
        ttk.Button(rf, text="📁 Seleccionar", command=self._seleccionar).pack(side='left', padx=2)

        # Botones
        bf = ttk.Frame(t2_content)
        bf.pack(fill='x', pady=(0, 8))
        ttk.Button(bf, text="✓ Validar Cambios", command=self._validar,
                  style='Accent.TButton').pack(side='left', padx=2)
        self._btn_aplicar = ttk.Button(bf, text="⚡ Aplicar Cambios",
                                       command=self._aplicar, state='disabled',
                                       style='Accent.TButton')
        self._btn_aplicar.pack(side='left', padx=2)

        # Resultado
        tk.Label(t2_content, text="Resumen de Cambios:", font=FONT_LABEL, bg=COL_BG).pack(anchor='w', pady=(8, 4))
        res_frame = ttk.Frame(t2_content)
        res_frame.pack(fill='both', expand=True)
        self._resultado = tk.Text(res_frame, font=('Consolas', 9),
                                  bg=COL_ENTRY_BG, fg=COL_TEXT, wrap='word', relief='solid', borderwidth=1)
        self._resultado.pack(side='left', fill='both', expand=True)
        vsb = ttk.Scrollbar(res_frame, orient='vertical', command=self._resultado.yview)
        vsb.pack(side='right', fill='y')
        self._resultado.configure(yscrollcommand=vsb.set)

        ttk.Button(main, text="Cerrar", command=self.window.destroy).pack(pady=8)

    def _seleccionar_todo(self):
        for v in self._campos_vars.values():
            v.set(True)

    def _deseleccionar_todo(self):
        for v in self._campos_vars.values():
            v.set(False)

    def _descargar(self):
        if not self.conn:
            messagebox.showerror("Error", "Sin conexión a BD")
            return
        campos_sel = [k for k, v in self._campos_vars.items() if v.get()]
        if not campos_sel:
            messagebox.showwarning("Aviso", "Seleccione al menos un campo")
            return
        def tarea():
            try:
                cur = self.conn.cursor()
                cols = ['EMPLEADO'] + campos_sel
                cur.execute(f"SELECT {', '.join(cols)} FROM RPEMPLEA WHERE {SQL_FILTER} ORDER BY EMPLEADO")
                rows = cur.fetchall()
                from openpyxl import Workbook
                from openpyxl.styles import Font
                wb = Workbook()
                ws = wb.active
                ws.title = "EMPLEADOS"
                for ci, h in enumerate(cols, 1):
                    ws.cell(row=1, column=ci, value=h).font = Font(bold=True)
                for ri, r in enumerate(rows, 2):
                    for ci, v in enumerate(r, 1):
                        ws.cell(row=ri, column=ci, value=v)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"PLANTILLA_EMPLEADOS_{ts}.xlsx"
                wb.save(fn)
                self.window.after(0, lambda: messagebox.showinfo("Éxito", f"Plantilla creada:\n{fn}"))
            except ImportError:
                self.window.after(0, lambda: messagebox.showerror("Error", "Requiere openpyxl:\npip install openpyxl"))
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()

    def _seleccionar(self):
        f = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self._archivo_var.set(f)
            self._btn_aplicar.config(state='disabled')

    def _validar(self):
        arch = self._archivo_var.get()
        if not arch:
            messagebox.showwarning("Aviso", "Seleccione un archivo")
            return
        def tarea():
            try:
                from openpyxl import load_workbook
                wb = load_workbook(arch, data_only=True)
                ws = wb['EMPLEADOS']
                headers = [c.value for c in ws[1]]
                if 'EMPLEADO' not in headers:
                    self.window.after(0, lambda: messagebox.showerror("Error", "Columna EMPLEADO requerida"))
                    return
                datos = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row[0]:
                        datos.append(row)
                if not datos:
                    self.window.after(0, lambda: messagebox.showerror("Error", "Sin datos"))
                    return
                ei = headers.index('EMPLEADO')
                cambios = []
                for row in datos:
                    emp = row[ei]
                    cur = self.conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM RPEMPLEA WHERE EMPLEADO=?", (emp,))
                    if cur.fetchone()[0] == 0:
                        continue
                    cambios_emp = {}
                    for i, h in enumerate(headers):
                        if h != 'EMPLEADO' and i < len(row) and row[i] is not None and str(row[i]).strip():
                            cambios_emp[h] = row[i]
                    if cambios_emp:
                        cambios.append({'codigo': emp, 'cambios': cambios_emp})
                self.datos_validados = cambios
                self.window.after(0, lambda: self._mostrar_validacion(cambios))
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_validacion(self, cambios):
        self._resultado.delete(1.0, 'end')
        t = sum(len(c['cambios']) for c in cambios)
        self._resultado.insert('end', f"Empleados con cambios: {len(cambios)}\n")
        self._resultado.insert('end', f"Total cambios: {t}\n\n")
        for c in cambios:
            self._resultado.insert('end', f"  {c['codigo']}: {', '.join(c['cambios'].keys())}\n")
        if cambios:
            self._btn_aplicar.config(state='normal')

    def _aplicar(self):
        if not self.datos_validados:
            return
        if not messagebox.askyesno("Confirmar", "¿Aplicar cambios masivos?", icon='warning'):
            return
        self._btn_aplicar.config(state='disabled')
        def tarea():
            try:
                ok, err = 0, 0
                for emp in self.datos_validados:
                    try:
                        sets = '=?, '.join(emp['cambios'].keys()) + '=?'
                        vals = list(emp['cambios'].values()) + [emp['codigo']]
                        self.conn.cursor().execute(
                            f"UPDATE RPEMPLEA SET {sets} WHERE EMPLEADO=? AND {SQL_FILTER}", vals)
                        ok += 1
                    except Exception:
                        err += 1
                self.conn.commit()
                self.window.after(0, lambda: messagebox.showinfo(
                    "Completado", f"Actualizados: {ok}, Errores: {err}"))
                self.window.after(0, self.app._cargar_lista)
                self.datos_validados = None
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════
# Búsqueda Avanzada
# ═══════════════════════════════════════════════════════════════════
class BuscadorAvanzadoFrame:
    def __init__(self, window, app):
        self.window = window
        self.app = app
        self.conn = app.conn
        self._build()

    def _build(self):
        main = ttk.Frame(self.window)
        main.pack(fill='both', expand=True, padx=20, pady=20)

        tk.Label(main, text="Búsqueda Avanzada de Empleados",
                 font=FONT_TITLE, fg=COL_HEADER, bg=COL_BG).pack(pady=(0, 14))

        g = ttk.LabelFrame(main, text="CRITERIOS DE BÚSQUEDA", padding=12)
        g.pack(fill='x', pady=(0, 12))

        self._apellido_var = tk.StringVar()
        self._nombre_var = tk.StringVar()
        self._cedula_var_b = tk.StringVar()
        self._estado_var_b = tk.StringVar(value="TODOS")
        self._depto_var_b = tk.StringVar()
        self._cargo_var_b = tk.StringVar()

        tk.Label(g, text="Apellidos:", font=FONT_LABEL, bg=COL_BG).grid(row=0, column=0, sticky='e', padx=6, pady=4)
        e1 = ttk.Entry(g, textvariable=self._apellido_var, width=30)
        e1.grid(row=0, column=1, sticky='w', padx=6, pady=4)
        e1.bind('<Return>', lambda ev: self._buscar())
        tk.Label(g, text="Nombres:", font=FONT_LABEL, bg=COL_BG).grid(row=0, column=2, sticky='e', padx=(14,6), pady=4)
        e2 = ttk.Entry(g, textvariable=self._nombre_var, width=30)
        e2.grid(row=0, column=3, sticky='w', padx=6, pady=4)
        e2.bind('<Return>', lambda ev: self._buscar())

        tk.Label(g, text="Cédula:", font=FONT_LABEL, bg=COL_BG).grid(row=1, column=0, sticky='e', padx=6, pady=4)
        ttk.Entry(g, textvariable=self._cedula_var_b, width=20).grid(row=1, column=1, sticky='w', padx=6, pady=4)
        tk.Label(g, text="Estado:", font=FONT_LABEL, bg=COL_BG).grid(row=1, column=2, sticky='e', padx=(14,6), pady=4)
        ttk.Combobox(g, textvariable=self._estado_var_b, values=["TODOS", "ACTIVO", "INACTIVO"],
                     width=12, state='readonly').grid(row=1, column=3, sticky='w', padx=6, pady=4)

        tk.Label(g, text="Departamento:", font=FONT_LABEL, bg=COL_BG).grid(row=2, column=0, sticky='e', padx=6, pady=4)
        ttk.Entry(g, textvariable=self._depto_var_b, width=12).grid(row=2, column=1, sticky='w', padx=6, pady=4)
        tk.Label(g, text="Cargo:", font=FONT_LABEL, bg=COL_BG).grid(row=2, column=2, sticky='e', padx=(14,6), pady=4)
        ttk.Entry(g, textvariable=self._cargo_var_b, width=12).grid(row=2, column=3, sticky='w', padx=6, pady=4)

        bf = ttk.Frame(g)
        bf.grid(row=3, column=0, columnspan=4, pady=(10, 0))
        ttk.Button(bf, text="🔍 BUSCAR", command=self._buscar, style='Accent.TButton').pack(side='left', padx=6)
        ttk.Button(bf, text="📋 MOSTRAR TODOS", command=self._mostrar_todos).pack(side='left', padx=6)
        ttk.Button(bf, text="✖ LIMPIAR", command=self._limpiar).pack(side='left', padx=6)
        ttk.Button(bf, text="📊 EXPORTAR EXCEL", command=self._exportar_excel).pack(side='left', padx=6)
        ttk.Separator(bf, orient='vertical').pack(side='left', fill='y', padx=10)
        self._info_label = tk.Label(bf, text="", font=FONT_LABEL,
                                     fg=COL_ACCENT, bg=COL_BG)
        self._info_label.pack(side='left', padx=10)

        res = ttk.LabelFrame(main, text="RESULTADOS", padding=6)
        res.pack(fill='both', expand=True)

        cols = ('cod', 'ape', 'nom', 'ced', 'cargo', 'cargo_nom', 'depto', 'depto_nom', 'sueldo', 'telefono', 'email', 'est')
        self._tree = ttk.Treeview(res, columns=cols, show='headings', height=14)
        heads = [
            ('cod', 'Cód.', 60, 'center'),
            ('ape', 'Apellidos', 140, 'w'),
            ('nom', 'Nombres', 140, 'w'),
            ('ced', 'Cédula', 110, 'center'),
            ('cargo', 'Cgo.', 50, 'center'),
            ('cargo_nom', 'Nombre Cargo', 110, 'w'),
            ('depto', 'Dpto.', 50, 'center'),
            ('depto_nom', 'Nombre Depto', 110, 'w'),
            ('sueldo', 'Sueldo', 100, 'e'),
            ('telefono', 'Teléfono', 110, 'w'),
            ('email', 'Email', 160, 'w'),
            ('est', 'Estado', 80, 'center'),
        ]
        for k, t, w, a in heads:
            self._tree.heading(k, text=t)
            self._tree.column(k, width=w, anchor=a)

        vsb = ttk.Scrollbar(res, orient='vertical', command=self._tree.yview)
        hsb = ttk.Scrollbar(res, orient='horizontal', command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        res.grid_rowconfigure(0, weight=1)
        res.grid_columnconfigure(0, weight=1)

        self._tree.bind('<Double-1>', lambda ev: self._seleccionar())
        self._tree.bind('<Return>', lambda ev: self._seleccionar())

        pie = tk.Frame(main, bg=COL_BG)
        pie.pack(fill='x', pady=(6, 0))
        tk.Label(pie, text="Doble clic o Enter para cargar en el formulario principal",
                 font=FONT_SMALL, fg=COL_GRAY, bg=COL_BG).pack(side='left')
        ttk.Button(pie, text="CERRAR", command=self.window.destroy).pack(side='right')

    def _buscar(self):
        ap = self._apellido_var.get().strip()
        nom = self._nombre_var.get().strip()
        ced = self._cedula_var_b.get().strip()
        est = self._estado_var_b.get()
        dep = self._depto_var_b.get().strip()
        car = self._cargo_var_b.get().strip()
        if not any([ap, nom, ced, dep, car]):
            messagebox.showwarning(
                "CRITERIOS DE BÚSQUEDA",
                "═══════════════════════════════════════════════════════════════\n"
                "  Ingrese al menos un criterio de búsqueda.\n\n"
                "  Puede buscar por:\n"
                "  • Apellidos (parcial)\n"
                "  • Nombres (parcial)\n"
                "  • Cédula exacta\n"
                "  • Departamento (código)\n"
                "  • Cargo (código)\n\n"
                "  O use 'MOSTRAR TODOS' para ver el listado completo.\n"
                "═══════════════════════════════════════════════════════════════"
            )
            return
        self._info_label.config(text="Buscando...")
        self.window.update_idletasks()
        def tarea():
            try:
                cur = self.conn.cursor()
                q = ("SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, CARGO, "
                     "'' as CARGO_NOM, DEPTO, '' as DEPTO_NOM, SUELDO, "
                     "TELEFONO, emp_mail, ESTADO "
                     "FROM RPEMPLEA WHERE " + SQL_FILTER)
                params = []
                if ap:
                    q += " AND UPPER(APELLIDOS) LIKE UPPER(?)"
                    params.append(f"%{ap}%")
                if nom:
                    for p in nom.split():
                        if p.strip():
                            q += " AND UPPER(NOMBRES) LIKE UPPER(?)"
                            params.append(f"%{p.strip()}%")
                if ced:
                    q += " AND CEDULA = ?"
                    params.append(ced)
                if est == "ACTIVO":
                    q += " AND ESTADO = 'ACT'"
                elif est == "INACTIVO":
                    q += " AND ESTADO != 'ACT'"
                if dep:
                    q += " AND DEPTO = ?"
                    params.append(dep)
                if car:
                    q += " AND CARGO = ?"
                    params.append(car)
                q += " ORDER BY APELLIDOS, NOMBRES"
                cur.execute(q, params)
                rows = cur.fetchall()

                # Obtener nombres descriptivos para cargos y deptos
                nombres_cargo = {}
                nombres_depto = {}
                try:
                    cur2 = self.conn.cursor()
                    cur2.execute("SELECT CODIGO, NOMBRE FROM DBTABLAS WHERE TIPO='CAR'")
                    for r in cur2.fetchall():
                        nombres_cargo[str(r[0]).strip()] = r[1]
                    cur2.execute("SELECT CODIGO, NOMBRE FROM DBTABLAS WHERE TIPO='DPT'")
                    for r in cur2.fetchall():
                        nombres_depto[str(r[0]).strip()] = r[1]
                except Exception:
                    pass

                resultados = []
                for r in rows:
                    r = list(r)
                    idx_cargo = 4
                    idx_depto = 6
                    r[5] = nombres_cargo.get(str(r[idx_cargo]).strip(), '') if r[idx_cargo] else ''
                    r[7] = nombres_depto.get(str(r[idx_depto]).strip(), '') if r[idx_depto] else ''
                    try:
                        if r[8]:
                            r[8] = f"${float(r[8]):,.2f}"
                    except Exception:
                        pass
                    resultados.append(r)

                self.window.after(0, lambda: self._mostrar_resultados(resultados))
            except Exception as e:
                self.window.after(0, lambda: self._info_label.config(text="Error en búsqueda"))
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_resultados(self, rows):
        self._tree.delete(*self._tree.get_children())
        for r in rows:
            self._tree.insert('', 'end', values=(
                r[0],
                (r[1] or '').upper(),
                (r[2] or '').upper(),
                r[3] or '',
                r[4] or '',
                r[5] or '',
                r[6] or '',
                r[7] or '',
                r[8] or '',
                r[9] or '',
                r[10] or '',
                r[11] or '',
            ))
        self._info_label.config(text=f"Encontrados: {len(rows)} empleados")

    def _mostrar_todos(self):
        self._info_label.config(text="Cargando todos...")
        self.window.update_idletasks()
        def tarea():
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, CARGO, "
                    "'' as CARGO_NOM, DEPTO, '' as DEPTO_NOM, SUELDO, "
                    "TELEFONO, emp_mail, ESTADO "
                    f"FROM RPEMPLEA WHERE {SQL_FILTER} ORDER BY APELLIDOS, NOMBRES"
                )
                rows = cur.fetchall()
                nombres_cargo = {}
                nombres_depto = {}
                try:
                    cur2 = self.conn.cursor()
                    cur2.execute("SELECT CODIGO, NOMBRE FROM DBTABLAS WHERE TIPO='CAR'")
                    for r in cur2.fetchall():
                        nombres_cargo[str(r[0]).strip()] = r[1]
                    cur2.execute("SELECT CODIGO, NOMBRE FROM DBTABLAS WHERE TIPO='DPT'")
                    for r in cur2.fetchall():
                        nombres_depto[str(r[0]).strip()] = r[1]
                except Exception:
                    pass
                resultados = []
                for r in rows:
                    r = list(r)
                    r[5] = nombres_cargo.get(str(r[4]).strip(), '') if r[4] else ''
                    r[7] = nombres_depto.get(str(r[6]).strip(), '') if r[6] else ''
                    try:
                        if r[8]:
                            r[8] = f"${float(r[8]):,.2f}"
                    except Exception:
                        pass
                    resultados.append(r)
                self.window.after(0, lambda: self._mostrar_resultados(resultados))
            except Exception as e:
                self.window.after(0, lambda: self._info_label.config(text="Error"))
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()

    def _limpiar(self):
        self._apellido_var.set("")
        self._nombre_var.set("")
        self._cedula_var_b.set("")
        self._estado_var_b.set("TODOS")
        self._depto_var_b.set("")
        self._cargo_var_b.set("")
        self._tree.delete(*self._tree.get_children())
        self._info_label.config(text="")

    def _seleccionar(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(
                "SELECCIÓN",
                "═══════════════════════════════════════════════\n"
                "  Seleccione un empleado de la lista primero.\n"
                "═══════════════════════════════════════════════"
            )
            return
        item = self._tree.item(sel[0])
        cod = item['values'][0]
        nom = f"{item['values'][1]} {item['values'][2]}".strip()
        if messagebox.askyesno(
            "CONFIRMAR SELECCIÓN",
            "═══════════════════════════════════════════════\n"
            f"  ¿Cargar este empleado?\n\n"
            f"  {nom}\n"
            f"  Código: {cod}\n"
            "═══════════════════════════════════════════════"
        ):
            self.app._codigo_var.set(str(cod))
            self.window.destroy()
            self.app._buscar_por_codigo()

    def _exportar_excel(self):
        items = self._tree.get_children()
        if not items:
            messagebox.showwarning(
                "EXPORTAR",
                "═══════════════════════════════════════════════\n"
                "  No hay datos para exportar.\n"
                "  Realice una búsqueda primero.\n"
                "═══════════════════════════════════════════════"
            )
            return
        def tarea():
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                wb = Workbook()
                ws = wb.active
                ws.title = "EMPLEADOS"
                headers = ['Código', 'Apellidos', 'Nombres', 'Cédula', 'Cargo',
                           'Nombre Cargo', 'Depto', 'Nombre Depto',
                           'Sueldo', 'Teléfono', 'Email', 'Estado']
                hf = Font(bold=True, color="FFFFFF")
                hfill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
                for ci, h in enumerate(headers, 1):
                    c = ws.cell(row=1, column=ci, value=h)
                    c.font = hf
                    c.fill = hfill
                    c.alignment = Alignment(horizontal='center')
                for ri, item in enumerate(items, 2):
                    vals = self._tree.item(item)['values']
                    for ci, v in enumerate(vals, 1):
                        ws.cell(row=ri, column=ci, value=v)
                for ci in range(1, len(headers) + 1):
                    ws.column_dimensions[chr(64 + ci)].width = 14
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"BUSQUEDA_EMPLEADOS_{ts}.xlsx"
                wb.save(fn)
                self.window.after(0, lambda: messagebox.showinfo(
                    "EXPORTADO",
                    "═══════════════════════════════════════════════\n"
                    f"  Archivo creado:\n  {fn}\n"
                    f"  Filas: {len(items)}\n"
                    "═══════════════════════════════════════════════"
                ))
            except ImportError:
                self.window.after(0, lambda: messagebox.showerror(
                    "ERROR", "Requiere openpyxl:\npip install openpyxl"))
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════
# Vista Completa — Todos los Empleados
# ═══════════════════════════════════════════════════════════════════
class VistaCompletaWindow:
    def __init__(self, parent, conn):
        self.conn = conn
        self.window = parent
        self._crear_interfaz()
        self._cargar_empleados()

    def _crear_interfaz(self):
        frame = ttk.Frame(self.window)
        frame.pack(fill='both', expand=True, padx=8, pady=8)

        # Controles
        ctrl = tk.Frame(frame, bg=COL_BG)
        ctrl.pack(fill='x', pady=(0, 6))
        tk.Label(ctrl, text="Búsqueda:", font=FONT_LABEL, bg=COL_BG).pack(side='left')
        self._busq_var = tk.StringVar()
        e = ttk.Entry(ctrl, textvariable=self._busq_var, width=30)
        e.pack(side='left', padx=(6, 10))
        e.bind('<KeyRelease>', lambda ev: self._filtrar_busqueda())
        ttk.Button(ctrl, text="Refrescar", command=self._cargar_empleados).pack(side='left', padx=2)
        ttk.Button(ctrl, text="Exportar Excel", command=self._exportar_excel).pack(side='left', padx=2)

        # Treeview
        cols = ('cod', 'ced', 'ape', 'nom', 'cargo', 'depto', 'est', 'sueldo', 'tel', 'email')
        self._tree = ttk.Treeview(frame, columns=cols, show='headings', height=18)
        self._tree.heading('cod', text='Cód.')
        self._tree.heading('ced', text='Cédula')
        self._tree.heading('ape', text='Apellidos')
        self._tree.heading('nom', text='Nombres')
        self._tree.heading('cargo', text='Cargo')
        self._tree.heading('depto', text='Depto')
        self._tree.heading('est', text='Est.')
        self._tree.heading('sueldo', text='Sueldo')
        self._tree.heading('tel', text='Teléfono')
        self._tree.heading('email', text='Email')

        self._tree.column('cod', width=50, anchor='c')
        self._tree.column('ced', width=80, anchor='c')
        self._tree.column('ape', width=100)
        self._tree.column('nom', width=100)
        self._tree.column('cargo', width=80)
        self._tree.column('depto', width=70)
        self._tree.column('est', width=50, anchor='c')
        self._tree.column('sueldo', width=80, anchor='e')
        self._tree.column('tel', width=90)
        self._tree.column('email', width=120)

        vsb = ttk.Scrollbar(frame, orient='vertical', command=self._tree.yview)
        hsb = ttk.Scrollbar(frame, orient='horizontal', command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Estadísticas
        self._stats_lbl = tk.Label(frame, text="Cargando...", font=FONT_SMALL,
                                    fg=COL_TEXT, bg=COL_BG, anchor='w')
        self._stats_lbl.pack(fill='x', pady=(6, 0))

    def _cargar_empleados(self):
        def tarea():
            try:
                cur = self.conn.cursor()
                cur.execute(f"SELECT EMPLEADO, CEDULA, APELLIDOS, NOMBRES, CARGO, DEPTO, ESTADO, SUELDO, TELEFONO, emp_mail "
                           f"FROM RPEMPLEA WHERE {SQL_FILTER} ORDER BY APELLIDOS, NOMBRES")
                rows = cur.fetchall()
                self.window.after(0, lambda: self._mostrar_empleados(rows))
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_empleados(self, rows):
        self._tree.delete(*self._tree.get_children())
        total, activos, nomina = 0, 0, 0
        for r in rows:
            cod, ced, ape, nom, cargo, depto, est, sueldo, tel, mail = r
            sueldo_fmt = f"${float(sueldo):,.2f}" if sueldo else "$0.00"
            try:
                nomina += float(sueldo) if sueldo else 0
            except Exception:
                pass
            self._tree.insert('', 'end', values=(cod, ced or '', (ape or '').upper(),
                                                 (nom or '').upper(), cargo or '', depto or '',
                                                 est or '', sueldo_fmt, tel or '', mail or ''))
            total += 1
            if est and est.upper().startswith('ACT'):
                activos += 1
        inactivos = total - activos
        promedio = nomina / activos if activos > 0 else 0
        self._stats_lbl.config(text=f"Total: {total}  |  Activos: {activos}  |  Inactivos: {inactivos}  |  "
                                    f"Nómina: ${nomina:,.2f}  |  Promedio: ${promedio:,.2f}")

    def _filtrar_busqueda(self):
        termino = self._busq_var.get().lower()
        for item in self._tree.get_children():
            valores = self._tree.item(item)['values']
            mostrar = any(termino in str(v).lower() for v in valores)
            self._tree.reattach(item, '', 'end') if mostrar else self._tree.detach(item)

    def _exportar_excel(self):
        items = self._tree.get_children()
        if not items:
            messagebox.showwarning("EXPORTAR", "No hay datos para exportar.")
            return
        def tarea():
            try:
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                wb = Workbook()
                ws = wb.active
                ws.title = "EMPLEADOS"
                headers = ['Cód.', 'Cédula', 'Apellidos', 'Nombres', 'Cargo', 'Depto',
                          'Est.', 'Sueldo', 'Teléfono', 'Email']
                hf = Font(bold=True, color="FFFFFF")
                hfill = PatternFill(start_color="1E3A5F", end_color="1E3A5F", fill_type="solid")
                for ci, h in enumerate(headers, 1):
                    c = ws.cell(row=1, column=ci, value=h)
                    c.font, c.fill = hf, hfill
                    c.alignment = Alignment(horizontal='center')
                for ri, item in enumerate(items, 2):
                    for ci, v in enumerate(self._tree.item(item)['values'], 1):
                        ws.cell(row=ri, column=ci, value=v)
                for ci in range(1, len(headers) + 1):
                    ws.column_dimensions[chr(64 + ci)].width = 14
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"EMPLEADOS_COMPLETO_{ts}.xlsx"
                wb.save(fn)
                self.window.after(0, lambda: messagebox.showinfo("EXPORTADO",
                    f"Archivo: {fn}\nFilas: {len(items)}"))
            except ImportError:
                self.window.after(0, lambda: messagebox.showerror("ERROR", "Requiere openpyxl:\npip install openpyxl"))
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))
        threading.Thread(target=tarea, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════
# Agregar Observaciones Masivas
# ═══════════════════════════════════════════════════════════════════
class ObservacionesMasivasFrame:
    def __init__(self, window, app):
        self.window = window
        self.app = app
        self.conn = app._get_sql_conn()
        self.datos_validados = None

        nb = ttk.Notebook(window)
        nb.pack(fill='both', expand=True, padx=8, pady=8)

        t1 = ttk.Frame(nb)
        nb.add(t1, text="Descargar Plantilla")
        self._build_tab1(t1)

        t2 = ttk.Frame(nb)
        nb.add(t2, text="Cargar Observaciones")
        self._build_tab2(t2)

    def _build_tab1(self, parent):
        """Pestaña para descargar plantilla"""
        inst = tk.Label(parent,
            text="1. Selecciona empleados\n2. Elige una fecha\n3. Descarga la plantilla\n4. Agrega observaciones en la columna 'texto_obs'",
            font=FONT_LABEL, bg=COL_BG, justify='left')
        inst.pack(anchor='w', padx=12, pady=10)

        # Filtro de empleados
        row1 = tk.Frame(parent, bg=COL_BG)
        row1.pack(fill='x', padx=10, pady=8)
        tk.Label(row1, text="Empleados:", font=FONT_LABEL, bg=COL_BG).pack(side='left')
        self._filtro_emp_var = tk.StringVar(value="ACTIVOS")
        cb = ttk.Combobox(row1, textvariable=self._filtro_emp_var,
                         values=["ACTIVOS", "INACTIVOS", "TODOS"], width=15, state='readonly')
        cb.pack(side='left', padx=(6, 0))

        # Fecha
        row2 = tk.Frame(parent, bg=COL_BG)
        row2.pack(fill='x', padx=10, pady=8)
        tk.Label(row2, text="Fecha Obs:", font=FONT_LABEL, bg=COL_BG).pack(side='left')
        self._fecha_obs_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        e = ttk.Entry(row2, textvariable=self._fecha_obs_var, width=15)
        e.pack(side='left', padx=(6, 0))
        tk.Label(row2, text="(YYYY-MM-DD)", font=FONT_SMALL, bg=COL_BG).pack(side='left', padx=(6, 0))

        # Botón descargar
        ttk.Button(parent, text="⬇ Descargar Plantilla",
                  command=self._descargar_plantilla).pack(fill='x', padx=10, pady=10)

        # Área de resultado
        tk.Label(parent, text="Estado:", font=FONT_LABEL, bg=COL_BG).pack(anchor='w', padx=10, pady=(10, 0))
        self._resultado_t1 = tk.Text(parent, height=10, width=80, font=FONT_SMALL, bg=COL_ENTRY_BG, fg=COL_WHITE)
        self._resultado_t1.pack(fill='both', expand=True, padx=10, pady=(6, 10))

    def _build_tab2(self, parent):
        """Pestaña para cargar observaciones"""
        t2_content = ttk.Frame(parent)
        t2_content.pack(fill='both', expand=True, padx=8, pady=8)

        tk.Label(t2_content, text="Archivo Excel:", font=FONT_LABEL, bg=COL_BG).pack(anchor='w', pady=(0, 4))

        row = tk.Frame(t2_content, bg=COL_BG)
        row.pack(fill='x', pady=(0, 8))
        self._archivo_obs_var = tk.StringVar()
        e = ttk.Entry(row, textvariable=self._archivo_obs_var, width=50)
        e.pack(side='left', fill='x', expand=True)
        ttk.Button(row, text="📁 Seleccionar", command=self._seleccionar_obs_archivo).pack(side='left', padx=(6, 0))

        btn_row = tk.Frame(t2_content, bg=COL_BG)
        btn_row.pack(fill='x', pady=(0, 12))
        ttk.Button(btn_row, text="✓ Validar Cambios", command=self._validar_obs).pack(side='left', padx=(0, 6))
        self._btn_aplicar_obs = ttk.Button(btn_row, text="⚡ Aplicar Observaciones",
                                          command=self._aplicar_obs, state='disabled')
        self._btn_aplicar_obs.pack(side='left')

        tk.Label(t2_content, text="Resumen:", font=FONT_LABEL, bg=COL_BG).pack(anchor='w', pady=(6, 4))
        self._resultado_t2 = tk.Text(t2_content, height=18, width=90, font=FONT_SMALL, bg=COL_ENTRY_BG, fg=COL_WHITE)
        self._resultado_t2.pack(fill='both', expand=True)

    def _descargar_plantilla(self):
        """Descargar plantilla Excel"""
        if not self.conn:
            messagebox.showerror("Error", "Sin conexión a BD")
            return

        filtro = self._filtro_emp_var.get()
        fecha_str = self._fecha_obs_var.get()

        try:
            fecha_obs = datetime.strptime(fecha_str, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Error", "Formato de fecha inválido. Use YYYY-MM-DD")
            return

        def tarea():
            try:
                cur = self.conn.cursor()

                # Obtener empleados
                if filtro == "ACTIVOS":
                    estado_filter = "ESTADO='A'"
                elif filtro == "INACTIVOS":
                    estado_filter = "ESTADO='I'"
                else:
                    estado_filter = "1=1"

                cur.execute(f"SELECT EMPLEADO, APELLIDOS, NOMBRES FROM RPEMPLEA WHERE {SQL_FILTER} AND {estado_filter} ORDER BY APELLIDOS")
                rows = cur.fetchall()

                from openpyxl import Workbook
                from openpyxl.styles import Font
                wb = Workbook()
                ws = wb.active
                ws.title = "OBSERVACIONES"

                headers = ['empleado', 'apellidos', 'nombres', 'fecha_ven', 'texto_obs']
                for ci, h in enumerate(headers, 1):
                    ws.cell(row=1, column=ci, value=h).font = Font(bold=True)

                for ri, r in enumerate(rows, 2):
                    ws.cell(row=ri, column=1, value=r[0])  # empleado
                    ws.cell(row=ri, column=2, value=r[1])  # apellidos
                    ws.cell(row=ri, column=3, value=r[2])  # nombres
                    ws.cell(row=ri, column=4, value=fecha_obs)  # fecha_ven
                    ws.cell(row=ri, column=5, value="")  # texto_obs

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fn = f"PLANTILLA_OBSERVACIONES_{ts}.xlsx"
                wb.save(fn)

                self.window.after(0, lambda: messagebox.showinfo("Éxito", f"Plantilla creada:\n{fn}"))
                self.window.after(0, lambda: self._resultado_t1.insert('end', f"✓ Plantilla descargada: {fn}\n  Empleados: {len(rows)}\n  Fecha: {fecha_str}\n"))

            except ImportError:
                self.window.after(0, lambda: messagebox.showerror("Error", "Requiere openpyxl:\npip install openpyxl"))
            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))

        threading.Thread(target=tarea, daemon=True).start()

    def _seleccionar_obs_archivo(self):
        f = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if f:
            self._archivo_obs_var.set(f)
            self._btn_aplicar_obs.config(state='disabled')

    def _validar_obs(self):
        """Validar observaciones del Excel"""
        arch = self._archivo_obs_var.get()
        if not arch:
            messagebox.showwarning("Aviso", "Seleccione un archivo")
            return

        def tarea():
            try:
                from openpyxl import load_workbook
                wb = load_workbook(arch, data_only=True)
                ws = wb['OBSERVACIONES']
                headers = [c.value for c in ws[1]]

                if not all(h in headers for h in ['empleado', 'fecha_ven', 'texto_obs']):
                    self.window.after(0, lambda: messagebox.showerror("Error",
                        "Faltan columnas requeridas: empleado, fecha_ven, texto_obs"))
                    return

                datos = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row[0] and row[2]:  # empleado y texto_obs no vacíos
                        datos.append(row)

                if not datos:
                    self.window.after(0, lambda: messagebox.showerror("Error", "Sin datos válidos"))
                    return

                ei = headers.index('empleado')
                efe = headers.index('fecha_ven')
                et = headers.index('texto_obs')

                cambios = []
                for row in datos:
                    emp = str(row[ei]).strip()
                    fecha = row[efe]
                    texto = str(row[et]).strip()
                    if emp and texto:
                        cambios.append({'empleado': emp, 'fecha_ven': fecha, 'texto_obs': texto})

                self.datos_validados = cambios
                self.window.after(0, lambda: self._mostrar_validacion_obs(cambios))

            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_validacion_obs(self, cambios):
        self._resultado_t2.delete(1.0, 'end')
        self._resultado_t2.insert('end', f"Observaciones a agregar: {len(cambios)}\n\n")
        for c in cambios[:20]:  # Mostrar primeras 20
            self._resultado_t2.insert('end', f"• {c['empleado']} ({c['fecha_ven']}): {c['texto_obs'][:60]}{'...' if len(c['texto_obs']) > 60 else ''}\n")
        if len(cambios) > 20:
            self._resultado_t2.insert('end', f"\n... y {len(cambios) - 20} más\n")
        self._btn_aplicar_obs.config(state='normal')

    def _aplicar_obs(self):
        """Aplicar observaciones"""
        if not self.datos_validados:
            return
        if not messagebox.askyesno("Confirmar", f"¿Agregar {len(self.datos_validados)} observaciones?", icon='warning'):
            return

        self._btn_aplicar_obs.config(state='disabled')

        def tarea():
            try:
                from agregar_observaciones_masivas import procesar_carga
                stats = procesar_carga(self.datos_validados, force_new_row=True)

                self.window.after(0, lambda: self._mostrar_resultado_obs(stats))

            except Exception as e:
                self.window.after(0, lambda msg=str(e): messagebox.showerror("Error", msg))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_resultado_obs(self, stats):
        self._resultado_t2.delete(1.0, 'end')
        self._resultado_t2.insert('end', f"""
╔═══════════════════════════════════════════════════════╗
║             RESULTADO DE AGREGACIÓN                   ║
╚═══════════════════════════════════════════════════════╝

✓ Insertados:     {stats['insertados']}
⚠ Duplicados:     {stats['duplicados']}
❌ Sin espacio:    {stats['sin_espacio']}
🔴 Errores:       {stats['errores']}

Detalles:
───────────────────────────────────────────────────────
""")
        for d in stats['detalles'][:30]:
            if d['tipo'] == 'INSERTADO':
                self._resultado_t2.insert('end', f"✓ {d['empleado']} → {d['campo']}: {d['texto']}\n")
            elif d['tipo'] == 'DUPLICADO':
                self._resultado_t2.insert('end', f"⚠ {d['empleado']}: Duplicado (ya existe)\n")
            elif d['tipo'] == 'ERROR':
                self._resultado_t2.insert('end', f"❌ {d['empleado']}: {d.get('error', 'Error desconocido')}\n")

        if len(stats['detalles']) > 30:
            self._resultado_t2.insert('end', f"\n... y {len(stats['detalles']) - 30} más\n")

        messagebox.showinfo("Completado",
            f"Insertados: {stats['insertados']}\nDuplicados: {stats['duplicados']}\nErrores: {stats['errores']}")
        self.datos_validados = None


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    try:
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logo_insevig.ico')
        if os.path.exists(ico):
            root.iconbitmap(default=ico)
    except Exception:
        pass
    app = SistemaGestionEmpleados10(root)
    root.mainloop()


if __name__ == "__main__":
    main()
