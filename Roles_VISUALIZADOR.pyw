#!/usr/bin/env python3
"""
VISUALIZADOR DE ROLES - INSEVIG
Usa el generador para obtener datos y muestra el PDF en pantalla
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from datetime import datetime
import tempfile

try:
    from PIL import Image, ImageTk
    import fitz  # PyMuPDF
    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False

# Cargar el generador Y el módulo de datos reutilizable
exec(open('Roles_generador_VIZUALIZADOR_10.pyw').read().replace('if __name__ == "__main__":', 'if False:'))
from obtener_datos import ObtenerDatos

class VisualizadorRoles:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador de Roles - INSEVIG")
        self.root.geometry("950x850")

        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"

        self.vis_periodo_var = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        self.vis_buscar_var = tk.StringVar()
        self.vis_datos_actual = None

        # Crear instancia del generador
        self.generador = GeneradorRolesPagoINSEVIG(tk.Tk())
        self.generador.root.withdraw()

        # Crear instancia del módulo de datos reutilizable (BÚSQUEDA RÁPIDA)
        self.obtener_datos = ObtenerDatos()

        self.crear_interfaz()

    def crear_interfaz(self):
        # Header
        header = tk.Frame(self.root, bg=self.color_primary, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="VISUALIZADOR DE ROLES",
                font=("Arial", 12, "bold"), fg="white", bg=self.color_primary).pack(pady=6)
        tk.Label(header, text="INSEVIG CIA. LTDA.",
                font=("Arial", 8), fg=self.color_secondary, bg=self.color_primary).pack()

        # Controls
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(ctrl, text="Período:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Entry(ctrl, textvariable=self.vis_periodo_var, width=12).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(ctrl, text="Nombre o Cédula:").grid(row=0, column=2, padx=5, pady=5)
        entry_buscar = ttk.Entry(ctrl, textvariable=self.vis_buscar_var, width=30)
        entry_buscar.grid(row=0, column=3, padx=5, pady=5)
        entry_buscar.bind("<Return>", lambda e: self._buscar())

        ttk.Button(ctrl, text="🔍 Buscar", command=self._buscar).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(ctrl, text="💾 Descargar PDF", command=self._descargar).grid(row=0, column=5, padx=5, pady=5)

        self.status = tk.Label(ctrl, text="Ingrese período y nombre", fg='#666666', bg=self.color_bg)
        self.status.grid(row=1, column=0, columnspan=6, sticky="w", padx=5, pady=3)

        # Canvas para mostrar PDF
        scroll_frame = ttk.Frame(self.root)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        scroll = ttk.Scrollbar(scroll_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(scroll_frame, bg="white", yscrollcommand=scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.canvas.yview)

        self.photo_image = None

    def _buscar(self):
        periodo = self.vis_periodo_var.get().strip()
        filtro = self.vis_buscar_var.get().strip()

        if not periodo or not filtro:
            messagebox.showwarning("Advertencia", "Ingrese período y nombre/cédula")
            return

        self.status.config(text="⏳ Buscando...", fg='#cc6600')
        threading.Thread(target=self._buscar_thread, args=(periodo, filtro), daemon=True).start()

    def _buscar_thread(self, periodo, filtro):
        try:
            self.root.after(0, lambda: self.status.config(text="⏳ Buscando empleados...", fg='#cc6600'))

            # Usar búsqueda RÁPIDA que consulta directamente en BD
            # Sin cargar TODO el período (esto es crítico para rendimiento)
            resultados = self._buscar_empleados_bd(periodo, filtro)

            if resultados is None or resultados.empty:
                self.root.after(0, lambda: messagebox.showinfo("Sin resultados", f"No encontrado: {filtro}"))
                return

            # Mostrar lista de resultados para seleccionar
            self.root.after(0, lambda: self._mostrar_resultados(resultados, periodo))

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", err_msg))

    def _buscar_empleados_bd(self, periodo, filtro):
        """Búsqueda RÁPIDA directa en BD sin cargar todo el período"""
        try:
            import pyodbc
            import pandas as pd

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

            # Buscar empleados que coincidan con el filtro
            query = """
            SELECT TOP 100 [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [CARGO], [DEPTO], [SECCION]
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE CODEMP='10' AND CODSUC='10' AND [ESTADO]='ACT'
            AND ([NOMBRES] LIKE ? OR [APELLIDOS] LIKE ? OR [CEDULA] LIKE ?)
            ORDER BY [APELLIDOS], [NOMBRES]
            """

            filtro_sql = f'%{filtro}%'
            df = pd.read_sql(query, conn, params=[filtro_sql, filtro_sql, filtro_sql])

            # Crear nombres consolidados
            if df is not None and not df.empty:
                df['APELLIDOS_NOMBRES'] = (df['APELLIDOS'].fillna('').astype(str) + ' ' +
                                          df['NOMBRES'].fillna('').astype(str)).str.strip()

            conn.close()
            return df if df is not None else pd.DataFrame()

        except Exception as e:
            print(f"❌ Error en búsqueda: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()

    def _mostrar_resultados(self, resultados, periodo):
        """Mostrar lista de resultados para que el usuario seleccione"""

        # Crear ventana de selección
        win = tk.Toplevel(self.root)
        win.title("Seleccionar Empleado")
        win.geometry("900x500")
        win.resizable(True, True)

        # ═══ HEADER ═══
        header = tk.Frame(win, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="RESULTADOS DE BÚSQUEDA",
                font=("Arial", 12, "bold"), fg="white", bg=self.color_primary).pack(pady=5)
        tk.Label(header, text=f"Se encontraron {len(resultados)} empleado(s) | Período: {periodo}",
                font=("Arial", 9), fg=self.color_secondary, bg=self.color_primary).pack()

        # ═══ MARCO PRINCIPAL ═══
        main_frame = tk.Frame(win, bg="#f5f5f5")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # ═══ ENCABEZADOS DE COLUMNAS ═══
        header_frame = tk.Frame(main_frame, bg=self.color_primary, height=35)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="CÉDULA", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary, width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=5)
        tk.Label(header_frame, text="NOMBRE", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary, width=50, anchor="w").pack(side=tk.LEFT, padx=10)
        tk.Label(header_frame, text="DEPARTAMENTO", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary, anchor="w").pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)

        # ═══ LISTBOX CON SCROLLBAR ═══
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

        # ═══ LLENAR LISTBOX ═══
        items = []
        for idx, (i, emp) in enumerate(resultados.iterrows()):
            cedula = str(emp['CEDULA']).split('.')[0] if '.' in str(emp['CEDULA']) else str(emp['CEDULA'])
            nombre = emp['APELLIDOS_NOMBRES']
            depto = emp.get('DEPTO', 'N/A')

            # Formatear con espacios para que quede en columnas
            texto = f"{cedula:<15} {nombre:<50} {depto}"
            listbox.insert(tk.END, texto)

            # Alternar colores
            if idx % 2 == 0:
                listbox.itemconfig(tk.END, bg="#f9f9f9")

            items.append((i, emp))

        # Seleccionar primer elemento
        if items:
            listbox.selection_set(0)
            listbox.see(0)

        # Hacer doble-click para seleccionar
        def seleccionar_doble(event=None):
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un empleado")
                return
            idx_sel = sel[0]
            emp_row = items[idx_sel][1]

            # Cargar datos COMPLETOS del empleado seleccionado (incluye movimientos)
            self.status.config(text="⏳ Cargando rol del empleado...", fg='#cc6600')
            threading.Thread(target=self._cargar_y_mostrar_empleado,
                           args=(periodo, emp_row['CEDULA']), daemon=True).start()
            win.destroy()

        listbox.bind("<Double-Button-1>", seleccionar_doble)

        # ═══ BOTONES ═══
        btn_frame = tk.Frame(main_frame, bg="#f5f5f5")
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(btn_frame, text="✓ VER DETALLES", command=seleccionar_doble,
                 bg=self.color_primary, fg="white", font=("Arial", 10, "bold"),
                 padx=20, pady=8, relief=tk.RAISED, bd=2, cursor="hand2").pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="✕ CERRAR", command=win.destroy,
                 bg="#999999", fg="white", font=("Arial", 10),
                 padx=20, pady=8, relief=tk.RAISED, bd=2, cursor="hand2").pack(side=tk.LEFT, padx=5)

        # ═══ PIE DE PÁGINA ═══
        footer = tk.Frame(win, bg="#e0e0e0", height=30)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        tk.Label(footer, text="💡 Tip: Haz doble-click en un empleado para ver su rol",
                font=("Arial", 9), fg="#666666", bg="#e0e0e0").pack(pady=5)

        self.status.config(text=f"✓ {len(resultados)} resultados encontrados", fg='#28a745')

    def _cargar_y_mostrar_empleado(self, periodo, cedula):
        """Cargar datos COMPLETOS del empleado (incluye movimientos) - RÁPIDO"""
        try:
            # Limpiar la cédula: puede venir como float 1207868553.0
            # Convertir a int y luego a string para eliminar el .0
            cedula_limpia = str(int(float(str(cedula))))

            emp = self.obtener_datos.obtener_datos_empleado_rapido(periodo, cedula_limpia)

            if emp is None:
                self.root.after(0, lambda: messagebox.showerror("Error", "No se encontraron datos del empleado"))
                return

            self.vis_datos_actual = emp
            self.root.after(0, self._mostrar)

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error cargando empleado: {err_msg}"))

    def _mostrar(self):
        """Generar PDF usando el generador y mostrarlo en pantalla"""
        if self.vis_datos_actual is None:
            return

        try:
            emp = self.vis_datos_actual
            periodo = self.vis_periodo_var.get()

            # Generar PDF en archivo temporal
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                ruta_pdf = tmp.name

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"

            # Calcular correctamente la fecha final
            mes_num = int(mes)
            if mes_num == 12:
                año_fin = int(año) + 1
                mes_fin = 1
            else:
                año_fin = int(año)
                mes_fin = mes_num + 1

            fecha_fin = f"{año_fin}-{mes_fin:02d}-01"

            # Usar el generador para crear el PDF EXACTO
            self.generador.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)

            # Convertir PDF a imagen y mostrar
            if HAS_PDF_SUPPORT:
                self._mostrar_pdf_como_imagen(ruta_pdf)
            else:
                # Fallback: abrir en visor del sistema
                import subprocess
                subprocess.Popen(['xdg-open', ruta_pdf])
                messagebox.showinfo("PDF generado", f"Se abrió en el visor PDF")

            self.status.config(text=f"✓ {emp['APELLIDOS_NOMBRES']}", fg='#28a745')

        except Exception as e:
            messagebox.showerror("Error", f"Error generando PDF: {e}")

    def _mostrar_pdf_como_imagen(self, ruta_pdf):
        """Convertir PDF a imagen y mostrar en Canvas"""
        try:
            # Abrir PDF con PyMuPDF
            doc = fitz.open(ruta_pdf)
            page = doc[0]

            # Renderizar a imagen
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))  # Zoom 1.5x
            img_data = pix.tobytes("ppm")

            # Convertir a PIL Image
            from io import BytesIO
            img = Image.open(BytesIO(img_data))

            # Convertir a PhotoImage para Tkinter
            self.photo_image = ImageTk.PhotoImage(img)

            # Mostrar en canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.photo_image, anchor="nw")
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

            doc.close()

        except Exception as e:
            messagebox.showerror("Error", f"Error mostrando PDF: {e}")

    def _descargar(self):
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

            # Calcular correctamente la fecha final
            mes_num = int(mes)
            if mes_num == 12:
                año_fin = int(año) + 1
                mes_fin = 1
            else:
                año_fin = int(año)
                mes_fin = mes_num + 1

            fecha_fin = f"{año_fin}-{mes_fin:02d}-01"

            self.generador.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)
            messagebox.showinfo("Éxito", f"PDF descargado en:\n{ruta_pdf}")

        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")

if __name__ == '__main__':
    if not HAS_PDF_SUPPORT:
        print("⚠️  Falta PyMuPDF para mostrar PDF en pantalla")
        print("Instala: pip install pymupdf pillow")
        print("El visualizador abrirá PDFs en el visor del sistema")

    root = tk.Tk()
    app = VisualizadorRoles(root)
    root.mainloop()
