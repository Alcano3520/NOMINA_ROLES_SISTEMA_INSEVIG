#!/usr/bin/env python3
"""
ROLES DE PAGO - INSEVIG
Sistema integrado: Visualizador + Generador en pestañas
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from datetime import datetime
import tempfile
import calendar

try:
    from PIL import Image, ImageTk
    import fitz
    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False

import pyodbc
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from obtener_datos import ObtenerDatos
import warnings

warnings.filterwarnings('ignore', message='.*SQLAlchemy.*')

# Importar el generador cargando el archivo como módulo
ruta_generador = os.path.join(os.path.dirname(__file__), 'Roles_generador_VIZUALIZADOR_10.pyw')
import importlib.util
import importlib.machinery

loader = importlib.machinery.SourceFileLoader("gen_mod", ruta_generador)
gen_mod = loader.load_module()
GeneradorRolesPagoINSEVIG = gen_mod.GeneradorRolesPagoINSEVIG

class RolesPrincipal:
    def __init__(self, root):
        self.root = root
        self.root.title("Roles de Pago - INSEVIG")
        self.root.geometry("1000x800")

        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"

        # Notebook (pestañas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Pestaña 1: Visualizador
        tab1 = ttk.Frame(self.notebook)
        self.notebook.add(tab1, text="📋 Visualizador")
        self._crear_visualizador(tab1)

        # Pestaña 2: Generador (como Frame, no Toplevel)
        tab2 = ttk.Frame(self.notebook)
        self.notebook.add(tab2, text="📊 Generador")
        self._crear_generador(tab2)

        # Instancias
        self.obtener_datos = ObtenerDatos()
        self.vis_datos_actual = None

    def _crear_visualizador(self, parent):
        """Crear visualizador en pestaña 1"""
        
        # Header
        header = tk.Frame(parent, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="VISUALIZADOR DE ROLES",
                font=("Arial", 11, "bold"), fg="white", bg=self.color_primary).pack(pady=5)

        # Controles
        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(ctrl, text="Período:").grid(row=0, column=0, padx=5, pady=5)
        self.vis_periodo = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        ttk.Entry(ctrl, textvariable=self.vis_periodo, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(ctrl, text="Nombre o Cédula:").grid(row=0, column=2, padx=5, pady=5)
        self.vis_buscar = tk.StringVar()
        entry = ttk.Entry(ctrl, textvariable=self.vis_buscar, width=30)
        entry.grid(row=0, column=3, padx=5, pady=5)
        entry.bind("<Return>", lambda e: self._vis_buscar())

        ttk.Button(ctrl, text="🔍 Buscar", command=self._vis_buscar).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(ctrl, text="💾 Descargar", command=self._vis_descargar).grid(row=0, column=5, padx=5, pady=5)

        self.vis_status = tk.Label(ctrl, text="Ingrese período y nombre", fg='#666666')
        self.vis_status.grid(row=1, column=0, columnspan=6, sticky="w", padx=5)

        # Canvas PDF
        scroll_frame = ttk.Frame(parent)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scroll = ttk.Scrollbar(scroll_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.vis_canvas = tk.Canvas(scroll_frame, bg="white", yscrollcommand=scroll.set)
        self.vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.vis_canvas.yview)

        self.vis_photo = None

    def _vis_buscar(self):
        periodo = self.vis_periodo.get().strip()
        filtro = self.vis_buscar.get().strip()
        if not periodo or not filtro:
            messagebox.showwarning("Advertencia", "Ingrese período y nombre/cédula")
            return
        self.vis_status.config(text="⏳ Buscando...", fg='#cc6600')
        threading.Thread(target=self._vis_buscar_thread, args=(periodo, filtro), daemon=True).start()

    def _vis_buscar_thread(self, periodo, filtro):
        try:
            resultados = self._buscar_bd(filtro)
            if resultados is None or resultados.empty:
                self.root.after(0, lambda: messagebox.showinfo("Sin resultados", f"No encontrado: {filtro}"))
                return
            self.root.after(0, lambda: self._vis_mostrar_lista(resultados, periodo))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _buscar_bd(self, filtro):
        try:
            conn = pyodbc.connect(
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=192.168.2.115;DATABASE=insevig;UID=sa;PWD=puntosoft123*;'
                'Encrypt=No;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;'
            )
            query = """
            SELECT TOP 100 [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [CARGO], [DEPTO], [SECCION]
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE CODEMP='10' AND CODSUC='10' AND [ESTADO]='ACT'
            AND ([NOMBRES] LIKE ? OR [APELLIDOS] LIKE ? OR [CEDULA] LIKE ?)
            ORDER BY [APELLIDOS], [NOMBRES]
            """
            filtro_sql = f'%{filtro}%'
            df = pd.read_sql(query, conn, params=[filtro_sql, filtro_sql, filtro_sql])
            
            if df is not None and not df.empty:
                df['APELLIDOS_NOMBRES'] = (df['APELLIDOS'].fillna('').astype(str) + ' ' +
                                          df['NOMBRES'].fillna('').astype(str)).str.strip()
                df_dpt = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO='DPT' AND CODEMP='10'", conn)
                dic_dpt = dict(zip(df_dpt['CODIGO'].astype(str).str.strip(), df_dpt['NOMBRE']))
                df['DEPTO'] = df['DEPTO'].astype(str).str.strip().map(lambda x: dic_dpt.get(x, x))
            conn.close()
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"Error: {e}")
            return pd.DataFrame()

    def _vis_mostrar_lista(self, resultados, periodo):
        win = tk.Toplevel(self.root)
        win.title("Seleccionar Empleado")
        win.geometry("900x500")

        header = tk.Frame(win, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="RESULTADOS", font=("Arial", 12, "bold"),
                fg="white", bg=self.color_primary).pack(pady=5)

        main = tk.Frame(win, bg="#f5f5f5")
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        list_frame = tk.Frame(main, bg="white", relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scroll = ttk.Scrollbar(list_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scroll.set, font=("Courier", 9),
                            selectmode=tk.SINGLE, bg="white", bd=0, highlightthickness=0)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=listbox.yview)

        items = []
        for idx, (i, emp) in enumerate(resultados.iterrows()):
            cedula = str(emp['CEDULA']).split('.')[0] if '.' in str(emp['CEDULA']) else str(emp['CEDULA'])
            texto = f"{cedula:<15} {emp['APELLIDOS_NOMBRES']:<50} {emp.get('DEPTO', 'N/A')}"
            listbox.insert(tk.END, texto)
            if idx % 2 == 0:
                listbox.itemconfig(tk.END, bg="#f9f9f9")
            items.append((i, emp))

        if items:
            listbox.selection_set(0)

        def seleccionar(event=None):
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un empleado")
                return
            emp_row = items[sel[0]][1]
            self.vis_status.config(text="⏳ Cargando...", fg='#cc6600')
            threading.Thread(target=self._vis_cargar, args=(periodo, emp_row['EMPLEADO']), daemon=True).start()
            win.destroy()

        listbox.bind("<Double-Button-1>", seleccionar)
        tk.Button(main, text="✓ VER", command=seleccionar, bg=self.color_primary,
                 fg="white", font=("Arial", 10, "bold"), padx=20, pady=8).pack(side=tk.LEFT, padx=5, pady=10)

        self.vis_status.config(text=f"✓ {len(resultados)} resultados", fg='#28a745')

    def _vis_cargar(self, periodo, emp_code):
        try:
            emp = self.obtener_datos.obtener_datos_empleado_rapido(periodo, str(emp_code))
            if emp is None:
                self.root.after(0, lambda: messagebox.showerror("Error", "No hay datos"))
                return
            self.vis_datos_actual = emp
            self.root.after(0, self._vis_mostrar)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _vis_mostrar(self):
        if self.vis_datos_actual is None:
            return
        try:
            emp = self.vis_datos_actual
            periodo = self.vis_periodo.get()
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                ruta_pdf = tmp.name

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"
            _, ultimo_dia = calendar.monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{mes}-{ultimo_dia}"

            # Usar generador para PDF
            gen_temp = GeneradorRolesPagoINSEVIG(tk.Tk())
            gen_temp.root.withdraw()
            gen_temp.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)
            gen_temp.root.destroy()

            # Mostrar PDF
            if HAS_PDF_SUPPORT:
                doc = fitz.open(ruta_pdf)
                page = doc[0]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                from io import BytesIO
                img = Image.open(BytesIO(pix.tobytes("ppm")))
                self.vis_photo = ImageTk.PhotoImage(img)
                self.vis_canvas.delete("all")
                self.vis_canvas.create_image(0, 0, image=self.vis_photo, anchor="nw")
                self.vis_canvas.config(scrollregion=self.vis_canvas.bbox("all"))
                doc.close()
            else:
                os.system(f'xdg-open "{ruta_pdf}"')

            self.vis_status.config(text=f"✓ {emp['APELLIDOS_NOMBRES']}", fg='#28a745')
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _vis_descargar(self):
        if self.vis_datos_actual is None:
            messagebox.showwarning("Advertencia", "Busque primero")
            return
        carpeta = filedialog.askdirectory(title="Seleccione carpeta")
        if not carpeta:
            return
        try:
            emp = self.vis_datos_actual
            periodo = self.vis_periodo.get()
            cedula = str(emp['CEDULA']).split('.')[0]
            nombre = emp['APELLIDOS_NOMBRES'].replace(' ', '_')
            ruta_pdf = os.path.join(carpeta, f"{cedula}_{nombre}.pdf")

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"
            _, ultimo_dia = calendar.monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{mes}-{ultimo_dia}"

            gen_temp = GeneradorRolesPagoINSEVIG(tk.Tk())
            gen_temp.root.withdraw()
            gen_temp.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)
            gen_temp.root.destroy()
            messagebox.showinfo("Éxito", f"PDF guardado en:\n{ruta_pdf}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _crear_generador(self, parent):
        """Integrar generador en pestaña 2"""
        # Crear instancia del generador pero dirigir su interfaz a esta pestaña
        self.generador = GeneradorRolesPagoINSEVIG(tk.Frame(parent))
        # Mover los widgets del generador a esta pestaña
        for widget in self.generador.root.winfo_children():
            widget.master = parent
        self.generador.root.pack(fill=tk.BOTH, expand=True)


if __name__ == '__main__':
    root = tk.Tk()
    app = RolesPrincipal(root)
    root.mainloop()
