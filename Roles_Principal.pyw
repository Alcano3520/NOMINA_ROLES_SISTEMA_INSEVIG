import pyodbc
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import threading
from datetime import datetime
import calendar
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageTk
import tempfile
import warnings

try:
    import fitz
    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False

warnings.filterwarnings('ignore', message='.*SQLAlchemy.*')

class GeneradorRolesPagoINSEVIG:
    def __init__(self, root):
        self.root = root
        self.is_embedded = isinstance(root, (ttk.Frame, tk.Frame))  # Detectar si está embebido

        # Solo hacer setup de ventana si es Tk (aplicación principal)
        if not self.is_embedded:
            self.root.title("Generador de Roles de Pago INSEVIG")
            self.root.geometry("750x720")

            # Configurar icono de la ventana
            try:
                if hasattr(sys, '_MEIPASS'):
                    icon_path = os.path.join(sys._MEIPASS, 'icon.ico')
                else:
                    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')

                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
                    print(f"Icono cargado: {icon_path}")
                else:
                    print(f"Icono no encontrado en: {icon_path}")
            except Exception as e:
                print(f"No se pudo cargar el icono: {e}")

        # Configurar colores corporativos
        self.color_primary = "#1a4d8f"  # Azul corporativo
        self.color_secondary = "#ffd700"  # Amarillo/dorado
        self.color_bg = "#f0f0f0"  # Fondo gris claro
        self.color_white = "#ffffff"

        # Configurar estilo de la ventana (solo si es Tk)
        if not self.is_embedded:
            self.root.configure(bg=self.color_bg)
        
        self.carpeta_base = tk.StringVar()
        self.periodo_seleccionado = tk.StringVar()
        self.filtro_empleado = tk.StringVar()
        self.formato_nombre = tk.StringVar(value="cedula-nombre")
        self.dos_por_hoja = tk.BooleanVar(value=False)
        self.incluir_logo = tk.BooleanVar(value=False)
        self.ruta_logo = tk.StringVar()
        self.carpeta_salida = None

        # Buscar logo automáticamente en la carpeta del programa
        self.buscar_logo_automatico()
        
        # Parámetros de conexión a la base de datos
        self.server = '192.168.2.115'
        self.database = 'insevig'
        self.username = 'sa'
        self.password = 'puntosoft123*'
        self.sql_filter = "CODEMP='10' AND CODSUC='10'"
        
        # Crear la interfaz
        self.crear_interfaz()
    
    def crear_interfaz(self):
        # Configurar estilo ttk
        style = ttk.Style()
        style.theme_use('clam')

        # Estilos personalizados
        style.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), foreground=self.color_primary, background=self.color_bg)
        style.configure('Subtitle.TLabel', font=('Segoe UI', 10, 'italic'), foreground='#666666', background=self.color_bg)
        style.configure('Header.TLabelframe', background=self.color_bg, borderwidth=2, relief='solid')
        style.configure('Header.TLabelframe.Label', font=('Segoe UI', 11, 'bold'), foreground=self.color_primary, background=self.color_bg)
        style.configure('TButton', font=('Segoe UI', 10), padding=8)
        style.configure('Primary.TButton', font=('Segoe UI', 11, 'bold'), padding=10)
        style.map('Primary.TButton', background=[('active', self.color_primary)])

        # SI está embebido en un Frame, usar scroll directo
        if self.is_embedded:
            canvas = tk.Canvas(self.root, bg=self.color_bg, highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.configure(style='TFrame')

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            frame = scrollable_frame
        else:
            # SI es ventana Tk, usar canvas+scroll
            canvas = tk.Canvas(self.root, bg=self.color_bg, highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            scrollable_frame.configure(style='TFrame')

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            frame = scrollable_frame

        # Header con logo y título
        header_frame = tk.Frame(frame, bg=self.color_primary, height=80)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        header_frame.pack_propagate(False)

        # Título en header
        title_label = tk.Label(header_frame, text="GENERADOR DE ROLES DE PAGO",
                               font=("Segoe UI", 20, "bold"), fg=self.color_white, bg=self.color_primary)
        title_label.pack(pady=10)

        subtitle_label = tk.Label(header_frame, text="INSEVIG CIA. LTDA. • Sistema de Gestión de Nómina",
                                  font=("Segoe UI", 10), fg=self.color_secondary, bg=self.color_primary)
        subtitle_label.pack()

        # Container principal con padding
        main_container = ttk.Frame(frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Frame para selección de parámetros
        params_frame = ttk.LabelFrame(main_container, text="📋 Parámetros de Generación", padding="15", style='Header.TLabelframe')
        params_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Período
        ttk.Label(params_frame, text="Período (YYYY-MM):").grid(row=0, column=0, sticky="w", pady=5)
        self.periodo_entry = ttk.Entry(params_frame, textvariable=self.periodo_seleccionado, width=20)
        self.periodo_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(params_frame, text="Seleccionar...", command=self.seleccionar_periodo).grid(row=0, column=2, pady=5)
        
        # Filtro de empleados
        ttk.Label(params_frame, text="Filtro de texto (ej: FENIX):").grid(row=1, column=0, sticky="w", pady=5)
        self.filtro_entry = ttk.Entry(params_frame, textvariable=self.filtro_empleado, width=20)
        self.filtro_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Formato del nombre del archivo
        ttk.Label(params_frame, text="Formato del nombre del archivo:").grid(row=2, column=0, sticky="w", pady=5)
        formato_combo = ttk.Combobox(params_frame, textvariable=self.formato_nombre, width=35, state="readonly")
        formato_combo['values'] = (
            "cedula-nombre",
            "nombre-cedula",
            "cedula-nombre-cargo",
            "cedula-nombre-depto",
            "nombre-cargo-cedula",
            "depto-nombre-cedula"
        )
        formato_combo.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # Opción de 2 roles por hoja
        ttk.Label(params_frame, text="Opciones de impresión:").grid(row=3, column=0, sticky="w", pady=5)
        opciones_frame = ttk.Frame(params_frame)
        opciones_frame.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        ttk.Checkbutton(opciones_frame, text="2 roles por hoja", variable=self.dos_por_hoja).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(opciones_frame, text="Incluir logo", variable=self.incluir_logo,
                       command=self.toggle_logo).pack(side=tk.LEFT)

        # Selección de logo
        logo_frame = ttk.Frame(params_frame)
        logo_frame.grid(row=3, column=2, sticky="w", padx=5, pady=5)
        self.boton_logo = ttk.Button(logo_frame, text="Seleccionar logo...",
                                     command=self.seleccionar_logo, state=tk.DISABLED)
        self.boton_logo.pack()

        # Carpeta base para guardar
        ttk.Label(params_frame, text="Carpeta padre (donde crear subcarpeta):").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(params_frame, textvariable=self.carpeta_base, width=50).grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(params_frame, text="Examinar...", command=self.seleccionar_carpeta_base).grid(row=4, column=2, pady=5)

        # Frame para cédulas específicas
        cedulas_frame = ttk.LabelFrame(main_container, text="🔍 Filtro por Cédulas Específicas (opcional)", padding="10", style='Header.TLabelframe')
        cedulas_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(cedulas_frame, text="Pegue las cédulas (una por línea o separadas por comas):").pack(anchor=tk.W, pady=2)

        # Crear un frame con scrollbar para el Text widget
        text_scroll_frame = ttk.Frame(cedulas_frame)
        text_scroll_frame.pack(fill=tk.X, pady=2)

        cedulas_scrollbar = ttk.Scrollbar(text_scroll_frame)
        cedulas_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.cedulas_text = tk.Text(text_scroll_frame, height=4, width=70, yscrollcommand=cedulas_scrollbar.set)
        self.cedulas_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        cedulas_scrollbar.config(command=self.cedulas_text.yview)

        ttk.Label(cedulas_frame, text="Nota: Si ingresa cédulas aquí, solo se generarán roles para estas cédulas",
                  font=("Arial", 8, "italic")).pack(anchor=tk.W, pady=2)

        # Información del proceso (más compacta y visual)
        info_frame = ttk.LabelFrame(main_container, text="ℹ️ Información", padding="10", style='Header.TLabelframe')
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_text = ("✓ Datos desde BD INSEVIG\n"
                     "✓ Filtro por texto: nombre, cargo o departamento\n"
                     "✓ Filtro por cédulas específicas\n"
                     "✓ Formato de nombre personalizable\n"
                     "✓ Opción de 2 roles por hoja para ahorro de papel\n"
                     "✓ Logo automático en blanco y negro")

        info_label = tk.Label(info_frame, text=info_text, justify=tk.LEFT, font=("Segoe UI", 9),
                              bg=self.color_white, fg='#333333', relief=tk.FLAT, padx=10, pady=8)
        info_label.pack(fill=tk.X)
        
        # Frame de estado y progreso
        status_frame = ttk.LabelFrame(main_container, text="📊 Estado del Proceso", padding="10", style='Header.TLabelframe')
        status_frame.pack(fill=tk.X, pady=(0, 10))

        # Etiqueta para mostrar la carpeta de destino
        self.etiqueta_carpeta = tk.Label(status_frame, text="📁 Subcarpeta: Ninguna seleccionada",
                                          foreground=self.color_primary, font=("Segoe UI", 9),
                                          bg=self.color_white, anchor='w')
        self.etiqueta_carpeta.pack(fill=tk.X, pady=2)

        # Barra de progreso
        prog_frame = ttk.Frame(status_frame)
        prog_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prog_frame, text="Progreso:", font=("Segoe UI", 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        self.barra_progreso = ttk.Progressbar(prog_frame, length=400, mode='determinate')
        self.barra_progreso.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Etiqueta de estado
        self.etiqueta_estado = tk.Label(status_frame, text="✓ Listo para generar roles de pago",
                                        font=("Segoe UI", 9), fg='#28a745',
                                        bg=self.color_white, anchor='w')
        self.etiqueta_estado.pack(fill=tk.X, pady=2)

        # Botones con mejor diseño
        botones_frame = ttk.Frame(main_container)
        botones_frame.pack(pady=15)

        self.boton_generar = ttk.Button(botones_frame, text="🚀 Generar Roles de Pago",
                                        command=self.iniciar_generacion, style='Primary.TButton')
        self.boton_generar.pack(side=tk.LEFT, padx=5, ipadx=20)

        ttk.Button(botones_frame, text="❌ Salir", command=self.root.destroy).pack(side=tk.LEFT, padx=5, ipadx=20)

        # Bind mousewheel para scroll
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def seleccionar_periodo(self):
        """Función para seleccionar el período usando un diálogo"""
        try:
            # Crear una ventana de diálogo personalizada
            dialog = tk.Toplevel(self.root)
            dialog.title("Seleccionar Periodo")
            dialog.geometry("300x200")
            dialog.resizable(False, False)
            
            # Hacer que la ventana sea modal
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centrar el diálogo en la ventana principal
            dialog.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50))
            
            # Variables para almacenar los valores
            year_var = tk.IntVar(value=datetime.now().year)
            month_var = tk.IntVar(value=datetime.now().month)
            resultado = [None, None]
            
            # Función para confirmar y cerrar el diálogo
            def confirmar():
                resultado[0] = year_var.get()
                resultado[1] = month_var.get()
                dialog.destroy()
            
            # Función para cancelar
            def cancelar():
                dialog.destroy()
            
            # Frame para el contenido
            frame = ttk.Frame(dialog, padding="20 20 20 20")
            frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            ttk.Label(frame, text="Seleccione el periodo", font=("Arial", 12, "bold")).pack(pady=(0, 20))
            
            # Año
            year_frame = ttk.Frame(frame)
            year_frame.pack(fill=tk.X, pady=5)
            ttk.Label(year_frame, text="Año:").pack(side=tk.LEFT)
            
            años = list(range(2000, 2100))
            year_combo = ttk.Combobox(year_frame, textvariable=year_var, values=años, width=10)
            year_combo.pack(side=tk.LEFT, padx=10)
            year_combo.set(datetime.now().year)
            
            # Mes
            month_frame = ttk.Frame(frame)
            month_frame.pack(fill=tk.X, pady=5)
            ttk.Label(month_frame, text="Mes:").pack(side=tk.LEFT)
            
            meses = [(i, calendar.month_name[i]) for i in range(1, 13)]
            month_values = [f"{m[0]} - {m[1]}" for m in meses]
            month_combo = ttk.Combobox(month_frame, values=month_values, width=20)
            month_combo.current(datetime.now().month - 1)
            month_combo.pack(side=tk.LEFT, padx=10)
            
            # Función para actualizar la variable cuando cambia el combobox
            def actualizar_mes(event):
                seleccion = month_combo.current() + 1
                month_var.set(seleccion)
            
            month_combo.bind("<<ComboboxSelected>>", actualizar_mes)
            
            # Botones
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill=tk.X, pady=(20, 0))
            
            ttk.Button(button_frame, text="Cancelar", command=cancelar).pack(side=tk.RIGHT, padx=5)
            ttk.Button(button_frame, text="Aceptar", command=confirmar).pack(side=tk.RIGHT, padx=5)
            
            # Dar foco al diálogo y esperar hasta que se cierre
            dialog.focus_set()
            self.root.wait_window(dialog)
            
            # Procesar el resultado
            if resultado[0] is None or resultado[1] is None:
                return
                
            year = resultado[0]
            month = resultado[1]
            
            periodo_str = f"{year}-{month:02d}"
            self.periodo_seleccionado.set(periodo_str)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al seleccionar periodo: {str(e)}")
    
    def buscar_logo_automatico(self):
        """Buscar el logo automáticamente en la carpeta del programa"""
        # Obtener la carpeta donde está el script
        if hasattr(sys, '_MEIPASS'):
            # Si es un ejecutable empaquetado
            carpeta_programa = sys._MEIPASS
        else:
            # Si es un script .pyw
            carpeta_programa = os.path.dirname(os.path.abspath(__file__))

        # Buscar archivos de logo comunes
        nombres_logo = ['logo-insevig-v1.png', 'logo.png', 'logo-insevig.png', 'insevig.png']

        for nombre in nombres_logo:
            ruta_logo = os.path.join(carpeta_programa, nombre)
            if os.path.exists(ruta_logo):
                self.ruta_logo.set(ruta_logo)
                print(f"Logo encontrado automáticamente: {ruta_logo}")
                return

        print("No se encontró logo automáticamente en la carpeta del programa")

    def seleccionar_carpeta_base(self):
        carpeta = filedialog.askdirectory(
            title="Seleccionar carpeta PADRE donde crear la subcarpeta de roles"
        )
        if carpeta:
            self.carpeta_base.set(carpeta)

    def toggle_logo(self):
        """Habilitar/deshabilitar el botón de selección de logo"""
        if self.incluir_logo.get():
            self.boton_logo.config(state=tk.NORMAL)
        else:
            self.boton_logo.config(state=tk.DISABLED)

    def seleccionar_logo(self):
        """Seleccionar archivo de imagen para el logo (opcional, ya se busca automáticamente)"""
        archivo = filedialog.askopenfilename(
            title="Seleccionar logo INSEVIG (opcional)",
            filetypes=[
                ("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif"),
                ("Todos los archivos", "*.*")
            ]
        )
        if archivo:
            self.ruta_logo.set(archivo)
            messagebox.showinfo("Logo seleccionado", f"Logo: {os.path.basename(archivo)}")
    
    def iniciar_generacion(self):
        # Verificar que se hayan seleccionado los parámetros
        if not self.periodo_seleccionado.get():
            messagebox.showwarning("Advertencia", "Por favor seleccione un período")
            return

        if not self.carpeta_base.get():
            messagebox.showwarning("Advertencia", "Por favor seleccione una carpeta padre donde crear la subcarpeta de roles")
            return

        # Verificar logo si está activado
        if self.incluir_logo.get() and self.ruta_logo.get() and not os.path.exists(self.ruta_logo.get()):
            messagebox.showwarning("Advertencia", "El archivo de logo seleccionado no existe. Se buscará automáticamente.")
            self.buscar_logo_automatico()
        
        # Desactivar el botón mientras se procesan los PDFs
        self.boton_generar.config(state=tk.DISABLED)
        self.etiqueta_estado.config(text="Iniciando proceso...")
        
        # Ejecutar la generación de PDFs en un hilo separado
        threading.Thread(target=self.ejecutar_generacion, daemon=True).start()
    
    def ejecutar_generacion(self):
        try:
            periodo = self.periodo_seleccionado.get()
            year, month = periodo.split('-')
            
            # Crear carpeta con formato año-mes
            carpeta_destino = os.path.join(self.carpeta_base.get(), f"{year}-{month}")
            os.makedirs(carpeta_destino, exist_ok=True)
            
            self.carpeta_salida = carpeta_destino
            self.etiqueta_carpeta.config(text=f"📁 Subcarpeta: {carpeta_destino}")
            
            # Obtener datos desde la base de datos
            self.etiqueta_estado.config(text="🔄 Conectando a la base de datos...", fg='#ff8c00')
            self.barra_progreso["value"] = 10
            
            df_consolidado = self.obtener_datos_bd(periodo)

            if df_consolidado is None or df_consolidado.empty:
                messagebox.showwarning("Advertencia", f"No se encontraron datos para el período {periodo}")
                self.etiqueta_estado.config(text="No se encontraron datos")
                return

            # Aplicar filtro por cédulas específicas (tiene prioridad)
            cedulas_text = self.cedulas_text.get("1.0", tk.END).strip()
            if cedulas_text:
                # Procesar las cédulas (pueden estar separadas por líneas o comas)
                cedulas_lista = []
                cedulas_lista_debug = []  # Para debug
                for linea in cedulas_text.split('\n'):
                    # Separar por comas también
                    for cedula in linea.split(','):
                        cedula_limpia = cedula.strip()
                        if cedula_limpia:
                            # Normalizar la cédula (eliminar caracteres no numéricos)
                            cedula_normalizada = ''.join(filter(str.isdigit, cedula_limpia))
                            if cedula_normalizada:
                                cedulas_lista.append(cedula_normalizada)
                                cedulas_lista_debug.append(cedula_normalizada)

                if cedulas_lista:
                    total_antes = len(df_consolidado)
                    print(f"DEBUG: Buscando {len(cedulas_lista)} cédulas: {cedulas_lista_debug[:5]}...")

                    # Ver ejemplos de cédulas en la BD (primeras 10)
                    print(f"DEBUG: Ejemplos de cédulas en BD: {df_consolidado['CEDULA'].head(10).tolist()}")
                    print(f"DEBUG: Tipo de dato de CEDULA: {df_consolidado['CEDULA'].dtype}")

                    # Función para normalizar cédulas (solo dígitos)
                    def normalizar_cedula(x):
                        return ''.join(filter(str.isdigit, str(x)))

                    # Crear conjunto de cédulas buscadas (con todas las variantes posibles)
                    cedulas_set = set()
                    for cedula in cedulas_lista:
                        # Agregar la cédula tal cual
                        cedulas_set.add(cedula)
                        # Agregar con cero inicial si tiene 9 dígitos
                        if len(cedula) == 9:
                            cedulas_set.add('0' + cedula)
                        # Agregar sin cero inicial si tiene 10 y empieza con 0
                        if len(cedula) == 10 and cedula.startswith('0'):
                            cedulas_set.add(cedula[1:])
                        # Agregar versión con ceros a la izquierda hasta 10 dígitos
                        cedulas_set.add(cedula.zfill(10))

                    print(f"DEBUG: Conjunto de búsqueda (variantes): {list(cedulas_set)[:15]}")

                    # Filtrar DataFrame
                    mascara = df_consolidado['CEDULA'].apply(lambda x: normalizar_cedula(x) in cedulas_set)
                    df_consolidado_filtrado = df_consolidado[mascara].copy()

                    total_despues = len(df_consolidado_filtrado)
                    print(f"DEBUG: Encontrados {total_despues} empleados")

                    if total_despues > 0:
                        print(f"DEBUG: Cédulas encontradas: {df_consolidado_filtrado['CEDULA'].tolist()}")
                        df_consolidado = df_consolidado_filtrado
                    else:
                        # Búsqueda más exhaustiva: comparar por subconjuntos
                        print("DEBUG: Intentando búsqueda más flexible...")
                        cedulas_bd_normalizadas = df_consolidado['CEDULA'].apply(normalizar_cedula).tolist()
                        print(f"DEBUG: Muestra de cédulas BD normalizadas: {cedulas_bd_normalizadas[:10]}")

                    self.etiqueta_estado.config(text=f"Filtro por cédulas: {total_despues} de {total_antes} empleados encontrados")

                    if df_consolidado.empty:
                        messagebox.showwarning("Advertencia", f"No se encontraron empleados con las cédulas especificadas.\nVerifique que las cédulas existan en el período seleccionado.")
                        self.etiqueta_estado.config(text="No se encontraron empleados con las cédulas")
                        return
            else:
                # Aplicar filtro de texto solo si no hay cédulas específicas
                filtro = self.filtro_empleado.get().strip()
                if filtro:
                    total_antes = len(df_consolidado)
                    # Filtrar por nombre, cédula, cargo, depto o sección
                    df_consolidado = df_consolidado[
                        df_consolidado['APELLIDOS_NOMBRES'].str.contains(filtro, case=False, na=False) |
                        df_consolidado['CEDULA'].astype(str).str.contains(filtro, case=False, na=False) |
                        df_consolidado['CARGO'].astype(str).str.contains(filtro, case=False, na=False) |
                        df_consolidado['DEPTO'].astype(str).str.contains(filtro, case=False, na=False) |
                        df_consolidado['SECCION'].astype(str).str.contains(filtro, case=False, na=False)
                    ]
                    total_despues = len(df_consolidado)
                    self.etiqueta_estado.config(text=f"Filtro de texto: {total_despues} de {total_antes} empleados")

                    if df_consolidado.empty:
                        messagebox.showwarning("Advertencia", f"No se encontraron empleados que coincidan con el filtro '{filtro}'")
                        self.etiqueta_estado.config(text="No se encontraron empleados con el filtro")
                        return
            
            # Generar fechas para el período
            _, last_day = calendar.monthrange(int(year), int(month))
            start_date = f"01/{month}/{year}"
            end_date = f"{last_day:02d}/{month}/{year}"
            period_str = f"{year}{month}"
            
            # Generar los PDFs
            self.etiqueta_estado.config(text="📄 Generando PDFs de roles de pago...", fg='#ff8c00')
            self.barra_progreso["value"] = 30
            
            success = self.generar_roles_pdf_desde_bd(
                df_consolidado, 
                carpeta_destino, 
                start_date, 
                end_date, 
                period_str
            )
            
            if success:
                messagebox.showinfo("✅ Éxito", f"Roles de pago generados correctamente en:\n{carpeta_destino}")
                self.etiqueta_estado.config(text="✅ Roles de pago generados correctamente", fg='#28a745')
                self.barra_progreso["value"] = 100
            else:
                self.etiqueta_estado.config(text="❌ Error al generar roles de pago", fg='#dc3545')
                self.barra_progreso["value"] = 0
            
        except Exception as e:
            import traceback
            error_detalle = traceback.format_exc()
            print(f"ERROR COMPLETO:\n{error_detalle}")
            messagebox.showerror("Error", f"Error al generar roles de pago:\n{str(e)}\n\nDetalle:\n{error_detalle}")
            self.etiqueta_estado.config(text=f"Error: {str(e)}")
            self.barra_progreso["value"] = 0
        
        finally:
            # Reactivar el botón
            self.boton_generar.config(state=tk.NORMAL)
    
    def obtener_datos_bd(self, periodo):
        """
        Obtiene los datos consolidados directamente de la base de datos.

        Flujo de búsqueda de movimientos:
          1. Busca en RPINGDES (tabla de movimientos del período ABIERTO/actual)
          2. Si no encuentra datos, busca en RPHISTOR (tabla de períodos CERRADOS/asentados)
             - Cuando el sistema de nómina cierra un período, los movimientos se mueven
               de RPINGDES a RPHISTOR automáticamente.
             - Se detectan las columnas de RPHISTOR dinámicamente para compatibilidad.

        Tablas consultadas (SOLO LECTURA):
          - RPEMPLEA: datos maestros de empleados (nombre, cédula, cargo, depto, sección)
          - RPINGDES: movimientos de ingresos/descuentos del período abierto
          - RPHISTOR: movimientos históricos de períodos cerrados (fallback)
          - DBTABLAS: tabla de códigos para traducir CARGO, DEPTO, SECCION a nombres

        DEPTO y SECCION se obtienen desde RPEMPLEA (no desde los movimientos).
        """
        try:
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password};'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
                f'ApplicationIntent=ReadOnly;'
            )
            
            print("Conectando a la base de datos...")
            conn = pyodbc.connect(conn_str)
            
            # 1. Traer datos de empleados ACTIVOS - ✅ INCLUIR DEPTO y SECCION
            print("Obteniendo empleados ACTIVOS...")
            query_empleados = f"""
            SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                   [FECHA_ING], [FECHA_SAL], [CARGO], [CTA_AHO], [CTA_CTE],
                   [ESTADO], [ANTIQUINC], [DEPTO], [SECCION]
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE {self.sql_filter} AND [ESTADO] = 'ACT'
            """
            
            df_empleados = pd.read_sql(query_empleados, conn)
            print(f"Empleados ACTIVOS encontrados: {len(df_empleados)}")
            
            # Crear columna consolidada APELLIDOS + NOMBRES
            df_empleados['APELLIDOS_NOMBRES'] = (df_empleados['APELLIDOS'].fillna('').astype(str) + ' ' + 
                                               df_empleados['NOMBRES'].fillna('').astype(str)).str.strip()
            
            # Lógica CTA_AHO con respaldo CTA_CTE
            def consolidar_cuenta(row):
                cta_aho = str(row['CTA_AHO']).strip() if pd.notna(row['CTA_AHO']) else ''
                cta_cte = str(row['CTA_CTE']).strip() if pd.notna(row['CTA_CTE']) else ''
                
                if cta_aho and cta_aho != 'nan':
                    return cta_aho
                elif cta_cte and cta_cte != 'nan':
                    return cta_cte
                else:
                    return ''
            
            df_empleados['CTA_AHO_CONSOLIDADA'] = df_empleados.apply(consolidar_cuenta, axis=1)
            
            # 2. Traer movimientos del período solicitado
            # Primero busca en RPINGDES (período abierto/actual).
            # Si no encuentra, busca en RPHISTOR (períodos cerrados/asentados).
            año, mes = periodo.split('-')
            fecha_inicio = pd.Timestamp(f'{año}-{mes}-01')
            if mes == '12':
                fecha_fin = pd.Timestamp(f'{int(año)+1}-01-01') - pd.Timedelta(days=1)
            else:
                fecha_fin = pd.Timestamp(f'{año}-{int(mes)+1:02d}-01') - pd.Timedelta(days=1)

            print(f"Buscando datos para el período: {periodo}")
            print(f"Rango de fechas: {fecha_inicio.strftime('%Y-%m-%d')} al {fecha_fin.strftime('%Y-%m-%d')}")

            # --- PASO 2a: Buscar en RPINGDES (movimientos del período abierto) ---
            print("Buscando en RPINGDES (período abierto)...")
            query_movimientos = f"""
            SELECT [NUMERO], [FECHA], [EMPLEADO], [CODSUC], [CODEMP], [CODIGO], [CLASE],
                   [SECUENCIA], [HORAS], [VALOR], [FECHA_VEN],
                   [CONCEPTO], [DIAS], [ASENTADO], [ACTUALIZA], [APORTA], [MONTO],
                   [DIVIDENDO], [ROL], [TIPO_PGO], [TIPO_TRA], [OBSERV]
            FROM [insevig].[dbo].[RPINGDES]
            WHERE {self.sql_filter}
              AND [FECHA_VEN] IS NOT NULL
              AND [FECHA_VEN] >= ?
              AND [FECHA_VEN] <= ?
            """
            df_movimientos = pd.read_sql(query_movimientos, conn, params=[fecha_inicio, fecha_fin])

            df_movimientos_periodo = df_movimientos
            movimiento_minimo_por_empleado = 10
            hay_pocos_movimientos = (
                len(df_movimientos_periodo) > 0 and
                len(df_movimientos_periodo) < len(df_empleados) * movimiento_minimo_por_empleado
            )
            
            # Primero verificar si hay más datos en RPHISTOR con un COUNT
            hay_datos_rphistor = False
            try:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT COUNT(*) FROM [insevig].[dbo].[RPHISTOR] WITH (NOLOCK) "
                    f"WHERE {self.sql_filter} AND [FECHA_VEN] >= ? AND [FECHA_VEN] <= ?",
                    [fecha_inicio, fecha_fin]
                )
                count_rphistor = cursor.fetchone()[0]
                print(f"COUNT en RPHISTOR para {periodo}: {count_rphistor} filas")
                if count_rphistor > 0:
                    hay_datos_rphistor = True
            except Exception as e_count:
                print(f"Error al contar RPHISTOR: {e_count}")

            # Condición para fallback: RPINGDES vacío O hay muy pocos O hay más datos en RPHISTOR
            if df_movimientos_periodo.empty or hay_pocos_movimientos or (hay_datos_rphistor and len(df_movimientos_periodo) < count_rphistor):
                try:
                    query_columnas = """
                    SELECT COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'RPHISTOR'
                    ORDER BY ORDINAL_POSITION
                    """
                    df_columnas = pd.read_sql(query_columnas, conn)
                    columnas_histor = df_columnas['COLUMN_NAME'].tolist()

                    columnas_necesarias = ['NUMERO', 'FECHA', 'EMPLEADO', 'CODSUC', 'CODEMP', 'CODIGO', 'CLASE',
                                           'SECUENCIA', 'HORAS', 'VALOR', 'FECHA_VEN',
                                           'CONCEPTO', 'DIAS', 'ASENTADO', 'ACTUALIZA', 'APORTA', 'MONTO',
                                           'DIVIDENDO', 'ROL', 'TIPO_PGO', 'TIPO_TRA', 'OBSERV']

                    columnas_faltantes = [c for c in columnas_necesarias if c not in columnas_histor]
                    if columnas_faltantes:
                        print(f"Nota: columnas no disponibles en RPHISTOR: {columnas_faltantes}")

                    select_cols = []
                    for c in columnas_necesarias:
                        if c in columnas_histor:
                            select_cols.append(f"[{c}]")
                        else:
                            select_cols.append(f"NULL AS [{c}]")

                    query_histor = f"""
                    SELECT {', '.join(select_cols)}
                    FROM [insevig].[dbo].[RPHISTOR]
                    WHERE {self.sql_filter}
                      AND [FECHA_VEN] IS NOT NULL
                      AND [FECHA_VEN] >= ?
                      AND [FECHA_VEN] <= ?
                    """
                    df_histor = pd.read_sql(query_histor, conn, params=[fecha_inicio, fecha_fin])
                    df_movimientos_periodo = df_histor

                except Exception as e_hist:
                    print(f"Error al consultar RPHISTOR: {e_hist}")

            if df_movimientos_periodo.empty:
                print(f"No se encontraron movimientos para {periodo} en RPINGDES ni en RPHISTOR")
                conn.close()
                return None
            
            # Mapeo de conceptos
            mapeo_conceptos = {
                100: 'SUELDO',                    
                102: 'BONIFICACION',              
                104: 'FONDO_RESERVA',             
                107: 'DECIMO_TERCERA',            
                108: 'DECIMO_CUARTA',             
                110: 'MANIOBRAS',                 
                111: 'REEMBOLSOS',                
                113: 'SOBRETIEMPO_25',            
                114: 'SOBRETIEMPO_50',            
                115: 'SOBRETIEMPO_100',           
                120: 'MOVILIZACION',              
                200: 'APORT_IESS',                
                201: 'ANTICIPOS_OTROS',           
                202: 'ANTICIPO_SUELDO',           
                203: 'MULTAS',                    
                204: 'PRESTAMOS_QUIROGRAFARIOS',  
                205: 'PRESTAMOS_COMPANIA',        
                206: 'PENSION_ALIMENTICIA',       
                207: 'PRESTAMO_HIPOTECARIO',      
                217: 'ANTICIPOS_OTROS',           
                218: 'APORT_IESS_CONYUGE',        
                219: 'IMPUESTO_RENTA',            
                250: 'ANTICIPOS_SURTIDOS',        
            }
            
            # Códigos a ignorar
            codigos_ignorar = {105, 126, 199}
            
            # Procesar movimientos
            df_movimientos_periodo['CLASE'] = pd.to_numeric(df_movimientos_periodo['CLASE'], errors='coerce')
            df_movimientos_periodo = df_movimientos_periodo.dropna(subset=['CLASE'])
            df_movimientos_periodo['CLASE'] = df_movimientos_periodo['CLASE'].astype(int)
            
            # Consolidar por empleado
            resultados = []
            grupos = df_movimientos_periodo.groupby('EMPLEADO')
            print(f"Procesando {len(grupos)} empleados...")
            
            for empleado, grupo in grupos:
                fila = {
                    'EMPLEADO': empleado,
                    'APELLIDOS_NOMBRES': '',
                    'CEDULA': '',
                    'SUELDO_BASE': 0.0,
                    'FECHA_ING': '',
                    'FECHA_SAL': '',
                    'CARGO': '',
                    'CTA_AHO': '',
                    'PERIODO': periodo,
                    'DEPTO': '',      # ✅ Se obtendrá desde RPEMPLEA
                    'SECCION': '',    # ✅ Se obtendrá desde RPEMPLEA
                    'DIAS': 0
                }
                
                # Conceptos de ingresos y egresos
                conceptos_ingresos = [
                    'SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 
                    'DECIMO_TERCERA', 'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS',
                    'SOBRETIEMPO_25', 'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 
                    'MOVILIZACION'
                ]
                
                conceptos_egresos = [
                    'APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
                    'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                    'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                    'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO'
                ]
                
                # Inicializar conceptos
                for concepto in conceptos_ingresos + conceptos_egresos:
                    fila[concepto] = 0.0
                
                # Procesar cada movimiento
                for _, registro in grupo.iterrows():
                    clase_codigo = registro['CLASE']
                    tipo_movimiento = registro['CODIGO']
                    
                    if clase_codigo in codigos_ignorar:
                        continue
                    
                    valor = registro['VALOR'] if pd.notna(registro['VALOR']) else 0
                    asentado = registro['ASENTADO']
                    
                    if clase_codigo in mapeo_conceptos:
                        concepto = mapeo_conceptos[clase_codigo]
                        
                        if concepto in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                            if asentado:
                                fila[concepto] += round(valor, 2)
                        elif concepto == 'SUELDO':
                            fila[concepto] += round(valor, 2)
                            if pd.notna(registro['DIAS']):
                                fila['DIAS'] = registro['DIAS']
                        else:
                            if concepto in conceptos_ingresos + conceptos_egresos:
                                fila[concepto] += round(valor, 2)
                    else:
                        # Códigos no mapeados: egresos van a ANTICIPOS_SURTIDOS
                        if tipo_movimiento == 'EGR':
                            fila['ANTICIPOS_SURTIDOS'] += round(valor, 2)
                
                # Calcular totales
                total_ingresos = round(sum(fila[concepto] for concepto in conceptos_ingresos), 2)
                total_egresos = round(sum(fila[concepto] for concepto in conceptos_egresos), 2)
                
                fila['TOTAL_INGRESOS'] = total_ingresos
                fila['TOTAL_EGRESOS'] = total_egresos
                fila['TOTAL_RECIBIR'] = round(total_ingresos - total_egresos, 2)
                
                resultados.append(fila)
            
            # Convertir a DataFrame
            df_consolidado = pd.DataFrame(resultados)
            print(f"Empleados procesados: {len(df_consolidado)}")
            
            # ✅ HACER JOIN con empleados - INCLUIR DEPTO y SECCION
            print("Combinando con datos de empleados...")
            
            # Renombrar columnas en df_empleados ANTES del merge para evitar conflictos
            df_empleados_renamed = df_empleados.rename(columns={
                'APELLIDOS_NOMBRES': 'APELLIDOS_NOMBRES_EMP',
                'CEDULA': 'CEDULA_EMP', 
                'SUELDO': 'SUELDO_EMP',
                'FECHA_ING': 'FECHA_ING_EMP',
                'FECHA_SAL': 'FECHA_SAL_EMP',
                'CARGO': 'CARGO_EMP',
                'CTA_AHO_CONSOLIDADA': 'CTA_AHO_EMP',
                'ANTIQUINC': 'ANTIQUINC_EMP',
                'DEPTO': 'DEPTO_EMP',      # ✅ INCLUIR
                'SECCION': 'SECCION_EMP'   # ✅ INCLUIR
            })
            
            df_consolidado = df_consolidado.merge(
                df_empleados_renamed[['EMPLEADO', 'APELLIDOS_NOMBRES_EMP', 'CEDULA_EMP', 'SUELDO_EMP', 
                                    'FECHA_ING_EMP', 'FECHA_SAL_EMP', 'CARGO_EMP', 'CTA_AHO_EMP', 
                                    'ANTIQUINC_EMP', 'DEPTO_EMP', 'SECCION_EMP']], # ✅ INCLUIR
                on='EMPLEADO', 
                how='inner'
            )
            
            print(f"Empleados después del JOIN: {len(df_consolidado)}")
            
            # ✅ Actualizar campos con datos de RPEMPLEA - INCLUIR DEPTO y SECCION
            df_consolidado['APELLIDOS_NOMBRES'] = df_consolidado['APELLIDOS_NOMBRES_EMP'].fillna('')

            # ✅ CORREGIR: Convertir CEDULA a string limpio (sin decimales)
            def limpiar_cedula(x):
                if pd.isna(x):
                    return ''
                # Convertir a string y eliminar .0 si existe
                cedula_str = str(x)
                if '.' in cedula_str:
                    cedula_str = cedula_str.split('.')[0]
                return cedula_str

            df_consolidado['CEDULA'] = df_consolidado['CEDULA_EMP'].apply(limpiar_cedula)

            df_consolidado['SUELDO_BASE'] = df_consolidado['SUELDO_EMP'].fillna(0.0)
            df_consolidado['FECHA_ING'] = df_consolidado['FECHA_ING_EMP'].fillna('')
            df_consolidado['FECHA_SAL'] = df_consolidado['FECHA_SAL_EMP'].fillna('')
            df_consolidado['CARGO'] = df_consolidado['CARGO_EMP'].fillna('')
            df_consolidado['CTA_AHO'] = df_consolidado['CTA_AHO_EMP'].fillna('')
            df_consolidado['DEPTO'] = df_consolidado['DEPTO_EMP'].fillna('')      # ✅ DESDE EMPLEADOS
            df_consolidado['SECCION'] = df_consolidado['SECCION_EMP'].fillna('')  # ✅ DESDE EMPLEADOS

            # ✅ CONVERSIÓN A NOMBRES DESCRIPTIVOS (ANTES de usar los datos en la interfaz)
            print("Convirtiendo códigos a nombres descriptivos (carga batch)...")

            df_dbtablas_fnc = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'FNC' AND CODEMP = '10'", conn)
            df_dbtablas_dpt = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'DPT' AND CODEMP = '10'", conn)
            df_dbtablas_sec = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'SEC' AND CODEMP = '10'", conn)

            dic_fnc = dict(zip(df_dbtablas_fnc['CODIGO'].astype(str).str.strip(), df_dbtablas_fnc['NOMBRE']))
            dic_dpt = dict(zip(df_dbtablas_dpt['CODIGO'].astype(str).str.strip(), df_dbtablas_dpt['NOMBRE']))
            dic_sec = dict(zip(df_dbtablas_sec['CODIGO'].astype(str).str.strip(), df_dbtablas_sec['NOMBRE']))

            for idx in df_consolidado.index:
                cargo_codigo = str(df_consolidado.loc[idx, 'CARGO']).strip()
                df_consolidado.loc[idx, 'CARGO'] = dic_fnc.get(cargo_codigo, cargo_codigo)

                depto_codigo = str(df_consolidado.loc[idx, 'DEPTO']).strip()
                df_consolidado.loc[idx, 'DEPTO'] = dic_dpt.get(depto_codigo, depto_codigo)

                seccion_codigo = str(df_consolidado.loc[idx, 'SECCION']).strip()
                df_consolidado.loc[idx, 'SECCION'] = dic_sec.get(seccion_codigo, seccion_codigo)

            # Aplicar lógica ANTIQUINC para FONDO_RESERVA
            df_consolidado.loc[df_consolidado['ANTIQUINC_EMP'] == 0, 'FONDO_RESERVA'] = 0.00

            # Recalcular totales después de aplicar lógica ANTIQUINC
            for idx in df_consolidado.index:
                total_ingresos_nuevo = round(sum(df_consolidado.loc[idx, concepto] for concepto in conceptos_ingresos), 2)
                df_consolidado.loc[idx, 'TOTAL_INGRESOS'] = total_ingresos_nuevo
                total_egresos = df_consolidado.loc[idx, 'TOTAL_EGRESOS']
                df_consolidado.loc[idx, 'TOTAL_RECIBIR'] = round(total_ingresos_nuevo - total_egresos, 2)
            
            conn.close()
            
            # Limpiar columnas duplicadas
            columnas_a_eliminar = [col for col in df_consolidado.columns if col.endswith('_EMP')]
            df_consolidado = df_consolidado.drop(columns=columnas_a_eliminar)
            
            print(f"✅ Datos consolidados obtenidos: {len(df_consolidado)} empleados")
            return df_consolidado

        except Exception as e:
            print(f"❌ Error al obtener datos de BD: {e}")
            import traceback
            traceback.print_exc()
            return None

    def obtener_datos_empleado_rapido(self, periodo, cedula_o_nombre):
        """
        MÉTODO RÁPIDO: Obtiene datos de UN SOLO empleado sin cargar todo el período.
        Mucho más rápido que obtener_datos_bd para búsquedas individuales.
        """
        try:
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password};'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
                f'ApplicationIntent=ReadOnly;'
            )

            print("⚡ Búsqueda rápida de empleado...")
            conn = pyodbc.connect(conn_str)

            # 1. Buscar el empleado por cédula o nombre
            try:
                cedula_num = int(cedula_o_nombre)
                query_emp = f"""
                SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                       [CARGO], [DEPTO], [SECCION]
                FROM [insevig].[dbo].[RPEMPLEA]
                WHERE {self.sql_filter} AND [ESTADO]='ACT' AND [CEDULA] = ?
                """
                df_emp = pd.read_sql(query_emp, conn, params=[cedula_num])
            except:
                query_emp = f"""
                SELECT [EMPLEADO], [APELLIDOS], [NOMBRES], [CEDULA], [SUELDO],
                       [CARGO], [DEPTO], [SECCION]
                FROM [insevig].[dbo].[RPEMPLEA]
                WHERE {self.sql_filter} AND [ESTADO]='ACT' AND
                      ([NOMBRES] LIKE ? OR [APELLIDOS] LIKE ?)
                """
                filtro = f'%{cedula_o_nombre}%'
                df_emp = pd.read_sql(query_emp, conn, params=[filtro, filtro])

            if df_emp.empty:
                print("❌ Empleado no encontrado")
                conn.close()
                return None

            emp = df_emp.iloc[0]
            empleado_code = emp['EMPLEADO']

            print(f"✓ Empleado encontrado: {emp['APELLIDOS']} {emp['NOMBRES']}")

            # 2. Obtener movimientos SOLO de este empleado
            año, mes = periodo.split('-')
            fecha_inicio = f'{año}-{mes}-01'
            if mes == '12':
                fecha_fin = f'{int(año)+1}-01-01'
            else:
                fecha_fin = f'{año}-{int(mes)+1:02d}-01'

            # RPINGDES
            query_mov = f"""
            SELECT *
            FROM [insevig].[dbo].[RPINGDES]
            WHERE {self.sql_filter} AND [EMPLEADO] = ?
                  AND [FECHA_VEN] >= ? AND [FECHA_VEN] < ?
            """
            df_mov = pd.read_sql(query_mov, conn, params=[empleado_code, fecha_inicio, fecha_fin])

            # Si no hay en RPINGDES, buscar en RPHISTOR
            if df_mov.empty:
                print("  → Buscando en RPHISTOR (períodos cerrados)...")
                query_hist = f"""
                SELECT *
                FROM [insevig].[dbo].[RPHISTOR]
                WHERE {self.sql_filter} AND [EMPLEADO] = ?
                      AND [FECHA_VEN] >= ? AND [FECHA_VEN] < ?
                """
                df_mov = pd.read_sql(query_hist, conn, params=[empleado_code, fecha_inicio, fecha_fin])

            # 3. Consolidar movimientos
            conceptos = {}
            for idx, row in df_mov.iterrows():
                clase = int(row['CLASE']) if pd.notna(row['CLASE']) else 0
                valor = float(row['VALOR']) if pd.notna(row['VALOR']) else 0

                if clase not in [105, 126, 199]:  # ignorar ciertos códigos
                    mapeo = {
                        101: 'SUELDO', 102: 'BONIFICACION', 103: 'FONDO_RESERVA',
                        104: 'DECIMO_TERCERA', 109: 'DECIMO_CUARTA',
                        106: 'MANIOBRAS', 107: 'REEMBOLSOS',
                        108: 'SOBRETIEMPO_25', 112: 'SOBRETIEMPO_50', 113: 'SOBRETIEMPO_100',
                        114: 'MOVILIZACION',
                        201: 'APORT_IESS', 202: 'PRESTAMOS_QUIROGRAFARIOS',
                        203: 'PRESTAMOS_COMPANIA', 204: 'ANTICIPO_SUELDO',
                        205: 'ANTICIPOS_OTROS', 206: 'ANTICIPOS_SURTIDOS',
                        207: 'APORT_IESS_CONYUGE', 208: 'IMPUESTO_RENTA',
                        209: 'MULTAS', 210: 'PENSION_ALIMENTICIA', 211: 'PRESTAMO_HIPOTECARIO'
                    }

                    concepto = mapeo.get(clase, f'CONCEPTO_{clase}')
                    conceptos[concepto] = conceptos.get(concepto, 0) + valor

            # 4. Obtener DIAS para SUELDO
            dias = 30.0
            if 'SUELDO' in conceptos:
                dias_query = f"""
                SELECT TOP 1 ISNULL(DIAS, 30) as DIAS
                FROM [insevig].[dbo].[RPINGDES]
                WHERE {self.sql_filter} AND [EMPLEADO] = ? AND [CLASE] = 101
                """
                df_dias = pd.read_sql(dias_query, conn, params=[empleado_code])
                if not df_dias.empty:
                    dias = float(df_dias.iloc[0]['DIAS'])

            # 5. Calcular totales
            ingresos = sum(v for k, v in conceptos.items() if k in
                          ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA',
                           'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25',
                           'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION'])
            egresos = sum(v for k, v in conceptos.items() if k in
                         ['APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
                          'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                          'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                          'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO'])

            # 6. Obtener nombres descriptivos
            df_dbt_fnc = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO='FNC' AND CODEMP='10'", conn)
            df_dbt_dpt = pd.read_sql("SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO='DPT' AND CODEMP='10'", conn)

            dic_fnc = dict(zip(df_dbt_fnc['CODIGO'].astype(str).str.strip(), df_dbt_fnc['NOMBRE']))
            dic_dpt = dict(zip(df_dbt_dpt['CODIGO'].astype(str).str.strip(), df_dbt_dpt['NOMBRE']))

            cargo_nombre = dic_fnc.get(str(emp['CARGO']).strip(), str(emp['CARGO']))
            depto_nombre = dic_dpt.get(str(emp['DEPTO']).strip(), str(emp['DEPTO']))

            # 7. Armar resultado
            resultado = {
                'EMPLEADO': emp['EMPLEADO'],
                'APELLIDOS_NOMBRES': f"{emp['APELLIDOS']} {emp['NOMBRES']}".strip(),
                'CEDULA': emp['CEDULA'],
                'CARGO': cargo_nombre,
                'DEPTO': depto_nombre,
                'DIAS': dias,
                'TOTAL_INGRESOS': ingresos,
                'TOTAL_EGRESOS': egresos,
                'TOTAL_RECIBIR': ingresos - egresos,
            }

            # Agregar todos los conceptos
            resultado.update(conceptos)

            conn.close()

            # Retornar como pandas Series para compatibilidad
            return pd.Series(resultado)

        except Exception as e:
            print(f"❌ Error en búsqueda rápida: {e}")
            import traceback
            traceback.print_exc()
            return None

    def obtener_nombre_tabla(self, conn, tipo, codigo):
        """
        Obtiene el nombre descriptivo de un código desde la tabla DBTABLAS
        """
        if not codigo:
            return ""
        try:
            cursor = conn.cursor()
            query = "SELECT TOP 1 NOMBRE FROM dbo.DBTABLAS WHERE TIPO = ? AND CODIGO = ?"
            cursor.execute(query, [tipo, str(codigo).strip()])
            resultado = cursor.fetchone()
            return resultado[0] if resultado else str(codigo)
        except Exception as e:
            print(f"Error al obtener nombre para {tipo}-{codigo}: {e}")
            return str(codigo)
    
    def generar_roles_pdf_desde_bd(self, df, output_folder, start_date, end_date, period_str):
        """
        Genera PDFs usando los datos obtenidos directamente de la base de datos
        """
        try:
            total_empleados = len(df)

            print(f"Generando PDFs para {total_empleados} empleados...")

            for contador, (index, row) in enumerate(df.iterrows()):
                progreso = int(30 + (contador / max(total_empleados, 1)) * 70)
                self.barra_progreso["value"] = progreso
                self.etiqueta_estado.config(text=f"📄 Generando PDF {contador+1} de {total_empleados}...", fg='#ff8c00')
                try:
                    self.root.update_idletasks()
                except Exception:
                    pass

                # Generar el nombre del archivo según el formato seleccionado
                filename = self.generar_nombre_archivo(row, output_folder, period_str)

                # Crear PDF usando los datos directos de BD
                logo_path = self.ruta_logo.get() if self.incluir_logo.get() else None
                if self.dos_por_hoja.get():
                    self.crear_pdf_empleado_doble(filename, row, start_date, end_date, logo_path)
                else:
                    self.crear_pdf_empleado_bd(filename, row, start_date, end_date, logo_path)

            return True

        except Exception as e:
            print(f"Error al generar PDFs: {str(e)}")
            return False

    def generar_nombre_archivo(self, row, output_folder, period_str):
        """
        Genera el nombre del archivo según el formato seleccionado
        """
        cedula = self.format_cedula(row['CEDULA'])
        nombre_limpio = str(row['APELLIDOS_NOMBRES']).replace('/', '_').replace('\\', '_').replace(' ', '_')
        cargo_limpio = str(row['CARGO']).replace('/', '_').replace('\\', '_').replace(' ', '_')
        depto_limpio = str(row['DEPTO']).replace('/', '_').replace('\\', '_').replace(' ', '_')

        formato = self.formato_nombre.get()

        if formato == "nombre-cedula":
            nombre_archivo = f"{nombre_limpio}-{cedula}_{period_str}.pdf"
        elif formato == "cedula-nombre-cargo":
            nombre_archivo = f"{cedula}-{nombre_limpio}-{cargo_limpio}_{period_str}.pdf"
        elif formato == "cedula-nombre-depto":
            nombre_archivo = f"{cedula}-{nombre_limpio}-{depto_limpio}_{period_str}.pdf"
        elif formato == "nombre-cargo-cedula":
            nombre_archivo = f"{nombre_limpio}-{cargo_limpio}-{cedula}_{period_str}.pdf"
        elif formato == "depto-nombre-cedula":
            nombre_archivo = f"{depto_limpio}-{nombre_limpio}-{cedula}_{period_str}.pdf"
        else:  # "cedula-nombre" por defecto
            nombre_archivo = f"{cedula}-{nombre_limpio}_{period_str}.pdf"

        return f"{output_folder}/{nombre_archivo}"
    
    def crear_pdf_empleado_doble(self, filename, row, start_date, end_date, logo_path=None):
        """
        Crea el PDF con 2 roles idénticos en una misma hoja
        """
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4

        # Dibujar el primer rol en la parte superior
        self.dibujar_rol_en_posicion(c, row, start_date, end_date, width, height, y_offset=height/2, logo_path=logo_path)

        # Dibujar línea divisoria punteada en el medio (color gris oscuro)
        c.setStrokeColorRGB(0.4, 0.4, 0.4)  # Gris oscuro
        c.setDash(3, 3)  # Patrón de puntos: 3 unidades línea, 3 unidades espacio
        c.line(30, height/2, width-30, height/2)

        # Restaurar estilo de línea normal
        c.setStrokeColorRGB(0, 0, 0)  # Negro
        c.setDash()  # Sin puntos

        # Dibujar el segundo rol en la parte inferior
        self.dibujar_rol_en_posicion(c, row, start_date, end_date, width, height, y_offset=0, logo_path=logo_path)

        c.save()

    def crear_pdf_empleado_bd(self, filename, row, start_date, end_date, logo_path=None):
        """
        Crea el PDF para un empleado individual usando datos directos de BD
        """
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4

        # Dibujar el rol completo en la parte superior (y_offset = height/2)
        self.dibujar_rol_en_posicion(c, row, start_date, end_date, width, height, y_offset=height/2, logo_path=logo_path)

        c.save()

    def dibujar_rol_en_posicion(self, c, row, start_date, end_date, width, height, y_offset=0, logo_path=None):
        """
        Dibuja un rol de pago en una posición específica de la página
        y_offset: desplazamiento vertical (0 para rol simple, height/2 para rol superior en modo doble)
        logo_path: ruta al archivo de imagen del logo (opcional)
        """
        margin = 40

        # Ajustar todas las coordenadas Y según el offset
        base_y = y_offset

        c.rect(margin-10, base_y + height/2 - 350, width-2*(margin-10), 310)

        # Dibujar logo si está disponible (esquina superior DERECHA del recuadro)
        if logo_path and os.path.exists(logo_path):
            try:
                print(f"DEBUG: Intentando cargar logo desde: {logo_path}")

                # Convertir imagen a blanco y negro
                img_original = Image.open(logo_path)
                img_bw = img_original.convert('L')  # Convertir a escala de grises

                # Guardar temporalmente la imagen en escala de grises
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                img_bw.save(temp_file.name, 'PNG')
                temp_file.close()

                # Tamaño del logo (ajustable)
                logo_width = 60
                logo_height = 60

                # Posición en esquina superior DERECHA, DENTRO del recuadro
                # El recuadro está en: (margin-10, base_y + height/2 - 350) con ancho width-2*(margin-10)
                logo_x = width - (margin - 10) - logo_width - 10  # Esquina derecha con margen
                logo_y = base_y + height/2 - 350 + 310 - logo_height - 5  # Arriba dentro del recuadro

                print(f"DEBUG: Dibujando logo en posición X={logo_x}, Y={logo_y}, tamaño={logo_width}x{logo_height}")

                # Dibujar la imagen en blanco y negro
                c.drawImage(temp_file.name, logo_x, logo_y, width=logo_width, height=logo_height,
                           preserveAspectRatio=True, mask='auto')

                # Eliminar archivo temporal
                os.unlink(temp_file.name)

                print(f"DEBUG: Logo dibujado exitosamente")
            except Exception as e:
                print(f"ERROR al cargar logo: {e}")
                import traceback
                traceback.print_exc()
        else:
            if logo_path:
                print(f"DEBUG: Archivo de logo no existe: {logo_path}")
            else:
                print(f"DEBUG: No se proporcionó ruta de logo")

        c.setFont("Times-Bold", 14)
        title_y = base_y + height/2 - 60
        c.drawCentredString(width/2, title_y, "SOBRES DE PAGOS")
        c.drawCentredString(width/2, title_y-15, "INSEVIG CIA.LTDA.")
        
        c.setFont("Times-Roman", 11)
        y = base_y + height/2 - 95
        cedula = self.format_cedula(row['CEDULA'])
        c.drawString(margin, y, f"Cedula empleado: {cedula}")
        c.drawString(margin, y-12, f"Nombre del Empleado: {str(row['APELLIDOS_NOMBRES'])}     ({str(row['EMPLEADO'])})")
        c.drawString(margin, y-24, f"Periodo de pago: Desde {start_date} Hasta {end_date}")
        # ✅ AHORA DEPTO muestra el nombre descriptivo correcto desde RPEMPLEA
        c.drawString(margin, y-36, f"Departamento: {str(row['DEPTO'])}     Cargo: {str(row['CARGO'])}")

        table_top = y-50
        table_bottom = table_top-200
        table_width = width - 2*margin

        c.rect(margin, table_bottom, table_width, table_top - table_bottom)
        
        col_concept = margin + 5
        col_income = margin + 205
        col_deduct = margin + 310
        col_net = margin + 415
        
        c.setFont("Times-Italic", 10)
        headers_y = table_top - 12
        
        c.drawString(col_concept, headers_y, "Concepto")
        c.drawString(col_income, headers_y, "Ingresos")
        c.drawString(col_deduct, headers_y, "Descuentos")
        c.drawString(col_net, headers_y, "Neto a Recibir")
        
        c.line(margin + 200, table_bottom, margin + 200, table_top)
        c.line(margin + 305, table_bottom, margin + 305, table_top)
        c.line(margin + 410, table_bottom, margin + 410, table_top)
        
        c.line(margin, headers_y - 5, margin + table_width, headers_y - 5)
        
        c.setFont("Times-Roman", 12)
        y = headers_y - 15
        line_height = 12
        
        total_income = 0
        total_deductions = 0
        
        # SUELDO - usar columna directa de BD
        sueldo = self.safe_get_bd(row, 'SUELDO')
        dias = self.safe_get_bd(row, 'DIAS')
        if sueldo > 0:
            c.drawString(col_concept, y, f"SUELDO                     {int(dias)} Dias")
            c.drawRightString(col_deduct - 10, y, f"{sueldo:.2f}")
            total_income += sueldo
            y -= line_height
        
        # HORAS EXTRAS - usar columnas directas de BD
        overtime = self.calculate_overtime_bd(row)
        if overtime > 0:
            c.drawString(col_concept, y, "HORAS EXTRAS(noct-suplem-extraor)")
            c.drawRightString(col_deduct - 10, y, f"{overtime:.2f}")
            total_income += overtime
            y -= line_height
        
        # FONDOS DE RESERVA - usar columna directa de BD
        fondo_reserva = self.safe_get_bd(row, 'FONDO_RESERVA')
        if fondo_reserva == 0:
            base_calculo = self.calculate_reserve_fund_base_bd(row)
            fondo_reserva = base_calculo * 0.0833
            
            c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33%")
            c.drawRightString(col_deduct - 10, y, f"{fondo_reserva:.2f}")
            total_income += fondo_reserva
            y -= line_height
            
            total_deductions += fondo_reserva
        elif fondo_reserva > 0:
            c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33%")
            c.drawRightString(col_deduct - 10, y, f"{fondo_reserva:.2f}")
            total_income += fondo_reserva
            y -= line_height
        
        # OTROS INGRESOS - usar columnas directas de BD
        otros_ingresos = [
            ('REEMBOLSOS', "REEMBOLSOS"),
            ('DECIMO_TERCERA', "DECIMO TERCER SUELDO"),
            ('DECIMO_CUARTA', "DECIMO CUARTO SUELDO"),
            ('BONIFICACION', "BONIFICACION"),
            ('MANIOBRAS', "MANIOBRAS"),
            ('MOVILIZACION', "MOVILIZACION")
        ]
        
        for columna_bd, label in otros_ingresos:
            value = self.safe_get_bd(row, columna_bd)
            if value > 0:
                c.drawString(col_concept, y, label)
                c.drawRightString(col_deduct - 10, y, f"{value:.2f}")
                total_income += value
                y -= line_height
        
        # DESCUENTOS
        if fondo_reserva > 0 and self.safe_get_bd(row, 'FONDO_RESERVA') == 0:
            c.drawString(col_concept, y, "FONDOS DE RESERVA 8.33% EN IESS")
            c.drawRightString(col_net - 10, y, f"{fondo_reserva:.2f}")
            y -= line_height
        
        # DESCUENTOS - usar columnas directas de BD
        descuentos_bd = [
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
        
        for columna_bd, label in descuentos_bd:
            value = self.safe_get_bd(row, columna_bd)
            if value > 0:
                c.drawString(col_concept, y, label)
                c.drawRightString(col_net - 10, y, f"{value:.2f}")
                total_deductions += value
                y -= line_height
        
        # TOTALES
        total_y = table_bottom + 25
        c.line(margin, total_y, margin + table_width, total_y)
        
        net_pay = total_income - total_deductions
        
        c.setFont("Times-Roman", 14)
        c.drawString(col_concept, total_y - 15, "Total a Pagar ===========>")
        c.drawRightString(col_deduct - 10, total_y - 15, f"{total_income:.2f}")
        c.drawRightString(col_net - 10, total_y - 15, f"{total_deductions:.2f}")
        c.drawRightString(margin + table_width - 10, total_y - 15, f"{net_pay:.2f}")
        
        # FIRMA (ajustada para mayor espacio)
        firma_y = base_y + height/2 - 410
        c.drawCentredString(width/2, firma_y, "F I R M A")
        c.line(width/2 - 80, firma_y+10, width/2 + 80, firma_y+10)
    
    # Funciones auxiliares para trabajar con datos de BD
    def format_cedula(self, cedula):
        try:
            cedula_str = str(cedula)
            cedula_str = cedula_str.split('.')[0]
            return cedula_str.zfill(10)
        except:
            return str(cedula)

    def format_cedula_busqueda(self, cedula):
        """Formatea una cédula para búsqueda (solo dígitos, sin espacios ni caracteres especiales)"""
        try:
            # Eliminar todo excepto dígitos
            cedula_str = ''.join(filter(str.isdigit, str(cedula)))
            return cedula_str if cedula_str else '0'
        except:
            return str(cedula)
    
    def safe_get_bd(self, row, column_name, default=0):
        """Función para obtener valores de forma segura desde DataFrame de BD"""
        try:
            value = row.get(column_name, default)
            if pd.isna(value):
                return 0.0
            if isinstance(value, str):
                value = value.replace(',', '').replace('$', '').strip()
            return float(value) if value != '' else 0.0
        except:
            return 0.0
    
    def calculate_overtime_bd(self, row):
        """Calcula horas extras usando columnas de BD"""
        return (self.safe_get_bd(row, 'SOBRETIEMPO_25') +
                self.safe_get_bd(row, 'SOBRETIEMPO_50') +
                self.safe_get_bd(row, 'SOBRETIEMPO_100'))
    
    def calculate_reserve_fund_base_bd(self, row):
        """Calcula la base para el fondo de reserva usando columnas de BD"""
        return (self.safe_get_bd(row, 'SUELDO') +
                self.safe_get_bd(row, 'BONIFICACION') +
                self.safe_get_bd(row, 'MANIOBRAS') +
                self.safe_get_bd(row, 'SOBRETIEMPO_25') +
                self.safe_get_bd(row, 'SOBRETIEMPO_50') +
                self.safe_get_bd(row, 'SOBRETIEMPO_100'))


# ════════════════════════════════════════════════════════════════════════════════
# VISUALIZADOR INTEGRADO
# ════════════════════════════════════════════════════════════════════════════════

from obtener_datos import ObtenerDatos

class VisualizadorRoles:
    def __init__(self, parent, fuente=None):
        self.parent = parent
        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"
        self.fuente = fuente

        self.obtener_datos = ObtenerDatos()
        self.vis_datos_actual = None

        self._crear_interfaz()
    
    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self.parent, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="VISUALIZADOR DE ROLES",
                font=("Arial", 11, "bold"), fg="white", bg=self.color_primary).pack(pady=5)

        # Controles
        ctrl = ttk.Frame(self.parent)
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
        scroll_frame = ttk.Frame(self.parent)
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
                messagebox.showinfo("Sin resultados", f"No encontrado: {filtro}")
                return
            self._vis_mostrar_lista(resultados, periodo)
        except Exception as e:
            messagebox.showerror("Error", str(e))

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
        win = tk.Toplevel(self.parent)
        win.title("Seleccionar Empleado")
        win.geometry("900x500")

        header = tk.Frame(win, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="RESULTADOS",font=("Arial", 12, "bold"), fg="white", bg=self.color_primary).pack(pady=5)

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
            fuente_actual = self.fuente.get() if self.fuente else 'SQL Server'

            # Elegir método según la fuente
            if fuente_actual == 'Supabase':
                emp = self.obtener_datos.obtener_datos_empleado_supabase(periodo, str(emp_code))
            else:
                emp = self.obtener_datos.obtener_datos_empleado_rapido(periodo, str(emp_code))

            if emp is None:
                messagebox.showerror("Error", "No hay datos")
                return
            self.vis_datos_actual = emp
            self._vis_mostrar(periodo)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _vis_mostrar(self, periodo):
        if self.vis_datos_actual is None:
            return
        try:
            emp = self.vis_datos_actual
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                ruta_pdf = tmp.name

            año, mes = periodo.split('-')
            fecha_inicio = f"{año}-{mes}-01"
            _, ultimo_dia = calendar.monthrange(int(año), int(mes))
            fecha_fin = f"{año}-{mes}-{ultimo_dia}"

            gen_temp = GeneradorRolesPagoINSEVIG(tk.Tk())
            gen_temp.root.withdraw()
            gen_temp.crear_pdf_empleado_bd(ruta_pdf, emp, fecha_inicio, fecha_fin)
            gen_temp.root.destroy()

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


