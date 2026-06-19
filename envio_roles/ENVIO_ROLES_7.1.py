import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import threading
import time
from datetime import datetime
import os
import glob
import win32com.client
import pyodbc

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
        # Botón de conexión
        conn_frame = tk.Frame(parent, bg="#E8F0FE")
        conn_frame.pack(fill=tk.X, padx=5, pady=(8, 2))
        tk.Button(conn_frame, text="Probar Conexión", command=self.test_connection,
                  bg="#1A73E8", fg="white", width=20).pack(side=tk.LEFT)
        
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
    
    def _get_connection(self):
        """Abre y devuelve una conexión pyodbc al SQL Server. Lanza excepción si falla."""
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=SERVER\\server;"
            "DATABASE=insevig;"
            "UID=sa;PWD=puntosoft123*;"
            "Encrypt=No;TrustServerCertificate=yes;"
        )
        return pyodbc.connect(conn_str)

    def test_connection(self):
        """Verifica que la conexión al SQL Server funcione."""
        try:
            conn = self._get_connection()
            conn.close()
            messagebox.showinfo("Conexión exitosa", "Conexión a la base de datos establecida correctamente.")
        except Exception as e:
            messagebox.showerror("Error de conexión", f"No se pudo conectar:\n{e}")
    
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
        """Diagnóstico completo del proceso de filtrado paso a paso."""
        try:
            conn = self._get_connection()
            try:
                counts_query = """
                SELECT
                    COUNT(*)                                                   AS total_rpemplea,
                    SUM(CASE WHEN ESTADO = 'ACT' AND FECHA_SAL IS NULL
                             THEN 1 ELSE 0 END)                                AS activos_sin_salida,
                    SUM(CASE WHEN ESTADO = 'ACT' AND FECHA_SAL IS NOT NULL
                             THEN 1 ELSE 0 END)                                AS act_con_salida_excluidos,
                    SUM(CASE WHEN ESTADO != 'ACT' OR ESTADO IS NULL
                             THEN 1 ELSE 0 END)                                AS inactivos_por_estado,
                    SUM(CASE WHEN ESTADO = 'ACT' AND FECHA_SAL IS NULL
                              AND emp_mail IS NOT NULL AND emp_mail <> ''
                             THEN 1 ELSE 0 END)                                AS activos_con_email
                FROM RPEMPLEA
                WHERE CODEMP = '10' AND CODSUC = '10'
                """
                row = pd.read_sql(counts_query, conn).iloc[0]

                excl_query = """
                SELECT DISTINCT
                    ISNULL(D.NOMBRE, CAST(E.DEPTO AS VARCHAR)) AS departamento,
                    COUNT(*) AS empleados_activos_con_email
                FROM RPEMPLEA E
                OUTER APPLY (
                    SELECT TOP 1 NOMBRE FROM DBTABLAS
                    WHERE TIPO = 'DPT' AND CODIGO = E.DEPTO
                      AND CODEMP = '10'
                ) D
                WHERE E.CODEMP = '10' AND E.CODSUC = '10'
                  AND E.ESTADO = 'ACT'
                  AND E.FECHA_SAL IS NULL
                  AND E.emp_mail IS NOT NULL
                  AND E.emp_mail <> ''
                GROUP BY ISNULL(D.NOMBRE, CAST(E.DEPTO AS VARCHAR))
                ORDER BY departamento
                """
                deptos_df = pd.read_sql(excl_query, conn)

                preview_query = """
                SELECT TOP 10
                    E.EMPLEADO                       AS codigo,
                    E.APELLIDOS + ' ' + E.NOMBRES    AS nombre,
                    E.CEDULA                         AS cedula,
                    E.emp_mail                       AS correo,
                    ISNULL(D.NOMBRE, '')             AS departamento
                FROM RPEMPLEA E
                OUTER APPLY (
                    SELECT TOP 1 NOMBRE FROM DBTABLAS
                    WHERE TIPO = 'DPT' AND CODIGO = E.DEPTO
                      AND CODEMP = '10'
                ) D
                WHERE E.CODEMP = '10' AND E.CODSUC = '10'
                  AND E.ESTADO = 'ACT'
                  AND E.FECHA_SAL IS NULL
                  AND E.emp_mail IS NOT NULL
                  AND E.emp_mail <> ''
                ORDER BY E.APELLIDOS, E.NOMBRES
                """
                preview_df = pd.read_sql(preview_query, conn)

                # Todos los activos con email → validar formato en Python
                mail_query = """
                SELECT
                    E.EMPLEADO                       AS codigo,
                    E.APELLIDOS + ' ' + E.NOMBRES    AS nombre,
                    E.CEDULA                         AS cedula,
                    E.emp_mail                       AS correo,
                    ISNULL(D.NOMBRE, '')             AS departamento
                FROM RPEMPLEA E
                OUTER APPLY (
                    SELECT TOP 1 NOMBRE FROM DBTABLAS
                    WHERE TIPO = 'DPT' AND CODIGO = E.DEPTO
                      AND CODEMP = '10'
                ) D
                WHERE E.CODEMP = '10' AND E.CODSUC = '10'
                  AND E.ESTADO = 'ACT'
                  AND E.FECHA_SAL IS NULL
                  AND E.emp_mail IS NOT NULL
                  AND E.emp_mail <> ''
                """
                mail_df = pd.read_sql(mail_query, conn)
            finally:
                conn.close()

            # ── Validar formato de correo ────────────────────────────────────
            import re
            _patron = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
            mail_df['_ok'] = mail_df['correo'].apply(
                lambda e: bool(_patron.match(str(e).strip())))
            invalidos_df = mail_df[~mail_df['_ok']].drop(columns=['_ok'])
            n_invalidos = len(invalidos_df)

            # ── Cálculos post-query ──────────────────────────────────────────
            def es_excluido(nombre):
                for kw in self.excluded_keywords:
                    if kw.lower() in nombre.lower():
                        return "EXCLUIDO"
                return ""
            deptos_df['estado_filtro'] = deptos_df['departamento'].apply(es_excluido)
            excluidos_df = deptos_df[deptos_df['estado_filtro'] == 'EXCLUIDO']
            n_excluidos = int(excluidos_df['empleados_activos_con_email'].sum())
            n_final = int(row['activos_con_email']) - n_excluidos - n_invalidos

            # ── Ventana de diagnóstico ────────────────────────────────────────
            win = tk.Toplevel(self.root)
            win.title("Diagnóstico de Datos")
            win.geometry("750x780")
            win.configure(bg="#E8F0FE")

            ttk.Label(win, text="DIAGNÓSTICO DE FILTRADO", font=("Arial", 13, "bold"),
                      foreground="#1A73E8", background="#E8F0FE").pack(pady=(10, 4))

            # Resumen de conteos
            alerta_inv = f"  ⚠ Correos con formato inválido  : {n_invalidos}\n" if n_invalidos else ""
            resumen = (
                f"  Total RPEMPLEA (emp.10/suc.10): {int(row['total_rpemplea'])}\n"
                f"  Activos sin fecha de salida   : {int(row['activos_sin_salida'])}\n"
                f"  Inactivos (ESTADO != ACT)     : {int(row['inactivos_por_estado'])}\n"
                f"  ACT con FECHA_SAL (excluidos) : {int(row['act_con_salida_excluidos'])}\n"
                f"  Activos con e-mail en BD      : {int(row['activos_con_email'])}\n"
                + alerta_inv +
                f"  Excluidos por departamento    : {n_excluidos}\n"
                f"  ──────────────────────────────────────\n"
                f"  TOTAL QUE RECIBIRÍAN ROL      : {n_final}"
            )
            frm_res = tk.LabelFrame(win, text="Resumen", bg="#E8F0FE", fg="#1A73E8",
                                    padx=8, pady=6)
            frm_res.pack(fill=tk.X, padx=10, pady=4)
            tk.Label(frm_res, text=resumen, bg="#E8F0FE", fg="#222", justify=tk.LEFT,
                     font=("Courier", 10)).pack(anchor=tk.W)

            # Tabla de departamentos (todos, marcando excluidos)
            ttk.Label(win, text="Departamentos presentes en activos con email (● = excluido):",
                      background="#E8F0FE", foreground="#1A73E8").pack(anchor=tk.W, padx=10)

            frm_deptos = tk.Frame(win, bg="#E8F0FE")
            frm_deptos.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

            sb_d = tk.Scrollbar(frm_deptos)
            sb_d.pack(side=tk.RIGHT, fill=tk.Y)
            cols_d = ("departamento", "empleados", "filtro")
            tree_d = ttk.Treeview(frm_deptos, columns=cols_d, show="headings",
                                  height=8, yscrollcommand=sb_d.set)
            tree_d.heading("departamento", text="Departamento")
            tree_d.heading("empleados",   text="Empleados")
            tree_d.heading("filtro",      text="Estado filtro")
            tree_d.column("departamento", width=380)
            tree_d.column("empleados",    width=90, anchor="center")
            tree_d.column("filtro",       width=110, anchor="center")
            sb_d.config(command=tree_d.yview)

            for _, r in deptos_df.iterrows():
                tag = "excluido" if r['estado_filtro'] == "EXCLUIDO" else ""
                tree_d.insert("", tk.END,
                              values=(r['departamento'], r['empleados_activos_con_email'],
                                      r['estado_filtro']),
                              tags=(tag,))
            tree_d.tag_configure("excluido", foreground="#CC0000")
            tree_d.pack(fill=tk.BOTH, expand=True)

            # Muestra del listado final
            ttk.Label(win, text="Primeros 10 del listado final (antes de aplicar exclusiones en Python):",
                      background="#E8F0FE", foreground="#1A73E8").pack(anchor=tk.W, padx=10, pady=(6, 0))

            frm_prev = tk.Frame(win, bg="#E8F0FE")
            frm_prev.pack(fill=tk.X, padx=10, pady=(2, 10))
            sb_p = tk.Scrollbar(frm_prev, orient=tk.HORIZONTAL)
            sb_p.pack(side=tk.BOTTOM, fill=tk.X)
            prev_txt = tk.Text(frm_prev, height=5, wrap=tk.NONE,
                               xscrollcommand=sb_p.set, font=("Courier", 9))
            prev_txt.pack(fill=tk.X)
            sb_p.config(command=prev_txt.xview)
            prev_txt.insert(tk.END, preview_df.to_string(index=False))

            # ── Sección correos inválidos ─────────────────────────────────────
            color_sec = "#FFEBEE" if n_invalidos else "#E8F0FE"
            titulo_inv = (f"⚠  {n_invalidos} correo(s) con formato inválido — se excluirán al generar Excel:"
                          if n_invalidos else
                          "✔  Todos los correos tienen formato válido")
            ttk.Label(win, text=titulo_inv,
                      background="#E8F0FE",
                      foreground="#B71C1C" if n_invalidos else "#2E7D32",
                      font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=10, pady=(8, 0))

            if n_invalidos:
                frm_inv = tk.Frame(win, bg=color_sec)
                frm_inv.pack(fill=tk.X, padx=10, pady=(2, 10))

                sb_iv = tk.Scrollbar(frm_inv)
                sb_iv.pack(side=tk.RIGHT, fill=tk.Y)
                cols_i = ("codigo", "nombre", "cedula", "correo_invalido", "departamento")
                tree_i = ttk.Treeview(frm_inv, columns=cols_i, show="headings",
                                      height=5, yscrollcommand=sb_iv.set)
                tree_i.heading("codigo",          text="Código")
                tree_i.heading("nombre",          text="Nombre")
                tree_i.heading("cedula",          text="Cédula")
                tree_i.heading("correo_invalido", text="Correo (inválido)")
                tree_i.heading("departamento",    text="Departamento")
                tree_i.column("codigo",          width=65,  anchor="center")
                tree_i.column("nombre",          width=190)
                tree_i.column("cedula",          width=95,  anchor="center")
                tree_i.column("correo_invalido", width=170)
                tree_i.column("departamento",    width=150)
                sb_iv.config(command=tree_i.yview)
                for _, r in invalidos_df.iterrows():
                    tree_i.insert("", tk.END, values=(
                        r.get('codigo', ''), r.get('nombre', ''),
                        r.get('cedula', ''), r.get('correo', ''),
                        r.get('departamento', '')))
                tree_i.pack(fill=tk.X)

        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar datos: {str(e)}")
    
    def _mostrar_correos_invalidos(self, invalidos_df):
        """Ventana que lista los empleados con correo inválido o mal formado."""
        win = tk.Toplevel(self.root)
        win.title("⚠ Correos inválidos — no incluidos en el Excel")
        win.geometry("720x400")
        win.configure(bg="#FFF8E1")

        tk.Label(win,
                 text=f"Se encontraron {len(invalidos_df)} empleado(s) con correo inválido — NO fueron incluidos en el Excel.",
                 bg="#FFF8E1", fg="#B71C1C", font=("Arial", 10, "bold"),
                 wraplength=680, justify=tk.LEFT).pack(padx=10, pady=(10, 4), anchor=tk.W)

        tk.Label(win,
                 text="Corrija estos correos en la base de datos para incluirlos en el próximo envío:",
                 bg="#FFF8E1", fg="#555", font=("Arial", 9)).pack(padx=10, anchor=tk.W)

        frm = tk.Frame(win, bg="#FFF8E1")
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        sb_v = tk.Scrollbar(frm)
        sb_v.pack(side=tk.RIGHT, fill=tk.Y)
        sb_h = tk.Scrollbar(frm, orient=tk.HORIZONTAL)
        sb_h.pack(side=tk.BOTTOM, fill=tk.X)

        cols = ("codigo", "nombre", "cedula", "correo_invalido", "departamento")
        tree = ttk.Treeview(frm, columns=cols, show="headings",
                            yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        tree.heading("codigo",          text="Código")
        tree.heading("nombre",          text="Nombre")
        tree.heading("cedula",          text="Cédula")
        tree.heading("correo_invalido", text="Correo (inválido)")
        tree.heading("departamento",    text="Departamento")
        tree.column("codigo",          width=70,  anchor="center")
        tree.column("nombre",          width=200)
        tree.column("cedula",          width=100, anchor="center")
        tree.column("correo_invalido", width=180)
        tree.column("departamento",    width=160)
        sb_v.config(command=tree.yview)
        sb_h.config(command=tree.xview)

        for _, r in invalidos_df.iterrows():
            tree.insert("", tk.END, values=(
                r.get('codigo', ''),
                r.get('nombre', ''),
                r.get('cedula', ''),
                r.get('correo', ''),
                r.get('departamento', ''),
            ))
        tree.pack(fill=tk.BOTH, expand=True)

        tk.Button(win, text="Cerrar", command=win.destroy,
                  bg="#1A73E8", fg="white", width=12).pack(pady=8)

    def export_to_excel(self):
        try:
            # Diálogo de progreso
            export_dialog = tk.Toplevel(self.root)
            export_dialog.title("Exportando datos...")
            export_dialog.geometry("300x100")
            export_dialog.transient(self.root)
            export_dialog.grab_set()

            progress_label = ttk.Label(export_dialog, text="Conectando a SQL Server...")
            progress_label.pack(pady=10)

            progress_bar = ttk.Progressbar(export_dialog, mode='indeterminate')
            progress_bar.pack(fill=tk.X, padx=20)
            progress_bar.start()
            export_dialog.update()

            # Conexión SQL Server
            conn = self._get_connection()

            progress_label.config(text="Extrayendo empleados activos...")
            export_dialog.update()

            # OUTER APPLY evita duplicados: toma el primer nombre de depto (igual que SISTEMA_GESTION)
            query = """
            SELECT
                E.EMPLEADO                              AS codigo,
                E.APELLIDOS + ' ' + E.NOMBRES           AS nombre,
                E.CEDULA                                AS cedula,
                E.emp_mail                              AS correo,
                ISNULL(D.NOMBRE, '')                    AS departamento
            FROM RPEMPLEA E
            OUTER APPLY (
                SELECT TOP 1 NOMBRE
                FROM DBTABLAS
                WHERE TIPO = 'DPT' AND CODIGO = E.DEPTO
                  AND CODEMP = '10'
            ) D
            WHERE E.CODEMP = '10' AND E.CODSUC = '10'
              AND E.ESTADO = 'ACT'
              AND E.FECHA_SAL IS NULL
              AND E.emp_mail IS NOT NULL
              AND E.emp_mail <> ''
            """
            all_df = pd.read_sql(query, conn)
            conn.close()

            # ── Validar formato de correo ────────────────────────────────────
            import re
            _patron = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

            def _email_valido(email):
                return bool(_patron.match(str(email).strip()))

            all_df['_email_ok'] = all_df['correo'].apply(_email_valido)
            invalidos_df = all_df[~all_df['_email_ok']].copy()
            all_df = all_df[all_df['_email_ok']].drop(columns=['_email_ok']).copy()

            # ── Filtrar departamentos excluidos ──────────────────────────────
            total_validos = len(all_df)
            mask = pd.Series(True, index=all_df.index)
            for keyword in self.excluded_keywords:
                mask = mask & ~all_df['departamento'].str.contains(keyword, case=False, na=False)
            df = all_df[mask].copy()

            # Ordenar según selección
            sort_field = self.sort_var.get()
            df = df.sort_values(by=sort_field)

            progress_label.config(text="Guardando archivo Excel...")
            export_dialog.update()

            # Pedir ruta de guardado
            current_date = datetime.now().strftime("%Y%m%d")
            default_filename = f"Empleados_Activos_{current_date}.xlsx"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=default_filename
            )

            if file_path:
                writer = pd.ExcelWriter(file_path, engine='xlsxwriter')
                df.to_excel(writer, sheet_name='Empleados Activos', index=False)

                workbook = writer.book
                worksheet = writer.sheets['Empleados Activos']

                header_format = workbook.add_format({
                    'bold': True, 'text_wrap': True, 'valign': 'top',
                    'fg_color': '#D7E4BC', 'border': 1
                })
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

                worksheet.set_column('A:A', 10)
                worksheet.set_column('B:B', 35)
                worksheet.set_column('C:C', 15)
                worksheet.set_column('D:D', 35)
                worksheet.set_column('E:E', 35)

                writer.close()
                self.archivo_excel.set(file_path)

                summary = (
                    f"Exportación completada.\n\n"
                    f"- Activos sin fecha de salida con email en BD : {total_validos + len(invalidos_df)}\n"
                    f"- Correos con formato inválido (excluidos)    : {len(invalidos_df)}\n"
                    f"- Filtrados por departamento excluido         : {total_validos - len(df)}\n"
                    f"- Empleados incluidos en el Excel             : {len(df)}\n"
                    f"- Ordenado por: {sort_field}"
                )
                messagebox.showinfo("Éxito", summary)

                # ── Mostrar correos inválidos si los hay ─────────────────────
                if not invalidos_df.empty:
                    self._mostrar_correos_invalidos(invalidos_df)

            export_dialog.destroy()

        except Exception as e:
            try:
                export_dialog.destroy()
            except Exception:
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
    
    # Icono de la aplicación
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(_base, "icon_envio.ico")
        # Generar el icono si no existe
        if not os.path.exists(icon_path):
            from crear_icono_envio import generar_ico
            generar_ico(icon_path)
        root.iconbitmap(icon_path)
    except Exception:
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
