import pyodbc
import pandas as pd
import os
import sys
import configparser
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from tkinter.font import Font
import tempfile
from tkinter import filedialog
from PIL import Image, ImageTk
import threading

# Archivo de configuración junto al script
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

def mostrar_error_copiable(titulo, mensaje):
    """Muestra un diálogo de error con texto seleccionable y botón Copiar."""
    dialogo = tk.Toplevel()
    dialogo.title(titulo)
    dialogo.geometry("520x280")
    dialogo.resizable(True, True)
    dialogo.grab_set()

    tk.Label(dialogo, text=titulo, font=('Arial', 11, 'bold'), fg='#c62828').pack(pady=(14, 6))

    frame_txt = tk.Frame(dialogo)
    frame_txt.pack(padx=14, pady=(0, 8), fill='both', expand=True)

    txt = tk.Text(frame_txt, wrap='word', height=8, font=('Consolas', 9),
                  bg='#fff8f8', relief='solid', borderwidth=1)
    scroll = tk.Scrollbar(frame_txt, command=txt.yview)
    txt.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    txt.pack(side='left', fill='both', expand=True)
    txt.insert('1.0', mensaje)
    txt.configure(state='normal')  # seleccionable pero editable solo con Ctrl+C

    def copiar_todo():
        dialogo.clipboard_clear()
        dialogo.clipboard_append(mensaje)
        btn_copiar.config(text="¡Copiado!", bg='#388e3c')
        dialogo.after(1500, lambda: btn_copiar.config(text="Copiar todo", bg='#1565c0'))

    btn_frame = tk.Frame(dialogo)
    btn_frame.pack(pady=(0, 12))
    btn_copiar = tk.Button(btn_frame, text="Copiar todo", command=copiar_todo,
                           bg='#1565c0', fg='white', width=12)
    btn_copiar.pack(side='left', padx=6)
    tk.Button(btn_frame, text="Cerrar", command=dialogo.destroy, width=10).pack(side='left', padx=6)

    dialogo.wait_window()

def leer_config():
    """Lee la configuración de conexión desde config.ini"""
    config = configparser.ConfigParser()
    config['database'] = {
        'server': 'SERVER\\server',
        'database': 'insevig',
        'username': 'sa',
        'password': 'puntosoft123*',
    }
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding='utf-8')
    return config['database']

def guardar_config(server, database, username, password):
    """Guarda la configuración de conexión en config.ini"""
    config = configparser.ConfigParser()
    config['database'] = {
        'server': server,
        'database': database,
        'username': username,
        'password': password,
    }
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        config.write(f)

def mostrar_dialogo_configuracion(error_previo=''):
    """Muestra diálogo para configurar la conexión manualmente. Retorna True si el usuario guardó."""
    cfg = leer_config()

    dialogo = tk.Toplevel()
    dialogo.title("Configuración de Conexión")
    dialogo.geometry("420x320")
    dialogo.resizable(False, False)
    dialogo.grab_set()

    tk.Label(dialogo, text="Configuración de Base de Datos", font=('Arial', 12, 'bold')).pack(pady=(15, 5))

    if error_previo:
        tk.Label(dialogo, text="No se pudo conectar. Verifique los datos:", fg='red', wraplength=380).pack(pady=(0, 8))

    frame = tk.Frame(dialogo)
    frame.pack(padx=20, fill='x')

    campos = [
        ("Servidor (IP o nombre):", 'server'),
        ("Base de datos:", 'database'),
        ("Usuario:", 'username'),
        ("Contraseña:", 'password'),
    ]
    entradas = {}
    for i, (label, key) in enumerate(campos):
        tk.Label(frame, text=label, anchor='w').grid(row=i, column=0, sticky='w', pady=4)
        show = '*' if key == 'password' else ''
        e = tk.Entry(frame, width=28, show=show)
        e.insert(0, cfg.get(key, ''))
        e.grid(row=i, column=1, padx=(10, 0), pady=4)
        entradas[key] = e

    tk.Label(frame, text="Ejemplo de servidor: 192.168.1.10\\server  o  SERVER\\server",
             fg='gray', font=('Arial', 8)).grid(row=len(campos), column=0, columnspan=2, pady=(4, 0))

    resultado = {'guardado': False}

    def guardar():
        guardar_config(
            entradas['server'].get().strip(),
            entradas['database'].get().strip(),
            entradas['username'].get().strip(),
            entradas['password'].get().strip(),
        )
        resultado['guardado'] = True
        dialogo.destroy()

    def cancelar():
        dialogo.destroy()

    btn_frame = tk.Frame(dialogo)
    btn_frame.pack(pady=15)
    tk.Button(btn_frame, text="Guardar y Conectar", command=guardar,
              bg='#2e7d32', fg='white', width=18).pack(side='left', padx=5)
    tk.Button(btn_frame, text="Cancelar", command=cancelar, width=10).pack(side='left', padx=5)

    dialogo.wait_window()
    return resultado['guardado']

def formatear_cedula_ec(cedula):
    """Formatea cédula ecuatoriana a 10 dígitos con ceros a la izquierda"""
    if pd.isnull(cedula) or cedula == '':
        return ''

    # Convertir a string y limpiar
    cedula_str = str(cedula).strip()

    # Si es un número flotante (ej: 1701234567.0), quitarle el .0
    if '.' in cedula_str:
        cedula_str = cedula_str.split('.')[0]

    # Remover caracteres no numéricos
    cedula_num = ''.join(filter(str.isdigit, cedula_str))

    # Si está vacía, retornar vacío
    if not cedula_num:
        return ''

    # Completar con ceros a la IZQUIERDA hasta 10 dígitos
    cedula_formateada = cedula_num.zfill(10)

    # Si tiene más de 10 dígitos, tomar solo los últimos 10 (por si acaso)
    if len(cedula_formateada) > 10:
        cedula_formateada = cedula_formateada[-10:]

    return cedula_formateada

def obtener_drivers_disponibles():
    """Obtiene lista de drivers ODBC disponibles en el sistema"""
    try:
        drivers = pyodbc.drivers()
        return drivers
    except:
        return []

def intentar_conexion(server, database, username, password, drivers_validos):
    """Intenta conectar con los drivers disponibles. Retorna (conn, error)."""
    ultimo_error = ""
    for driver in drivers_validos:
        try:
            conn_str = (
                f'DRIVER={driver};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password};'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
                f'ApplicationIntent=ReadOnly;'
            )
            conn = pyodbc.connect(conn_str, timeout=8)
            conn.timeout = 30  # timeout de 30s por consulta
            # READ UNCOMMITTED: los SELECT no esperan bloqueos de PowerBuilder
            cursor = conn.cursor()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            cursor.close()
            print(f"Conexión exitosa con driver: {driver}")
            return conn, None
        except Exception as e:
            ultimo_error = str(e)
            print(f"Driver {driver} no funcionó: {e}")
    return None, ultimo_error

def conectar_bd():
    """Establece conexión con la base de datos SQL Server.
    Lee servidor/credenciales de config.ini. Si falla, muestra diálogo de configuración."""
    # Lista de drivers a probar en orden de preferencia
    drivers_a_probar = [
        '{ODBC Driver 17 for SQL Server}',
        '{ODBC Driver 18 for SQL Server}',
        '{ODBC Driver 13 for SQL Server}',
        '{ODBC Driver 11 for SQL Server}',
        '{SQL Server Native Client 11.0}',
        '{SQL Server}',
    ]

    drivers_disponibles = obtener_drivers_disponibles()
    print(f"Drivers ODBC disponibles: {drivers_disponibles}")

    drivers_validos = [d for d in drivers_a_probar if any(d.replace('{','').replace('}','') in driver for driver in drivers_disponibles)]

    if not drivers_validos:
        mostrar_error_copiable("Error de Driver ODBC",
            "No se encontró ningún driver ODBC de SQL Server instalado.\n\n"
            "Por favor instale 'ODBC Driver 17 for SQL Server'.\n\n"
            f"Drivers instalados en este equipo:\n{chr(10).join(drivers_disponibles) if drivers_disponibles else '(ninguno detectado)'}\n\n"
            "Descarga: https://aka.ms/odbc17"
        )
        return None

    # Primer intento con la configuración guardada (o la predeterminada)
    cfg = leer_config()
    conn, error = intentar_conexion(
        cfg['server'], cfg['database'], cfg['username'], cfg['password'], drivers_validos
    )
    if conn:
        return conn

    # Si falló, mostrar diálogo de configuración y reintentar
    guardado = mostrar_dialogo_configuracion(error_previo=error)
    if not guardado:
        return None

    cfg = leer_config()
    conn, error = intentar_conexion(
        cfg['server'], cfg['database'], cfg['username'], cfg['password'], drivers_validos
    )
    if conn:
        return conn

    mostrar_error_copiable("Error de Conexión",
        f"No se pudo conectar con los datos ingresados.\n\n"
        f"Error técnico:\n{error}\n\n"
        f"Verifique que:\n"
        f"• El servidor sea accesible desde esta PC (pruebe: ping {cfg['server'].split(chr(92))[0]})\n"
        f"• El ODBC Driver 17 for SQL Server esté instalado\n"
        f"• El servicio SQL Server Browser esté activo en el servidor"
    )
    return None

