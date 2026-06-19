#!/usr/bin/env python3
"""
ROLES DE PAGO - SISTEMA INTEGRADO INSEVIG
Combina Visualizador + Generador en una sola aplicación con pestañas
- Pestaña 1: Visualizador de Roles (búsqueda individual)
- Pestaña 2: Generador de Roles (batch)
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
import warnings

try:
    from PIL import Image, ImageTk
    import fitz  # PyMuPDF
    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False

import pyodbc
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from obtener_datos import ObtenerDatos

warnings.filterwarnings('ignore', message='.*SQLAlchemy.*')

class RolesPrincipal:
    """Aplicación principal con pestañas: Visualizador + Generador"""

    def __init__(self, root):
        self.root = root
        self.root.title("Roles de Pago - INSEVIG")
        self.root.geometry("1000x800")

        # Colores corporativos
        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"

        # Crear Notebook (pestañas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Pestaña 1: Visualizador
        tab_vis = ttk.Frame(self.notebook)
        self.notebook.add(tab_vis, text="📋 Visualizador")
        self._crear_tab_visualizador(tab_vis)

        # Pestaña 2: Generador
        tab_gen = ttk.Frame(self.notebook)
        self.notebook.add(tab_gen, text="📊 Generador Batch")
        self._crear_tab_generador(tab_gen)

        # Variables compartidas
        self.obtener_datos = ObtenerDatos()
        self.vis_datos_actual = None

    # ═════════════════════════════════════════════════════════════════
    # PESTAÑA 1: VISUALIZADOR
    # ═════════════════════════════════════════════════════════════════

    def _crear_tab_visualizador(self, parent):
        """Crear interfaz del visualizador individual"""

        # Header
        header = tk.Frame(parent, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="VISUALIZADOR DE ROLES - BÚSQUEDA INDIVIDUAL",
                font=("Arial", 11, "bold"), fg="white", bg=self.color_primary).pack(pady=5)

        # Controles
        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(ctrl, text="Período:").grid(row=0, column=0, padx=5, pady=5)
        self.vis_periodo_var = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        ttk.Entry(ctrl, textvariable=self.vis_periodo_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(ctrl, text="Nombre o Cédula:").grid(row=0, column=2, padx=5, pady=5)
        self.vis_buscar_var = tk.StringVar()
        entry_buscar = ttk.Entry(ctrl, textvariable=self.vis_buscar_var, width=30)
        entry_buscar.grid(row=0, column=3, padx=5, pady=5)
        entry_buscar.bind("<Return>", lambda e: self._vis_buscar())

        ttk.Button(ctrl, text="🔍 Buscar", command=self._vis_buscar).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(ctrl, text="💾 Descargar PDF", command=self._vis_descargar).grid(row=0, column=5, padx=5, pady=5)

        self.vis_status = tk.Label(ctrl, text="Ingrese período y nombre", fg='#666666')
        self.vis_status.grid(row=1, column=0, columnspan=6, sticky="w", padx=5, pady=3)

        # Canvas para mostrar PDF
        scroll_frame = ttk.Frame(parent)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scroll = ttk.Scrollbar(scroll_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.vis_canvas = tk.Canvas(scroll_frame, bg="white", yscrollcommand=scroll.set)
        self.vis_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.vis_canvas.yview)

        self.vis_photo_image = None

    def _vis_buscar(self):
        """Buscar empleado en visualizador"""
        periodo = self.vis_periodo_var.get().strip()
        filtro = self.vis_buscar_var.get().strip()

        if not periodo or not filtro:
            messagebox.showwarning("Advertencia", "Ingrese período y nombre/cédula")
            return

        self.vis_status.config(text="⏳ Buscando...", fg='#cc6600')
        threading.Thread(target=self._vis_buscar_thread, args=(periodo, filtro), daemon=True).start()

    def _vis_buscar_thread(self, periodo, filtro):
        """Thread de búsqueda del visualizador"""
        try:
            self.root.after(0, lambda: self.vis_status.config(text="⏳ Buscando empleados...", fg='#cc6600'))

            # Búsqueda en BD
            resultados = self._buscar_empleados_bd(filtro)

            if resultados is None or resultados.empty:
                self.root.after(0, lambda: messagebox.showinfo("Sin resultados", f"No encontrado: {filtro}"))
                return

            # Mostrar lista de resultados
            self.root.after(0, lambda: self._vis_mostrar_resultados(resultados, periodo))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _buscar_empleados_bd(self, filtro):
        """Buscar empleados en BD"""
        try:
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER=192.168.2.115;'
                f'DATABASE=insevig;'
                f'UID=sa;'
                f'PWD=puntosoft123*;'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
                f'ApplicationIntent=ReadOnly;'
            )
            conn = pyodbc.connect(conn_str)

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

                # Convertir DEPTO de código a nombre
                df_dpt = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO='DPT' AND CODEMP='10'", conn)
                dic_dpt = dict(zip(df_dpt['CODIGO'].astype(str).str.strip(), df_dpt['NOMBRE']))
                df['DEPTO'] = df['DEPTO'].astype(str).str.strip().map(lambda x: dic_dpt.get(x, x))

            conn.close()
            return df if df is not None else pd.DataFrame()

        except Exception as e:
            print(f"Error: {e}")
            return pd.DataFrame()

    def _vis_mostrar_resultados(self, resultados, periodo):
        """Mostrar ventana de selección de empleados"""

        win = tk.Toplevel(self.root)
        win.title("Seleccionar Empleado")
        win.geometry("900x500")
        win.resizable(True, True)

        # Header
        header = tk.Frame(win, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="RESULTADOS DE BÚSQUEDA",
                font=("Arial", 12, "bold"), fg="white", bg=self.color_primary).pack(pady=5)
        tk.Label(header, text=f"Se encontraron {len(resultados)} empleado(s)",
                font=("Arial", 9), fg=self.color_secondary, bg=self.color_primary).pack()

        # Marco principal
        main_frame = tk.Frame(win, bg="#f5f5f5")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Encabezados
        header_frame = tk.Frame(main_frame, bg=self.color_primary, height=35)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="CÉDULA", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary, width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=5)
        tk.Label(header_frame, text="NOMBRE", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary, width=50, anchor="w").pack(side=tk.LEFT, padx=10)
        tk.Label(header_frame, text="DEPARTAMENTO", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary, anchor="w").pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)

        # Listbox
        list_frame = tk.Frame(main_frame, bg="white", relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        scroll = ttk.Scrollbar(list_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scroll.set,
            font=("Courier", 9),
            selectmode=tk.SINGLE,
            bg="white",
            fg="#333333",
            activestyle="none",
            bd=0,
            highlightthickness=0
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=listbox.yview)

        # Llenar listbox
        items = []
        for idx, (i, emp) in enumerate(resultados.iterrows()):
            cedula = str(emp['CEDULA']).split('.')[0] if '.' in str(emp['CEDULA']) else str(emp['CEDULA'])
            nombre = emp['APELLIDOS_NOMBRES']
            depto = emp.get('DEPTO', 'N/A')

            texto = f"{cedula:<15} {nombre:<50} {depto}"
            listbox.insert(tk.END, texto)

            if idx % 2 == 0:
                listbox.itemconfig(tk.END, bg="#f9f9f9")

            items.append((i, emp))

        if items:
            listbox.selection_set(0)
            listbox.see(0)

        def seleccionar_doble(event=None):
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un empleado")
                return
            idx_sel = sel[0]
            emp_row = items[idx_sel][1]

            self.vis_status.config(text="⏳ Cargando rol...", fg='#cc6600')
            threading.Thread(target=self._vis_cargar_empleado,
                           args=(periodo, emp_row['EMPLEADO']), daemon=True).start()
            win.destroy()

        listbox.bind("<Double-Button-1>", seleccionar_doble)

        # Botones
        btn_frame = tk.Frame(main_frame, bg="#f5f5f5")
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(btn_frame, text="✓ VER DETALLES", command=seleccionar_doble,
                 bg=self.color_primary, fg="white", font=("Arial", 10, "bold"),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="✕ CERRAR", command=win.destroy,
                 bg="#999999", fg="white", font=("Arial", 10),
                 padx=20, pady=8).pack(side=tk.LEFT, padx=5)

        self.vis_status.config(text=f"✓ {len(resultados)} resultados encontrados", fg='#28a745')

    def _vis_cargar_empleado(self, periodo, empleado_code):
        """Cargar empleado y mostrar rol"""
        try:
            emp = self.obtener_datos.obtener_datos_empleado_rapido(periodo, str(empleado_code))

            if emp is None:
                self.root.after(0, lambda: messagebox.showerror("Error", "No se encontraron datos"))
                return

            self.vis_datos_actual = emp
            self.root.after(0, self._vis_mostrar_pdf)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

    def _vis_mostrar_pdf(self):
        """Mostrar PDF en canvas"""
        if self.vis_datos_actual is None:
            return

        try:
            emp = self.vis_datos_actual
            periodo = self.vis_periodo_var.get()

            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                ruta_pdf = tmp.name

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"
            _, ultimo_dia = calendar.monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{mes}-{ultimo_dia}"

            # Crear PDF usando el generador
            self._generar_pdf(ruta_pdf, emp, fecha_inicio, fecha_fin)

            # Mostrar PDF
            if HAS_PDF_SUPPORT:
                self._mostrar_pdf_canvas(ruta_pdf)
            else:
                os.system(f'xdg-open "{ruta_pdf}"')
                messagebox.showinfo("PDF generado", "Se abrió en el visor PDF")

            self.vis_status.config(text=f"✓ {emp['APELLIDOS_NOMBRES']}", fg='#28a745')

        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    def _mostrar_pdf_canvas(self, ruta_pdf):
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
        """Descargar PDF del visualizador"""
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
            _, ultimo_dia = calendar.monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{mes}-{ultimo_dia}"

            self._generar_pdf(ruta_pdf, emp, fecha_inicio, fecha_fin)
            messagebox.showinfo("Éxito", f"PDF descargado en:\n{ruta_pdf}")

        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

    # ═════════════════════════════════════════════════════════════════
    # PESTAÑA 2: GENERADOR BATCH
    # ═════════════════════════════════════════════════════════════════

    def _crear_tab_generador(self, parent):
        """Crear interfaz del generador batch"""

        # Header
        header = tk.Frame(parent, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="GENERADOR DE ROLES - BATCH",
                font=("Arial", 11, "bold"), fg="white", bg=self.color_primary).pack(pady=5)

        # Controles
        ctrl = ttk.LabelFrame(parent, text="Parámetros", padding="10")
        ctrl.pack(fill=tk.X, padx=10, pady=8)

        # Período
        ttk.Label(ctrl, text="Período (YYYY-MM):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.gen_periodo_var = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        ttk.Entry(ctrl, textvariable=self.gen_periodo_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        # Carpeta de destino
        ttk.Label(ctrl, text="Carpeta de salida:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self.gen_carpeta_var = tk.StringVar(value=os.path.expanduser("~/Roles"))
        ttk.Entry(ctrl, textvariable=self.gen_carpeta_var, width=40).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(ctrl, text="...", command=self._gen_seleccionar_carpeta).grid(row=0, column=4, padx=5, pady=5)

        # Botón generar
        ttk.Button(ctrl, text="▶ GENERAR ROLES", command=self._gen_generar).grid(row=1, column=0, columnspan=5, pady=10)

        # Estado
        self.gen_status = tk.Label(ctrl, text="Listo para generar", fg='#666666')
        self.gen_status.grid(row=2, column=0, columnspan=5, sticky="w", padx=5, pady=3)

        # Barra de progreso
        self.gen_progreso = ttk.Progressbar(ctrl, mode='determinate')
        self.gen_progreso.grid(row=3, column=0, columnspan=5, sticky="ew", padx=5, pady=5)

    def _gen_seleccionar_carpeta(self):
        """Seleccionar carpeta de salida"""
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if carpeta:
            self.gen_carpeta_var.set(carpeta)

    def _gen_generar(self):
        """Generar roles en batch"""
        periodo = self.gen_periodo_var.get().strip()
        carpeta = self.gen_carpeta_var.get().strip()

        if not periodo or not carpeta:
            messagebox.showwarning("Advertencia", "Complete los campos requeridos")
            return

        self.gen_status.config(text="⏳ Generando...", fg='#cc6600')
        self.gen_progreso['value'] = 0

        threading.Thread(target=self._gen_thread, args=(periodo, carpeta), daemon=True).start()

    def _gen_thread(self, periodo, carpeta):
        """Thread para generar roles"""
        try:
            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"
            _, ultimo_dia = calendar.monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{mes}-{ultimo_dia}"

            # Crear carpeta si no existe
            os.makedirs(carpeta, exist_ok=True)

            # Obtener datos de todos los empleados
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER=192.168.2.115;'
                f'DATABASE=insevig;'
                f'UID=sa;'
                f'PWD=puntosoft123*;'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
            )
            conn = pyodbc.connect(conn_str)

            query = """
            SELECT [EMPLEADO] FROM [insevig].[dbo].[RPEMPLEA]
            WHERE CODEMP='10' AND CODSUC='10' AND [ESTADO]='ACT'
            ORDER BY [EMPLEADO]
            """

            df_empleados = pd.read_sql(query, conn)
            conn.close()

            total = len(df_empleados)
            generados = 0

            for idx, row in df_empleados.iterrows():
                try:
                    empleado = str(row['EMPLEADO'])
                    emp = self.obtener_datos.obtener_datos_empleado_rapido(periodo, empleado)

                    if emp is not None:
                        cedula = str(emp['CEDULA']).split('.')[0]
                        nombre = emp['APELLIDOS_NOMBRES'].replace(' ', '_')
                        nombre_archivo = f"{cedula}_{nombre}.pdf"
                        ruta_pdf = os.path.join(carpeta, nombre_archivo)

                        self._generar_pdf(ruta_pdf, emp, fecha_inicio, fecha_fin)
                        generados += 1

                    # Actualizar progreso
                    self.gen_progreso['value'] = ((idx + 1) / total) * 100
                    self.root.after(0, lambda: self.gen_status.config(
                        text=f"Generados: {generados}/{total}", fg='#cc6600'))

                except Exception as e:
                    print(f"Error con empleado {empleado}: {e}")

            self.root.after(0, lambda: messagebox.showinfo("Éxito", f"Se generaron {generados} roles en:\n{carpeta}"))
            self.root.after(0, lambda: self.gen_status.config(text="✓ Completado", fg='#28a745'))
            self.gen_progreso['value'] = 100

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.gen_status.config(text="❌ Error", fg='#dc3545'))

    # ═════════════════════════════════════════════════════════════════
    # MÉTODOS COMUNES DE GENERACIÓN DE PDF
    # ═════════════════════════════════════════════════════════════════

    def _generar_pdf(self, ruta_pdf, emp, fecha_inicio, fecha_fin):
        """Generar PDF simple de rol"""
        # Implementación simplificada - usar el generador del archivo original
        # Para no duplicar código extenso de ReportLab
        try:
            # Crear PDF simple con los datos
            from reportlab.pdfgen import canvas as rl_canvas
            from reportlab.lib.pagesizes import A4

            c = rl_canvas.Canvas(ruta_pdf, pagesize=A4)
            width, height = A4

            # Título
            c.setFont("Helvetica-Bold", 14)
            c.drawString(100, height - 50, "ROLES DE PAGO")

            # Datos del empleado
            c.setFont("Helvetica", 10)
            y = height - 100
            c.drawString(100, y, f"Empleado: {emp.get('APELLIDOS_NOMBRES', 'N/A')}")
            y -= 20
            c.drawString(100, y, f"Cédula: {emp.get('CEDULA', 'N/A')}")
            y -= 20
            c.drawString(100, y, f"Período: {fecha_inicio} a {fecha_fin}")

            # Concepto
            y -= 40
            c.setFont("Helvetica-Bold", 10)
            c.drawString(100, y, "CONCEPTO")
            c.drawString(300, y, "VALOR")

            y -= 20
            c.setFont("Helvetica", 9)

            # Ingresos
            ing_fields = ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA',
                         'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25',
                         'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION']

            total_ing = 0
            for campo in ing_fields:
                valor = emp.get(campo, 0)
                if valor > 0:
                    c.drawString(100, y, campo)
                    c.drawString(300, y, f"${valor:,.2f}")
                    total_ing += valor
                    y -= 15

            y -= 10
            c.drawString(100, y, "TOTAL INGRESOS")
            c.drawString(300, y, f"${total_ing:,.2f}")

            # Egresos
            y -= 30
            egr_fields = ['APORT_IESS', 'ANTICIPO_SUELDO', 'PRESTAMOS_QUIROGRAFARIOS',
                         'PRESTAMOS_COMPANIA', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                         'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                         'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO']

            total_egr = 0
            for campo in egr_fields:
                valor = emp.get(campo, 0)
                if valor > 0:
                    c.drawString(100, y, campo)
                    c.drawString(300, y, f"${valor:,.2f}")
                    total_egr += valor
                    y -= 15

            y -= 10
            c.drawString(100, y, "TOTAL EGRESOS")
            c.drawString(300, y, f"${total_egr:,.2f}")

            # Total a recibir
            y -= 20
            c.setFont("Helvetica-Bold", 11)
            c.drawString(100, y, "NETO A RECIBIR")
            c.drawString(300, y, f"${total_ing - total_egr:,.2f}")

            c.save()

        except Exception as e:
            print(f"Error generando PDF: {e}")
            raise


if __name__ == '__main__':
    root = tk.Tk()
    app = RolesPrincipal(root)
    root.mainloop()