# ════════════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL CON PESTAÑAS
# ════════════════════════════════════════════════════════════════════════════════

class RolesPrincipal:
    def __init__(self, root, fuente='SQL Server'):
        self.root = root
        self.root.title("Roles de Pago - INSEVIG")
        self.root.geometry("1000x800")
        self.color_primary = "#1a4d8f"
        self.color_secondary = "#ffd700"
        self.color_bg = "#f0f0f0"
        self.fuente = tk.StringVar(value=fuente)
        self.obtener_datos = ObtenerDatos()

        # Header con selector
        header = tk.Frame(self.root, bg=self.color_primary, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="Seleccionar Fuente:", font=("Arial", 10, "bold"),
                fg="white", bg=self.color_primary).pack(side=tk.LEFT, padx=15, pady=10)

        ttk.Combobox(header, textvariable=self.fuente, values=['SQL Server', 'Supabase'],
                    state='readonly', width=15).pack(side=tk.LEFT, padx=5, pady=10)

        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Pestaña 1: Visualizador
        tab1 = ttk.Frame(self.notebook)
        self.notebook.add(tab1, text="📋 Visualizador")
        self.visualizador = VisualizadorRoles(tab1, fuente=self.fuente)

        # Pestaña 2: Generador (acceso directo con botón)
        tab2 = ttk.Frame(self.notebook)
        self.notebook.add(tab2, text="📊 Generador")

        gen_frame = tk.Frame(tab2, bg=self.color_bg)
        gen_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(gen_frame, text="GENERADOR DE ROLES", font=("Arial", 14, "bold"),
                fg=self.color_primary, bg=self.color_bg).pack(pady=20)

        tk.Label(gen_frame, text="Haz clic en el botón para abrir el generador de roles en batch",
                font=("Arial", 10), fg="#666666", bg=self.color_bg).pack(pady=10)

        tk.Button(gen_frame, text="🚀 ABRIR GENERADOR", command=self._abrir_generador,
                 bg=self.color_primary, fg="white", font=("Arial", 12, "bold"),
                 padx=30, pady=15, relief=tk.RAISED, bd=2, cursor="hand2",
                 activebackground="#0d4d7a").pack(pady=30)

        self.generador_window = None

    def _abrir_generador(self):
        """Abrir generador como ventana separada"""
        if self.generador_window is not None and self.generador_window.winfo_exists():
            self.generador_window.lift()
            return
        self.generador_window = tk.Toplevel(self.root)
        GeneradorRolesPagoINSEVIG(self.generador_window)


if __name__ == '__main__':
    root = tk.Tk()
    app = RolesPrincipal(root)
    root.mainloop()