def obtener_observaciones(conn, empleado=None, busqueda_exacta=False):
    """Obtiene observaciones de empleados con JOIN para búsqueda por nombre"""
    try:
        if not conn:
            return pd.DataFrame()
        cursor = conn.cursor()

        query = """
        SELECT
            o.empleado,
            o.codemp,
            o.codsuc,
            o.fecha_ven,
            o.refer1, o.refer2, o.refer3, o.refer4, o.refer5, o.refer6, o.refer7,
            e.APELLIDOS,
            e.NOMBRES
        FROM dbo.RPEMPOBSERV o
        LEFT JOIN dbo.RPEMPLEA e ON o.empleado = e.EMPLEADO
        """

        params = []

        if empleado and empleado.strip():
            if empleado.strip().isdigit():
                # Búsqueda por código
                if busqueda_exacta:
                    query += " WHERE o.empleado = ? "
                else:
                    query += " WHERE o.empleado LIKE ? "
                params.append(empleado.strip() if busqueda_exacta else f"%{empleado.strip()}%")
            else:
                # Búsqueda por nombre (usando + en lugar de CONCAT para compatibilidad)
                query += " WHERE (e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ? OR (ISNULL(e.APELLIDOS,'') + ' ' + ISNULL(e.NOMBRES,'')) LIKE ?) "
                search_term = f"%{empleado.strip()}%"
                params.extend([search_term, search_term, search_term])

        query += " ORDER BY o.fecha_ven ASC"

        cursor.execute(query, params)
        resultados = cursor.fetchall()
        columnas = [column[0] for column in cursor.description]
        df = pd.DataFrame.from_records(resultados, columns=columnas)

        return df

    except Exception as e:
        print(f"Error al consultar datos: {e}")
        return pd.DataFrame()

def obtener_multas(conn, empleado=None):
    """Obtiene multas (clase 203) de empleados"""
    try:
        if not conn:
            return pd.DataFrame()
        if not empleado or not empleado.strip() or not empleado.strip().isdigit():
            return pd.DataFrame()
            
        cursor = conn.cursor()
        
        query = """
        SELECT NUMERO, FECHA, EMPLEADO, CLASE, VALOR, CONCEPTO, OBSERV
        FROM dbo.RPHISTOR
        WHERE EMPLEADO = ? AND CLASE = '203'
        ORDER BY FECHA DESC
        """
        
        cursor.execute(query, [empleado.strip()])
        resultados = cursor.fetchall()
        columnas = [column[0] for column in cursor.description]
        df = pd.DataFrame.from_records(resultados, columns=columnas)
        
        return df
    
    except Exception as e:
        print(f"Error al consultar multas: {e}")
        return pd.DataFrame()

def obtener_faltas(conn, empleado):
    """Obtiene las faltas del empleado desde RPHORTOT (período actual)"""
    try:
        if not conn or not empleado or not empleado.strip():
            return pd.DataFrame()

        cursor = conn.cursor()

        query = """
        SELECT FECHA_VEN, ISNULL(TOTAUS, 0) as TOTAUS, ISNULL(TOTFJ, 0) as TOTFJ,
               ISNULL(TOTFI, 0) as TOTFI, ISNULL(TOTAUS, 0) + ISNULL(TOTFJ, 0) + ISNULL(TOTFI, 0) as TOTAL_FALTAS
        FROM dbo.RPHORTOT
        WHERE EMPLEADO = ?
        ORDER BY FECHA_VEN DESC
        """

        cursor.execute(query, [empleado.strip()])
        resultados = cursor.fetchall()

        if resultados:
            columnas = ['FECHA_VEN', 'TOTAUS', 'TOTFJ', 'TOTFI', 'TOTAL_FALTAS']
            df = pd.DataFrame.from_records(resultados, columns=columnas)
            return df

        return pd.DataFrame()

    except Exception as e:
        print(f"Error al consultar faltas: {e}")
        return pd.DataFrame()

def obtener_faltas_historicas(conn, empleado):
    """Obtiene las faltas históricas del empleado desde RPHORHIS (EXCLUYENDO SUSPENSIONES)"""
    try:
        if not conn or not empleado or not empleado.strip():
            return pd.DataFrame()

        cursor = conn.cursor()

        # Query: solo TOTAUS (ausentismo injustificado), capar a 48 hrs si tiene más
        query = """
        SELECT
            FECHA_VEN,
            ISNULL(TOTAUS, 0) as TOTAUS,
            ISNULL(TOTFJ, 0) as TOTFJ,
            ISNULL(TOTFI, 0) as TOTFI,
            CASE WHEN ISNULL(TOTAUS, 0) > 48 THEN 48 ELSE ISNULL(TOTAUS, 0) END as TOTAL_FALTAS,
            DEPTO,
            OBSERV
        FROM dbo.RPHORHIS
        WHERE EMPLEADO = ?
            AND ISNULL(TOTAUS, 0) > 0
            AND UPPER(ISNULL(OBSERV, '')) NOT LIKE '%PERMISO MEDICO%'
            AND UPPER(ISNULL(OBSERV, '')) NOT LIKE '%LICENCIA MEDICA%'
        ORDER BY FECHA_VEN DESC
        """

        cursor.execute(query, [empleado.strip()])
        resultados = cursor.fetchall()

        if resultados:
            columnas = ['FECHA_VEN', 'TOTAUS', 'TOTFJ', 'TOTFI', 'TOTAL_FALTAS', 'DEPTO', 'OBSERV']
            df = pd.DataFrame.from_records(resultados, columns=columnas)

            # Contar registros excluidos (permiso médico, licencias, >48 hrs, etc.)
            query_excluidos = """
            SELECT COUNT(*) as EXCLUIDOS
            FROM dbo.RPHORHIS
            WHERE EMPLEADO = ?
                AND ISNULL(TOTAUS, 0) > 0
                AND (
                    UPPER(ISNULL(OBSERV, '')) LIKE '%PERMISO MEDICO%'
                    OR UPPER(ISNULL(OBSERV, '')) LIKE '%LICENCIA MEDICA%'
                    OR UPPER(ISNULL(OBSERV, '')) LIKE '%VACACION%'
                    OR UPPER(ISNULL(OBSERV, '')) LIKE '%LICENCIA%'
                    OR UPPER(ISNULL(OBSERV, '')) LIKE '%MATERNIDAD%'
                    OR UPPER(ISNULL(OBSERV, '')) LIKE '%PATERNIDAD%'
                    OR ISNULL(TOTAUS, 0) > 48
                )
            """
            cursor.execute(query_excluidos, [empleado.strip()])
            excluidos = cursor.fetchone()[0]

            if excluidos > 0:
                print(f"ℹ️ Se excluyeron {excluidos} período(s) de ausencias justificadas (vacaciones, permisos, licencias, etc.) del empleado {empleado}")

            return df

        return pd.DataFrame()

    except Exception as e:
        print(f"Error al consultar faltas históricas: {e}")
        return pd.DataFrame()

