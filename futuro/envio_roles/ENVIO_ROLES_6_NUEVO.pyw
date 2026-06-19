import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import threading
import time
from datetime import datetime
import os
import glob
import win32com.client
import sqlite3

class AplicacionEnvioRoles:
    def __init__(self, root):
        self.root = root
        self.root.title("Envío Automático de Roles")
        self.root.geometry("800x700")
        self.root.configure(bg="#E8F0FE")
        
        # Variables
        self.archivo_excel = tk.StringVar()
        self.carpeta_pdfs = tk.StringVar()
        self.intervalo = tk.StringVar(value="5")
        self.db_path = tk.StringVar(value="\\\\server\\Respaldo 2017\\Base\\FICHA_TRABAJADORES.db")
        self.excluded_keywords = ["Q.A.P.", "MEDICO", "TRONCAL", "PROTEC VIP ESCOLTA MINAS"]
        self.enviando = False
        self.cuentas_outlook = []
        self.columnas_requeridas = {
            'correo': ['correo', 'email', 'mail', 'e-mail', 'correo electrónico'],
            'nombre': ['nombre', 'nombres', 'name'],
            'cedula': ['cedula', 'cédula', 'ci', 'documento'],
            'codigo': ['codigo', 'código', 'cod', 'id']
        }
        self.df = None
        self.columnas_encontradas = {}
        
        # Meses y años para selección
        self.meses = [f"{i:02d}" for i in range(1, 13)]  
        self.años = [str(year) for year in range(2000, datetime.now().year + 1)]  
        
        # Template HTML
        self.template_html = '''
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Aviso de Rol Digital</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}
                h2 {{
                    text-align: center;
                    color: #333;
                    font-size: 1.2em;
                }}
                p {{
                    margin-bottom: 10px;
                    color: #666;
                }}
                .no-responder {{
                    color: red;
                    font-weight: bold;
                }}
                .footer {{
                    margin-top: 20px;
                    text-align: center;
                    color: #888;
                }}
                img {{
                    display: block;
                    margin: 20px auto;
                    max-width: 80%;
                    height: auto;
                }}
            </style>
        </head>
        <body>
            <h2>Apreciado colaborador <strong>{{ StrNombres }}</strong>,</h2>
            <p>CC NO. <strong>{{ StrCedula }}</strong><br>
               COD: <strong>{{ StrEmpleado }}</strong></p>
            <p>Se adjunta su <strong>ROL DIGITAL</strong>.</p>
            <p><strong>INSEVIG CIA.LTDA</strong></p>
            <p class="no-responder">Por favor <strong>NO responder</strong>.</p>
            <div class="footer">
                <p>&copy; {{ año }} INSEVIG CIA.LTDA. Todos los derechos reservados.</p>
            </div>
            <img src="https://insevig.ec/wp-content/uploads/2018/12/insevig-logo.png" alt="Logo de Insevig">
        </body>
        </html>
        '''
        
        # Obtener cuentas de Outlook
        self.obtener_cuentas_outlook()
        
        self.crear_interfaz()
    
    def validar_excel(self):
        try:
            self.df = pd.read_excel(self.archivo_excel.get())
            columnas_excel = [col.lower().strip() for col in self.df.columns]
            
            self.columnas_encontradas = {}
            
            for tipo, posibles_nombres in self.columnas_requeridas.items():
                encontrada = False
                for nombre in posibles_nombres:
                    if nombre in columnas_excel:
                        self.columnas_encontradas[tipo] = nombre
                        encontrada = True
                        break
                if not encontrada:
                    messagebox.showerror("Error", f"No se encontró la columna {tipo}. Posibles nombres: {', '.join(posibles_nombres)}")
                    return False
            
            mensaje = "Columnas encontradas:\n\n"
            for tipo, nombre in self.columnas_encontradas.items():
                mensaje += f"{tipo}: {nombre}\n"
            messagebox.showinfo("Validación Exitosa", mensaje)
            
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error al leer el archivo Excel: {str(e)}")
            return False
    
    def validar_carpeta_pdfs(self):
        if not os.path.isdir(self.carpeta_pdfs.get()):
            messagebox.showerror("Error", "La carpeta seleccionada no existe.")
            return False
        
        archivos_pdf = glob.glob(os.path.join(self.carpeta_pdfs.get(), "*.pdf"))
        if not archivos_pdf:
            messagebox.showerror("Error", "No se encontraron archivos PDF en la carpeta seleccionada.")
            return False
        
        messagebox.showinfo("Validación Exitosa", f"Se encontraron {len(archivos_pdf)} archivos PDF en la carpeta.")
        return True
    
    def crear_interfaz(self):
        # Frame principal con scrollbar
        main_container = tk.Frame(self.root, bg="#E8F0FE")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(main_container, bg="#E8F0FE")
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        
        main_frame = tk.Frame(canvas, bg="#E8F0FE")
        
        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Título
        titulo = tk.Label(main_frame, text="Sistema de Envío de Roles", 
                         font=("Arial", 16, "bold"), bg="#E8F0FE", fg="#1A73E8")
        titulo.pack(pady=10)
        
        # Notebook para tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab para extracción de datos
        tab_extraccion = tk.Frame(notebook, bg="#E8F0FE")
        notebook.add(tab_extraccion, text="Extracción de Datos")
        
        # Tab para envío de roles
        tab_envio = tk.Frame(notebook, bg="#E8F0FE")
        notebook.add(tab_envio, text="Envío de Roles")
        
        # Componentes para extracción de datos
        self.crear_interfaz_extraccion(tab_extraccion)
        
        # Componentes para envío de roles
        self.crear_interfaz_envio(tab_envio)
        
        # Firma
        self.firma = tk.Label(main_frame, text="SysPereira", bg="#E8F0FE", fg="#1A73E8", font=("Arial", 10, "italic"))
        self.firma.pack(side=tk.BOTTOM, pady=(5, 10))

    def crear_interfaz_extraccion(self, parent):
        # Database path section
        db_frame = tk.LabelFrame(parent, text="Base de Datos", bg="#E8F0FE", fg="#1A73E8", padx=10, pady=10)
        db_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(db_frame, text="Ruta:", bg="#E8F0FE", fg="#1A73E8").grid(column=0, row=0, sticky=tk.W)
        tk.Entry(db_frame, textvariable=self.db_path, width=50).grid(column=1, row=0, sticky=(tk.W, tk.E))
        tk.Button(db_frame, text="Examinar", command=self.browse_db, bg="#1A73E8", fg="white").grid(column=2, row=0, padx=5)
        
        # Keyword exclusion section
        keyword_frame = tk.LabelFrame(parent, text="Excluir Departamentos por Palabras Clave", bg="#E8F0FE", fg="#1A73E8", padx=10, pady=10)
        keyword_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(keyword_frame, text="Agregar palabra clave:", bg="#E8F0FE", fg="#1A73E8").grid(column=0, row=0, sticky=tk.W)
        self.keyword_var = tk.StringVar()
        tk.Entry(keyword_frame, textvariable=self.keyword_var, width=20).grid(column=1, row=0, sticky=(tk.W, tk.E))
        tk.Button(keyword_frame, text="Agregar", command=self.add_keyword, bg="#1A73E8", fg="white").grid(column=2, row=0, padx=5)
        
        # Excluded keywords list
        tk.Label(keyword_frame, text="Palabras clave excluidas:", bg="#E8F0FE", fg="#1A73E8").grid(column=0, row=1, sticky=tk.W, pady=(10, 0))
        
        list_frame = tk.Frame(keyword_frame, bg="#E8F0FE")
        list_frame.grid(column=0, row=2, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.keyword_listbox = tk.Listbox(list_frame, height=6, width=40, yscrollcommand=scrollbar.set)
        self.keyword_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.keyword_listbox.yview)
        
        # Add default keywords to the listbox
        for keyword in self.excluded_keywords:
            self.keyword_listbox.insert(tk.END, keyword)
        
        tk.Button(keyword_frame, text="Eliminar Seleccionado", command=self.remove_keyword, bg="#1A73E8", fg="white").grid(column=0, row=3, pady=5, sticky=tk.W)
        
        # Sorting options section
        sort_frame = tk.LabelFrame(parent, text="Ordenamiento", bg="#E8F0FE", fg="#1A73E8", padx=10, pady=10)
        sort_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.sort_var = tk.StringVar(value="nombre")
        tk.Radiobutton(sort_frame, text="Ordenar por Nombre", variable=self.sort_var, value="nombre", bg="#E8F0FE", fg="#1A73E8").grid(column=0, row=0, sticky=tk.W, padx=5)
        tk.Radiobutton(sort_frame, text="Ordenar por Código", variable=self.sort_var, value="codigo", bg="#E8F0FE", fg="#1A73E8").grid(column=1, row=0, sticky=tk.W, padx=5)
        tk.Radiobutton(sort_frame, text="Ordenar por Cédula", variable=self.sort_var, value="cedula", bg="#E8F0FE", fg="#1A73E8").grid(column=2, row=0, sticky=tk.W, padx=5)
        
        # Export section
        export_frame = tk.Frame(parent, bg="#E8F0FE")
        export_frame.pack(fill=tk.X, padx=5, pady=10)
        
        tk.Button(export_frame, text="Exportar a Excel", command=self.export_to_excel, bg="#1A73E8", fg="white").pack(side=tk.RIGHT)
        tk.Button(export_frame, text="Verificar Datos", command=self.verify_data, bg="#1A73E8", fg="white").pack(side=tk.RIGHT, padx=5)

    def crear_interfaz_envio(self, parent):
        # Selección de archivo Excel
        frame_excel = tk.Frame(parent, bg="#E8F0FE")
        frame_excel.pack(fill=tk.X, pady=5)
        tk.Label(frame_excel, text="Archivo Excel:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        tk.Entry(frame_excel, textvariable=self.archivo_excel, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_excel, text="Buscar", command=self.seleccionar_excel, bg="#1A73E8", fg="white").pack(side=tk.LEFT)
        tk.Button(frame_excel, text="Validar", command=self.validar_excel, bg="#1A73E8", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Selección de carpeta de PDFs
        frame_pdfs = tk.Frame(parent, bg="#E8F0FE")
        frame_pdfs.pack(fill=tk.X, pady=5)
        tk.Label(frame_pdfs, text="Carpeta PDFs:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        tk.Entry(frame_pdfs, textvariable=self.carpeta_pdfs, width=40).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_pdfs, text="Buscar", command=self.seleccionar_carpeta_pdfs, bg="#1A73E8", fg="white").pack(side=tk.LEFT)
        tk.Button(frame_pdfs, text="Validar", command=self.validar_carpeta_pdfs, bg="#1A73E8", fg="white").pack(side=tk.LEFT, padx=5)
        
        # Selección de cuenta de Outlook
        frame_outlook = tk.Frame(parent, bg="#E8F0FE")
        frame_outlook.pack(fill=tk.X, pady=5)
        tk.Label(frame_outlook, text="Cuenta Outlook:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        self.combo_outlook = ttk.Combobox(frame_outlook, width=37)
        self.combo_outlook['values'] = [cuenta['email'] for cuenta in self.cuentas_outlook]
        self.combo_outlook.pack(side=tk.LEFT, padx=5)

        # Selección de CC
        frame_cc = tk.Frame(parent, bg="#E8F0FE")
        frame_cc.pack(fill=tk.X, pady=5)
        tk.Label(frame_cc, text="CC:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        self.correo_cc = tk.StringVar()
        tk.Entry(frame_cc, textvariable=self.correo_cc, width=40).pack(side=tk.LEFT, padx=5)

        # Selección de CCO
        frame_cco = tk.Frame(parent, bg="#E8F0FE")
        frame_cco.pack(fill=tk.X, pady=5)
        tk.Label(frame_cco, text="CCO:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        self.correo_cco = tk.StringVar()
        tk.Entry(frame_cco, textvariable=self.correo_cco, width=40).pack(side=tk.LEFT, padx=5)

        # Intervalo
        frame_intervalo = tk.Frame(parent, bg="#E8F0FE")
        frame_intervalo.pack(fill=tk.X, pady=5)
        tk.Label(frame_intervalo, text="Intervalo (segundos):", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        tk.Entry(frame_intervalo, textvariable=self.intervalo, width=10).pack(side=tk.LEFT, padx=5)

        # Selección de mes
        frame_mes = tk.Frame(parent, bg="#E8F0FE")
        frame_mes.pack(fill=tk.X, pady=5)
        tk.Label(frame_mes, text="Mes:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        self.combo_mes = ttk.Combobox(frame_mes, values=self.meses, width=5)
        self.combo_mes.set(datetime.now().strftime("%m"))  
        self.combo_mes.pack(side=tk.LEFT, padx=5)

        # Selección de año
        frame_anio = tk.Frame(parent, bg="#E8F0FE")
        frame_anio.pack(fill=tk.X, pady=5)
        tk.Label(frame_anio, text="Año:", bg="#E8F0FE", fg="#1A73E8").pack(side=tk.LEFT)
        self.combo_anio = ttk.Combobox(frame_anio, values=self.años, width=6)
        self.combo_anio.set(datetime.now().strftime("%Y"))  
        self.combo_anio.pack(side=tk.LEFT, padx=5)

        # Botones de envío
        frame_botones = tk.Frame(parent, bg="#E8F0FE")
        frame_botones.pack(fill=tk.X, pady=5)
        self.btn_iniciar = tk.Button(frame_botones, text="Iniciar Envío", command=self.iniciar_envio, width=15, bg="#1A73E8", fg="white")
        self.btn_iniciar.pack(side=tk.LEFT, padx=5)
        self.btn_detener = tk.Button(frame_botones, text="Detener Envío", 
                                     command=self.detener_envio, width=15, state=tk.DISABLED, bg="#E1E1E1", fg="black")
        self.btn_detener.pack(side=tk.LEFT, padx=5)
        
        # Log de eventos
        frame_log = tk.Frame(parent, bg="#E8F0FE")
        frame_log.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame_log, text="Log de eventos:", bg="#E8F0FE", fg="#1A73E8").pack(anchor=tk.W)
        self.log_text = tk.Text(frame_log, height=10, bg="#FFFFFF", fg="#333333")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Botón para cargar el archivo Excel generado
        frame_cargar = tk.Frame(parent, bg="#E8F0FE")
        frame_cargar.pack(fill=tk.X, pady=5)
        tk.Button(frame_cargar, text="Cargar Excel Generado", command=self.cargar_excel_generado, bg="#1A73E8", fg="white").pack(side=tk.LEFT, padx=5)

    def obtener_cuentas_outlook(self):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            
            for account in namespace.Accounts:
                self.cuentas_outlook.append({
                    'email': account.SmtpAddress,
                    'name': account.DisplayName
                })
        except Exception as e:
            messagebox.showwarning("Advertencia", 
                "No se pudieron detectar cuentas de Outlook. Error: " + str(e))
    
    def browse_db(self):
        db_file = filedialog.askopenfilename(
            title="Seleccionar Base de Datos",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")]
        )
        if db_file:
            self.db_path.set(db_file)
    
    def seleccionar_excel(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo Excel",
            filetypes=(("Archivos Excel", "*.xlsx;*.xls"), ("Todos los archivos", "*.*"))
        )
        if filename:
            self.archivo_excel.set(filename)
    
    def seleccionar_carpeta_pdfs(self):
        foldername = filedialog.askdirectory(
            title="Seleccionar carpeta de PDFs"
        )
        if foldername:
            self.carpeta_pdfs.set(foldername)
    
    def cargar_excel_generado(self):
        """Busca y carga el último archivo Excel generado en las sesiones anteriores"""
        try:
            # Obtener archivos con el patrón "Empleados_Activos_*.xlsx"
            desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
            documents = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Documents')
            
            # Buscar en ambas ubicaciones
            files_desktop = glob.glob(os.path.join(desktop, "Empleados_Activos_*.xlsx"))
            files_documents = glob.glob(os.path.join(documents, "Empleados_Activos_*.xlsx"))
            
            all_files = files_desktop + files_documents
            
            if not all_files:
                # Si no encuentra en ubicaciones por defecto, buscar en todos lados
                file_path = filedialog.askopenfilename(
                    title="Seleccionar Excel Generado",
                    filetypes=(("Archivos Excel", "*.xlsx"), ("Todos los archivos", "*.*")),
                    initialfile="Empleados_Activos_"
                )
                if file_path:
                    self.archivo_excel.set(file_path)
            else:
                # Ordenar por fecha de modificación (más reciente primero)
                latest_file = max(all_files, key=os.path.getmtime)
                self.archivo_excel.set(latest_file)
                messagebox.showinfo("Archivo Cargado", f"Se ha cargado el archivo: {os.path.basename(latest_file)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo Excel generado: {str(e)}")

    def add_keyword(self):
        keyword = self.keyword_var.get().strip()
        if keyword and keyword not in self.excluded_keywords:
            self.excluded_keywords.append(keyword)
            self.keyword_listbox.insert(tk.END, keyword)
            self.keyword_var.set("")
    
    def remove_keyword(self):
        try:
            index = self.keyword_listbox.curselection()[0]
            keyword = self.keyword_listbox.get(index)
            self.keyword_listbox.delete(index)
            self.excluded_keywords.remove(keyword)
        except (IndexError, ValueError):
            messagebox.showwarning("Advertencia", "Seleccione una palabra clave para eliminar")
    
    def encontrar_pdf_por_cedula(self, cedula, codigo=None):
        """Busca un archivo PDF que contenga el número de cédula o código en su nombre."""
        # Convertir cédula y código a string para asegurar compatibilidad
        str_cedula = str(cedula).strip()
        
        # Lista de patrones para buscar por cédula
        patrones = [
            f"*{str_cedula}*.pdf",  # Busca la cédula en cualquier parte del nombre
            f"{str_cedula}*.pdf",   # Busca archivos que empiecen con la cédula
            f"*_{str_cedula}*.pdf", # Busca archivos con guion bajo seguido de la cédula
            f"*-{str_cedula}*.pdf"  # Busca archivos con guion seguido de la cédula
        ]
        
        # Agregar patrones de búsqueda por código si está disponible
        if codigo is not None:
            str_codigo = str(codigo).strip()
            patrones.extend([
                f"*{str_codigo}*.pdf",  # Busca el código en cualquier parte del nombre
                f"{str_codigo}*.pdf",   # Busca archivos que empiecen con el código
                f"*_{str_codigo}*.pdf", # Busca archivos con guion bajo seguido del código
                f"*-{str_codigo}*.pdf"  # Busca archivos con guion seguido del código
            ])
        
        for patron in patrones:
            archivos = glob.glob(os.path.join(self.carpeta_pdfs.get(), patron))
            if archivos:
                return archivos[0]  # Devuelve el primer archivo encontrado
        
        return None  # No se encontró ningún archivo
            
    def verify_data(self):
        """Función para verificar los datos y ayudar en la depuración"""
        try:
            # Connect to the database
            db_path = self.db_path.get()
            conn = sqlite3.connect(db_path)
            
            # Query to check problematic records
            check_query = """
            SELECT "APELLIDOS Y NOMBRES" as nombre, 
                   CARGO as cargo,
                   FECHA_SAL as fecha_salida
            FROM empleados 
            WHERE FECHA_SAL IS NOT NULL 
               AND FECHA_SAL != ''
            LIMIT 10
            """
            
            check_df = pd.read_sql_query(check_query, conn)
            
            # Create verification window
            verify_window = tk.Toplevel(self.root)
            verify_window.title("Verificación de Datos")
            verify_window.geometry("600x400")
            
            # Show some sample records with exit dates
            ttk.Label(verify_window, text="Ejemplos de registros con fecha de salida:").pack(pady=5)
            
            sample_text = tk.Text(verify_window, height=10, width=80)
            sample_text.pack(padx=10, pady=5)
            sample_text.insert(tk.END, check_df.to_string())
            
            # Check cargo field problems
            cargo_query = """
            SELECT "APELLIDOS Y NOMBRES" as nombre, 
                   DEPTO as departamento,
                   FECHA_SAL as fecha_salida
            FROM empleados 
            WHERE DEPTO LIKE '%Q.A.P.%' OR DEPTO LIKE '%MEDICO%' OR DEPTO LIKE '%TRONCAL%'
            LIMIT 10
            """
            
            cargo_df = pd.read_sql_query(cargo_query, conn)
            
            ttk.Label(verify_window, text="Ejemplos de registros con departamentos excluidos:").pack(pady=5)
            
            cargo_text = tk.Text(verify_window, height=10, width=80)
            cargo_text.pack(padx=10, pady=5)
            cargo_text.insert(tk.END, cargo_df.to_string())
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar datos: {str(e)}")
    
    def export_to_excel(self):
            try:
                # Create and configure the export dialog
                export_dialog = tk.Toplevel(self.root)
                export_dialog.title("Exportando datos...")
                export_dialog.geometry("300x100")
                export_dialog.transient(self.root)
                export_dialog.grab_set()
                
                progress_label = ttk.Label(export_dialog, text="Conectando a la base de datos...")
                progress_label.pack(pady=10)
                
                progress_bar = ttk.Progressbar(export_dialog, mode='indeterminate')
                progress_bar.pack(fill=tk.X, padx=20)
                progress_bar.start()
                
                # Update UI to show progress
                export_dialog.update()
                
                # Connect to the database
                db_path = self.db_path.get()
                conn = sqlite3.connect(db_path)
                
                # Update progress
                progress_label.config(text="Extrayendo datos de empleados activos...")
                export_dialog.update()
                
                # Query to get data for debugging
                debug_query = """
                SELECT Empleado as codigo, 
                       "APELLIDOS Y NOMBRES" as nombre, 
                       CEDULA as cedula, 
                       EMAIL as correo,
                       DEPTO as departamento,
                       FECHA_SAL as fecha_salida
                FROM empleados 
                """
                
                # Execute query to get all employees for better filtering
                all_df = pd.read_sql_query(debug_query, conn)
                
                # Aplicar filtros con una copia explícita y usando .loc para modificaciones
                # 1. Filtrar por correos válidos
                filtered_df = all_df[all_df['correo'].notna() & (all_df['correo'] != '')].copy()
                
                # 2. Reemplazar strings vacíos con NA en fecha_salida
                filtered_df.loc[:, 'fecha_salida'] = filtered_df['fecha_salida'].replace('', pd.NA)
                
                # 3. Filtrar empleados activos
                filtered_df = filtered_df[filtered_df['fecha_salida'].isna()].copy()
                
                # 4. Manejar NaN en departamento
                filtered_df.loc[:, 'departamento'] = filtered_df['departamento'].fillna('')
                
                # 5. Filtrar por palabras clave de departamento excluidas
                mask = pd.Series(True, index=filtered_df.index)
                for keyword in self.excluded_keywords:
                    mask = mask & ~filtered_df['departamento'].str.contains(keyword, case=False, na=False)
                
                # Aplicar la máscara para obtener el DataFrame final
                df = filtered_df[mask].copy()
                
                # Sort the results based on the selected sort option
                sort_field = self.sort_var.get()
                df = df.sort_values(by=sort_field)
                
                # Remove the departamento column as it was only needed for filtering
                df = df.drop(columns=['departamento', 'fecha_salida'])
                
                # Update progress
                progress_label.config(text="Guardando archivo Excel...")
                export_dialog.update()
                
                # Ask for save location
                current_date = datetime.now().strftime("%Y%m%d")
                default_filename = f"Empleados_Activos_{current_date}.xlsx"
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".xlsx",
                    filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                    initialfile=default_filename
                )
                
                if file_path:
                    # Create Excel writer
                    writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
                    
                    # Write DataFrame to Excel
                    df.to_excel(writer, sheet_name='Empleados Activos', index=False)
                    
                    # Get the xlsxwriter objects
                    workbook = writer.book
                    worksheet = writer.sheets['Empleados Activos']
                    
                    # Add some formatting
                    header_format = workbook.add_format({
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'fg_color': '#D7E4BC',
                        'border': 1
                    })
                    
                    # Write the column headers with the formatting
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Adjust column widths
                    worksheet.set_column('A:A', 10)   # codigo
                    worksheet.set_column('B:B', 30)   # nombre
                    worksheet.set_column('C:C', 15)   # cedula
                    worksheet.set_column('D:D', 30)   # correo
                    
                    # Close the writer and save the Excel file
                    writer.close()
                    
                    # Auto-load the file for sending emails
                    self.archivo_excel.set(file_path)
                    
                    # Show summary of filtering results
                    summary = (
                        f"Datos exportados exitosamente a {file_path}\n\n"
                        f"Resumen del proceso de filtrado:\n"
                        f"- Total de empleados en la base: {len(all_df)}\n"
                        f"- Empleados con email: {len(all_df[all_df['correo'].notna() & (all_df['correo'] != '')])}\n"
                        f"- Empleados activos con email: {len(filtered_df)}\n"
                        f"- Empleados filtrados por departamentos excluidos: {len(filtered_df) - len(df)}\n"
                        f"- Empleados en el reporte final: {len(df)}\n"
                        f"- Ordenado por: {sort_field}"
                    )
                    messagebox.showinfo("Éxito", summary)
                
                conn.close()
                export_dialog.destroy()
                
            except Exception as e:
                try:
                    export_dialog.destroy()
                except:
                    pass
                messagebox.showerror("Error", f"Ocurrió un error al exportar: {str(e)}")
    
    def iniciar_envio(self):
        if not self.validar_excel():
            return
        
        if not self.validar_carpeta_pdfs():
            return
        
        self.enviando = True
        self.btn_iniciar.config(state=tk.DISABLED)
        self.btn_detener.config(state=tk.NORMAL)

        # Hilo para enviar correos
        threading.Thread(target=self.enviar_correos).start()

    def detener_envio(self):
        self.enviando = False
        self.btn_detener.config(state=tk.DISABLED)
        self.log_text.insert(tk.END, "Proceso detenido por el usuario.\n")
        self.log_text.yview(tk.END)
        # La bandera "enviando" será comprobada por el hilo de envío
        
    def enviar_correos(self):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            
            # Contar éxitos y errores
            total_enviados = 0
            total_errores = 0
            
            # Actualizar el log
            self.log_text.insert(tk.END, f"Iniciando proceso de envío con {len(self.df)} empleados...\n")
            self.log_text.yview(tk.END)
            
            for index, row in self.df.iterrows():
                if not self.enviando:
                    self.log_text.insert(tk.END, "Proceso interrumpido por el usuario.\n")
                    break

                # Obtener datos del DataFrame
                correo_destino = str(row[self.columnas_encontradas['correo']]).strip()
                str_nombres = str(row[self.columnas_encontradas['nombre']]).strip()
                str_cedula = str(row[self.columnas_encontradas['cedula']]).strip()
                str_empleado = str(row[self.columnas_encontradas['codigo']]).strip()
                
                # Verificar si el correo es válido
                if not correo_destino or '@' not in correo_destino:
                    self.log_text.insert(tk.END, f"ERROR: Correo inválido para {str_nombres} ({correo_destino})\n")
                    self.log_text.yview(tk.END)
                    total_errores += 1
                    continue
                
                # Buscar el archivo PDF correspondiente a la cédula o código
                ruta_pdf = self.encontrar_pdf_por_cedula(str_cedula, str_empleado)
                
                if not ruta_pdf:
                    self.log_text.insert(tk.END, f"ERROR: No se encontró PDF para {str_nombres} (Cédula: {str_cedula}, Código: {str_empleado})\n")
                    self.log_text.yview(tk.END)
                    total_errores += 1
                    continue
                
                # Generar asunto
                mes = self.combo_mes.get()
                anio = self.combo_anio.get()
                asunto = f"ROL {mes}/{anio}"

                # Crear el cuerpo del correo
                html_contenido = self.template_html.replace("{{ StrNombres }}", str_nombres) \
                                                    .replace("{{ StrCedula }}", str_cedula) \
                                                    .replace("{{ StrEmpleado }}", str_empleado) \
                                                    .replace("{{ año }}", str(anio))
                
                try:
                    # Crear el mensaje
                    mail = outlook.CreateItem(0)  # 0: olMailItem
                    mail.Subject = asunto
                    mail.HTMLBody = html_contenido
                    mail.To = correo_destino
                    
                    # Agregar CC y CCO
                    if self.correo_cc.get():
                        mail.CC = self.correo_cc.get()
                    if self.correo_cco.get():
                        mail.BCC = self.correo_cco.get()

                    # Adjuntar archivo PDF
                    mail.Attachments.Add(ruta_pdf)

                    # Enviar correo
                    mail.Send()
                    total_enviados += 1

                    # Log
                    self.log_text.insert(tk.END, f"✅ Correo enviado a: {correo_destino} (Nombre: {str_nombres})\n")
                    self.log_text.yview(tk.END)  # Desplazar hacia abajo
                    
                    # Actualizar la UI para mostrar el progreso
                    self.root.update_idletasks()
                    
                    # Esperar antes de enviar el siguiente
                    time.sleep(int(self.intervalo.get()))
                    
                except Exception as mail_error:
                    self.log_text.insert(tk.END, f"❌ ERROR al enviar a {correo_destino}: {str(mail_error)}\n")
                    self.log_text.yview(tk.END)
                    total_errores += 1

            # Resumen final
            self.log_text.insert(tk.END, f"\n----- RESUMEN -----\n")
            self.log_text.insert(tk.END, f"Total de correos enviados: {total_enviados}\n")
            self.log_text.insert(tk.END, f"Total de errores: {total_errores}\n")
            self.log_text.insert(tk.END, f"Proceso de envío completado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}.\n")
            
            # Reproducir sonido de notificación si está disponible
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except:
                pass
            
            self.btn_detener.config(state=tk.DISABLED)
            self.btn_iniciar.config(state=tk.NORMAL)
            
        except Exception as e:
            self.log_text.insert(tk.END, f"Error general en el proceso: {str(e)}\n")
            self.log_text.yview(tk.END)
            self.btn_detener.config(state=tk.DISABLED)
            self.btn_iniciar.config(state=tk.NORMAL)

if __name__ == "__main__":
    # Configurar el estilo para ttk
    try:
        from ttkthemes import ThemedStyle
        root = tk.Tk()
        style = ThemedStyle(root)
        style.set_theme("arc")  # Tema moderno
    except ImportError:
        root = tk.Tk()
        # Configuración de estilo básico si no está disponible ttkthemes
        ttk.Style().configure("TButton", padding=6, relief="flat", background="#1A73E8")
    
    # Configuración de la ventana
    root.title("Sistema Integrado de Gestión de Roles")
    
    # Icono de la aplicación (si está disponible)
    try:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except:
        pass
    
    # Iniciar la aplicación
    app = AplicacionEnvioRoles(root)
    
    # Centrar la ventana
    root.update_idletasks()
    ancho = root.winfo_width()
    alto = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (ancho // 2)
    y = (root.winfo_screenheight() // 2) - (alto // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()
