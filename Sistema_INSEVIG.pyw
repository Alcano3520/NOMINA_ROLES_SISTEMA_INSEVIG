#!/usr/bin/env python3
"""
SISTEMA INTEGRADO INSEVIG - VERSIÓN PROFESIONAL
Diseño corporativo con menú lateral
"""

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import sys
import os
import subprocess
import importlib.machinery
import threading

# Agregar shared/ al path para importar detect_db
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

# ════════════════════════════════════════════════════════════════════════════════
# COLORES
# ════════════════════════════════════════════════════════════════════════════════

COLOR_SIDEBAR = "#0d1b2a"
COLOR_PRIMARY = "#1a4d8f"
COLOR_SECONDARY = "#ffd700"
COLOR_BG = "#f5f7fa"
COLOR_WHITE = "#ffffff"
COLOR_TEXT = "#333333"
COLOR_HOVER = "#2a5caa"


# ════════════════════════════════════════════════════════════════════════════════
# LOGIN - VERSIÓN PROFESIONAL
# ════════════════════════════════════════════════════════════════════════════════

class LoginProfesional:
    def __init__(self, root):
        self.root = root
        self.root.title("INSEVIG - Acceso al Sistema")
        self.root.geometry("900x600")
        self.root.configure(bg=COLOR_SIDEBAR)
        self.root.resizable(False, False)

        x = (self.root.winfo_screenwidth() // 2) - 450
        y = (self.root.winfo_screenheight() // 2) - 300
        self.root.geometry(f"900x600+{x}+{y}")

        self._crear_interfaz()

    def _crear_interfaz(self):
        # ════ LADO IZQUIERDO - BRANDED ════
        left = tk.Frame(self.root, bg=COLOR_PRIMARY, width=400)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(left, bg=COLOR_PRIMARY)
        logo_frame.pack(pady=60)

        tk.Label(logo_frame, text="INSEVIG", font=("Arial", 32, "bold"),
                fg=COLOR_SECONDARY, bg=COLOR_PRIMARY).pack()

        tk.Label(logo_frame, text="CIA. LTDA.", font=("Arial", 14),
                fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack()

        # Descripción
        desc_frame = tk.Frame(left, bg=COLOR_PRIMARY)
        desc_frame.pack(fill=tk.BOTH, expand=True, padx=30)

        tk.Label(desc_frame, text="Sistema Integrado de\nGestión de Nómina",
                font=("Arial", 18, "bold"), fg=COLOR_WHITE, bg=COLOR_PRIMARY,
                justify=tk.CENTER).pack(pady=40)

        tk.Label(desc_frame, text="Administración eficiente de\nrecursos humanos y nómina",
                font=("Arial", 11), fg="#cccccc", bg=COLOR_PRIMARY,
                justify=tk.CENTER).pack()

        # ════ LADO DERECHO - LOGIN ════
        right = tk.Frame(self.root, bg=COLOR_WHITE)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        login_frame = tk.Frame(right, bg=COLOR_WHITE)
        login_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        tk.Label(login_frame, text="INICIAR SESIÓN", font=("Arial", 18, "bold"),
                fg=COLOR_SIDEBAR, bg=COLOR_WHITE).pack(anchor="w", pady=(0, 30))

        # Usuario
        tk.Label(login_frame, text="Usuario", font=("Arial", 10, "bold"),
                fg=COLOR_TEXT, bg=COLOR_WHITE).pack(anchor="w", pady=(10, 3))

        self.entry_usuario = tk.Entry(login_frame, font=("Arial", 11),
                                      bg="#f5f5f5", bd=1, relief=tk.SOLID)
        self.entry_usuario.pack(fill=tk.X, ipady=10, pady=(0, 20))

        # Contraseña
        tk.Label(login_frame, text="Contraseña", font=("Arial", 10, "bold"),
                fg=COLOR_TEXT, bg=COLOR_WHITE).pack(anchor="w", pady=(10, 3))

        self.entry_password = tk.Entry(login_frame, font=("Arial", 11),
                                       bg="#f5f5f5", bd=1, relief=tk.SOLID, show="•")
        self.entry_password.pack(fill=tk.X, ipady=10, pady=(0, 30))

        # Botón login
        tk.Button(login_frame, text="ACCEDER", command=self._login,
                 bg=COLOR_PRIMARY, fg=COLOR_WHITE, font=("Arial", 11, "bold"),
                 relief=tk.FLAT, bd=0, pady=12, cursor="hand2",
                 activebackground=COLOR_HOVER).pack(fill=tk.X, pady=(0, 20))

        # Credenciales
        tk.Label(login_frame, text="Usuario de prueba: admin | Contraseña: admin",
                font=("Arial", 8), fg="#999999", bg=COLOR_WHITE).pack(side=tk.BOTTOM)

        self.entry_usuario.focus()
        self.entry_password.bind("<Return>", lambda e: self._login())

    def _login(self):
        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get().strip()

        if usuario == "admin" and password == "admin":
            # Detectar disponibilidad de BD automáticamente
            self.root.destroy()
            root_dash = tk.Tk()
            DashboardProfesional(root_dash, usuario)
            root_dash.mainloop()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos")
            self.entry_password.delete(0, tk.END)


# ════════════════════════════════════════════════════════════════════════════════
# DASHBOARD - VERSIÓN PROFESIONAL
# ════════════════════════════════════════════════════════════════════════════════

class DashboardProfesional:
    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.root.title("INSEVIG - Panel de Control")
        self.root.geometry("1400x800")

        x = (self.root.winfo_screenwidth() // 2) - 700
        y = (self.root.winfo_screenheight() // 2) - 400
        self.root.geometry(f"1400x800+{x}+{y}")

        # Detectar BD disponible en background
        self.db_disponible = self._detectar_bd_disponible()

        self._crear_interfaz()

    def _detectar_bd_disponible(self):
        """Detecta automáticamente SQL Server o Supabase"""
        try:
            from detect_db import obtener_fuente_recomendada
            fuente = obtener_fuente_recomendada()
            print(f"Base de datos detectada: {fuente}")
            return fuente
        except Exception as e:
            print(f"Error detectando BD: {e}")
            return 'SQL Server'  # Default

    def _crear_interfaz(self):
        # ════ HEADER ════
        header = tk.Frame(self.root, bg=COLOR_PRIMARY, height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="INSEVIG - Sistema Integrado",
                font=("Arial", 16, "bold"), fg=COLOR_SECONDARY,
                bg=COLOR_PRIMARY).pack(side=tk.LEFT, padx=20, pady=15)

        info_frame = tk.Frame(header, bg=COLOR_PRIMARY)
        info_frame.pack(side=tk.RIGHT, padx=20, pady=15)

        tk.Label(info_frame, text=f"👤 {self.usuario.upper()} | 📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                font=("Arial", 10), fg=COLOR_WHITE,
                bg=COLOR_PRIMARY).pack()

        # ════ CONTENIDO PRINCIPAL ════
        main_content = tk.Frame(self.root, bg=COLOR_BG)
        main_content.pack(fill=tk.BOTH, expand=True)

        # ════ MENÚ LATERAL ════
        sidebar = tk.Frame(main_content, bg=COLOR_SIDEBAR, width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Título menú
        tk.Label(sidebar, text="MENÚ", font=("Arial", 12, "bold"),
                fg=COLOR_SECONDARY, bg=COLOR_SIDEBAR).pack(anchor="w", padx=15, pady=20)

        # Opciones menú
        opciones = [
            ("📋 Roles de Pago", self._abrir_roles),
            ("👥 Gestión Empleados", self._abrir_empleados),
            ("💰 Préstamos", self._abrir_prestamos),
            ("📝 Observaciones", self._abrir_observaciones),
            ("📊 Reportes", self._abrir_reportes),
            ("⚙️ Configuración", self._abrir_config),
        ]

        for opcion, comando in opciones:
            btn = tk.Button(sidebar, text=opcion, command=comando,
                          bg=COLOR_SIDEBAR, fg=COLOR_WHITE, font=("Arial", 10),
                          relief=tk.FLAT, anchor="w", padx=15, pady=15,
                          activebackground=COLOR_HOVER, activeforeground=COLOR_SECONDARY,
                          cursor="hand2", bd=0)
            btn.pack(fill=tk.X, padx=5, pady=3)

        # Separador
        tk.Frame(sidebar, bg=COLOR_PRIMARY, height=1).pack(fill=tk.X, padx=10, pady=20)

        # Botón salir
        tk.Button(sidebar, text="🚪 Salir", command=self.root.quit,
                 bg="#cc3333", fg=COLOR_WHITE, font=("Arial", 10, "bold"),
                 relief=tk.FLAT, padx=15, pady=15, activebackground="#bb2222",
                 activeforeground=COLOR_WHITE, cursor="hand2", bd=0).pack(fill=tk.X, padx=5, pady=3, side=tk.BOTTOM)

        # ════ CONTENIDO ════
        content = tk.Frame(main_content, bg=COLOR_BG)
        content.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Bienvenida
        tk.Label(content, text=f"Bienvenido, {self.usuario}",
                font=("Arial", 20, "bold"), fg=COLOR_SIDEBAR,
                bg=COLOR_BG).pack(anchor="w", pady=(0, 10))

        tk.Label(content, text="Selecciona una opción del menú o usa los accesos rápidos abajo",
                font=("Arial", 11), fg="#666666",
                bg=COLOR_BG).pack(anchor="w", pady=(0, 30))

        # Accesos rápidos
        quick_frame = tk.Frame(content, bg=COLOR_BG)
        quick_frame.pack(fill=tk.X, pady=(0, 30))

        tk.Label(quick_frame, text="📱 Accesos Rápidos:", font=("Arial", 10, "bold"),
                fg=COLOR_SIDEBAR, bg=COLOR_BG).pack(anchor="w", pady=(0, 10))

        btn_frame = tk.Frame(quick_frame, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X)

        quick_options = [
            ("📋 Roles", self._abrir_roles),
            ("👥 Empleados", self._abrir_empleados),
            ("📊 Reportes", self._abrir_reportes),
        ]

        for texto, comando in quick_options:
            tk.Button(btn_frame, text=texto, command=comando,
                     bg=COLOR_PRIMARY, fg=COLOR_WHITE, font=("Arial", 9),
                     relief=tk.RAISED, padx=15, pady=8, cursor="hand2",
                     activebackground=COLOR_HOVER).pack(side=tk.LEFT, padx=5, pady=0)

        # Tarjetas informativas
        info_frame = tk.Frame(content, bg=COLOR_BG)
        info_frame.pack(fill=tk.BOTH, expand=True)

        stats = [
            ("📋 Roles", "Generar y visualizar\nnóminas mensuales", "125"),
            ("👥 Empleados", "Gestión del personal\nactivo", "450"),
            ("📊 Reportes", "Reportes y análisis\nde nómina", "28"),
        ]

        col = 0
        for titulo, desc, num in stats:
            card = tk.Frame(info_frame, bg=COLOR_WHITE, relief=tk.FLAT, bd=0)
            card.grid(row=0, column=col, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=20)
            info_frame.grid_columnconfigure(col, weight=1)

            tk.Label(card, text=titulo, font=("Arial", 12, "bold"),
                    fg=COLOR_PRIMARY, bg=COLOR_WHITE).pack(anchor="w")

            tk.Label(card, text=desc, font=("Arial", 9),
                    fg="#666666", bg=COLOR_WHITE, justify=tk.LEFT).pack(anchor="w", pady=(5, 10))

            tk.Label(card, text=num, font=("Arial", 24, "bold"),
                    fg=COLOR_SECONDARY, bg=COLOR_WHITE).pack(anchor="w")

            col += 1

    def _abrir_roles(self):
        """Abre Roles_Principal.pyw como ventana secundaria sin icono separado"""
        try:
            # Cargar e integrar Roles_Principal
            ruta_roles = os.path.join(os.path.dirname(__file__), "Roles_Principal.pyw")
            if os.path.exists(ruta_roles):
                loader = importlib.machinery.SourceFileLoader("roles_mod", ruta_roles)
                roles_mod = loader.load_module()

                # Crear ventana secundaria (NO aparece en taskbar)
                ventana_roles = tk.Toplevel(self.root)
                ventana_roles.title("Roles de Pago - INSEVIG")
                ventana_roles.geometry("1000x800")

                # Hacer que sea ventana secundaria del dashboard
                ventana_roles.transient(self.root)

                # Centrar en pantalla
                x = (self.root.winfo_screenwidth() // 2) - 500
                y = (self.root.winfo_screenheight() // 2) - 400
                ventana_roles.geometry(f"1000x800+{x}+{y}")

                # Crear aplicación de roles en la nueva ventana
                app_roles = roles_mod.RolesPrincipal(ventana_roles)
            else:
                messagebox.showerror("Error", f"No se encontró Roles_Principal.pyw en {ruta_roles}")
        except Exception as e:
            messagebox.showerror("Error", f"Error abriendo Roles de Pago:\n{str(e)}")

    def _abrir_empleados(self):
        """Abre SISTEMA_GESTION_EMPLEADOS_10.pyw como ventana secundaria sin icono separado"""
        try:
            # Cargar e integrar SISTEMA_GESTION_EMPLEADOS_10
            ruta_empleados = os.path.join(os.path.dirname(__file__), "SISTEMA_GESTION_EMPLEADOS_10.pyw")
            if os.path.exists(ruta_empleados):
                loader = importlib.machinery.SourceFileLoader("empleados_mod", ruta_empleados)
                empleados_mod = loader.load_module()

                # Crear ventana secundaria (NO aparece en taskbar)
                ventana_empleados = tk.Toplevel(self.root)
                ventana_empleados.title("Gestión de Empleados - INSEVIG")
                ventana_empleados.geometry("1200x700")

                # Hacer que sea ventana secundaria del dashboard
                ventana_empleados.transient(self.root)

                # Centrar en pantalla
                x = (self.root.winfo_screenwidth() // 2) - 600
                y = (self.root.winfo_screenheight() // 2) - 350
                ventana_empleados.geometry(f"1200x700+{x}+{y}")

                # Crear aplicación de empleados en la nueva ventana
                app_empleados = empleados_mod.SistemaGestionEmpleados10(ventana_empleados)
            else:
                messagebox.showerror("Error", f"No se encontró SISTEMA_GESTION_EMPLEADOS_10.pyw en {ruta_empleados}")
        except Exception as e:
            messagebox.showerror("Error", f"Error abriendo Gestión de Empleados:\n{str(e)}")

    def _abrir_reportes(self):
        messagebox.showinfo("Reportes", "Abriendo Reportes...")

    def _abrir_prestamos(self):
        """Abre módulo de Préstamos como aplicación separada"""
        try:
            import subprocess, sys, os
            ruta_prestamos = os.path.join(os.path.dirname(__file__), 'prestamos', 'HISTORIAL_PRESTAMOS_10.pyw')
            if os.path.exists(ruta_prestamos):
                subprocess.Popen([sys.executable, ruta_prestamos])
            else:
                messagebox.showerror("Error", f"Archivo no encontrado: {ruta_prestamos}")
        except Exception as e:
            messagebox.showerror("Error", f"Error abriendo Préstamos:\n{str(e)}")

    def _abrir_observaciones(self):
        """Abre módulo de Observaciones como aplicación separada"""
        try:
            import subprocess, sys, os
            ruta_observaciones = os.path.join(os.path.dirname(__file__), 'observaciones', 'TOTAL_OSERVACIONES_4_0.pyw')
            if os.path.exists(ruta_observaciones):
                subprocess.Popen([sys.executable, ruta_observaciones])
            else:
                messagebox.showerror("Error", f"Archivo no encontrado: {ruta_observaciones}")
        except Exception as e:
            messagebox.showerror("Error", f"Error abriendo Observaciones:\n{str(e)}")

    def _abrir_config(self):
        messagebox.showinfo("Configuración", "Abriendo Configuración...")


if __name__ == '__main__':
    root = tk.Tk()
    LoginProfesional(root)
    root.mainloop()