def obtener_datos_empleado(conn, codigo):
    """Obtiene TODOS los datos del empleado por código"""
    try:
        if not conn or not codigo:
            return pd.DataFrame()
        cursor = conn.cursor()

        # Obtener datos del empleado
        query = """
        SELECT
            e.EMPLEADO,
            e.APELLIDOS,
            e.NOMBRES,
            e.CEDULA,
            e.FECHA_ING,
            e.FECHA_SAL,
            e.CODEMP,
            e.CODSUC,
            e.DEPTO,
            e.CARGO,
            e.SEXO,
            e.DIRECCION,
            e.TELEFONO
        FROM dbo.RPEMPLEA e
        WHERE e.EMPLEADO = ?
        """

        cursor.execute(query, [codigo.strip()])
        resultados = cursor.fetchall()

        if resultados:
            columnas = [column[0] for column in cursor.description]
            df = pd.DataFrame.from_records(resultados, columns=columnas)
            
            # Obtener nombre del departamento
            depto_cod = df.iloc[0]['DEPTO'] if 'DEPTO' in df.columns else None
            depto_nombre = ""
            if depto_cod:
                depto_str = str(depto_cod).strip()
                print(f"Buscando depto con código: '{depto_str}'")
                try:
                    cursor.execute("SELECT NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'DPT' AND RTRIM(CODIGO) = ?", [depto_str])
                    resultado = cursor.fetchone()
                    if resultado:
                        depto_nombre = resultado[0]
                        print(f"Departamento encontrado: {depto_nombre}")
                    else:
                        print(f"No se encontró depto para código: '{depto_str}'")
                except Exception as e:
                    print(f"Error depto: {e}")
            
            df.loc[df.index[0], 'NOMBRE_DEPTO'] = depto_nombre if depto_nombre else str(depto_cod) if depto_cod else ""
            
            # Obtener nombre del cargo/puesto
            cargo_cod = df.iloc[0]['CARGO'] if 'CARGO' in df.columns else None
            cargo_nombre = ""
            if cargo_cod:
                cargo_str = str(cargo_cod).strip()
                print(f"Buscando cargo con código: '{cargo_str}'")
                try:
                    # Primero buscar exacto
                    cursor.execute("SELECT NOMBRE FROM dbo.DBTABLAS WHERE TIPO = 'CAR' AND RTRIM(CODIGO) = ?", [cargo_str])
                    resultado = cursor.fetchone()
                    if resultado:
                        cargo_nombre = resultado[0]
                        print(f"Cargo encontrado (CAR): {cargo_nombre}")
                    else:
                        # Si no encuentra, buscar en otros tipos relacionados
                        cursor.execute("SELECT NOMBRE FROM dbo.DBTABLAS WHERE TIPO IN ('CAR', 'PUESTO', 'CARGO', 'OCUP') AND RTRIM(CODIGO) = ?", [cargo_str])
                        resultado = cursor.fetchone()
                        if resultado:
                            cargo_nombre = resultado[0]
                            print(f"Cargo encontrado (otro tipo): {cargo_nombre}")
                        else:
                            print(f"No se encontró cargo para código: '{cargo_str}'")
                except Exception as e:
                    print(f"Error cargo: {e}")
            
            df.loc[df.index[0], 'NOMBRE_PUESTO'] = cargo_nombre if cargo_nombre else str(cargo_cod) if cargo_cod else ""
            
            return df

        return pd.DataFrame()

    except Exception as e:
        print(f"Error al consultar empleado: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()

def buscar_empleados_por_cedula(conn, cedula):
    """Busca empleados por número de cédula"""
    try:
        if not conn or not cedula or not cedula.strip():
            return pd.DataFrame()

        cursor = conn.cursor()

        # Limpiar cédula - solo números
        cedula_limpia = ''.join(filter(str.isdigit, cedula.strip()))
        
        # Buscar por cédula - comparar como número sin ceros iniciales
        # SQL Server guarda la cédula como número, así que comparamos sin los ceros iniciales
        query = """
        SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, FECHA_ING
        FROM dbo.RPEMPLEA
        WHERE CAST(CAST(CEDULA AS BIGINT) AS VARCHAR) LIKE ?
        ORDER BY APELLIDOS, NOMBRES
        """
        
        # Buscar con % al inicio y final para encontrar el número en cualquier parte
        search_term = f"%{cedula_limpia.lstrip('0')}"
        print(f"DEBUG SQL cedula: search_term='{search_term}'")
        cursor.execute(query, [search_term])
        resultados = cursor.fetchall()

        if resultados:
            print(f"DEBUG: encontrados {len(resultados)} empleados por cédula")
            columnas = [column[0] for column in cursor.description]
            return pd.DataFrame.from_records(resultados, columns=columnas)
        
        # Si no encuentra, probar另一种 búsqueda
        query2 = """
        SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, FECHA_ING
        FROM dbo.RPEMPLEA
        WHERE LTRIM(STR(CEDULA, 10)) LIKE ?
        ORDER BY APELLIDOS, NOMBRES
        """
        search_term2 = f"{cedula_limpia}%"
        cursor.execute(query2, [search_term2])
        resultados2 = cursor.fetchall()
        if resultados2:
            print(f"DEBUG: encontrados {len(resultados2)} empleados por cédula (busqueda 2)")
            columnas = [column[0] for column in cursor.description]
            return pd.DataFrame.from_records(resultados2, columns=columnas)

        return pd.DataFrame()

    except Exception as e:
        print(f"Error al buscar por cédula: {e}")
        return pd.DataFrame()

def buscar_empleados_por_nombre(conn, nombre):
    """Busca empleados por nombre y retorna lista de coincidencias con nombre de puesto"""
    try:
        if not conn or not nombre or not nombre.strip():
            return pd.DataFrame()

        cursor = conn.cursor()

        query = """
        SELECT e.EMPLEADO, e.APELLIDOS, e.NOMBRES, e.CEDULA, e.FECHA_ING, e.FECHA_SAL,
               ISNULL(e.CARGO, '') AS CARGO_COD,
               ISNULL(e.DEPTO, '') AS DEPTO_COD,
               ISNULL((
                   SELECT TOP 1 NOMBRE FROM dbo.DBTABLAS
                   WHERE TIPO = 'DPT' AND RTRIM(CODIGO) = RTRIM(ISNULL(e.DEPTO,''))
               ), '') AS NOMBRE_DEPTO,
               ISNULL((
                   SELECT TOP 1 NOMBRE FROM dbo.DBTABLAS
                   WHERE TIPO IN ('CAR', 'PUESTO', 'CARGO', 'OCUP')
                     AND RTRIM(CODIGO) = RTRIM(ISNULL(e.CARGO,''))
                   ORDER BY CASE TIPO WHEN 'CAR' THEN 1 ELSE 2 END
               ), '') AS NOMBRE_CARGO
        FROM dbo.RPEMPLEA e
        WHERE e.APELLIDOS LIKE ? OR e.NOMBRES LIKE ?
              OR (ISNULL(e.APELLIDOS,'') + ' ' + ISNULL(e.NOMBRES,'')) LIKE ?
        ORDER BY e.APELLIDOS, e.NOMBRES
        """

        search_term = f"%{nombre.strip()}%"
        cursor.execute(query, [search_term, search_term, search_term])
        resultados = cursor.fetchall()

        if resultados:
            columnas = [column[0] for column in cursor.description]
            df = pd.DataFrame.from_records(resultados, columns=columnas)
            # Debug: muestra los primeros resultados para verificar puestos/dpto
            for _, row in df.head(3).iterrows():
                print(f"  Emp {row['EMPLEADO']}: CARGO_COD='{row.get('CARGO_COD','')}' NOMBRE_CARGO='{row.get('NOMBRE_CARGO','')}' | DEPTO_COD='{row.get('DEPTO_COD','')}' NOMBRE_DEPTO='{row.get('NOMBRE_DEPTO','')}'")
            return df

        return pd.DataFrame()

    except Exception as e:
        print(f"Error al buscar empleados: {e}")
        return pd.DataFrame()

class VisorEmpleados:
    def __init__(self, root):
        self.root = root
        self.root.title("INSEVIG - Visor de Empleados")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        
        # Icono INSEVIG - Fix para aparecer en taskbar de Windows
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, 'icono.ico')
            else:
                icon_path = "icono.ico"
            
            if os.path.exists(icon_path):
                # iconbitmap para el icono del exe y barra de título
                self.root.iconbitmap(icon_path)
                
                # iconphoto para forzar actualización en la barra de tareas
                # Convertir ICO a PhotoImage (tkinter)
                from PIL import Image
                img = Image.open(icon_path)
                # Usar el tamaño más grande disponible para mejor calidad
                photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, photo)
                # Guardar referencia para evitar garbage collection
                self.root._icon_photo = photo
        except Exception as e:
            print(f"Error cargando icono: {e}")
            pass
        
        # Variables
        self.df_observaciones = None
        self.df_multas = None
        self.df_faltas = None
        self.df_faltas_historicas = None
        self.df_empleado = None
        self.filtro_empleado = None
        self.conn = None
        self.busqueda_exacta = tk.BooleanVar(value=False)
        self._cargando = False

        # Crear interfaz
        self.crear_interfaz()
        
        # Conectar a la base de datos
        self.conectar_db()
    
    def crear_interfaz(self):
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', font=('Arial', 10))
        style.configure('TButton', font=('Arial', 10, 'bold'))
        
        # Header sin color (blanco/gris)
        header = tk.Frame(self.root, bg="#F5F5F5", height=60)
        header.pack(fill=tk.X)
        
        tk.Label(header, text="INSEVIG", font=("Arial", 22, "bold"), 
                bg="#F5F5F5", fg="#1565C0").pack(side=tk.LEFT, padx=20, pady=15)
        
        tk.Label(header, text=f"{datetime.now().strftime('%d/%m/%Y')}", 
                font=("Arial", 10), bg="#F5F5F5", fg="gray").pack(side=tk.RIGHT, padx=20)
        
        # Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestañas
        self.tab_obs = ttk.Frame(self.notebook)
        self.tab_multas = ttk.Frame(self.notebook)
        self.tab_faltas = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_obs, text="📋 Observaciones")
        self.notebook.add(self.tab_multas, text="💰 Multas")
        self.notebook.add(self.tab_faltas, text="⚠️ Faltas")
        
        # Configurar pestañas
        self.configurar_tab_observaciones()
        self.configurar_tab_multas()
        self.configurar_tab_faltas()
        
        # Barra de estado
        self.barra_estado = tk.Label(self.root, text="Listo", relief=tk.SUNKEN, 
                                    anchor=tk.W, bg="#f0f0f0", padx=10)
        self.barra_estado.pack(side=tk.BOTTOM, fill=tk.X)
    
    def configurar_tab_observaciones(self):
        frame = tk.Frame(self.tab_obs, bg="white")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Título
        tk.Label(frame, text="OBSERVACIONES DEL EMPLEADO", font=("Arial", 14, "bold"), 
                bg="#1565C0", fg="white").pack(pady=10)
        
        # Buscador
        buscar_frame = tk.Frame(frame, bg="white")
        buscar_frame.pack(fill=tk.X, pady=5)

        tk.Label(buscar_frame, text="Buscar:", bg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        self.entry_buscar = tk.Entry(buscar_frame, width=35, font=("Arial", 11))
        self.entry_buscar.pack(side=tk.LEFT, padx=5)
        self.entry_buscar.bind("<Return>", lambda e: self.buscar())
        self.entry_buscar.focus()

        self.btn_buscar = tk.Button(buscar_frame, text="🔍 Buscar", command=self.buscar,
                  bg="#1565C0", fg="white", font=("Arial", 10, "bold"))
        self.btn_buscar.pack(side=tk.LEFT, padx=5)

        tk.Button(buscar_frame, text="🖨️ Imprimir", command=self.guardar_texto,
                  bg="#F57C00", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # Ayuda de búsqueda
        ayuda_frame = tk.Frame(frame, bg="white")
        ayuda_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Label(ayuda_frame, text="💡 Ingrese código, cédula o nombre",
                bg="white", fg="#666", font=("Arial", 9, "italic")).pack(side=tk.LEFT, padx=5)
        
        # Panel de datos del empleado - campos copiables
        self.frame_emp = tk.Frame(frame, bg="#f0f4ff", relief='groove', borderwidth=1)
        self.frame_emp.pack(fill=tk.X, padx=5, pady=(4, 2))

        def _entry_info(parent, row, col, label, width, colspan=1):
            tk.Label(parent, text=label, bg="#f0f4ff", font=("Arial", 9, "bold"),
                     anchor='w').grid(row=row, column=col*2, sticky='w', padx=(8, 2), pady=2)
            e = tk.Entry(parent, width=width, font=("Arial", 10), relief='flat',
                         bg="#f0f4ff", readonlybackground="#f0f4ff",
                         disabledforeground="#222", state='normal')
            e.grid(row=row, column=col*2+1, sticky='ew', padx=(0, 10), pady=2,
                   columnspan=colspan)
            return e

        self.frame_emp.columnconfigure(1, weight=3)
        self.frame_emp.columnconfigure(3, weight=1)
        self.frame_emp.columnconfigure(5, weight=1)

        self.einfo_nombre   = _entry_info(self.frame_emp, 0, 0, "Nombre:",      38)
        self.einfo_cedula   = _entry_info(self.frame_emp, 0, 1, "Cédula:",      14)
        self.einfo_cod      = _entry_info(self.frame_emp, 0, 2, "Código:",       8)
        self.einfo_depto    = _entry_info(self.frame_emp, 1, 0, "Departamento:", 28)
        self.einfo_cargo    = _entry_info(self.frame_emp, 1, 1, "Cargo:",        22)
        self.einfo_sexo     = _entry_info(self.frame_emp, 1, 2, "Sexo:",          8)
        self.einfo_ingreso  = _entry_info(self.frame_emp, 2, 0, "Ingreso:",      14)
        self.einfo_salida   = _entry_info(self.frame_emp, 2, 1, "Salida:",       14)
        self.einfo_estado   = _entry_info(self.frame_emp, 2, 2, "Estado:",       10)

        def _set_readonly(e, val):
            e.config(state='normal')
            e.delete(0, 'end')
            e.insert(0, val)
            e.config(state='readonly')

        self._set_einfo = _set_readonly
        # Limpiar panel al inicio
        for e in (self.einfo_nombre, self.einfo_cedula, self.einfo_cod,
                  self.einfo_depto, self.einfo_cargo, self.einfo_sexo,
                  self.einfo_ingreso, self.einfo_salida, self.einfo_estado):
            _set_readonly(e, "")
        
        # Tabla
        table_frame = tk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrolly = tk.Scrollbar(table_frame)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollx = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tabla_obs = ttk.Treeview(table_frame, yscrollcommand=scrolly.set, 
                                      xscrollcommand=scrollx.set, height=15)
        
        scrolly.config(command=self.tabla_obs.yview)
        scrollx.config(command=self.tabla_obs.xview)
        
        self.tabla_obs['columns'] = ('codigo', 'nombre', 'fecha', 'observaciones')
        self.tabla_obs.column('#0', width=0, stretch=False)
        self.tabla_obs.column('codigo', width=80, anchor='center')
        self.tabla_obs.column('nombre', width=200, anchor='w')
        self.tabla_obs.column('fecha', width=100, anchor='center')
        self.tabla_obs.column('observaciones', width=400, anchor='w')

        self.tabla_obs.heading('#0', text='')
        self.tabla_obs.heading('codigo', text='Código')
        self.tabla_obs.heading('nombre', text='Nombre')
        self.tabla_obs.heading('fecha', text='Fecha')
        self.tabla_obs.heading('observaciones', text='Observaciones')
        
        self.tabla_obs.pack(fill=tk.BOTH, expand=True)
        self.tabla_obs.bind("<Double-1>", self.mostrar_detalle)
        
        self.lbl_info_obs = tk.Label(frame, text="Sin datos", bg="white", fg="gray")
        self.lbl_info_obs.pack(pady=5)
    
    def configurar_tab_multas(self):
        frame = tk.Frame(self.tab_multas, bg="white")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(frame, text="MULTAS (Clase 203)", font=("Arial", 14, "bold"), 
                bg="white", fg="#1565C0").pack(pady=10)
        
        table_frame = tk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrolly = tk.Scrollbar(table_frame)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollx = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tabla_mult = ttk.Treeview(table_frame, yscrollcommand=scrolly.set, 
                                      xscrollcommand=scrollx.set, height=15)
        
        scrolly.config(command=self.tabla_mult.yview)
        scrollx.config(command=self.tabla_mult.xview)
        
        self.tabla_mult['columns'] = ('numero', 'fecha', 'valor', 'concepto')
        self.tabla_mult.column('#0', width=0, stretch=False)
        self.tabla_mult.column('numero', width=50, anchor='center')
        self.tabla_mult.column('fecha', width=100, anchor='center')
        self.tabla_mult.column('valor', width=100, anchor='e')
        self.tabla_mult.column('concepto', width=350, anchor='w')
        
        self.tabla_mult.heading('#0', text='')
        self.tabla_mult.heading('numero', text='#')
        self.tabla_mult.heading('fecha', text='Fecha')
        self.tabla_mult.heading('valor', text='Valor')
        self.tabla_mult.heading('concepto', text='Concepto')
        
        self.tabla_mult.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_info_mult = tk.Label(frame, text="Sin datos", bg="white", fg="gray")
        self.lbl_info_mult.pack(pady=5)
    
    def configurar_tab_faltas(self):
        frame = tk.Frame(self.tab_faltas, bg="white")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(frame, text="FALTAS HISTÓRICAS (Solo TOTAUS ≤ 48 hrs)", font=("Arial", 14, "bold"),
                bg="white", fg="#E65100").pack(pady=10)

        # Nota explicativa
        nota_frame = tk.Frame(frame, bg="#FFF3E0", relief=tk.RIDGE, borderwidth=1)
        nota_frame.pack(fill=tk.X, pady=(0, 10), padx=10)
        tk.Label(nota_frame, text="💡 Conversión: 16 horas = 1 día de falta | Si tiene >48 hrs se muestra solo 48 (límite)",
                bg="#FFF3E0", fg="#E65100", font=("Arial", 9, "bold")).pack(pady=2)
        tk.Label(nota_frame, text="⚠️ Se excluyen: PERMISO MEDICO, Licencias, Vacaciones",
                bg="#FFF3E0", fg="#1565C0", font=("Arial", 8, "italic")).pack(pady=2)
        tk.Label(nota_frame, text="✓ Solo TOTAUS (ausentismo injustificado)",
                bg="#FFF3E0", fg="#1565C0", font=("Arial", 8, "bold")).pack(pady=2)
        
        table_frame = tk.Frame(frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrolly = tk.Scrollbar(table_frame)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        
        scrollx = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        scrollx.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tabla_faltas = ttk.Treeview(table_frame, yscrollcommand=scrolly.set, 
                                        xscrollcommand=scrollx.set, height=15)
        
        scrolly.config(command=self.tabla_faltas.yview)
        scrollx.config(command=self.tabla_faltas.xview)
        
        self.tabla_faltas['columns'] = ('periodo', 'ausencias', 'justificadas', 'injustificadas', 'total_hrs', 'dias', 'depto')
        self.tabla_faltas.column('#0', width=0, stretch=False)
        self.tabla_faltas.column('periodo', width=90, anchor='center')
        self.tabla_faltas.column('ausencias', width=75, anchor='center')
        self.tabla_faltas.column('justificadas', width=75, anchor='center')
        self.tabla_faltas.column('injustificadas', width=85, anchor='center')
        self.tabla_faltas.column('total_hrs', width=75, anchor='center')
        self.tabla_faltas.column('dias', width=80, anchor='center')
        self.tabla_faltas.column('depto', width=80, anchor='center')

        self.tabla_faltas.heading('#0', text='')
        self.tabla_faltas.heading('periodo', text='Período')
        self.tabla_faltas.heading('ausencias', text='Ausencias')
        self.tabla_faltas.heading('justificadas', text='Justific.')
        self.tabla_faltas.heading('injustificadas', text='Injustific.')
        self.tabla_faltas.heading('total_hrs', text='Total Hrs')
        self.tabla_faltas.heading('dias', text='Días Faltas')
        self.tabla_faltas.heading('depto', text='Dpto (Cód.)')
        
        self.tabla_faltas.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_info_faltas = tk.Label(frame, text="Sin datos", bg="white", fg="gray")
        self.lbl_info_faltas.pack(pady=5)
    
    def conectar_db(self):
        self.conn = conectar_bd()
        if self.conn:
            self.barra_estado.config(text="✓ Conectado a la base de datos")
        else:
            self.barra_estado.config(text="✗ Error de conexión")

    def _en_hilo(self, fn_db, fn_callback):
        """Ejecuta fn_db en un hilo de fondo y llama fn_callback(resultado) en el hilo principal."""
        def worker():
            try:
                resultado = fn_db()
            except Exception as e:
                print(f"Error en hilo de base de datos: {e}")
                def on_error(err=e):
                    self._set_cargando(False)
                    messagebox.showerror("Error de base de datos", str(err))
                self.root.after(0, on_error)
                return
            self.root.after(0, lambda r=resultado: fn_callback(r))
        threading.Thread(target=worker, daemon=True).start()

    def _set_cargando(self, activo, mensaje=None):
        """Activa o desactiva el indicador de carga y el botón Buscar."""
        self._cargando = activo
        try:
            self.btn_buscar.config(state='disabled' if activo else 'normal')
        except Exception:
            pass
        if mensaje:
            self.barra_estado.config(text=f"⏳ {mensaje}")

    def buscar(self):
        if self._cargando:
            return
        buscar = self.entry_buscar.get().strip()
        if not buscar:
            messagebox.showwarning("Aviso", "Ingrese código, cédula o nombre")
            return

        # Limpiar búsqueda pero mantener ceros al inicio
        solo_digitos = ''.join(filter(str.isdigit, buscar))
        if buscar.startswith('0') and not solo_digitos.startswith('0'):
            solo_digitos = '0' + solo_digitos
        elif buscar.startswith('00') and not solo_digitos.startswith('00'):
            solo_digitos = '00' + solo_digitos

        print(f"DEBUG buscar: '{buscar}' -> solo_digitos: '{solo_digitos}'")

        if solo_digitos and 7 <= len(solo_digitos) <= 10:
            # Probablemente es una cédula — buscar en hilo de fondo
            self._set_cargando(True, "Buscando por cédula...")
            def _buscar_cedula():
                return buscar_empleados_por_cedula(self.conn, solo_digitos)
            def _resultado_cedula(df_result):
                self._set_cargando(False)
                if df_result is None or df_result.empty:
                    messagebox.showwarning("Aviso", f"No se encontró empleado con cédula {buscar}")
                    return
                print(f"DEBUG: resultados cedula: {len(df_result)}")
                if len(df_result) == 1:
                    print(f"DEBUG: cedula encontrada, cargando empleado: {df_result.iloc[0]['EMPLEADO']}")
                    self.cargar_datos(str(df_result.iloc[0]['EMPLEADO']))
                else:
                    self.mostrar_selector_empleados(buscar)
            self._en_hilo(_buscar_cedula, _resultado_cedula)
        elif buscar.isdigit():
            # Búsqueda directa por código numérico
            self.cargar_datos(buscar)
        else:
            # Búsqueda por nombre - mostrar selector
            self.mostrar_selector_empleados(buscar)
    
    def cargar_datos(self, codigo):
        """Carga todos los datos de un empleado en un hilo de fondo para no bloquear la UI."""
        if self._cargando:
            return
        self.filtro_empleado = codigo
        self._set_cargando(True, f"Cargando datos del empleado {codigo}...")

        def _consultar():
            df_emp  = obtener_datos_empleado(self.conn, codigo)
            df_obs  = obtener_observaciones(self.conn, codigo, True)
            df_mult = obtener_multas(self.conn, codigo)
            df_falt = obtener_faltas_historicas(self.conn, codigo)
            return df_emp, df_obs, df_mult, df_falt

        def _actualizar(resultado):
            df_emp, df_obs, df_mult, df_falt = resultado
            self._set_cargando(False)

            if df_emp.empty:
                messagebox.showwarning("Aviso", f"No existe empleado {codigo}")
                self.barra_estado.config(text="✗ Empleado no encontrado")
                return

            emp = df_emp.iloc[0]
            nombre = f"{str(emp['APELLIDOS']).strip()} {str(emp['NOMBRES']).strip()}"
            cedula = formatear_cedula_ec(emp.get('CEDULA', ''))

            depto = ""
            if 'NOMBRE_DEPTO' in emp.index and emp['NOMBRE_DEPTO']:
                depto = str(emp['NOMBRE_DEPTO']).strip()
            if not depto and 'DEPTO' in emp.index and emp['DEPTO']:
                depto = str(emp['DEPTO']).strip()

            puesto = ""
            if 'NOMBRE_PUESTO' in emp.index and emp['NOMBRE_PUESTO']:
                puesto = str(emp['NOMBRE_PUESTO']).strip()
            if not puesto and 'CARGO' in emp.index and emp['CARGO']:
                puesto = str(emp['CARGO']).strip()

            print(f"DEBUG depto final: '{depto}'")
            print(f"DEBUG puesto final: '{puesto}'")

            sexo_raw = emp.get('SEXO', '') or ''
            sexo_texto = {"M": "Masculino", "F": "Femenino"}.get(str(sexo_raw).upper().strip(), str(sexo_raw).strip())

            fecha_ing = emp.get('FECHA_ING', '')
            fecha_ing_str = fecha_ing.strftime('%d/%m/%Y') if pd.notnull(fecha_ing) and hasattr(fecha_ing, 'strftime') else (str(fecha_ing) if pd.notnull(fecha_ing) else '')
            fecha_sal = emp.get('FECHA_SAL', '')
            fecha_sal_str = fecha_sal.strftime('%d/%m/%Y') if pd.notnull(fecha_sal) and hasattr(fecha_sal, 'strftime') else ''
            estado = "ACTIVO" if not fecha_sal_str else "RETIRADO"

            self._set_einfo(self.einfo_nombre,  nombre)
            self._set_einfo(self.einfo_cedula,  cedula)
            self._set_einfo(self.einfo_cod,     str(emp.get('EMPLEADO', '')))
            self._set_einfo(self.einfo_depto,   depto)
            self._set_einfo(self.einfo_cargo,   puesto)
            self._set_einfo(self.einfo_sexo,    sexo_texto)
            self._set_einfo(self.einfo_ingreso, fecha_ing_str)
            self._set_einfo(self.einfo_salida,  fecha_sal_str)
            self._set_einfo(self.einfo_estado,  estado)

            self.df_empleado = df_emp
            self.df_observaciones = df_obs
            self.actualizar_tabla_obs()

            self.df_multas = df_mult
            self.actualizar_tabla_multas()

            self.df_faltas_historicas = df_falt
            self.actualizar_tabla_faltas()

            self.notebook.select(self.tab_obs)
            self.barra_estado.config(text=f"✓ Datos cargados: {nombre}")

        self._en_hilo(_consultar, _actualizar)
    
    def mostrar_selector_empleados(self, nombre):
        """Busca empleados por nombre en hilo de fondo y muestra el selector."""
        if self._cargando:
            return
        self._set_cargando(True, "Buscando empleados...")

        def _buscar():
            return buscar_empleados_por_nombre(self.conn, nombre)

        def _resultado(df_empleados):
            self._set_cargando(False)
            if df_empleados is None or df_empleados.empty:
                messagebox.showwarning("Aviso", f"No se encontraron empleados con '{nombre}'")
                return
            if len(df_empleados) == 1:
                self.cargar_datos(str(df_empleados.iloc[0]['EMPLEADO']))
                return
            self._mostrar_dialogo_selector(df_empleados, nombre)

        self._en_hilo(_buscar, _resultado)

    def _mostrar_dialogo_selector(self, df_empleados, nombre):
        """Muestra ventana para seleccionar un empleado de la búsqueda."""
        # Pre-calcular la columna puesto para cada fila
        filas_datos = []
        for _, fila in df_empleados.iterrows():
            nombre_depto = str(fila.get('NOMBRE_DEPTO', '') or '').strip()
            nombre_cargo = str(fila.get('NOMBRE_CARGO', '') or '').strip()
            depto_cod    = str(fila.get('DEPTO_COD',   '') or '').strip()
            cargo_cod    = str(fila.get('CARGO_COD',   '') or '').strip()
            puesto = nombre_depto or nombre_cargo or depto_cod or cargo_cod
            fecha_sal = fila.get('FECHA_SAL', None)
            activo = not pd.notnull(fecha_sal)
            filas_datos.append({
                'codigo':    str(fila.get('EMPLEADO', '')),
                'apellidos': str(fila.get('APELLIDOS', '') or '').strip(),
                'nombres':   str(fila.get('NOMBRES',   '') or '').strip(),
                'puesto':    puesto,
                'cedula':    formatear_cedula_ec(fila.get('CEDULA', '')),
                'activo':    activo,
            })

        # Lista de puestos únicos para el filtro
        puestos_unicos = sorted({r['puesto'] for r in filas_datos if r['puesto']})

        # ── Ventana ──────────────────────────────────────────────
        selector = tk.Toplevel(self.root)
        selector.title("Seleccionar Empleado")
        selector.geometry("870x600")
        selector.grab_set()
        selector.transient(self.root)

        # Header
        header_frame = tk.Frame(selector, bg="#1565C0", pady=12)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text=f"Se encontraron {len(df_empleados)} empleado(s)",
                 bg="#1565C0", fg="white", font=("Arial", 13, "bold")).pack()
        tk.Label(header_frame, text=f"Búsqueda: '{nombre}'",
                 bg="#1565C0", fg="white", font=("Arial", 10)).pack()

        # ── Barra de filtros ─────────────────────────────────────
        filtro_frame = tk.Frame(selector, bg="#e8eaf6", pady=7, padx=12)
        filtro_frame.pack(fill=tk.X)

        tk.Label(filtro_frame, text="Departamento/Cargo:", bg="#e8eaf6",
                 font=("Arial", 9, "bold")).grid(row=0, column=0, sticky='w', padx=(0, 4))
        filtro_puesto_var = tk.StringVar()
        entry_puesto = tk.Entry(filtro_frame, textvariable=filtro_puesto_var, width=24, font=("Arial", 9))
        entry_puesto.grid(row=0, column=1, padx=(0, 12))

        tk.Label(filtro_frame, text="Nombre:", bg="#e8eaf6",
                 font=("Arial", 9, "bold")).grid(row=0, column=2, sticky='w', padx=(0, 4))
        filtro_nombre_var = tk.StringVar()
        entry_nombre = tk.Entry(filtro_frame, textvariable=filtro_nombre_var, width=20, font=("Arial", 9))
        entry_nombre.grid(row=0, column=3, padx=(0, 14))

        # Filtro de estado: Todos / Activos / Salientes
        filtro_estado_var = tk.StringVar(value="todos")
        estado_frame = tk.Frame(filtro_frame, bg="#e8eaf6")
        estado_frame.grid(row=0, column=4, padx=(0, 10))
        for texto, valor in [("Todos", "todos"), ("Activos", "activos"), ("Salientes", "salientes")]:
            tk.Radiobutton(estado_frame, text=texto, variable=filtro_estado_var, value=valor,
                           bg="#e8eaf6", font=("Arial", 9)).pack(side='left', padx=2)

        lbl_conteo = tk.Label(filtro_frame, text="", bg="#e8eaf6", fg="#1565C0",
                              font=("Arial", 9, "bold"))
        lbl_conteo.grid(row=0, column=5, sticky='w')

        # ── Tabla ────────────────────────────────────────────────
        table_frame = tk.Frame(selector)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 0))

        scrolly = tk.Scrollbar(table_frame)
        scrolly.pack(side=tk.RIGHT, fill=tk.Y)
        scrollx = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        scrollx.pack(side=tk.BOTTOM, fill=tk.X)

        style = ttk.Style()
        style.configure("Selector.Treeview", rowheight=25)

        tabla = ttk.Treeview(table_frame, yscrollcommand=scrolly.set,
                             xscrollcommand=scrollx.set, height=14,
                             style="Selector.Treeview")
        scrolly.config(command=tabla.yview)
        scrollx.config(command=tabla.xview)

        tabla['columns'] = ('codigo', 'apellidos', 'nombres', 'puesto', 'cedula')
        tabla.column('#0',       width=0,   stretch=False)
        tabla.column('codigo',   width=75,  anchor='center')
        tabla.column('apellidos',width=185, anchor='w')
        tabla.column('nombres',  width=175, anchor='w')
        tabla.column('puesto',   width=220, anchor='w')
        tabla.column('cedula',   width=110, anchor='center')

        tabla.heading('codigo',    text='Código')
        tabla.heading('apellidos', text='Apellidos')
        tabla.heading('nombres',   text='Nombres')
        tabla.heading('puesto',    text='Departamento / Cargo')
        tabla.heading('cedula',    text='Cédula')

        tabla.tag_configure('evenrow', background='#f5f5f5')
        tabla.tag_configure('oddrow',  background='white')
        tabla.pack(fill=tk.BOTH, expand=True)

        # ── Función para repoblar la tabla con filtros ────────────
        def repoblar(*_):
            filtro_puesto = filtro_puesto_var.get().strip().upper()
            filtro_nom    = filtro_nombre_var.get().strip().upper()
            filtro_estado = filtro_estado_var.get()

            for item in tabla.get_children():
                tabla.delete(item)

            visibles = 0
            for r in filas_datos:
                if filtro_puesto and filtro_puesto not in r['puesto'].upper():
                    continue
                if filtro_nom and filtro_nom not in (r['apellidos'] + ' ' + r['nombres']).upper():
                    continue
                if filtro_estado == 'activos' and not r['activo']:
                    continue
                if filtro_estado == 'salientes' and r['activo']:
                    continue
                tag = 'evenrow' if visibles % 2 == 0 else 'oddrow'
                tabla.insert('', 'end', values=(
                    r['codigo'], r['apellidos'], r['nombres'], r['puesto'], r['cedula']
                ), tags=(tag,))
                visibles += 1

            lbl_conteo.config(text=f"{visibles} de {len(filas_datos)}")

            hijos = tabla.get_children()
            if hijos:
                tabla.selection_set(hijos[0])
                tabla.focus(hijos[0])

        filtro_puesto_var.trace_add("write", repoblar)
        filtro_nombre_var.trace_add("write", repoblar)
        filtro_estado_var.trace_add("write", repoblar)

        # Poblar inicialmente
        repoblar()

        # ── Seleccionar empleado ──────────────────────────────────
        def seleccionar_empleado(event=None):
            seleccion = tabla.selection()
            if not seleccion:
                messagebox.showwarning("Aviso", "Por favor seleccione un empleado")
                return
            codigo_empleado = tabla.item(seleccion[0], 'values')[0]
            selector.destroy()
            self.cargar_datos(codigo_empleado)

        tabla.bind("<Double-1>", seleccionar_empleado)
        tabla.bind("<Return>",   seleccionar_empleado)

        # ── Botones ───────────────────────────────────────────────
        btn_frame = tk.Frame(selector, bg="white")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Ver Empleado Seleccionado", command=seleccionar_empleado,
                  bg="#1565C0", fg="white", font=("Arial", 11, "bold"),
                  padx=15, pady=7).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancelar", command=selector.destroy,
                  bg="#666", fg="white", font=("Arial", 11),
                  padx=15, pady=7).pack(side=tk.LEFT, padx=5)

        # Footer
        info_frame = tk.Frame(selector, bg="#f0f0f0")
        info_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(info_frame, text="Tip: Use las flechas arriba/abajo para navegar y Enter para seleccionar",
                 bg="#f0f0f0", fg="#666", font=("Arial", 9)).pack(pady=4)
    
    def mostrar_todos(self):
        self.filtro_empleado = None
        self.df_empleado = None
        for e in (self.einfo_nombre, self.einfo_cedula, self.einfo_cod,
                  self.einfo_depto, self.einfo_cargo, self.einfo_sexo,
                  self.einfo_ingreso, self.einfo_salida, self.einfo_estado):
            self._set_einfo(e, "")

        self.df_observaciones = obtener_observaciones(self.conn)
        self.actualizar_tabla_obs()

        self.df_multas = pd.DataFrame()
        self.actualizar_tabla_multas()

        self.df_faltas = pd.DataFrame()
        self.df_faltas_historicas = pd.DataFrame()
        self.actualizar_tabla_faltas()
    
    def actualizar_tabla_obs(self):
        for item in self.tabla_obs.get_children():
            self.tabla_obs.delete(item)

        if self.df_observaciones is None or self.df_observaciones.empty:
            self.lbl_info_obs.config(text="Sin observaciones")
            return

        total = len(self.df_observaciones)
        empleados_unicos = self.df_observaciones['empleado'].nunique() if 'empleado' in self.df_observaciones.columns else 0
        self.lbl_info_obs.config(text=f"Total: {total} observaciones de {empleados_unicos} empleado(s)", fg="#1565C0")

        for i, fila in self.df_observaciones.iterrows():
            fecha = fila.get('fecha_ven', '')
            if pd.notnull(fecha):
                fecha_str = fecha.strftime('%d/%m/%Y') if hasattr(fecha, 'strftime') else str(fecha)
            else:
                fecha_str = ""

            # Nombre completo
            apellidos = str(fila.get('APELLIDOS', '')).strip() if pd.notnull(fila.get('APELLIDOS')) else ''
            nombres = str(fila.get('NOMBRES', '')).strip() if pd.notnull(fila.get('NOMBRES')) else ''
            nombre_completo = f"{apellidos} {nombres}".strip()

            obs = ""
            for j in range(1, 8):
                campo = f'refer{j}'
                if campo in fila and pd.notnull(fila[campo]) and str(fila[campo]).strip():
                    if obs: obs += "  "
                    obs += str(fila[campo]).strip()

            obs_display = obs[:60] + "..." if len(obs) > 60 else obs

            self.tabla_obs.insert('', 'end', values=(
                str(fila.get('empleado', '')),
                nombre_completo,
                fecha_str,
                obs_display
            ))
    
    def actualizar_tabla_multas(self):
        for item in self.tabla_mult.get_children():
            self.tabla_mult.delete(item)
        
        if self.df_multas is None or self.df_multas.empty:
            self.lbl_info_mult.config(text="Sin multas")
            return
        
        total = len(self.df_multas)
        valor = self.df_multas['VALOR'].sum() if 'VALOR' in self.df_multas.columns else 0
        self.lbl_info_mult.config(text=f"Total: {total} multas | Valor: ${valor:.2f}", fg="#1565C0")
        
        for i, fila in self.df_multas.iterrows():
            fecha = fila.get('FECHA', '')
            if pd.notnull(fecha):
                fecha_str = fecha.strftime('%d/%m/%Y') if hasattr(fecha, 'strftime') else str(fecha)
            else:
                fecha_str = ""
            
            valor = fila.get('VALOR', 0)
            valor_str = f"{valor:.2f}" if pd.notnull(valor) else "0.00"
            
            self.tabla_mult.insert('', 'end', values=(
                fila.get('NUMERO', ''),
                fecha_str,
                valor_str,
                str(fila.get('CONCEPTO', ''))[:50]
            ))
    
    def actualizar_tabla_faltas(self):
        for item in self.tabla_faltas.get_children():
            self.tabla_faltas.delete(item)

        if self.df_faltas_historicas is None or self.df_faltas_historicas.empty:
            self.lbl_info_faltas.config(text="Sin faltas históricas registradas")
            return

        total = len(self.df_faltas_historicas)
        hrs_total = self.df_faltas_historicas['TOTAL_FALTAS'].sum() if 'TOTAL_FALTAS' in self.df_faltas_historicas.columns else 0
        dias_total = hrs_total / 16  # Convertir horas a días (16 horas = 1 día)
        self.lbl_info_faltas.config(text=f"Total: {total} períodos | {hrs_total:.0f} horas ({dias_total:.1f} días de faltas)", fg="#E65100")

        for i, fila in self.df_faltas_historicas.iterrows():
            fecha = fila.get('FECHA_VEN', '')
            if pd.notnull(fecha):
                fecha_str = fecha.strftime('%Y-%m') if hasattr(fecha, 'strftime') else str(fecha)[:7]
            else:
                fecha_str = ""

            # Calcular días de falta (16 horas = 1 día)
            total_hrs = fila.get('TOTAL_FALTAS', 0)
            dias_faltas = total_hrs / 16

            # Resaltar en rojo si tiene más de 3 días de falta (48 horas, ya que 16 hrs = 1 día)
            tags = ('alto',) if total_hrs > 48 else ()

            self.tabla_faltas.insert('', 'end', values=(
                fecha_str,
                f"{fila.get('TOTAUS', 0):.0f}",
                f"{fila.get('TOTFJ', 0):.0f}",
                f"{fila.get('TOTFI', 0):.0f}",
                f"{total_hrs:.0f}",
                f"{dias_faltas:.1f}"
            ), tags=tags)

        # Configurar tag para resaltar
        self.tabla_faltas.tag_configure('alto', background='#FFEBEE', foreground='#1565C0')
    
    def mostrar_detalle(self, event):
        seleccion = self.tabla_obs.selection()
        if not seleccion:
            return

        valores = self.tabla_obs.item(seleccion[0], 'values')
        if len(valores) < 4:
            return

        codigo_empleado = valores[0]
        nombre_empleado = valores[1]

        # Si ya estamos viendo un empleado específico, mostrar detalle de observación
        # Si estamos en vista de "Todos", ofrecer cargar el empleado completo
        if self.filtro_empleado and self.filtro_empleado == codigo_empleado:
            # Mostrar detalle de la observación
            self.mostrar_detalle_observacion(codigo_empleado, nombre_empleado, seleccion[0])
        else:
            # Cargar empleado completo directamente
            self.cargar_datos(codigo_empleado)

    def mostrar_detalle_observacion(self, codigo_empleado, nombre_empleado, idx_seleccion):
        """Muestra el detalle completo de una observación"""
        detalle = tk.Toplevel(self.root)
        detalle.title(f"Observación - {nombre_empleado}")
        detalle.geometry("700x500")

        frame = tk.Frame(detalle, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Header con info del empleado
        header_frame = tk.Frame(frame, bg="#1565C0", pady=10)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(header_frame, text=f"👤 {nombre_empleado}",
                bg="#1565C0", fg="white", font=("Arial", 12, "bold")).pack()
        tk.Label(header_frame, text=f"Código: {codigo_empleado}",
                bg="#1565C0", fg="white", font=("Arial", 10)).pack()

        # Observaciones completas
        idx = int(idx_seleccion)
        obs_completo = ""
        for j in range(1, 8):
            campo = f'refer{j}'
            if campo in self.df_observaciones.iloc[idx] and pd.notnull(self.df_observaciones.iloc[idx][campo]):
                if obs_completo: obs_completo += "\n\n"
                obs_completo += f"[Campo {j}]\n" + str(self.df_observaciones.iloc[idx][campo])

        txt = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=80, height=20, font=("Arial", 10))
        txt.pack(fill=tk.BOTH, expand=True, pady=5)
        txt.insert(tk.INSERT, obs_completo if obs_completo else "Sin observaciones detalladas")
        txt.config(state=tk.DISABLED)

        # Botones
        btn_frame = tk.Frame(frame)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Cerrar", command=detalle.destroy,
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
    
    def generar_seccion_datos_empleado(self):
        """Genera HTML con todos los datos del empleado"""
        if self.df_empleado is None or self.df_empleado.empty:
            return ""

        emp = self.df_empleado.iloc[0]

        # Datos básicos
        codigo = emp.get('EMPLEADO', '')
        apellidos = emp.get('APELLIDOS', '')
        nombres = emp.get('NOMBRES', '')
        cedula = formatear_cedula_ec(emp.get('CEDULA', ''))

        # Fechas
        fecha_ing = emp.get('FECHA_ING', '')
        fecha_ing_str = fecha_ing.strftime('%d/%m/%Y') if pd.notnull(fecha_ing) and hasattr(fecha_ing, 'strftime') else str(fecha_ing) if pd.notnull(fecha_ing) else 'N/A'

        fecha_sal = emp.get('FECHA_SAL', '')
        fecha_sal_str = fecha_sal.strftime('%d/%m/%Y') if pd.notnull(fecha_sal) and hasattr(fecha_sal, 'strftime') else 'ACTIVO'

        # Organización - USAR NOMBRES en lugar de códigos
        depto_cod = str(emp.get('DEPTO', '')).strip() if emp.get('DEPTO') else ''
        depto_nom = str(emp.get('NOMBRE_DEPTO', '')).strip() if emp.get('NOMBRE_DEPTO') else ''
        depto = depto_nom if depto_nom else depto_cod if depto_cod else 'N/A'
        
        cargo_cod = str(emp.get('CARGO', '')).strip() if emp.get('CARGO') else ''
        cargo_nom = str(emp.get('NOMBRE_PUESTO', '')).strip() if emp.get('NOMBRE_PUESTO') else ''
        cargo = cargo_nom if cargo_nom else cargo_cod if cargo_cod else 'N/A'

        # Sexo - convertir a texto legible
        sexo_raw = emp.get('SEXO', '')
        if sexo_raw:
            sexo_upper = str(sexo_raw).upper().strip()
            if sexo_upper == 'M':
                sexo = "Masculino"
            elif sexo_upper == 'F':
                sexo = "Femenino"
            else:
                sexo = str(sexo_raw)
        else:
            sexo = 'N/A'

        direccion = emp.get('DIRECCION', 'N/A') if pd.notnull(emp.get('DIRECCION')) else 'N/A'
        telefono = emp.get('TELEFONO', 'N/A') if pd.notnull(emp.get('TELEFONO')) else 'N/A'

        html = f"""
    <div style="background-color:#FFFFFF; border:2px solid #1565C0; border-radius:5px; padding:8px; margin:5px auto; width:60%;">
        <h3 style="margin:0 0 8px 0; color:#1565C0; text-align:center; font-size:16px;">
            👤 DATOS DEL EMPLEADO - INSEVIG
        </h3>
        <table style="width:100%; border:none; font-size:14px; margin:0 auto;">
            <tr>
                <td style="border:none; padding:3px;"><strong>Cód:</strong> {codigo}</td>
                <td style="border:none; padding:3px;"><strong>Céd:</strong> {cedula}</td>
                <td style="border:none; padding:3px;"><strong>Sexo:</strong> {sexo}</td>
                <td style="border:none; padding:3px;"><strong>Ing:</strong> {fecha_ing_str}</td>
                <td style="border:none; padding:3px;"><strong>Sal:</strong> {fecha_sal_str}</td>
            </tr>
            <tr>
                <td style="border:none; padding:3px;" colspan="5"><strong>Nombre:</strong> {apellidos}, {nombres}</td>
            </tr>
            <tr>
                <td style="border:none; padding:3px;"><strong>Dpto:</strong> {depto}</td>
                <td style="border:none; padding:3px;" colspan="4"><strong>Cargo:</strong> {cargo}</td>
            </tr>
        </table>
    </div>
"""
        return html

    def guardar_texto(self):
        if ((self.df_observaciones is None or self.df_observaciones.empty) and
            (self.df_multas is None or self.df_multas.empty) and
            (self.df_faltas_historicas is None or self.df_faltas_historicas.empty)):
            messagebox.showinfo("Info", "No hay datos para guardar")
            return

        # Generar archivo HTML temporal
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(temp_dir, f"reporte_empleados_{timestamp}.html")

        try:
            # Obtener código del empleado
            codigo_empleado = ""
            if self.df_observaciones is not None and not self.df_observaciones.empty:
                codigo_empleado = str(self.df_observaciones.iloc[0]['empleado']) if self.df_observaciones.iloc[0]['empleado'] is not None else ""
            elif self.df_multas is not None and not self.df_multas.empty:
                codigo_empleado = str(self.df_multas.iloc[0]['EMPLEADO']) if self.df_multas.iloc[0]['EMPLEADO'] is not None else ""

            # Obtener nombre y cédula del empleado PRIMERO
            nombre_completo = ""
            cedula_empleado = ""
            if self.df_empleado is not None and not self.df_empleado.empty:
                emp = self.df_empleado.iloc[0]
                nombre_completo = f"{emp.get('APELLIDOS', '')} {emp.get('NOMBRES', '')}".strip()
                cedula_empleado = formatear_cedula_ec(emp.get('CEDULA', ''))

            # Datos para el encabezado
            empresa = "INSEVIG CIA LTDA."
            fecha_actual = datetime.now().strftime('%d %B del %Y Hora:%H:%M:%S')
            username = os.getenv('USERNAME', 'USUARIO')
            titulo = "Informe Completo del Empleado"

            subtitulo = f"Código: {codigo_empleado}"
            if nombre_completo:
                subtitulo += f" - {nombre_completo}"
            if cedula_empleado:
                subtitulo += f" | CI: {cedula_empleado}"

            with open(file_path, 'w', encoding='utf-8') as f:
                # Calcular totales
                total_obs = len(self.df_observaciones) if self.df_observaciones is not None and not self.df_observaciones.empty else 0
                total_multas = len(self.df_multas) if self.df_multas is not None and not self.df_multas.empty else 0
                valor_multas = self.df_multas['VALOR'].sum() if total_multas > 0 else 0
                total_faltas_hrs = self.df_faltas_historicas['TOTAL_FALTAS'].sum() if self.df_faltas_historicas is not None and not self.df_faltas_historicas.empty else 0
                total_faltas_dias = total_faltas_hrs / 16
                total_registros_faltas = len(self.df_faltas_historicas) if self.df_faltas_historicas is not None and not self.df_faltas_historicas.empty else 0

                # Escribir HTML
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{titulo}</title>
    <link rel="icon" type="image/x-icon" href="icono.ico">
    <style>
        @page {{ size: A4 portrait; margin: 1.5cm; }}
        body {{ font-family: Arial, sans-serif; font-size: 12px; line-height: 1.3; }}
        .header {{ margin-bottom: 15px; }}
        .empresa {{ font-weight: bold; }}
        .pagina {{ text-align: right; }}
        .titulo {{ text-align: center; font-size: 18px; font-weight: bold; margin: 20px 0 5px 0; }}
        .subtitulo {{ text-align: center; font-size: 16px; font-weight: bold; margin-bottom: 20px; }}

        .resumen-box {{
            background-color: #E3F2FD;
            border: 2px solid #4CAF50;
            padding: 15px;
            margin: 20px auto;
            border-radius: 5px;
            width: 60%;
        }}
        .resumen-titulo {{
            font-size: 16px;
            font-weight: bold;
            color: #1565C0;
            margin-bottom: 10px;
            text-align: center;
        }}
        .resumen-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 10px;
        }}
        .resumen-item {{
            text-align: center;
            padding: 10px;
            background-color: white;
            border-radius: 4px;
        }}
        .resumen-label {{
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
        }}
        .resumen-valor {{
            font-size: 24px;
            font-weight: bold;
            color: #1565C0;
        }}

        .seccion-titulo {{ font-size: 16px; font-weight: bold; margin: 25px 0 10px 0;
                          padding: 5px; background-color: #f0f0f0; border-left: 4px solid #4CAF50; }}
        .observacion {{ margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px dashed #ccc; }}
        .multa {{ margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px dashed #ccc; }}
        .fecha {{ font-weight: bold; margin-top: 15px; }}
        .contenido {{ margin-left: 20px; text-align: justify; }}
        .valor {{ font-weight: bold; color: #1565C0; }}
        .concepto {{ font-weight: bold; margin-top: 5px; }}
        hr {{ border: 1px solid #000; margin: 5px 0; }}
        @media print {{
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="text-align: center; padding: 10px; background-color: #ffffe0; margin-bottom: 20px;">
        <p>Este documento está listo para imprimir. Utilice Ctrl+P o el botón de imprimir del navegador.</p>
        <button onclick="window.print()">Imprimir Ahora</button>
    </div>

    <div class="header">
        <div class="empresa">{empresa}</div>
        <div class="usuario">{username} Emisión: {fecha_actual}</div>
        <div class="pagina">Page 1</div>
    </div>

    <hr>

    <div class="titulo">{titulo}</div>
    <div class="subtitulo">{subtitulo}</div>

    """ + self.generar_seccion_datos_empleado() + f"""

    <div class="resumen-box">
        <div class="resumen-titulo">📊 RESUMEN GENERAL</div>
        <div class="resumen-grid">
            <div class="resumen-item">
                <div class="resumen-label">📋 Observaciones</div>
                <div class="resumen-valor">{total_obs}</div>
            </div>
            <div class="resumen-item">
                <div class="resumen-label">💰 Total Multas</div>
                <div class="resumen-valor">{total_multas}</div>
                <div class="resumen-label">${valor_multas:.2f}</div>
            </div>
            <div class="resumen-item">
                <div class="resumen-label">⚠️ Faltas Históricas</div>
                <div class="resumen-valor">{total_faltas_dias:.1f}</div>
                <div class="resumen-label">días ({total_faltas_hrs:.0f} hrs)</div>
            </div>
        </div>
    </div>
""")

                # OBSERVACIONES
                if self.df_observaciones is not None and not self.df_observaciones.empty:
                    f.write('<div class="seccion-titulo">OBSERVACIONES DEL EMPLEADO</div>\n')

                    for i, fila in self.df_observaciones.iterrows():
                        # Formatear fecha
                        fecha = fila.get('fecha_ven', '')
                        if pd.notnull(fecha):
                            fecha_str = fecha.strftime('%d/%m/%Y') if hasattr(fecha, 'strftime') else str(fecha)
                        else:
                            fecha_str = ""

                        # Combinar observaciones
                        observaciones = ""
                        for j in range(1, 8):  # refer1 a refer7
                            campo = f'refer{j}'
                            if campo in fila and pd.notnull(fila[campo]) and str(fila[campo]).strip():
                                if observaciones:
                                    observaciones += " "
                                observaciones += str(fila[campo]).strip()

                        if not observaciones.strip():
                            continue  # Saltar registros sin observaciones

                        # Escapar HTML
                        observaciones = observaciones.replace("<", "&lt;").replace(">", "&gt;")

                        # Agregar observación
                        f.write(f"""
                <div class="observacion">
                    <div class="fecha">Fecha: {fecha_str}</div>
                    <div class="contenido">{observaciones}</div>
                </div>
                """)

                # MULTAS
                if self.df_multas is not None and not self.df_multas.empty:
                    f.write('<div class="seccion-titulo">MULTAS DEL EMPLEADO (CLASE 203)</div>\n')

                    # Agregar detalle de cada multa
                    for i, fila in self.df_multas.iterrows():
                        # Formatear fecha
                        fecha = fila.get('FECHA', '')
                        if pd.notnull(fecha):
                            fecha_str = fecha.strftime('%d/%m/%Y') if hasattr(fecha, 'strftime') else str(fecha)
                        else:
                            fecha_str = ""

                        # Formatear valor
                        valor = fila.get('VALOR', 0)
                        if pd.notnull(valor):
                            valor_str = f"{valor:.2f}"
                        else:
                            valor_str = ""

                        # Obtener concepto y observaciones
                        concepto = fila.get('CONCEPTO', '') if pd.notnull(fila.get('CONCEPTO')) else ""
                        observ = fila.get('OBSERV', '') if pd.notnull(fila.get('OBSERV')) else ""

                        # Escapar HTML
                        concepto = concepto.replace("<", "&lt;").replace(">", "&gt;")
                        observ = observ.replace("<", "&lt;").replace(">", "&gt;")

                        # Agregar multa detallada
                        f.write(f"""
                <div class="multa">
                    <div><strong>Número:</strong> {fila.get('NUMERO', '')} - <strong>Fecha:</strong> {fecha_str}</div>
                    <div class="valor">Valor: ${valor_str}</div>
                    <div class="concepto">Concepto: {concepto}</div>
                    <div class="contenido">{observ}</div>
                </div>
                """)
                # FALTAS HISTÓRICAS - NO INCLUIR EN REPORTE
                """
                # if self.df_faltas_historicas is not None and not self.df_faltas_historicas.empty:
                #     f.write('<div class="seccion-titulo">FALTAS HISTÓRICAS DEL EMPLEADO</div>\n')
                #     f.write('<div style="background-color:#FFF9C4; padding:10px; margin-bottom:10px; border-left:4px solid #F57C00; font-size:11px; border-radius:4px;">')
                #     f.write('<strong>⚠️ EXCLUSIONES:</strong> ')
                #     f.write('Se excluyen: PERMISO MEDICO, Licencias, Vacaciones.<br>')
                #     f.write('<strong>✓ Solo TOTAUS</strong> (ausentismo injustificado). Si >48 hrs se muestra solo 48 (límite).<br>')
                #     f.write('<strong>📊 Conversión:</strong> 16 horas = 1 día de falta. | ')
                #     f.write('</div>\n')
                #     f.write('<table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:11px;">\n')
                #     f.write('<tr style="background-color:#f2f2f2;">')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:left; width:12%;">Período</th>')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:center; width:15%;">Ausencias (hrs)</th>')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:center; width:15%;">Justif. (hrs)</th>')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:center; width:15%;">Injustif. (hrs)</th>')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:center; width:13%;">Total Hrs</th>')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:center; background-color:#E3F2FD; width:15%;">🗓️ Días</th>')
                #     f.write('<th style="border:1px solid #ddd; padding:6px; text-align:left; width:15%;">Dpto (Cód.)</th>')
                #     f.write('</tr>\n')
                #
                #     for i, fila in self.df_faltas_historicas.iterrows():
                #         fecha = fila.get('FECHA_VEN', '')
                #         if pd.notnull(fecha):
                #             fecha_str = fecha.strftime('%Y-%m') if hasattr(fecha, 'strftime') else str(fecha)[:7]
                #         else:
                #             fecha_str = ""
                #
                #         depto = str(fila.get('DEPTO', '')) if pd.notnull(fila.get('DEPTO')) else ''
                #
                #         total_hrs = fila.get("TOTAL_FALTAS", 0)
                #         dias_faltas = total_hrs / 16
                #
                #         estilo_total = 'font-weight:bold; color:#1565C0;' if total_hrs > 48 else 'font-weight:bold;'
                #         estilo_fila = 'background-color:#FFEBEE;' if total_hrs > 48 else ''
                #
                #         f.write(f'<tr style="{estilo_fila}">')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px;">{fecha_str}</td>')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px; text-align:center;">{fila.get("TOTAUS", 0):.0f}</td>')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px; text-align:center;">{fila.get("TOTFJ", 0):.0f}</td>')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px; text-align:center;">{fila.get("TOTFI", 0):.0f}</td>')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px; text-align:center; {estilo_total}">{total_hrs:.0f}</td>')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px; text-align:center; font-weight:bold; background-color:#E3F2FD;">{dias_faltas:.1f}</td>')
                #         f.write(f'<td style="border:1px solid #ddd; padding:6px;">{depto}</td>')
                #         f.write('</tr>\n')
                #
                #     f.write('</table>\n')
                #
                #     total_ausencias = self.df_faltas_historicas['TOTAUS'].sum()
                #     total_justif = self.df_faltas_historicas['TOTFJ'].sum()
                #     total_injustif = self.df_faltas_historicas['TOTFI'].sum()
                #     total_general = self.df_faltas_historicas['TOTAL_FALTAS'].sum()
                #     total_dias = total_general / 16
                #
                #     f.write(f'<div style="margin-top:10px; padding:12px; background-color:#FFF3E0; border-left:4px solid #F57C00; border-radius:4px;">')
                #     f.write(f'<strong style="font-size:13px;">📊 RESUMEN DE FALTAS:</strong><br>')
                #     f.write(f'<div style="margin-top:8px; font-size:12px;">')
                #     f.write(f'• Total Ausencias: <strong>{total_ausencias:.0f} hrs</strong> ({total_ausencias/16:.1f} días)<br>')
                #     f.write(f'• Justificadas: <strong>{total_justif:.0f} hrs</strong> ({total_justif/16:.1f} días)<br>')
                #     f.write(f'• Injustificadas: <strong>{total_injustif:.0f} hrs</strong> ({total_injustif/16:.1f} días)<br>')
                #     f.write(f'<div style="margin-top:8px; padding:8px; background-color:#FF9800; color:white; border-radius:3px; text-align:center;">')
                #     f.write(f'<strong style="font-size:14px;">TOTAL GENERAL: {total_general:.0f} horas = {total_dias:.1f} días de faltas</strong>')
                #     f.write(f'</div>')
                #     f.write(f'</div>')
                #     f.write(f'</div>\n')
                """

                # Cerrar HTML
                f.write('</body>\n</html>')

            # Abrir en el navegador
            webbrowser.open(f'file:///{file_path}')

            self.barra_estado.config(text=f"✓ Reporte generado y abierto en navegador")
            messagebox.showinfo("Éxito", f"Reporte generado y abierto en el navegador\n\nUbicación:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar reporte:\n{e}")
            print(f"Error detallado: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VisorEmpleados(root)
    root.mainloop()
