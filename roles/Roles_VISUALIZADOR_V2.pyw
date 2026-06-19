#!/usr/bin/env python3
"""
VISUALIZADOR DE ROLES - INSEVIG
Usa el generador para obtener datos e los muestra en pantalla
"""

import sys
import os

# Agregar el directorio actual al path para importar el generador
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkFont
import threading
from datetime import datetime

# Importar la clase del generador para usar su método obtener_datos_bd
from Roles_generador_VIZUALIZADOR_10 import GeneradorRolesPagoINSEVIG

class VisualizadorRoles:
    def __init__(self, root):
        self.root = root
        self.root.title("Visualizador de Roles - INSEVIG")
        self.root.geometry("900x800")
        
        # Crear instancia del generador para usar sus métodos
        self.generador = GeneradorRolesPagoINSEVIG(tk.Tk())  # root dummy
        
        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"
        
        self.vis_periodo_var = tk.StringVar(value=datetime.now().strftime('%Y-%m'))
        self.vis_buscar_var = tk.StringVar()
        self.vis_datos_actual = None
        
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
        ttk.Entry(ctrl, textvariable=self.vis_buscar_var, width=30).grid(row=0, column=3, padx=5, pady=5)
        
        ttk.Button(ctrl, text="🔍 Buscar", command=self._buscar).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(ctrl, text="💾 Descargar", command=self._descargar).grid(row=0, column=5, padx=5, pady=5)
        
        self.status = tk.Label(ctrl, text="Ingrese período y nombre", fg='#666666', bg=self.color_bg)
        self.status.grid(row=1, column=0, columnspan=6, sticky="w", padx=5, pady=3)
        
        # Canvas para el rol
        scroll_frame = ttk.Frame(self.root)
        scroll_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        scroll = ttk.Scrollbar(scroll_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(scroll_frame, bg="white", yscrollcommand=scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=self.canvas.yview)
    
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
            # Usar el método del generador
            df = self.generador.obtener_datos_bd(periodo)
            
            if df is None or df.empty:
                self.root.after(0, lambda: messagebox.showwarning("Sin datos", f"No hay para {periodo}"))
                return
            
            # Buscar
            mask = (
                df['APELLIDOS_NOMBRES'].str.contains(filtro, case=False, na=False) |
                df['CEDULA'].astype(str).str.contains(filtro, case=False, na=False)
            )
            res = df[mask]
            
            if res.empty:
                self.root.after(0, lambda: messagebox.showinfo("Sin resultados", f"No encontrado: {filtro}"))
                return
            
            self.vis_datos_actual = res.iloc[0]
            self.root.after(0, self._mostrar)
        
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
    
    def _mostrar(self):
        if self.vis_datos_actual is None:
            return

        emp = self.vis_datos_actual

        # Limpiar canvas
        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, 800, 1200))

        # Dibujar exactamente como el PDF
        margin = 30
        x = margin
        y = 20

        font_title = tkFont.Font(family="Arial", size=13, weight="bold")
        font_subtitle = tkFont.Font(family="Arial", size=10)
        font_label = tkFont.Font(family="Arial", size=9, weight="bold")
        font_normal = tkFont.Font(family="Arial", size=9)

        # Recuadro principal
        self.canvas.create_rectangle(margin-10, y, 800-margin, 1150, outline="black", width=2)

        # Encabezado
        y += 15
        self.canvas.create_text(400, y, text="SOBRES DE PAGOS", font=font_title, anchor="center")
        y += 20
        self.canvas.create_text(400, y, text="INSEVIG CIA. LTDA.", font=font_label, anchor="center")

        # Separador
        y += 20
        self.canvas.create_line(margin, y, 800-margin, y, fill="black", width=1)

        # Datos del empleado
        y += 15
        cedula = str(emp['CEDULA']).split('.')[0] if '.' in str(emp['CEDULA']) else str(emp['CEDULA'])
        self.canvas.create_text(x, y, text=f"Cedula empleado: {cedula}", font=font_normal, anchor="nw")
        y += 16
        self.canvas.create_text(x, y, text=f"Nombre del Empleado: {emp['APELLIDOS_NOMBRES']} ({emp['EMPLEADO']})",
                               font=font_normal, anchor="nw")
        y += 16
        periodo = self.vis_periodo_var.get()
        año, mes = periodo.split('-')
        fecha_inicio = f"{año}-{mes}-01"
        if mes == '12':
            fecha_fin = f"{int(año)+1}-01-01"
        else:
            fecha_fin = f"{año}-{int(mes)+1:02d}-01"
        self.canvas.create_text(x, y, text=f"Periodo de pago: Desde {fecha_inicio} Hasta {fecha_fin}",
                               font=font_normal, anchor="nw")
        y += 16
        self.canvas.create_text(x, y, text=f"Departamento: {emp['DEPTO']}     Cargo: {emp['CARGO']}",
                               font=font_normal, anchor="nw")

        # Tabla de movimientos
        y += 25
        col1 = x + 5
        col2 = x + 210
        col3 = x + 315
        col4 = x + 420

        self.canvas.create_text(col1, y, text="CONCEPTO", font=font_label, anchor="nw")
        self.canvas.create_text(col2, y, text="INGRESOS", font=font_label, anchor="nw")
        self.canvas.create_text(col3, y, text="DESCUENTOS", font=font_label, anchor="nw")
        self.canvas.create_text(col4, y, text="NETO A RECIBIR", font=font_label, anchor="nw")

        # Líneas de columna
        y += 15
        self.canvas.create_line(col2-5, y, col2-5, y+350, fill="gray", width=1)
        self.canvas.create_line(col3-5, y, col3-5, y+350, fill="gray", width=1)
        self.canvas.create_line(col4-5, y, col4-5, y+350, fill="gray", width=1)
        self.canvas.create_line(margin, y, 800-margin, y, fill="black", width=1)

        # Datos de movimientos
        y += 8
        line_height = 16

        total_income = 0.0
        total_deductions = 0.0

        # SUELDO con DÍAS
        sueldo = self._get_val(emp, 'SUELDO')
        dias = self._get_val(emp, 'DIAS')
        if sueldo > 0:
            dias_str = f"{int(dias)} Dias" if dias > 0 else ""
            self.canvas.create_text(col1, y, text=f"SUELDO {dias_str}", font=font_normal, anchor="nw")
            self.canvas.create_text(col2+5, y, text=f"{sueldo:.2f}", font=font_normal, anchor="ne")
            total_income += sueldo
            y += line_height

        # HORAS EXTRAS
        overtime = (self._get_val(emp, 'SOBRETIEMPO_25') +
                   self._get_val(emp, 'SOBRETIEMPO_50') +
                   self._get_val(emp, 'SOBRETIEMPO_100'))
        if overtime > 0:
            self.canvas.create_text(col1, y, text="HORAS EXTRAS", font=font_normal, anchor="nw")
            self.canvas.create_text(col2+5, y, text=f"{overtime:.2f}", font=font_normal, anchor="ne")
            total_income += overtime
            y += line_height

        # OTROS INGRESOS
        otros_ing = [
            ('BONIFICACION', "BONIFICACION"),
            ('FONDO_RESERVA', "FONDOS DE RESERVA 8.33%"),
            ('DECIMO_TERCERA', "DECIMO TERCER SUELDO"),
            ('DECIMO_CUARTA', "DECIMO CUARTO SUELDO"),
            ('MANIOBRAS', "MANIOBRAS"),
            ('REEMBOLSOS', "REEMBOLSOS"),
            ('MOVILIZACION', "MOVILIZACION")
        ]

        for col_name, label in otros_ing:
            valor = self._get_val(emp, col_name)
            if valor > 0:
                self.canvas.create_text(col1, y, text=label, font=font_normal, anchor="nw")
                self.canvas.create_text(col2+5, y, text=f"{valor:.2f}", font=font_normal, anchor="ne")
                total_income += valor
                y += line_height

        # DESCUENTOS
        desc = [
            ('APORT_IESS', "APORT.IESS"),
            ('PRESTAMOS_QUIROGRAFARIOS', "PRESTAMOS QUIROGRAFARIOS"),
            ('PRESTAMOS_COMPANIA', "PRESTAMOS COMPAÑIA"),
            ('ANTICIPO_SUELDO', "ANTICIPO DE SUELDO"),
            ('ANTICIPOS_OTROS', "ANTICIPOS OTROS"),
            ('ANTICIPOS_SURTIDOS', "ANTICIPOS SURTIDOS"),
            ('APORT_IESS_CONYUGE', "APORTE IESS CONYUGE"),
            ('IMPUESTO_RENTA', "IMPUESTO A LA RENTA"),
            ('MULTAS', "MULTAS"),
            ('PENSION_ALIMENTICIA', "PENSION ALIMENTICIA"),
            ('PRESTAMO_HIPOTECARIO', "PRESTAMO HIPOTECARIO")
        ]

        for col_name, label in desc:
            valor = self._get_val(emp, col_name)
            if valor > 0:
                self.canvas.create_text(col1, y, text=label, font=font_normal, anchor="nw")
                self.canvas.create_text(col4+5, y, text=f"{valor:.2f}", font=font_normal, anchor="ne")
                total_deductions += valor
                y += line_height

        # TOTALES
        y += 10
        self.canvas.create_line(margin, y, 800-margin, y, fill="black", width=2)
        y += 12

        net_pay = total_income - total_deductions

        self.canvas.create_text(col1, y, text="TOTAL A PAGAR", font=font_label, anchor="nw")
        self.canvas.create_text(col2+5, y, text=f"{total_income:.2f}", font=font_label, anchor="ne")
        self.canvas.create_text(col3+5, y, text=f"{total_deductions:.2f}", font=font_label, anchor="ne")
        self.canvas.create_text(col4+5, y, text=f"{net_pay:.2f}", font=font_label, anchor="ne")

        self.status.config(text=f"✓ {emp['APELLIDOS_NOMBRES']}", fg='#28a745')
    
    def _get_val(self, row, col):
        """Obtener valor de pandas Series de forma segura"""
        try:
            import pandas as pd
            if col in row.index and pd.notna(row[col]):
                return float(row[col])
            return 0.0
        except:
            return 0.0
    
    def _descargar(self):
        if self.vis_datos_actual is None:
            messagebox.showwarning("Advertencia", "Busque primero un empleado")
            return
        messagebox.showinfo("Info", "Use el Generador para descargar PDFs")

if __name__ == '__main__':
    root = tk.Tk()
    app = VisualizadorRoles(root)
    root.mainloop()
