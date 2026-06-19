#!/usr/bin/env python3
"""
OBSERVACIONES DE EMPLEADOS - VERSIÓN SIMPLIFICADA PARA LINUX
Compatible con SQL Server y Supabase (fallback)
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sys
import os

# Agregar shared/ al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

try:
    from detect_db import obtener_fuente_recomendada
except:
    obtener_fuente_recomendada = lambda: 'Supabase'


class VisorObservacionesSimple:
    def __init__(self, root):
        self.root = root
        self.root.title("Observaciones de Empleados - INSEVIG")
        self.root.geometry("1000x700")

        # Detectar BD disponible
        self.db_fuente = obtener_fuente_recomendada()
        print(f"BD detectada: {self.db_fuente}")

        # Colores
        self.color_primary = "#1a4d8f"
        self.color_bg = "#f0f0f0"

        self._crear_interfaz()
        self._cargar_empleados()

    def _crear_interfaz(self):
        """Crear interfaz simplificada"""
        # Header
        header = tk.Frame(self.root, bg=self.color_primary, height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="📝 OBSERVACIONES DE EMPLEADOS",
                font=("Arial", 14, "bold"), fg="white",
                bg=self.color_primary).pack(pady=10)

        # Información de BD
        info_text = f"Fuente: {self.db_fuente}"
        tk.Label(header, text=info_text, font=("Arial", 9),
                fg="#ffff99", bg=self.color_primary).pack()

        # Contenido
        content = tk.Frame(self.root, bg=self.color_bg)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Búsqueda
        search_frame = tk.Frame(content, bg=self.color_bg)
        search_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(search_frame, text="Buscar empleado:",
                font=("Arial", 10), bg=self.color_bg).pack(side=tk.LEFT, padx=(0, 10))

        self.search_var = tk.StringVar()
        entry = tk.Entry(search_frame, textvariable=self.search_var, width=40)
        entry.pack(side=tk.LEFT, padx=(0, 10))
        entry.bind("<Return>", lambda e: self._buscar())

        tk.Button(search_frame, text="🔍 Buscar", command=self._buscar,
                 bg=self.color_primary, fg="white",
                 font=("Arial", 9), padx=15).pack(side=tk.LEFT)

        # Lista de empleados
        list_frame = tk.Frame(content, bg="white", relief=tk.SUNKEN, bd=1)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        scroll = ttk.Scrollbar(list_frame)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scroll.set,
                                  font=("Courier", 9), bg="white")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._mostrar_observaciones())
        scroll.config(command=self.listbox.yview)

        # Observaciones
        obs_label = tk.Label(content, text="Observaciones:",
                            font=("Arial", 10, "bold"), bg=self.color_bg)
        obs_label.pack(anchor="w", pady=(0, 5))

        self.obs_text = scrolledtext.ScrolledText(content, height=10,
                                                  font=("Courier", 9),
                                                  bg="white", relief=tk.SUNKEN, bd=1)
        self.obs_text.pack(fill=tk.BOTH, expand=True)

        # Status
        self.status = tk.Label(content, text="Cargando...",
                              font=("Arial", 9), fg="#666", bg=self.color_bg)
        self.status.pack(anchor="w", pady=(10, 0))

    def _cargar_empleados(self):
        """Cargar lista de empleados"""
        try:
            if self.db_fuente == 'Supabase':
                self._cargar_empleados_supabase()
            else:
                self._cargar_empleados_sqlserver()
        except Exception as e:
            self.status.config(text=f"Error: {str(e)}", fg="red")
            print(f"Error cargando empleados: {e}")

    def _cargar_empleados_sqlserver(self):
        """Cargar desde SQL Server"""
        try:
            import pyodbc

            conn = pyodbc.connect(
                'Driver={ODBC Driver 17 for SQL Server};'
                'Server=192.168.2.115;'
                'Database=insevig;'
                'UID=sa;'
                'PWD=puntosoft123*;'
                'TrustServerCertificate=yes'
            )
            cursor = conn.cursor()

            # Consulta simple
            query = """
                SELECT EMPLEADO, NOMBRES, APELLIDOS, CEDULA
                FROM RPEMPLEA
                WHERE CODEMP='10' AND CODSUC='10'
                ORDER BY APELLIDOS, NOMBRES
            """
            cursor.execute(query)

            self.empleados = {}
            for row in cursor.fetchall():
                key = f"{row[1]} {row[2]} ({row[3]})"
                self.empleados[key] = row[0]
                self.listbox.insert(tk.END, key)

            cursor.close()
            conn.close()

            self.status.config(text=f"✓ {len(self.empleados)} empleados cargados", fg="#27ae60")
        except Exception as e:
            self.status.config(text=f"Error SQL Server: {str(e)}", fg="red")
            self._cargar_empleados_supabase()

    def _cargar_empleados_supabase(self):
        """Cargar desde Supabase"""
        try:
            from supabase import create_client
            import os

            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_KEY')

            if not url or not key:
                raise Exception("Credenciales Supabase no configuradas")

            client = create_client(url, key)
            response = client.table('rpemplea').select('empleado,nombres,apellidos,cedula')\
                .eq('codemp', '10').eq('codsuc', '10')\
                .order('apellidos').order('nombres').execute()

            self.empleados = {}
            for row in response.data:
                key = f"{row['nombres']} {row['apellidos']} ({row['cedula']})"
                self.empleados[key] = row['empleado']
                self.listbox.insert(tk.END, key)

            self.status.config(text=f"✓ {len(self.empleados)} empleados cargados (Supabase)", fg="#27ae60")
        except Exception as e:
            self.status.config(text=f"Error: {str(e)}", fg="red")
            messagebox.showerror("Error", f"No se pudo cargar empleados:\n{str(e)}")

    def _buscar(self):
        """Buscar empleados por nombre"""
        texto = self.search_var.get().lower()
        if not texto:
            return

        self.listbox.delete(0, tk.END)
        for nombre in self.empleados.keys():
            if texto in nombre.lower():
                self.listbox.insert(tk.END, nombre)

    def _mostrar_observaciones(self):
        """Mostrar observaciones del empleado seleccionado"""
        sel = self.listbox.curselection()
        if not sel:
            return

        self.obs_text.delete(1.0, tk.END)
        self.obs_text.insert(tk.END,
            "📌 OBSERVACIONES\n"
            "================\n\n"
            "(Módulo en desarrollo - versión simplificada para Linux)\n\n"
            "Funcionalidades disponibles:\n"
            "• Ver empleados\n"
            "• Registrar observaciones\n"
            "• Historial de notas\n\n"
            "Para usar todas las funciones, use la versión completa en Windows."
        )


if __name__ == '__main__':
    root = tk.Tk()
    app = VisorObservacionesSimple(root)
    root.mainloop()
