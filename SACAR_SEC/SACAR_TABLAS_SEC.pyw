import pyodbc
import pandas as pd
import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

class ExportadorDBTABLAS:
    def __init__(self, root):
        self.root = root
        self.root.title("Exportar DBTABLAS - Empresa 10")
        self.root.geometry("500x500")
        self.root.resizable(False, False)

        # Conexion
        self.conn_str = (
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=SERVER\\server;DATABASE=insevig;'
            'UID=sa;PWD=puntosoft123*;'
            'Encrypt=No;TrustServerCertificate=yes;'
            'ApplicationIntent=ReadOnly;'
        )

        self._crear_interfaz()
        self._cargar_tipos()

    def _crear_interfaz(self):
        # Titulo
        ttk.Label(self.root, text="Exportar DBTABLAS a Excel",
                  font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(self.root, text="Filtrado por CODEMP = '10'",
                  font=('Arial', 10)).pack()

        # Frame para tipos
        frame_tipos = ttk.LabelFrame(self.root, text="Seleccione los TIPOS a exportar")
        frame_tipos.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Frame interior con scroll
        canvas = tk.Canvas(frame_tipos, height=250)
        scrollbar = ttk.Scrollbar(frame_tipos, orient="vertical", command=canvas.yview)
        self.frame_checks = ttk.Frame(canvas)

        self.frame_checks.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=self.frame_checks, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.check_vars = {}

        # Botones de seleccion rapida
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Button(btn_frame, text="Solo SEC y DPT",
                   command=self._solo_sec_dpt).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Seleccionar Todos",
                   command=self._seleccionar_todos).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Deseleccionar Todos",
                   command=self._deseleccionar_todos).pack(side=tk.LEFT, padx=5)

        # Boton exportar
        ttk.Button(self.root, text="EXPORTAR A EXCEL",
                   command=self._exportar, style='Accent.TButton').pack(pady=15)

        # Status
        self.status = tk.StringVar(value="Listo")
        ttk.Label(self.root, textvariable=self.status,
                  relief=tk.SUNKEN).pack(fill=tk.X, side=tk.BOTTOM)

    def _cargar_tipos(self):
        try:
            conn = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT TIPO FROM DBTABLAS WHERE CODEMP = '10' ORDER BY TIPO")
            tipos = [row[0] for row in cursor.fetchall()]
            conn.close()

            # Tipos prioritarios (marcados por defecto)
            tipos_defecto = ['SEC', 'DPT']

            for i, tipo in enumerate(tipos):
                var = tk.BooleanVar(value=(tipo in tipos_defecto))
                self.check_vars[tipo] = var

                cb = ttk.Checkbutton(self.frame_checks, text=tipo, variable=var)
                cb.grid(row=i//3, column=i%3, sticky='w', padx=10, pady=2)

            self.status.set(f"Tipos cargados: {len(tipos)}")

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar tipos: {e}")

    def _solo_sec_dpt(self):
        for tipo, var in self.check_vars.items():
            var.set(tipo in ['SEC', 'DPT'])

    def _seleccionar_todos(self):
        for var in self.check_vars.values():
            var.set(True)

    def _deseleccionar_todos(self):
        for var in self.check_vars.values():
            var.set(False)

    def _exportar(self):
        # Obtener tipos seleccionados
        tipos_sel = [tipo for tipo, var in self.check_vars.items() if var.get()]

        if not tipos_sel:
            messagebox.showwarning("Aviso", "Seleccione al menos un TIPO")
            return

        # Preguntar donde guardar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tipos_txt = "_".join(tipos_sel[:3])
        if len(tipos_sel) > 3:
            tipos_txt += "_etc"

        archivo = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"DBTABLAS_{tipos_txt}_{timestamp}.xlsx"
        )

        if not archivo:
            return

        try:
            self.status.set("Conectando...")
            self.root.update()

            conn = pyodbc.connect(self.conn_str)

            # Construir query con filtro
            tipos_str = ",".join([f"'{t}'" for t in tipos_sel])
            query = f"""
                SELECT TIPO, CODIGO, NOMBRE, FACTOR, T_C, T_P
                FROM DBTABLAS
                WHERE CODEMP = '10' AND TIPO IN ({tipos_str})
                ORDER BY TIPO, CODIGO
            """

            self.status.set("Ejecutando consulta...")
            self.root.update()

            df = pd.read_sql(query, conn)
            conn.close()

            if df.empty:
                messagebox.showwarning("Aviso", "No se encontraron datos")
                self.status.set("Sin datos")
                return

            self.status.set(f"Exportando {len(df)} registros...")
            self.root.update()

            # Exportar a Excel
            with pd.ExcelWriter(archivo, engine='openpyxl') as writer:
                # Una hoja por cada tipo
                for tipo in tipos_sel:
                    df_tipo = df[df['TIPO'] == tipo]
                    if not df_tipo.empty:
                        df_tipo.to_excel(writer, sheet_name=tipo, index=False)

                # Hoja con todo junto
                df.to_excel(writer, sheet_name='TODOS', index=False)

            self.status.set(f"Exportado: {len(df)} registros")
            messagebox.showinfo("Exito",
                f"Archivo creado:\n{archivo}\n\n"
                f"Registros: {len(df)}\n"
                f"Tipos: {', '.join(tipos_sel)}")

            # Abrir carpeta
            abrir_carpeta(os.path.dirname(archivo))

        except Exception as e:
            messagebox.showerror("Error", f"Error al exportar: {e}")
            self.status.set("Error")


def main():
    root = tk.Tk()
    app = ExportadorDBTABLAS(root)
    root.mainloop()


def abrir_carpeta(ruta):
    sistema = sys.platform
    if sistema == 'win32':
        os.startfile(ruta)
    elif sistema == 'darwin':
        subprocess.run(['open', ruta])
    else:
        subprocess.run(['xdg-open', ruta])


if __name__ == "__main__":
    main()
