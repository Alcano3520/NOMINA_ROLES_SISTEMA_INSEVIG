#!/usr/bin/env python3
"""
SISTEMA INTEGRADO INSEVIG - VERSIÓN MODERNA
Diseño minimalista con gradientes y bordes redondeados
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from PIL import Image, ImageDraw, ImageTk
import io

# ════════════════════════════════════════════════════════════════════════════════
# COLORES
# ════════════════════════════════════════════════════════════════════════════════

COLOR_PRIMARY = "#1a4d8f"
COLOR_SECONDARY = "#ffd700"
COLOR_BG = "#f5f7fa"
COLOR_WHITE = "#ffffff"
COLOR_DARK = "#0d1b2a"
COLOR_ACCENT = "#00a8e8"


# ════════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ════════════════════════════════════════════════════════════════════════════════

def crear_imagen_redondeada(ancho, alto, color, radio=20):
    """Crear imagen con bordes redondeados"""
    img = Image.new('RGBA', (ancho, alto), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(0, 0), (ancho-1, alto-1)], radius=radio, fill=color)
    return img


# ════════════════════════════════════════════════════════════════════════════════
# LOGIN - VERSIÓN MODERNA
# ════════════════════════════════════════════════════════════════════════════════

class LoginModerno:
    def __init__(self, root):
        self.root = root
        self.root.title("INSEVIG - Login")
        self.root.geometry("600x700")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)

        # Centrar
        x = (self.root.winfo_screenwidth() // 2) - 300
        y = (self.root.winfo_screenheight() // 2) - 350
        self.root.geometry(f"600x700+{x}+{y}")

        self._crear_interfaz()

    def _crear_interfaz(self):
        # Frame principal con degradado (simulado)
        main_frame = tk.Frame(self.root, bg=COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Logo circular
        logo_frame = tk.Frame(main_frame, bg=COLOR_PRIMARY, relief=tk.FLAT)
        logo_frame.pack(pady=(0, 30))

        tk.Label(logo_frame, text="✓", font=("Arial", 60, "bold"),
                fg=COLOR_SECONDARY, bg=COLOR_PRIMARY, padx=20, pady=20).pack()

        # Títulos
        tk.Label(main_frame, text="BIENVENIDO", font=("Arial", 24, "bold"),
                fg=COLOR_DARK, bg=COLOR_BG).pack()

        tk.Label(main_frame, text="Sistema de Gestión de Nómina INSEVIG",
                font=("Arial", 10), fg="#666666", bg=COLOR_BG).pack(pady=(0, 40))

        # Campos de entrada
        tk.Label(main_frame, text="Usuario", font=("Arial", 11, "bold"),
                fg=COLOR_DARK, bg=COLOR_BG).pack(anchor="w")

        self.entry_usuario = tk.Entry(main_frame, font=("Arial", 11),
                                      bg=COLOR_WHITE, bd=0, relief=tk.FLAT)
        self.entry_usuario.pack(fill=tk.X, ipady=12, pady=(5, 20))

        # Línea separadora
        tk.Frame(main_frame, bg="#e0e0e0", height=1).pack(fill=tk.X, pady=(0, 15))

        tk.Label(main_frame, text="Contraseña", font=("Arial", 11, "bold"),
                fg=COLOR_DARK, bg=COLOR_BG).pack(anchor="w")

        self.entry_password = tk.Entry(main_frame, font=("Arial", 11),
                                       bg=COLOR_WHITE, bd=0, relief=tk.FLAT, show="•")
        self.entry_password.pack(fill=tk.X, ipady=12, pady=(5, 30))

        # Línea separadora
        tk.Frame(main_frame, bg="#e0e0e0", height=1).pack(fill=tk.X, pady=(0, 30))

        # Botón login
        btn_login = tk.Button(main_frame, text="INGRESAR", command=self._login,
                             bg=COLOR_ACCENT, fg=COLOR_WHITE, font=("Arial", 12, "bold"),
                             relief=tk.FLAT, bd=0, padx=40, pady=14, cursor="hand2",
                             activebackground="#0088bb")
        btn_login.pack(fill=tk.X, pady=(0, 20))

        # Credenciales demo
        tk.Label(main_frame, text="Demo: admin / admin",
                font=("Arial", 8, "italic"), fg="#999999", bg=COLOR_BG).pack()

        self.entry_usuario.focus()
        self.entry_password.bind("<Return>", lambda e: self._login())

    def _login(self):
        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get().strip()

        if usuario == "admin" and password == "admin":
            self.root.destroy()
            root_dash = tk.Tk()
            DashboardModerno(root_dash, usuario)
            root_dash.mainloop()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos")
            self.entry_password.delete(0, tk.END)


# ════════════════════════════════════════════════════════════════════════════════
# DASHBOARD - VERSIÓN MODERNA
# ════════════════════════════════════════════════════════════════════════════════

class DashboardModerno:
    def __init__(self, root, usuario):
        self.root = root
        self.usuario = usuario
        self.root.title("INSEVIG - Dashboard")
        self.root.geometry("1300x750")
        self.root.configure(bg=COLOR_BG)

        x = (self.root.winfo_screenwidth() // 2) - 650
        y = (self.root.winfo_screenheight() // 2) - 375
        self.root.geometry(f"1300x750+{x}+{y}")

        self._crear_interfaz()

    def _crear_interfaz(self):
        # ════ HEADER ════
        header = tk.Frame(self.root, bg=COLOR_WHITE, height=90)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Logo
        logo_frame = tk.Frame(header, bg=COLOR_PRIMARY)
        logo_frame.pack(side=tk.LEFT, padx=20, pady=15)

        tk.Label(logo_frame, text="INSEVIG", font=("Arial", 16, "bold"),
                fg=COLOR_SECONDARY, bg=COLOR_PRIMARY, padx=15, pady=8).pack()

        # Info usuario
        info_frame = tk.Frame(header, bg=COLOR_WHITE)
        info_frame.pack(side=tk.RIGHT, padx=20, pady=15)

        tk.Label(info_frame, text=f"👤 {self.usuario.upper()}",
                font=("Arial", 11, "bold"), fg=COLOR_DARK,
                bg=COLOR_WHITE).pack(anchor="e")

        hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        tk.Label(info_frame, text=f"📅 {hora}",
                font=("Arial", 9), fg="#666666",
                bg=COLOR_WHITE).pack(anchor="e")

        # Separador
        tk.Frame(self.root, bg="#e0e0e0", height=1).pack(fill=tk.X)

        # ════ CONTENIDO ════
        content = tk.Frame(self.root, bg=COLOR_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Título
        tk.Label(content, text="Aplicaciones Disponibles",
                font=("Arial", 18, "bold"), fg=COLOR_DARK,
                bg=COLOR_BG).pack(anchor="w", pady=(0, 30))

        # Cards
        apps_frame = tk.Frame(content, bg=COLOR_BG)
        apps_frame.pack(fill=tk.BOTH, expand=True)

        apps = [
            ("📋 Roles de Pago", "Visualizar y generar", COLOR_PRIMARY),
            ("👥 Empleados", "Gestión de personal", COLOR_ACCENT),
            ("📊 Reportes", "Estadísticas y análisis", "#00a86b"),
            ("⚙️ Configuración", "Parámetros del sistema", "#cc5500"),
        ]

        col = 0
        for nombre, desc, color in apps:
            self._crear_card(apps_frame, nombre, desc, color, col)
            col += 1
            if col >= 2:
                col = 0

        # Botón salir
        tk.Button(self.root, text="SALIR", command=self.root.quit,
                 bg="#ff6b6b", fg=COLOR_WHITE, font=("Arial", 10, "bold"),
                 relief=tk.FLAT, padx=30, pady=10, cursor="hand2",
                 activebackground="#ff5252").pack(side=tk.BOTTOM, pady=15)

    def _crear_card(self, parent, titulo, desc, color, col):
        """Crear tarjeta de aplicación"""
        card = tk.Frame(parent, bg=COLOR_WHITE, relief=tk.FLAT, bd=0)
        card.grid(row=0, column=col, padx=10, pady=10, sticky="nsew", ipadx=20, ipady=20)
        parent.grid_columnconfigure(col, weight=1)

        # Línea de color
        tk.Frame(card, bg=color, height=4).pack(fill=tk.X, pady=(0, 15))

        tk.Label(card, text=titulo, font=("Arial", 13, "bold"),
                fg=COLOR_DARK, bg=COLOR_WHITE).pack(anchor="w")

        tk.Label(card, text=desc, font=("Arial", 9),
                fg="#666666", bg=COLOR_WHITE, wraplength=180).pack(anchor="w", pady=(5, 0))

        card.bind("<Enter>", lambda e: card.config(relief=tk.RAISED, bd=1))
        card.bind("<Leave>", lambda e: card.config(relief=tk.FLAT, bd=0))
        card.bind("<Button-1>", lambda e: messagebox.showinfo("App", titulo))

        for child in card.winfo_children():
            child.bind("<Enter>", lambda e: card.config(relief=tk.RAISED, bd=1))
            child.bind("<Leave>", lambda e: card.config(relief=tk.FLAT, bd=0))
            child.bind("<Button-1>", lambda e: messagebox.showinfo("App", titulo))


if __name__ == '__main__':
    root = tk.Tk()
    LoginModerno(root)
    root.mainloop()
