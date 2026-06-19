#!/usr/bin/env python3
"""
SISTEMA INTEGRADO INSEVIG
Login + Dashboard + Aplicaciones
"""

import tkinter as tk
from tkinter import messagebox, ttk
import sys
import os
from datetime import datetime

# ════════════════════════════════════════════════════════════════════════════════
# COLORES CORPORATIVOS
# ════════════════════════════════════════════════════════════════════════════════

COLOR_PRIMARY = "#1a4d8f"      # Azul corporativo
COLOR_SECONDARY = "#ffd700"     # Amarillo/dorado
COLOR_BG = "#f0f0f0"           # Fondo gris claro
COLOR_WHITE = "#ffffff"         # Blanco
COLOR_DARK = "#0d1b2a"         # Azul oscuro


# ════════════════════════════════════════════════════════════════════════════════
# VENTANA DE LOGIN
# ════════════════════════════════════════════════════════════════════════════════

class VentanaLogin:
    def __init__(self, root):
        self.root = root
        self.root.title("INSEVIG - Sistema de Nómina")
        self.root.geometry("500x600")
        self.root.configure(bg=COLOR_PRIMARY)

        # Centrar ventana
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.root.winfo_screenheight() // 2) - (600 // 2)
        self.root.geometry(f"500x600+{x}+{y}")

        self.usuario_logueado = None
        self._crear_interfaz()

    def _crear_interfaz(self):
        # Frame central
        frame_central = tk.Frame(self.root, bg=COLOR_PRIMARY)
        frame_central.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Logo/Título
        tk.Label(frame_central, text="INSEVIG", font=("Arial", 28, "bold"),
                fg=COLOR_SECONDARY, bg=COLOR_PRIMARY).pack(pady=20)

        tk.Label(frame_central, text="CIA. LTDA.", font=("Arial", 12),
                fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack()

        tk.Label(frame_central, text="Sistema de Gestión de Nómina",
                font=("Arial", 10, "italic"), fg=COLOR_WHITE,
                bg=COLOR_PRIMARY).pack(pady=(0, 30))

        # Línea separadora
        tk.Frame(frame_central, bg=COLOR_SECONDARY, height=2).pack(fill=tk.X, pady=20)

        # Usuario
        tk.Label(frame_central, text="Usuario:", font=("Arial", 11, "bold"),
                fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack(anchor="w", pady=(10, 5))

        self.entry_usuario = tk.Entry(frame_central, font=("Arial", 11), width=30)
        self.entry_usuario.pack(pady=(0, 15), ipady=8)
        self.entry_usuario.focus()

        # Contraseña
        tk.Label(frame_central, text="Contraseña:", font=("Arial", 11, "bold"),
                fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack(anchor="w", pady=(10, 5))

        self.entry_password = tk.Entry(frame_central, font=("Arial", 11),
                                      width=30, show="•")
        self.entry_password.pack(pady=(0, 30), ipady=8)
        self.entry_password.bind("<Return>", lambda e: self._intentar_login())

        # Botón de login
        tk.Button(frame_central, text="ENTRAR AL SISTEMA", command=self._intentar_login,
                 bg=COLOR_SECONDARY, fg=COLOR_PRIMARY, font=("Arial", 12, "bold"),
                 relief=tk.FLAT, padx=40, pady=12, cursor="hand2",
                 activebackground="#e6c200", activeforeground=COLOR_PRIMARY).pack(pady=20)

        # Info al pie
        tk.Label(frame_central, text="Usuario: admin | Contraseña: admin",
                font=("Arial", 8), fg="#cccccc", bg=COLOR_PRIMARY).pack(side=tk.BOTTOM, pady=10)

    def _intentar_login(self):
        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get().strip()

        if not usuario or not password:
            messagebox.showwarning("Advertencia", "Ingrese usuario y contraseña")
            return

        # Verificación simple (en producción usar BD)
        if usuario == "admin" and password == "admin":
            self.usuario_logueado = usuario
            self.root.destroy()
            # Abrir dashboard
            root_dashboard = tk.Tk()
            Dashboard(root_dashboard, usuario)
            root_dashboard.mainloop()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos")
            self.entry_password.delete(0, tk.END)


# ════════════════════════════════════════════════════════════════════════════════
# DASHBOARD PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════════

class Dashboard:
    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.root.title("INSEVIG - Dashboard")
        self.root.geometry("1200x700")

        # Centrar ventana
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (1200 // 2)
        y = (self.root.winfo_screenheight() // 2) - (700 // 2)
        self.root.geometry(f"1200x700+{x}+{y}")

        self._crear_interfaz()

    def _crear_interfaz(self):
        # ════ BANNER SUPERIOR ════
        banner = tk.Frame(self.root, bg=COLOR_PRIMARY, height=80)
        banner.pack(fill=tk.X)
        banner.pack_propagate(False)

        # Logo y título
        frame_izq = tk.Frame(banner, bg=COLOR_PRIMARY)
        frame_izq.pack(side=tk.LEFT, padx=20, pady=10)

        tk.Label(frame_izq, text="INSEVIG", font=("Arial", 16, "bold"),
                fg=COLOR_SECONDARY, bg=COLOR_PRIMARY).pack()
        tk.Label(frame_izq, text="Sistema Integrado de Nómina",
                font=("Arial", 9), fg=COLOR_WHITE, bg=COLOR_PRIMARY).pack()

        # Información del usuario
        frame_der = tk.Frame(banner, bg=COLOR_PRIMARY)
        frame_der.pack(side=tk.RIGHT, padx=20, pady=10)

        tk.Label(frame_der, text=f"👤 {self.usuario.upper()}",
                font=("Arial", 10, "bold"), fg=COLOR_SECONDARY,
                bg=COLOR_PRIMARY).pack(anchor="e")

        hora_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
        tk.Label(frame_der, text=f"📅 {hora_actual}",
                font=("Arial", 9), fg=COLOR_WHITE,
                bg=COLOR_PRIMARY).pack(anchor="e")

        # ════ CONTENIDO PRINCIPAL ════
        content = tk.Frame(self.root, bg=COLOR_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título
        tk.Label(content, text="APLICACIONES DISPONIBLES",
                font=("Arial", 14, "bold"), fg=COLOR_PRIMARY,
                bg=COLOR_BG).pack(anchor="w", pady=(0, 20))

        # Grid de aplicaciones
        apps_frame = tk.Frame(content, bg=COLOR_BG)
        apps_frame.pack(fill=tk.BOTH, expand=True)

        aplicaciones = [
            {
                "nombre": "📋 Roles de Pago",
                "descripcion": "Visualizar y generar roles en batch",
                "comando": self._abrir_roles,
                "color": "#1a4d8f"
            },
            {
                "nombre": "👥 Gestión de Empleados",
                "descripcion": "Administrar datos de empleados",
                "comando": self._abrir_empleados,
                "color": "#0066cc"
            },
            {
                "nombre": "📊 Reportes",
                "descripcion": "Reportes y estadísticas de nómina",
                "comando": self._abrir_reportes,
                "color": "#003d99"
            },
            {
                "nombre": "⚙️ Configuración",
                "descripcion": "Parámetros del sistema",
                "comando": self._abrir_config,
                "color": "#002966"
            },
        ]

        col = 0
        row = 0
        for app in aplicaciones:
            self._crear_tarjeta_app(apps_frame, app, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        # ════ BOTÓN SALIR ════
        tk.Button(self.root, text="SALIR", command=self._salir,
                 bg="#ff6b6b", fg=COLOR_WHITE, font=("Arial", 10, "bold"),
                 relief=tk.FLAT, padx=20, pady=8, cursor="hand2").pack(side=tk.BOTTOM, pady=15)

    def _crear_tarjeta_app(self, parent, app, row, col):
        """Crear tarjeta de aplicación clickeable"""
        card = tk.Frame(parent, bg=app["color"], relief=tk.RAISED, bd=2)
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew", ipady=20, ipadx=20)

        parent.grid_rowconfigure(row, weight=1)
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(card, text=app["nombre"], font=("Arial", 12, "bold"),
                fg=COLOR_WHITE, bg=app["color"]).pack(pady=(0, 10))

        tk.Label(card, text=app["descripcion"], font=("Arial", 9),
                fg="#e0e0e0", bg=app["color"], wraplength=200, justify=tk.CENTER).pack()

        # Bind click
        card.bind("<Button-1>", lambda e: app["comando"]())
        for child in card.winfo_children():
            child.bind("<Button-1>", lambda e: app["comando"]())

    def _abrir_roles(self):
        messagebox.showinfo("Roles", "Abriendo Generador de Roles...")
        # Aquí se abrirá Roles_Principal.pyw

    def _abrir_empleados(self):
        messagebox.showinfo("Empleados", "Abriendo Gestión de Empleados...")
        # Aquí se abrirá SISTEMA_GESTION_EMPLEADOS_10.pyw

    def _abrir_reportes(self):
        messagebox.showinfo("Reportes", "Abriendo Reportes...")

    def _abrir_config(self):
        messagebox.showinfo("Configuración", "Abriendo Configuración...")

    def _salir(self):
        self.root.destroy()


# ════════════════════════════════════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    root = tk.Tk()
    login = VentanaLogin(root)
    root.mainloop()
