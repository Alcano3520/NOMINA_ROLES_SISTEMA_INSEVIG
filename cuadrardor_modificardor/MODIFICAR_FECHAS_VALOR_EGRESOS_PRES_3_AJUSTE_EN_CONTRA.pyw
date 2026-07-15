import pyodbc
import pandas as pd
import os
import sys
import json
import tkinter as tk
from tkinter import messagebox, StringVar, Entry, Label, Button, Frame, IntVar, Checkbutton
import tkinter.ttk as ttk  # Importar ttk como un módulo separado
from tkinter.scrolledtext import ScrolledText
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import calendar
from dateutil.relativedelta import relativedelta
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import subprocess

# Configuración de carpetas para logs y respaldos
CARPETA_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs_modificaciones")
CARPETA_RESPALDOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "respaldos_egresos")

# Crear carpetas si no existen
for carpeta in [CARPETA_LOGS, CARPETA_RESPALDOS]:
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)

def abrir_ruta_multiplataforma(ruta):
    """Abre un archivo o carpeta con la aplicación predeterminada del sistema (Windows/Linux/Mac)"""
    if sys.platform.startswith('win'):
        os.startfile(ruta)
    elif sys.platform == 'darwin':
        subprocess.run(['open', ruta])
    else:
        subprocess.run(['xdg-open', ruta])

def registrar_log(tipo_operacion, detalles, exito=True):
    """Registra una operación en el archivo de log"""
    try:
        fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        archivo_log = os.path.join(CARPETA_LOGS, f"log_{datetime.now().strftime('%Y%m')}.txt")

        estado = "EXITOSO" if exito else "ERROR"

        with open(archivo_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{fecha_hora}] {tipo_operacion} - {estado}\n")
            f.write(f"{'-'*80}\n")
            if isinstance(detalles, dict):
                for key, value in detalles.items():
                    f.write(f"  {key}: {value}\n")
            else:
                f.write(f"  {detalles}\n")
            f.write(f"{'='*80}\n")

        return True
    except Exception as e:
        print(f"Error al registrar log: {e}")
        return False

def crear_respaldo_egresos(conn, empleados_numeros, motivo):
    """Crea un respaldo de los registros antes de modificarlos"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo_respaldo = os.path.join(CARPETA_RESPALDOS, f"respaldo_{timestamp}.json")

        cursor = conn.cursor()
        respaldo_data = {
            "fecha_respaldo": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "motivo": motivo,
            "registros": []
        }

        for codigo_empleado, numeros in empleados_numeros.items():
            for numero in numeros:
                # Obtener datos actuales del registro
                query = """
                SELECT NUMERO, FECHA, EMPLEADO, CODSUC, CODEMP, CODIGO, CLASE, SECUENCIA,
                       DEPTO, SECCION, HORAS, VALOR, FECHA_VEN, CONCEPTO, DIAS,
                       ASENTADO, ACTUALIZA, APORTA, MONTO, DIVIDENDO, ROL, TIPO_PGO, TIPO_TRA, OBSERV
                FROM [insevig].[dbo].[RPINGDES]
                WHERE EMPLEADO = ? AND NUMERO = ? AND CODIGO = 'EGR'
                """
                cursor.execute(query, (codigo_empleado, numero))
                registros = cursor.fetchall()

                for reg in registros:
                    registro_dict = {
                        "NUMERO": reg[0],
                        "FECHA": reg[1].strftime("%Y-%m-%d") if reg[1] else None,
                        "EMPLEADO": reg[2],
                        "CODSUC": reg[3],
                        "CODEMP": reg[4],
                        "CODIGO": reg[5],
                        "CLASE": reg[6],
                        "SECUENCIA": reg[7],
                        "DEPTO": reg[8],
                        "SECCION": reg[9],
                        "HORAS": reg[10],
                        "VALOR": float(reg[11]) if reg[11] else None,
                        "FECHA_VEN": reg[12].strftime("%Y-%m-%d") if reg[12] else None,
                        "CONCEPTO": reg[13],
                        "DIAS": reg[14],
                        "ASENTADO": bool(reg[15]),
                        "ACTUALIZA": bool(reg[16]),
                        "APORTA": bool(reg[17]),
                        "MONTO": float(reg[18]) if reg[18] else None,
                        "DIVIDENDO": reg[19],
                        "ROL": reg[20],
                        "TIPO_PGO": reg[21],
                        "TIPO_TRA": reg[22],
                        "OBSERV": reg[23]
                    }
                    respaldo_data["registros"].append(registro_dict)

        # Guardar respaldo
        with open(archivo_respaldo, "w", encoding="utf-8") as f:
            json.dump(respaldo_data, f, indent=2, ensure_ascii=False)

        registrar_log("RESPALDO_CREADO", {
            "archivo": archivo_respaldo,
            "registros": len(respaldo_data["registros"]),
            "motivo": motivo
        })

        return archivo_respaldo

    except Exception as e:
        registrar_log("ERROR_RESPALDO", {"error": str(e)}, exito=False)
        return None

def restaurar_desde_respaldo(conn, archivo_respaldo):
    """Restaura los registros desde un archivo de respaldo"""
    try:
        with open(archivo_respaldo, "r", encoding="utf-8") as f:
            respaldo_data = json.load(f)

        cursor = conn.cursor()
        restaurados = 0

        for reg in respaldo_data["registros"]:
            # Restaurar FECHA_VEN original
            query = """
            UPDATE [insevig].[dbo].[RPINGDES]
            SET FECHA_VEN = ?
            WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
            """
            fecha_ven = datetime.strptime(reg["FECHA_VEN"], "%Y-%m-%d") if reg["FECHA_VEN"] else None
            cursor.execute(query, (fecha_ven, reg["NUMERO"], reg["EMPLEADO"], reg["SECUENCIA"]))
            restaurados += cursor.rowcount

        conn.commit()

        registrar_log("RESTAURACION", {
            "archivo": archivo_respaldo,
            "registros_restaurados": restaurados
        })

        return restaurados

    except Exception as e:
        registrar_log("ERROR_RESTAURACION", {"error": str(e)}, exito=False)
        raise e

class ModificadorRPINGDESApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Modificador RPINGDES Completo - Ver Egresos y Ajuste Inteligente")
        self.root.geometry("1350x850")
        self.root.resizable(True, True)
        
        # Parámetros de conexión
        self.server = 'SERVER\\server'
        self.database = 'insevig'
        self.username = 'sa'
        self.password = 'puntosoft123*'
        
        # Crear cuaderno de pestañas
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Crear las cinco pestañas principales
        self.tab_individual = Frame(self.notebook)
        self.tab_prestamos = Frame(self.notebook)
        self.tab_ver_egresos = Frame(self.notebook)
        self.tab_ajuste_inteligente = Frame(self.notebook)
        self.tab_ajuste_preciso = Frame(self.notebook)

        self.notebook.add(self.tab_individual, text="Modificar Registros Individuales")
        self.notebook.add(self.tab_prestamos, text="Modificar Préstamos Múltiples")
        self.notebook.add(self.tab_ver_egresos, text="Ver Egresos del Período")
        self.notebook.add(self.tab_ajuste_inteligente, text="Ajuste Inteligente (Mover)")
        self.notebook.add(self.tab_ajuste_preciso, text="Ajuste Preciso (Dividir)")

        # Inicializar las cinco pestañas
        self.inicializar_tab_individual()
        self.inicializar_tab_prestamos()
        self.inicializar_tab_ver_egresos()
        self.inicializar_tab_ajuste_inteligente()
        self.inicializar_tab_ajuste_preciso()

        # Cache para rubros
        self.cache_rubros = {}
        self.cache_empleados = []
        
    # =========== PESTAÑA DE REGISTROS INDIVIDUALES ===========
    def inicializar_tab_individual(self):
        # Variables para los campos de entrada
        self.ind_numero_var = StringVar()
        self.ind_empleado_var = StringVar()
        self.ind_nuevo_valor_var = StringVar()  # Nueva variable para el valor
        
        # Panel principal dividido en dos
        main_frame = Frame(self.tab_individual, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)
        
        # Panel izquierdo para la búsqueda
        left_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2, width=300)
        left_frame.pack(side=tk.LEFT, fill="both", expand=False)
        
        # Panel derecho para los resultados
        right_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2)
        right_frame.pack(side=tk.RIGHT, fill="both", expand=True)
        
        # === PANEL IZQUIERDO ===
        # Título
        titulo = Label(left_frame, text="Buscar Registro Individual", font=("Arial", 14, "bold"))
        titulo.grid(row=0, column=0, columnspan=2, pady=10, sticky="w")
        
        # Campo NUMERO
        Label(left_frame, text="NUMERO:", font=("Arial", 11)).grid(row=1, column=0, sticky="w", pady=5)
        Entry(left_frame, textvariable=self.ind_numero_var, width=20).grid(row=1, column=1, sticky="w", pady=5)
        
        # Campo EMPLEADO
        Label(left_frame, text="EMPLEADO:", font=("Arial", 11)).grid(row=2, column=0, sticky="w", pady=5)
        Entry(left_frame, textvariable=self.ind_empleado_var, width=20).grid(row=2, column=1, sticky="w", pady=5)
        
        # Botón de búsqueda
        Button(left_frame, text="Verificar Registro", command=self.verificar_registro_individual, 
               bg="#4CAF50", fg="white", font=("Arial", 11), width=15).grid(row=4, column=0, columnspan=2, pady=20)
        
        # === PANEL DERECHO ===
        # Título
        Label(right_frame, text="Información del Registro", font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        # Área de información
        self.ind_info_text = ScrolledText(right_frame, height=10, wrap=tk.WORD, font=("Arial", 10))
        self.ind_info_text.pack(fill="both", expand=True, pady=5)
        self.ind_info_text.insert(tk.END, "Busque un registro usando NUMERO y EMPLEADO para ver su información " + 
                             "y poder modificar su fecha de vencimiento o valor.")
        
        # Frame para el selector de fecha
        fecha_frame = Frame(right_frame, padx=10, pady=10, relief=tk.GROOVE, bd=2)
        fecha_frame.pack(fill="x", expand=False, pady=10)
        
        Label(fecha_frame, text="Modificar Fecha de Vencimiento:", 
              font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
        
        # Selector de fecha
        self.ind_fecha_entry = DateEntry(fecha_frame, width=15, background='darkblue', foreground='white', 
                                      date_pattern='yyyy-mm-dd', font=("Arial", 12))
        self.ind_fecha_entry.pack(anchor="w", pady=5)
        
        # Botón para modificar fecha
        Button(fecha_frame, text="Modificar Fecha", command=self.modificar_fecha_individual, 
               bg="#2196F3", fg="white", font=("Arial", 12, "bold")).pack(anchor="w", pady=10)
        
        # Nuevo frame para modificar VALOR
        valor_frame = Frame(right_frame, padx=10, pady=10, relief=tk.GROOVE, bd=2)
        valor_frame.pack(fill="x", expand=False, pady=10)
        
        Label(valor_frame, text="Modificar Valor:", 
              font=("Arial", 12, "bold")).pack(anchor="w", pady=5)
        
        # Campo para nuevo valor
        valor_input_frame = Frame(valor_frame)
        valor_input_frame.pack(anchor="w", pady=5)
        
        Label(valor_input_frame, text="Nuevo Valor:", font=("Arial", 11)).pack(side=tk.LEFT, padx=(0, 10))
        Entry(valor_input_frame, textvariable=self.ind_nuevo_valor_var, width=15, font=("Arial", 12)).pack(side=tk.LEFT)
        
        # Botón para modificar valor
        Button(valor_frame, text="Modificar Valor", command=self.modificar_valor_individual, 
               bg="#FF9800", fg="white", font=("Arial", 12, "bold")).pack(anchor="w", pady=10)
        
        # Variables para almacenar información del registro seleccionado
        self.ind_registro_actual = None
    
    def verificar_registro_individual(self):
        """Verifica si el registro individual existe y muestra sus datos"""
        numero = self.ind_numero_var.get().strip()
        empleado = self.ind_empleado_var.get().strip()
        
        if not numero or not empleado:
            messagebox.showwarning("Datos Incompletos", "Por favor ingrese tanto NUMERO como EMPLEADO.")
            return
        
        # Conectar a la base de datos
        if not self.conectar_bd():
            return
            
        try:
            # Consultar el registro
            cursor = self.conn.cursor()
            query = """
            SELECT * FROM [insevig].[dbo].[RPINGDES]
            WHERE NUMERO = ? AND EMPLEADO = ?
            """
            cursor.execute(query, (numero, empleado))
            registro = cursor.fetchone()
            
            if registro:
                # Guardar información del registro
                columnas = [column[0] for column in cursor.description]
                self.ind_registro_actual = {}
                for i, columna in enumerate(columnas):
                    self.ind_registro_actual[columna] = registro[i]
                
                # Mostrar información del registro
                info_text = "Registro encontrado:\n\n"
                
                for columna in columnas:
                    valor = str(self.ind_registro_actual[columna] if self.ind_registro_actual[columna] is not None else "NULL")
                    
                    # Resaltar FECHA_VEN y VALOR
                    if columna in ["FECHA_VEN", "VALOR"]:
                        info_text += f"👉 {columna}: {valor} 👈\n"
                    else:
                        info_text += f"{columna}: {valor}\n"
                
                self.ind_info_text.delete(1.0, tk.END)
                self.ind_info_text.insert(tk.END, info_text)
                
                # Configurar la fecha actual en el selector
                if self.ind_registro_actual["FECHA_VEN"]:
                    self.ind_fecha_entry.set_date(self.ind_registro_actual["FECHA_VEN"])
                
                # Configurar el valor actual en el campo
                if self.ind_registro_actual["VALOR"] is not None:
                    self.ind_nuevo_valor_var.set(str(self.ind_registro_actual["VALOR"]))
                else:
                    self.ind_nuevo_valor_var.set("")
                
                messagebox.showinfo("Éxito", "Registro encontrado. Revise la información y proceda con la modificación si es correcto.")
            else:
                self.ind_info_text.delete(1.0, tk.END)
                self.ind_info_text.insert(tk.END, "No se encontró ningún registro con los valores proporcionados.")
                self.ind_registro_actual = None
                messagebox.warning("No Encontrado", "No se encontró ningún registro que coincida con NUMERO y EMPLEADO proporcionados.")
        
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al buscar el registro:\n{str(e)}")
        finally:
            self.cerrar_conexion()
    
    def modificar_fecha_individual(self):
        """Modifica la FECHA_VEN del registro individual"""
        if not self.ind_registro_actual:
            messagebox.showwarning("Sin Registro", "Primero debe buscar y verificar un registro.")
            return
        
        nueva_fecha = self.ind_fecha_entry.get_date()
        
        # Confirmación
        confirmar = messagebox.askyesno("Confirmar Modificación", 
                                       f"¿Está seguro de modificar la FECHA_VEN a {nueva_fecha} para el registro?\n\n" +
                                       f"NUMERO: {self.ind_registro_actual['NUMERO']}\n" +
                                       f"EMPLEADO: {self.ind_registro_actual['EMPLEADO']}")
        if not confirmar:
            return
            
        # Conectar a la base de datos
        if not self.conectar_bd():
            return
            
        try:
            # Actualizar el registro
            cursor = self.conn.cursor()
            
            query_actualizar = """
            UPDATE [insevig].[dbo].[RPINGDES]
            SET FECHA_VEN = ?
            WHERE NUMERO = ? AND EMPLEADO = ?
            """
            cursor.execute(query_actualizar, (nueva_fecha, 
                                              self.ind_registro_actual["NUMERO"], 
                                              self.ind_registro_actual["EMPLEADO"]))
            self.conn.commit()
            
            messagebox.showinfo("Éxito", "La FECHA_VEN ha sido actualizada correctamente.")
            
            # Actualizar información mostrada
            self.verificar_registro_individual()
            
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al modificar el registro:\n{str(e)}")
            # Hacer rollback en caso de error
            if self.conn:
                self.conn.rollback()
        finally:
            self.cerrar_conexion()
    
    def modificar_valor_individual(self):
        """Modifica el VALOR del registro individual"""
        if not self.ind_registro_actual:
            messagebox.showwarning("Sin Registro", "Primero debe buscar y verificar un registro.")
            return
        
        # Obtener y validar el nuevo valor
        try:
            nuevo_valor_str = self.ind_nuevo_valor_var.get().strip()
            
            if not nuevo_valor_str:
                messagebox.showwarning("Valor Vacío", "Por favor ingrese un valor.")
                return
            
            # Intentar convertir a float
            try:
                nuevo_valor = float(nuevo_valor_str)
            except ValueError:
                messagebox.showerror("Error", "El valor debe ser un número válido.")
                return
            
            # Confirmación con doble verificación para mayor seguridad
            confirmar = messagebox.askyesno("⚠️ CONFIRMACIÓN DE MODIFICACIÓN DE VALOR ⚠️", 
                                         f"⚠️ ATENCIÓN: Está a punto de modificar el VALOR del registro:\n\n" +
                                         f"NUMERO: {self.ind_registro_actual['NUMERO']}\n" +
                                         f"EMPLEADO: {self.ind_registro_actual['EMPLEADO']}\n\n" +
                                         f"Valor actual: {self.ind_registro_actual['VALOR']}\n" +
                                         f"Nuevo valor: {nuevo_valor}\n\n" +
                                         f"Esta acción afecta directamente cálculos de nómina. ¿Está COMPLETAMENTE SEGURO?")
            
            if not confirmar:
                return
            
            # Segunda confirmación para mayor seguridad
            confirmar2 = messagebox.askyesno("⚠️ CONFIRMACIÓN FINAL ⚠️", 
                                          "Por seguridad, confirme una vez más:\n\n" +
                                          f"¿Realmente desea cambiar el VALOR a {nuevo_valor}?", 
                                          icon=messagebox.WARNING)
            
            if not confirmar2:
                return
            
            # Conectar a la base de datos
            if not self.conectar_bd():
                return
                
            try:
                # Actualizar el registro
                cursor = self.conn.cursor()
                
                query_actualizar = """
                UPDATE [insevig].[dbo].[RPINGDES]
                SET VALOR = ?
                WHERE NUMERO = ? AND EMPLEADO = ?
                """
                cursor.execute(query_actualizar, (nuevo_valor, 
                                                self.ind_registro_actual["NUMERO"], 
                                                self.ind_registro_actual["EMPLEADO"]))
                self.conn.commit()
                
                messagebox.showinfo("Éxito", "El VALOR ha sido actualizado correctamente.")
                
                # Actualizar información mostrada
                self.verificar_registro_individual()
                
            except Exception as e:
                messagebox.showerror("Error", f"Ocurrió un error al modificar el registro:\n{str(e)}")
                # Hacer rollback en caso de error
                if self.conn:
                    self.conn.rollback()
            finally:
                self.cerrar_conexion()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error en el proceso: {str(e)}")
    
    # =========== PESTAÑA DE PRÉSTAMOS MÚLTIPLES ===========
    def inicializar_tab_prestamos(self):
        # Variables para los campos de entrada
        self.prest_numero_var = StringVar()
        self.prest_empleado_var = StringVar()
        self.prest_nuevo_valor_var = StringVar()  # Nueva variable para valor masivo
        
        # Para almacenar los registros encontrados
        self.prest_registros_encontrados = []
        self.prest_variables_checkbox = []
        self.prest_campos_fecha = []
        
        # Panel principal dividido en dos
        main_frame = Frame(self.tab_prestamos)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Panel izquierdo para búsqueda
        left_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2)
        left_frame.pack(side=tk.LEFT, fill="both", expand=False, padx=5, pady=5)
        
        # Panel derecho para los resultados y la edición
        right_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2)
        right_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=5, pady=5)
        
        # === PANEL IZQUIERDO ===
        # Título
        titulo = Label(left_frame, text="Buscar Préstamos", font=("Arial", 14, "bold"))
        titulo.grid(row=0, column=0, columnspan=2, pady=10, sticky="w")
        
        # Campo NUMERO
        Label(left_frame, text="NUMERO:", font=("Arial", 11)).grid(row=1, column=0, sticky="w", pady=5)
        Entry(left_frame, textvariable=self.prest_numero_var, width=15).grid(row=1, column=1, sticky="w", pady=5)
        
        # Campo EMPLEADO
        Label(left_frame, text="EMPLEADO:", font=("Arial", 11)).grid(row=2, column=0, sticky="w", pady=5)
        Entry(left_frame, textvariable=self.prest_empleado_var, width=15).grid(row=2, column=1, sticky="w", pady=5)
        
        # Botones de búsqueda
        Button(left_frame, text="Buscar Préstamos", command=self.buscar_prestamos, bg="#4CAF50", fg="white", 
               font=("Arial", 11), width=18).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Panel para herramientas de modificación masiva
        tools_frame = Frame(left_frame, relief=tk.GROOVE, bd=2, padx=10, pady=10)
        tools_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        
        Label(tools_frame, text="Herramientas de Modificación Masiva", font=("Arial", 12, "bold")).pack(anchor="w")
        
        # Opciones para modificar todas las fechas
        Button(tools_frame, text="Seleccionar Todos", command=self.seleccionar_todos, 
               bg="#2196F3", fg="white").pack(fill="x", pady=5)
        Button(tools_frame, text="Deseleccionar Todos", command=self.deseleccionar_todos, 
               bg="#f44336", fg="white").pack(fill="x", pady=5)
        
        # Botones para posponer fechas
        Label(tools_frame, text="Posponer fechas seleccionadas:").pack(anchor="w", pady=(10,5))
        
        buttons_frame = Frame(tools_frame)
        buttons_frame.pack(fill="x")
        
        # Botones para posponer 1, 3 o 6 meses
        Button(buttons_frame, text="+1 Mes", command=lambda: self.posponer_fechas(1), 
               bg="#9C27B0", fg="white").pack(side=tk.LEFT, fill="x", expand=True, padx=2)
        Button(buttons_frame, text="+3 Meses", command=lambda: self.posponer_fechas(3), 
               bg="#9C27B0", fg="white").pack(side=tk.LEFT, fill="x", expand=True, padx=2)
        Button(buttons_frame, text="+6 Meses", command=lambda: self.posponer_fechas(6), 
               bg="#9C27B0", fg="white").pack(side=tk.LEFT, fill="x", expand=True, padx=2)
        
        # Nuevo panel para modificar VALOR de registros seleccionados
        valor_frame = Frame(tools_frame, relief=tk.GROOVE, bd=2, padx=10, pady=10)
        valor_frame.pack(fill="x", expand=False, pady=10)
        
        Label(valor_frame, text="Modificar VALOR para seleccionados:", font=("Arial", 10, "bold")).pack(anchor="w")
        
        valor_input_frame = Frame(valor_frame)
        valor_input_frame.pack(fill="x", pady=5)
        
        Label(valor_input_frame, text="Nuevo Valor:").pack(side=tk.LEFT, padx=(0, 10))
        Entry(valor_input_frame, textvariable=self.prest_nuevo_valor_var, width=12).pack(side=tk.LEFT, padx=(0, 10))
        
        Button(valor_input_frame, text="Aplicar", command=self.aplicar_valor_seleccionados, 
               bg="#FF9800", fg="white").pack(side=tk.LEFT)
        
        # Botón para guardar todos los cambios
        Button(left_frame, text="GUARDAR TODOS LOS CAMBIOS", command=self.guardar_todos_cambios, 
               bg="#FF9800", fg="white", font=("Arial", 12, "bold")).grid(row=5, column=0, columnspan=2, pady=20, sticky="ew")
        
        # === PANEL DERECHO ===
        # Título para el panel de resultados
        Label(right_frame, text="Registros de Préstamos", font=("Arial", 14, "bold")).pack(anchor="w", pady=5)
        
        # Panel de información (inicialmente con instrucciones)
        self.prest_info_text = ScrolledText(right_frame, height=5, wrap=tk.WORD, font=("Arial", 10))
        self.prest_info_text.pack(fill="x", expand=False, pady=5)
        self.prest_info_text.insert(tk.END, "Busque un préstamo usando el NUMERO y EMPLEADO para ver sus registros. " + 
                                  "Puede modificar las fechas de vencimiento y valores individualmente o usar las herramientas de modificación masiva.")
        
        # Crear un contenedor con scrollbar para los registros
        self.scroll_container = Frame(right_frame)
        self.scroll_container.pack(fill="both", expand=True, pady=5)
        
        # Scrollbar vertical
        self.scrollbar_y = tk.Scrollbar(self.scroll_container, orient=tk.VERTICAL)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas que contendrá el frame de registros
        self.canvas = tk.Canvas(self.scroll_container, yscrollcommand=self.scrollbar_y.set)
        self.canvas.pack(side=tk.LEFT, fill="both", expand=True)
        
        # Configurar la scrollbar
        self.scrollbar_y.config(command=self.canvas.yview)
        
        # Frame para los registros encontrados (se llena dinámicamente)
        self.prest_registros_frame = Frame(self.canvas)
        
        # Crear una ventana en el canvas con el frame de registros
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.prest_registros_frame, anchor='nw')
        
        # Configurar el canvas para que se ajuste al tamaño del frame de registros
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        self.prest_registros_frame.bind('<Configure>', self.on_frame_configure)
        
        # Habilitar scroll con la rueda del ratón
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Crear el encabezado para la tabla de resultados
        self.crear_encabezado_tabla()
    
    def on_canvas_configure(self, event):
        """Ajusta el ancho del canvas al tamaño del frame"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
    
    def on_frame_configure(self, event):
        """Ajusta la región scrollable del canvas"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_mousewheel(self, event):
        """Maneja el evento de rueda del ratón para hacer scroll"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def crear_encabezado_tabla(self):
        """Crea el encabezado para la tabla de resultados"""
        header_frame = Frame(self.prest_registros_frame, bg="#f0f0f0")
        header_frame.pack(fill="x", expand=False)
        
        # Columnas
        Label(header_frame, text="Seleccionar", width=10, bg="#f0f0f0", relief=tk.RIDGE, font=("Arial", 10, "bold")).grid(row=0, column=0, padx=1, pady=1)
        Label(header_frame, text="SECUENCIA", width=10, bg="#f0f0f0", relief=tk.RIDGE, font=("Arial", 10, "bold")).grid(row=0, column=1, padx=1, pady=1)
        Label(header_frame, text="VALOR", width=8, bg="#f0f0f0", relief=tk.RIDGE, font=("Arial", 10, "bold")).grid(row=0, column=2, padx=1, pady=1)
        Label(header_frame, text="FECHA_VEN Actual", width=20, bg="#f0f0f0", relief=tk.RIDGE, font=("Arial", 10, "bold")).grid(row=0, column=3, padx=1, pady=1)
        Label(header_frame, text="Nueva FECHA_VEN", width=20, bg="#f0f0f0", relief=tk.RIDGE, font=("Arial", 10, "bold")).grid(row=0, column=4, padx=1, pady=1)
        Label(header_frame, text="Nuevo VALOR", width=12, bg="#f0f0f0", relief=tk.RIDGE, font=("Arial", 10, "bold")).grid(row=0, column=5, padx=1, pady=1)
    
    def conectar_bd(self):
        """Establece conexión con la base de datos"""
        try:
            # Cadena de conexión
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password};'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
            )
            
            self.conn = pyodbc.connect(conn_str)
            return True
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No se pudo conectar a la base de datos:\n{str(e)}")
            return False
            
    def cerrar_conexion(self):
        """Cierra la conexión con la base de datos"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None
    
    def limpiar_registros_frame(self):
        """Limpia el frame de registros para poder mostrar nuevos resultados"""
        # Destruir todos los widgets dentro del frame de registros
        for widget in self.prest_registros_frame.winfo_children():
            widget.destroy()
        
        # Volver a crear el encabezado
        self.crear_encabezado_tabla()
        
        # Limpiar las variables
        self.prest_registros_encontrados = []
        self.prest_variables_checkbox = []
        self.prest_campos_fecha = []
        self.prest_campos_valor = []  # Nueva lista para campos de valor
    
    def buscar_prestamos(self):
        """Busca registros de préstamos según NUMERO y EMPLEADO"""
        numero = self.prest_numero_var.get().strip()
        empleado = self.prest_empleado_var.get().strip()
        
        if not numero or not empleado:
            messagebox.showwarning("Datos Incompletos", "Por favor ingrese tanto NUMERO como EMPLEADO.")
            return
        
        # Limpiar registros anteriores
        self.limpiar_registros_frame()
        
        # Conectar a la base de datos
        if not self.conectar_bd():
            return
            
        try:
            # Consultar los registros
            cursor = self.conn.cursor()
            query = """
            SELECT NUMERO, EMPLEADO, SECUENCIA, VALOR, FECHA_VEN, CODIGO, CODSUC, CODEMP, CLASE
            FROM [insevig].[dbo].[RPINGDES]
            WHERE NUMERO = ? AND EMPLEADO = ?
            ORDER BY SECUENCIA
            """
            cursor.execute(query, (numero, empleado))
            registros = cursor.fetchall()
            
            if not registros:
                self.actualizar_info_prestamos("No se encontraron registros para el NUMERO y EMPLEADO especificados.")
                messagebox.warning("No Encontrado", "No se encontraron registros con los criterios especificados.")
                return
            
            # Guardar los registros encontrados
            self.prest_registros_encontrados = []
            for row in registros:
                reg = {}
                for i, col in enumerate(cursor.description):
                    reg[col[0]] = row[i]
                self.prest_registros_encontrados.append(reg)
            
            # Actualizar panel de información
            info_text = f"Se encontraron {len(registros)} registros para NUMERO={numero}, EMPLEADO={empleado}.\n"
            if hasattr(registros[0], 'CODIGO') and hasattr(registros[0], 'CODSUC') and hasattr(registros[0], 'CLASE'):
                info_text += f"Código: {registros[0].CODIGO}, Sucursal: {registros[0].CODSUC}, Clase: {registros[0].CLASE}\n"
            info_text += "Seleccione los registros que desea modificar y establezca las nuevas fechas de vencimiento o valores."
            self.actualizar_info_prestamos(info_text)
            
            # Mostrar los registros encontrados en la interfaz
            self.mostrar_registros_prestamos()
            
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al buscar los registros:\n{str(e)}")
        finally:
            self.cerrar_conexion()
    
    def mostrar_registros_prestamos(self):
        """Muestra los registros de préstamos encontrados en la interfaz gráfica"""
        # Limpiar las listas de control
        self.prest_variables_checkbox = []
        self.prest_campos_fecha = []
        self.prest_campos_valor = []  # Lista para campos de valor
        
        # Para cada registro, crear una fila en la tabla
        for i, registro in enumerate(self.prest_registros_encontrados):
            row_frame = Frame(self.prest_registros_frame)
            row_frame.pack(fill="x", expand=False)
            
            # Variable para el checkbox
            var = IntVar()
            self.prest_variables_checkbox.append(var)
            
            # Checkbox para seleccionar el registro
            Checkbutton(row_frame, variable=var).grid(row=0, column=0, padx=5)
            
            # SECUENCIA
            Label(row_frame, text=str(registro["SECUENCIA"]), width=10).grid(row=0, column=1, padx=1, pady=3)
            
            # VALOR actual
            Label(row_frame, text=str(registro["VALOR"]), width=8).grid(row=0, column=2, padx=1, pady=3)
            
            # FECHA_VEN actual
            fecha_actual = registro["FECHA_VEN"]
            Label(row_frame, text=fecha_actual.strftime("%Y-%m-%d") if fecha_actual else "N/A", 
                  width=20).grid(row=0, column=3, padx=1, pady=3)
            
            # Campo para nueva FECHA_VEN
            fecha_entry = DateEntry(row_frame, width=18, background='darkblue', foreground='white', 
                                    date_pattern='yyyy-mm-dd')
            if fecha_actual:
                fecha_entry.set_date(fecha_actual)
            fecha_entry.grid(row=0, column=4, padx=1, pady=3)
            self.prest_campos_fecha.append(fecha_entry)
            
            # Campo para nuevo VALOR
            valor_var = StringVar()
            valor_var.set(str(registro["VALOR"]))  # Establecer valor actual
            valor_entry = Entry(row_frame, textvariable=valor_var, width=12)
            valor_entry.grid(row=0, column=5, padx=1, pady=3)
            self.prest_campos_valor.append(valor_var)  # Guardar referencia a la variable
            
            # Botón para guardar cambios individuales
            Button(row_frame, text="Guardar", command=lambda idx=i: self.guardar_cambio_individual(idx), 
                   bg="#4CAF50", fg="white").grid(row=0, column=6, padx=5, pady=3)
    
    def aplicar_valor_seleccionados(self):
        """Aplica el mismo valor a todos los registros seleccionados"""
        # Verificar si hay registros seleccionados
        seleccionados = [i for i, var in enumerate(self.prest_variables_checkbox) if var.get() == 1]
        
        if not seleccionados:
            messagebox.showwarning("Advertencia", "No hay registros seleccionados para modificar.")
            return
        
        # Validar el nuevo valor
        nuevo_valor_str = self.prest_nuevo_valor_var.get().strip()
        if not nuevo_valor_str:
            messagebox.showwarning("Valor Vacío", "Por favor ingrese un valor para aplicar.")
            return
        
        try:
            nuevo_valor = float(nuevo_valor_str)
        except ValueError:
            messagebox.showerror("Error", "El valor debe ser un número válido.")
            return
        
        # Confirmación con doble verificación para mayor seguridad
        confirmar = messagebox.askyesno("⚠️ CONFIRMACIÓN DE MODIFICACIÓN DE VALOR ⚠️", 
                                     f"⚠️ ATENCIÓN: Está a punto de modificar el VALOR de {len(seleccionados)} registros a {nuevo_valor}.\n\n" +
                                     f"Esta acción afecta directamente cálculos de nómina. ¿Está COMPLETAMENTE SEGURO?",
                                     icon=messagebox.WARNING)
        
        if not confirmar:
            return
        
        # Segunda confirmación para mayor seguridad
        confirmar2 = messagebox.askyesno("⚠️ CONFIRMACIÓN FINAL ⚠️", 
                                      "Por seguridad, confirme una vez más:\n\n" +
                                      f"¿Realmente desea cambiar el VALOR de {len(seleccionados)} registros a {nuevo_valor}?", 
                                      icon=messagebox.WARNING)
        
        if not confirmar2:
            return
        
        # Aplicar el nuevo valor a los registros seleccionados
        for i in seleccionados:
            self.prest_campos_valor[i].set(str(nuevo_valor))
        
        messagebox.showinfo("Valor Aplicado", 
                         f"El valor {nuevo_valor} ha sido aplicado a los registros seleccionados.\n\n" +
                         "⚠️ IMPORTANTE: Estos cambios no se guardarán hasta que presione el botón 'GUARDAR TODOS LOS CAMBIOS'.")
    
    def actualizar_info_prestamos(self, texto):
        """Actualiza el panel de información de préstamos con el texto proporcionado"""
        self.prest_info_text.delete(1.0, tk.END)
        self.prest_info_text.insert(tk.END, texto)
    
    def seleccionar_todos(self):
        """Selecciona todos los registros de préstamos"""
        for var in self.prest_variables_checkbox:
            var.set(1)
    
    def deseleccionar_todos(self):
        """Deselecciona todos los registros de préstamos"""
        for var in self.prest_variables_checkbox:
            var.set(0)
    
    def posponer_fechas(self, meses):
        """Pospone las fechas seleccionadas por el número de meses especificado"""
        # Verificar si hay registros seleccionados
        seleccionados = [i for i, var in enumerate(self.prest_variables_checkbox) if var.get() == 1]
        
        if not seleccionados:
            messagebox.showwarning("Advertencia", "No hay registros seleccionados para modificar.")
            return
        
        # Confirmar la acción
        confirmar = messagebox.askyesno("Confirmar", 
                                     f"¿Está seguro de posponer {meses} meses las fechas de vencimiento de los {len(seleccionados)} registros seleccionados?")
        if not confirmar:
            return
        
        # Posponer las fechas en los campos DateEntry
        for i in seleccionados:
            fecha_actual = self.prest_campos_fecha[i].get_date()
            # Usar relativedelta para mantener el último día del mes cuando corresponda
            nueva_fecha = fecha_actual + relativedelta(months=meses)
            self.prest_campos_fecha[i].set_date(nueva_fecha)
    
    def guardar_cambio_individual(self, indice):
        """Guarda el cambio de fecha y valor para un registro individual de préstamo"""
        if indice >= len(self.prest_registros_encontrados) or indice >= len(self.prest_campos_fecha):
            messagebox.showerror("Error", "Error de índice al guardar cambio individual.")
            return
        
        registro = self.prest_registros_encontrados[indice]
        nueva_fecha = self.prest_campos_fecha[indice].get_date()
        
        # Obtener y validar nuevo valor
        try:
            nuevo_valor_str = self.prest_campos_valor[indice].get().strip()
            if nuevo_valor_str:
                try:
                    nuevo_valor = float(nuevo_valor_str)
                except ValueError:
                    messagebox.showerror("Error", "El valor debe ser un número válido.")
                    return
            else:
                # Si está vacío, mantener el valor actual
                nuevo_valor = registro["VALOR"]
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar el valor: {str(e)}")
            return
        
        # Determinar qué ha cambiado
        fecha_cambio = nueva_fecha != registro["FECHA_VEN"]
        valor_cambio = nuevo_valor != registro["VALOR"]
        
        if not fecha_cambio and not valor_cambio:
            messagebox.showinfo("Sin Cambios", "No hay cambios para guardar.")
            return
        
        # Mensaje de confirmación
        mensaje = "¿Está seguro de guardar los siguientes cambios?\n\n"
        if fecha_cambio:
            mensaje += f"FECHA_VEN: {registro['FECHA_VEN']} → {nueva_fecha}\n"
        if valor_cambio:
            mensaje += f"VALOR: {registro['VALOR']} → {nuevo_valor}\n"
        
        # Confirmar la acción
        confirmar = messagebox.askyesno("Confirmar", mensaje)
        if not confirmar:
            return
        
        # Conectar a la base de datos
        if not self.conectar_bd():
            return
            
        try:
            # Actualizar el registro
            cursor = self.conn.cursor()
            
            # Construir la consulta según lo que haya cambiado
            if fecha_cambio and valor_cambio:
                query = """
                UPDATE [insevig].[dbo].[RPINGDES]
                SET FECHA_VEN = ?, VALOR = ?
                WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ?
                """
                cursor.execute(query, (nueva_fecha, nuevo_valor, registro["NUMERO"], registro["EMPLEADO"], registro["SECUENCIA"]))
            elif fecha_cambio:
                query = """
                UPDATE [insevig].[dbo].[RPINGDES]
                SET FECHA_VEN = ?
                WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ?
                """
                cursor.execute(query, (nueva_fecha, registro["NUMERO"], registro["EMPLEADO"], registro["SECUENCIA"]))
            elif valor_cambio:
                query = """
                UPDATE [insevig].[dbo].[RPINGDES]
                SET VALOR = ?
                WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ?
                """
                cursor.execute(query, (nuevo_valor, registro["NUMERO"], registro["EMPLEADO"], registro["SECUENCIA"]))
            
            self.conn.commit()
            
            # Actualizar el registro en memoria
            self.prest_registros_encontrados[indice]["FECHA_VEN"] = nueva_fecha
            self.prest_registros_encontrados[indice]["VALOR"] = nuevo_valor
            
            messagebox.showinfo("Éxito", "El registro ha sido actualizado correctamente.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al modificar el registro:\n{str(e)}")
            # Hacer rollback en caso de error
            if self.conn:
                self.conn.rollback()
        finally:
            self.cerrar_conexion()
    
    def guardar_todos_cambios(self):
        """Guarda los cambios de fecha y valor para todos los registros de préstamos seleccionados"""
        # Verificar si hay registros seleccionados
        seleccionados = [i for i, var in enumerate(self.prest_variables_checkbox) if var.get() == 1]
        
        if not seleccionados:
            messagebox.showwarning("Advertencia", "No hay registros seleccionados para modificar.")
            return
        
        # Confirmar la acción
        confirmar = messagebox.askyesno("Confirmar", 
                                     f"¿Está seguro de guardar los cambios para los {len(seleccionados)} registros seleccionados?")
        if not confirmar:
            return
        
        # Conectar a la base de datos
        if not self.conectar_bd():
            return
            
        try:
            # Iniciar transacción
            self.conn.autocommit = False
            cursor = self.conn.cursor()
            
            # Contador de éxitos
            actualizados = 0
            
            # Actualizar cada registro seleccionado
            for i in seleccionados:
                registro = self.prest_registros_encontrados[i]
                nueva_fecha = self.prest_campos_fecha[i].get_date()
                
                # Obtener y validar nuevo valor
                try:
                    nuevo_valor_str = self.prest_campos_valor[i].get().strip()
                    if nuevo_valor_str:
                        nuevo_valor = float(nuevo_valor_str)
                    else:
                        nuevo_valor = registro["VALOR"]
                except ValueError:
                    messagebox.showerror("Error", f"Valor inválido en el registro con SECUENCIA={registro['SECUENCIA']}.")
                    self.conn.rollback()
                    self.cerrar_conexion()
                    return
                
                # Determinar qué ha cambiado
                fecha_cambio = nueva_fecha != registro["FECHA_VEN"]
                valor_cambio = nuevo_valor != registro["VALOR"]
                
                if not fecha_cambio and not valor_cambio:
                    continue  # No hay cambios para este registro
                
                # Construir la consulta según lo que haya cambiado
                if fecha_cambio and valor_cambio:
                    query = """
                    UPDATE [insevig].[dbo].[RPINGDES]
                    SET FECHA_VEN = ?, VALOR = ?
                    WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ?
                    """
                    cursor.execute(query, (nueva_fecha, nuevo_valor, registro["NUMERO"], registro["EMPLEADO"], registro["SECUENCIA"]))
                elif fecha_cambio:
                    query = """
                    UPDATE [insevig].[dbo].[RPINGDES]
                    SET FECHA_VEN = ?
                    WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ?
                    """
                    cursor.execute(query, (nueva_fecha, registro["NUMERO"], registro["EMPLEADO"], registro["SECUENCIA"]))
                elif valor_cambio:
                    query = """
                    UPDATE [insevig].[dbo].[RPINGDES]
                    SET VALOR = ?
                    WHERE NUMERO = ? AND EMPLEADO = ? AND SECUENCIA = ?
                    """
                    cursor.execute(query, (nuevo_valor, registro["NUMERO"], registro["EMPLEADO"], registro["SECUENCIA"]))
                
                # Actualizar el registro en memoria
                self.prest_registros_encontrados[i]["FECHA_VEN"] = nueva_fecha
                self.prest_registros_encontrados[i]["VALOR"] = nuevo_valor
                
                actualizados += 1
            
            # Commit
            self.conn.commit()
            
            if actualizados > 0:
                messagebox.showinfo("Éxito", f"Se han actualizado correctamente {actualizados} registros.")
            else:
                messagebox.showinfo("Sin Cambios", "No se detectaron cambios para guardar.")
            
            # Volver a buscar los registros para refrescar la vista
            self.buscar_prestamos()
            
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al modificar los registros:\n{str(e)}")
            # Hacer rollback en caso de error
            if self.conn:
                self.conn.rollback()
        finally:
            self.conn.autocommit = True
            self.cerrar_conexion()

    # =========== PESTAÑA DE VER EGRESOS DEL PERÍODO ===========
    def inicializar_tab_ver_egresos(self):
        """Inicializa la pestaña para ver egresos del período"""
        # Variables
        self.egr_empleado_var = StringVar()
        self.egr_empleado_nombre_var = StringVar()
        self.egr_egresos_data = []

        # Panel principal
        main_frame = Frame(self.tab_ver_egresos, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Panel superior para filtros
        filtros_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2)
        filtros_frame.pack(fill="x", expand=False, pady=(0, 10))

        # Título
        Label(filtros_frame, text="Consulta de Egresos del Período",
              font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=8, pady=10, sticky="w")

        # Fila de filtros
        # Fecha Desde
        Label(filtros_frame, text="Desde:", font=("Arial", 11)).grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.egr_fecha_desde = DateEntry(filtros_frame, width=12, background='darkblue', foreground='white',
                                          date_pattern='dd/mm/yyyy', font=("Arial", 10))
        # Establecer primer día del mes actual
        hoy = datetime.now()
        primer_dia_mes = hoy.replace(day=1)
        self.egr_fecha_desde.set_date(primer_dia_mes)
        self.egr_fecha_desde.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Fecha Hasta
        Label(filtros_frame, text="Hasta:", font=("Arial", 11)).grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.egr_fecha_hasta = DateEntry(filtros_frame, width=12, background='darkblue', foreground='white',
                                          date_pattern='dd/mm/yyyy', font=("Arial", 10))
        # Establecer último día del mes actual
        ultimo_dia_mes = (hoy.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        self.egr_fecha_hasta.set_date(ultimo_dia_mes)
        self.egr_fecha_hasta.grid(row=1, column=3, sticky="w", padx=5, pady=5)

        # Empleado
        Label(filtros_frame, text="Empleado:", font=("Arial", 11)).grid(row=1, column=4, sticky="w", padx=5, pady=5)
        self.egr_empleado_entry = Entry(filtros_frame, textvariable=self.egr_empleado_var, width=10, font=("Arial", 10))
        self.egr_empleado_entry.grid(row=1, column=5, sticky="w", padx=5, pady=5)

        # Nombre del empleado (solo lectura)
        self.egr_nombre_label = Label(filtros_frame, textvariable=self.egr_empleado_nombre_var,
                                       font=("Arial", 10, "bold"), fg="blue", width=35, anchor="w")
        self.egr_nombre_label.grid(row=1, column=6, sticky="w", padx=5, pady=5)

        # Botón Consultar
        Button(filtros_frame, text="Consultar", command=self.consultar_egresos_periodo,
               bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), width=12).grid(row=1, column=7, padx=10, pady=5)

        # Botón para generar PDF
        Button(filtros_frame, text="Generar PDF", command=self.generar_pdf_egresos,
               bg="#2196F3", fg="white", font=("Arial", 11, "bold"), width=12).grid(row=1, column=8, padx=10, pady=5)

        # Vincular evento para buscar nombre al escribir código
        self.egr_empleado_entry.bind('<KeyRelease>', self.buscar_nombre_empleado_egr)
        self.egr_empleado_entry.bind('<Return>', lambda e: self.consultar_egresos_periodo())

        # Frame para información del empleado
        self.info_emp_frame = Frame(main_frame, padx=10, pady=5, relief=tk.GROOVE, bd=1)
        self.info_emp_frame.pack(fill="x", expand=False, pady=(0, 5))

        self.egr_info_empleado_label = Label(self.info_emp_frame, text="", font=("Arial", 10), anchor="w")
        self.egr_info_empleado_label.pack(fill="x", padx=5, pady=2)

        # Frame para la tabla de egresos
        tabla_frame = Frame(main_frame, padx=5, pady=5, relief=tk.RIDGE, bd=2)
        tabla_frame.pack(fill="both", expand=True)

        # Crear Treeview con estilo similar al sistema
        style = ttk.Style()
        style.configure("Egresos.Treeview", font=("Arial", 9), rowheight=25)
        style.configure("Egresos.Treeview.Heading", font=("Arial", 10, "bold"))

        # Columnas de la tabla
        columnas = ("numero", "fecha_trans", "fecha_liq", "rubro", "valor", "concepto")

        # Scrollbars
        scroll_y = ttk.Scrollbar(tabla_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(tabla_frame, orient=tk.HORIZONTAL)

        self.egr_treeview = ttk.Treeview(tabla_frame, columns=columnas, show="headings",
                                          style="Egresos.Treeview",
                                          yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.config(command=self.egr_treeview.yview)
        scroll_x.config(command=self.egr_treeview.xview)

        # Configurar columnas
        self.egr_treeview.heading("numero", text="Numero", anchor="center")
        self.egr_treeview.heading("fecha_trans", text="Fecha Transacción", anchor="center")
        self.egr_treeview.heading("fecha_liq", text="Fecha Liquidación", anchor="center")
        self.egr_treeview.heading("rubro", text="Rubro", anchor="w")
        self.egr_treeview.heading("valor", text="Valor", anchor="e")
        self.egr_treeview.heading("concepto", text="Concepto", anchor="w")

        self.egr_treeview.column("numero", width=80, anchor="center")
        self.egr_treeview.column("fecha_trans", width=120, anchor="center")
        self.egr_treeview.column("fecha_liq", width=120, anchor="center")
        self.egr_treeview.column("rubro", width=200, anchor="w")
        self.egr_treeview.column("valor", width=100, anchor="e")
        self.egr_treeview.column("concepto", width=350, anchor="w")

        # Posicionar elementos
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.egr_treeview.pack(fill="both", expand=True)

        # Configurar colores alternados
        self.egr_treeview.tag_configure('oddrow', background='#f0f0f0')
        self.egr_treeview.tag_configure('evenrow', background='white')
        self.egr_treeview.tag_configure('total', background='#e6f2ff', font=("Arial", 10, "bold"))

        # Frame para el total
        total_frame = Frame(main_frame, padx=10, pady=10, relief=tk.GROOVE, bd=2)
        total_frame.pack(fill="x", expand=False, pady=(10, 0))

        self.egr_total_label = Label(total_frame, text="Total General ------> 0.00",
                                     font=("Arial", 14, "bold"), fg="darkred")
        self.egr_total_label.pack(side=tk.RIGHT, padx=20)

    def buscar_nombre_empleado_egr(self, event=None):
        """Busca el nombre del empleado al escribir el código"""
        codigo = self.egr_empleado_var.get().strip()

        if not codigo:
            self.egr_empleado_nombre_var.set("")
            return

        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()
            query = """
            SELECT APELLIDOS, NOMBRES, ESTADO
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE EMPLEADO = ?
            """
            cursor.execute(query, (codigo,))
            resultado = cursor.fetchone()

            if resultado:
                nombre_completo = f"{resultado[0]} {resultado[1]}".strip()
                estado = resultado[2] if resultado[2] else ""
                self.egr_empleado_nombre_var.set(f"{nombre_completo} ({estado})")
            else:
                self.egr_empleado_nombre_var.set("(No encontrado)")

        except Exception as e:
            self.egr_empleado_nombre_var.set("(Error)")
        finally:
            self.cerrar_conexion()

    def obtener_nombre_rubro(self, clase):
        """Obtiene el nombre del rubro desde la cache o la base de datos"""
        if clase in self.cache_rubros:
            return self.cache_rubros[clase]

        return str(clase)  # Retornar el código si no está en cache

    def cargar_rubros_cache(self):
        """Carga todos los rubros en cache"""
        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()
            query = """
            SELECT CLASE, NOMBRE_L
            FROM [insevig].[dbo].[RPRUBROS]
            WHERE CODEMP = '01' AND CODSUC = '001'
            """
            cursor.execute(query)
            resultados = cursor.fetchall()

            for row in resultados:
                self.cache_rubros[str(row[0]).strip()] = row[1] if row[1] else str(row[0])

        except Exception as e:
            print(f"Error al cargar rubros: {e}")
        finally:
            self.cerrar_conexion()

    def consultar_egresos_periodo(self):
        """Consulta los egresos del empleado en el período especificado"""
        codigo_empleado = self.egr_empleado_var.get().strip()

        if not codigo_empleado:
            messagebox.showwarning("Datos Incompletos", "Por favor ingrese el código del empleado.")
            return

        fecha_desde = self.egr_fecha_desde.get_date()
        fecha_hasta = self.egr_fecha_hasta.get_date()

        if fecha_desde > fecha_hasta:
            messagebox.showwarning("Fechas Inválidas", "La fecha 'Desde' no puede ser mayor que la fecha 'Hasta'.")
            return

        # Limpiar tabla
        for item in self.egr_treeview.get_children():
            self.egr_treeview.delete(item)

        self.egr_egresos_data = []

        # Cargar rubros si no están en cache
        if not self.cache_rubros:
            self.cargar_rubros_cache()

        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()

            # Obtener información del empleado
            query_emp = """
            SELECT EMPLEADO, APELLIDOS, NOMBRES, CEDULA, CARGO, DEPTO, ESTADO
            FROM [insevig].[dbo].[RPEMPLEA]
            WHERE EMPLEADO = ?
            """
            cursor.execute(query_emp, (codigo_empleado,))
            emp_info = cursor.fetchone()

            if not emp_info:
                messagebox.showwarning("No Encontrado", "No se encontró el empleado con el código especificado.")
                self.cerrar_conexion()
                return

            # Mostrar info del empleado
            nombre_completo = f"{emp_info[1]} {emp_info[2]}".strip()
            cedula = str(emp_info[3]) if emp_info[3] else ""
            estado = emp_info[6] if emp_info[6] else ""
            self.egr_info_empleado_label.config(
                text=f"{codigo_empleado}    {nombre_completo}    {estado}"
            )
            self.egr_empleado_nombre_var.set(f"{nombre_completo} ({estado})")

            # Consultar egresos
            query_egresos = """
            SELECT r.NUMERO, r.FECHA, r.FECHA_VEN, r.CLASE, r.VALOR, r.CONCEPTO, r.MONTO, r.OBSERV,
                   rb.NOMBRE_L
            FROM [insevig].[dbo].[RPINGDES] r
            LEFT JOIN [insevig].[dbo].[RPRUBROS] rb
                ON r.CLASE = rb.CLASE AND r.CODIGO = rb.CODIGO AND rb.CODEMP = '01' AND rb.CODSUC = '001'
            WHERE r.EMPLEADO = ?
              AND r.CODIGO = 'EGR'
              AND r.FECHA_VEN >= ?
              AND r.FECHA_VEN <= ?
            ORDER BY r.FECHA_VEN, r.NUMERO
            """
            cursor.execute(query_egresos, (codigo_empleado, fecha_desde, fecha_hasta))
            egresos = cursor.fetchall()

            if not egresos:
                messagebox.showinfo("Sin Resultados",
                                   f"No se encontraron egresos para el empleado {codigo_empleado} en el período especificado.")
                self.egr_total_label.config(text="Total General ------> 0.00")
                self.cerrar_conexion()
                return

            # Llenar la tabla
            total_egresos = 0.0
            for idx, egreso in enumerate(egresos):
                numero = int(egreso[0]) if egreso[0] else ""
                fecha_trans = egreso[1].strftime("%d/%m/%Y") if egreso[1] else ""
                fecha_liq = egreso[2].strftime("%d/%m/%Y") if egreso[2] else ""
                clase = str(egreso[3]).strip() if egreso[3] else ""
                valor = float(egreso[4]) if egreso[4] else 0.0
                concepto = egreso[5] if egreso[5] else ""
                observ = egreso[7] if egreso[7] else ""
                nombre_rubro = egreso[8] if egreso[8] else self.obtener_nombre_rubro(clase)

                # Construir concepto completo
                concepto_completo = concepto
                if observ and observ.strip():
                    concepto_completo = f"{concepto} {observ}".strip() if concepto else observ

                total_egresos += valor

                # Determinar tag para colores alternados
                tag = 'evenrow' if idx % 2 == 0 else 'oddrow'

                # Insertar en treeview
                self.egr_treeview.insert("", "end", values=(
                    numero,
                    fecha_trans,
                    fecha_liq,
                    nombre_rubro,
                    f"{valor:,.2f}",
                    concepto_completo
                ), tags=(tag,))

                # Guardar datos para PDF
                self.egr_egresos_data.append({
                    'numero': numero,
                    'fecha_trans': fecha_trans,
                    'fecha_liq': fecha_liq,
                    'rubro': nombre_rubro,
                    'valor': valor,
                    'concepto': concepto_completo
                })

            # Mostrar total
            self.egr_total_label.config(text=f"Total General ------> {total_egresos:,.2f}")

            messagebox.showinfo("Consulta Exitosa",
                               f"Se encontraron {len(egresos)} egresos para el período.\nTotal: ${total_egresos:,.2f}")

        except Exception as e:
            messagebox.showerror("Error", f"Error al consultar egresos:\n{str(e)}")
        finally:
            self.cerrar_conexion()

    def generar_pdf_egresos(self):
        """Genera un PDF con el reporte de egresos similar al sistema"""
        if not self.egr_egresos_data:
            messagebox.showwarning("Sin Datos", "Primero debe consultar los egresos de un empleado.")
            return

        codigo_empleado = self.egr_empleado_var.get().strip()
        nombre_empleado = self.egr_empleado_nombre_var.get().replace("(ACT)", "").replace("(INA)", "").strip()
        fecha_desde = self.egr_fecha_desde.get_date().strftime("%d/%m/%Y")
        fecha_hasta = self.egr_fecha_hasta.get_date().strftime("%d/%m/%Y")

        # Crear nombre del archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"ROL_DESCUENTO_{codigo_empleado}_{timestamp}.pdf"

        try:
            # Crear documento PDF
            doc = SimpleDocTemplate(nombre_archivo, pagesize=letter,
                                    leftMargin=0.5*inch, rightMargin=0.5*inch,
                                    topMargin=0.5*inch, bottomMargin=0.5*inch)

            elements = []
            styles = getSampleStyleSheet()

            # Estilo para el encabezado
            estilo_titulo = ParagraphStyle(
                'Titulo',
                parent=styles['Heading1'],
                fontSize=12,
                alignment=TA_CENTER,
                spaceAfter=10
            )

            estilo_subtitulo = ParagraphStyle(
                'Subtitulo',
                parent=styles['Normal'],
                fontSize=10,
                alignment=TA_CENTER,
                spaceAfter=5
            )

            estilo_info = ParagraphStyle(
                'Info',
                parent=styles['Normal'],
                fontSize=9,
                alignment=TA_LEFT,
                spaceAfter=3
            )

            # Encabezado de empresa
            elements.append(Paragraph("<b>INSEVIG CIA.LTDA.</b>", estilo_titulo))
            elements.append(Paragraph("PEDRO MONCAYO 1005 Y VELEZ", estilo_subtitulo))
            elements.append(Paragraph(f"Guayaquil-Ecuador RUC:0992399368001 {datetime.now().strftime('%d de %B del %Y Hora:%H:%M:%S')}", estilo_subtitulo))
            elements.append(Spacer(1, 10))

            # Título del reporte
            elements.append(Paragraph(f"<b>ROL DESCUENTO DE EMPLEADOS DESDE:{fecha_desde} HASTA: {fecha_hasta} DETALLADO</b>", estilo_titulo))
            elements.append(Spacer(1, 10))

            # Información del empleado
            elements.append(Paragraph(f"<b>{codigo_empleado}    {nombre_empleado}</b>", estilo_info))
            elements.append(Spacer(1, 10))

            # Crear tabla de datos
            datos_tabla = [["Numero", "Fecha\nTransacción", "Fecha\nLiquidación", "Rubro", "Valor", "Concepto"]]

            for egreso in self.egr_egresos_data:
                datos_tabla.append([
                    str(egreso['numero']),
                    egreso['fecha_trans'],
                    egreso['fecha_liq'],
                    egreso['rubro'][:25] if egreso['rubro'] else "",
                    f"{egreso['valor']:,.2f}",
                    egreso['concepto'][:50] if egreso['concepto'] else ""
                ])

            # Calcular total
            total = sum(e['valor'] for e in self.egr_egresos_data)
            datos_tabla.append(["", "", "", "", f"{total:,.2f}", ""])

            # Crear tabla
            tabla = Table(datos_tabla, colWidths=[60, 70, 70, 130, 70, 180])

            # Estilo de tabla
            estilo_tabla = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'LEFT'),
                ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
                ('ALIGN', (5, 1), (5, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.gray),
                ('BACKGROUND', (0, -1), (-1, -1), colors.Color(0.9, 0.95, 1.0)),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ])

            tabla.setStyle(estilo_tabla)
            elements.append(tabla)

            # Total general
            elements.append(Spacer(1, 15))
            elements.append(Paragraph(f"<b>Total General ------> {total:,.2f}</b>",
                                      ParagraphStyle('Total', fontSize=12, alignment=TA_RIGHT, textColor=colors.darkred)))

            # Construir PDF
            doc.build(elements)

            messagebox.showinfo("PDF Generado", f"El archivo PDF se ha generado correctamente:\n{os.path.abspath(nombre_archivo)}")

            # Abrir el PDF
            try:
                abrir_ruta_multiplataforma(os.path.abspath(nombre_archivo))
            except:
                pass

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar PDF:\n{str(e)}")

    # =========== PESTAÑA DE AJUSTE INTELIGENTE DE EGRESOS ===========
    def inicializar_tab_ajuste_inteligente(self):
        """Inicializa la pestaña para ajuste inteligente de egresos"""
        # Variables
        self.aj_periodo_var = StringVar()
        self.aj_empleados_en_contra = []
        self.aj_egresos_a_mover = {}

        # Panel principal con scroll
        main_frame = Frame(self.tab_ajuste_inteligente, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Panel superior para configuración
        config_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2)
        config_frame.pack(fill="x", expand=False, pady=(0, 10))

        # Título
        Label(config_frame, text="Ajuste Inteligente de Egresos - Evitar Saldos en Contra",
              font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=6, pady=10, sticky="w")

        # Período del rol (mes/año)
        Label(config_frame, text="Período del Rol:", font=("Arial", 11)).grid(row=1, column=0, sticky="w", padx=5, pady=5)

        periodo_frame = Frame(config_frame)
        periodo_frame.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # Mes
        Label(periodo_frame, text="Mes:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))
        self.aj_mes_combo = ttk.Combobox(periodo_frame, width=10, state="readonly",
                                          values=["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        # Establecer mes anterior por defecto (el rol generalmente es del mes anterior)
        hoy = datetime.now()
        mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
        self.aj_mes_combo.current(mes_anterior - 1)
        self.aj_mes_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Año
        Label(periodo_frame, text="Año:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))
        año_actual = hoy.year if hoy.month > 1 else hoy.year - 1
        self.aj_año_spin = ttk.Spinbox(periodo_frame, from_=2020, to=2030, width=6)
        self.aj_año_spin.set(año_actual)
        self.aj_año_spin.pack(side=tk.LEFT)

        # Campo para códigos de empleados
        Label(config_frame, text="Códigos de Empleados:", font=("Arial", 11)).grid(row=2, column=0, sticky="nw", padx=5, pady=5)

        codigos_frame = Frame(config_frame)
        codigos_frame.grid(row=2, column=1, columnspan=3, sticky="w", padx=5, pady=5)

        self.aj_codigos_text = tk.Text(codigos_frame, width=50, height=3, font=("Arial", 10))
        self.aj_codigos_text.pack(side=tk.LEFT, fill="x", expand=True)

        Label(codigos_frame, text="(Separados por comas, espacios o líneas)", font=("Arial", 8), fg="gray").pack(side=tk.LEFT, padx=10)

        # Botones de acción
        botones_frame = Frame(config_frame)
        botones_frame.grid(row=3, column=0, columnspan=6, pady=15)

        Button(botones_frame, text="Analizar Empleados", command=self.analizar_empleados_en_contra,
               bg="#FF9800", fg="white", font=("Arial", 11, "bold"), width=18).pack(side=tk.LEFT, padx=10)

        Button(botones_frame, text="Seleccionar Egresos Sugeridos", command=self.seleccionar_egresos_sugeridos,
               bg="#2196F3", fg="white", font=("Arial", 11, "bold"), width=22).pack(side=tk.LEFT, padx=10)

        Button(botones_frame, text="APLICAR CAMBIOS", command=self.aplicar_ajuste_inteligente,
               bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=18).pack(side=tk.LEFT, padx=10)

        # Panel de resultados dividido en dos
        resultados_frame = Frame(main_frame)
        resultados_frame.pack(fill="both", expand=True)

        # Panel izquierdo: Lista de empleados en contra
        left_panel = Frame(resultados_frame, padx=5, pady=5, relief=tk.RIDGE, bd=2)
        left_panel.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 5))

        Label(left_panel, text="Empleados en Contra", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)

        # Treeview para empleados
        emp_columns = ("codigo", "nombre", "ingresos", "egresos", "saldo")
        emp_scroll = ttk.Scrollbar(left_panel, orient=tk.VERTICAL)

        self.aj_emp_treeview = ttk.Treeview(left_panel, columns=emp_columns, show="headings",
                                             yscrollcommand=emp_scroll.set, height=8)
        emp_scroll.config(command=self.aj_emp_treeview.yview)

        self.aj_emp_treeview.heading("codigo", text="Código", anchor="center")
        self.aj_emp_treeview.heading("nombre", text="Nombre", anchor="w")
        self.aj_emp_treeview.heading("ingresos", text="Ingresos", anchor="e")
        self.aj_emp_treeview.heading("egresos", text="Egresos", anchor="e")
        self.aj_emp_treeview.heading("saldo", text="Saldo", anchor="e")

        self.aj_emp_treeview.column("codigo", width=70, anchor="center")
        self.aj_emp_treeview.column("nombre", width=180, anchor="w")
        self.aj_emp_treeview.column("ingresos", width=80, anchor="e")
        self.aj_emp_treeview.column("egresos", width=80, anchor="e")
        self.aj_emp_treeview.column("saldo", width=80, anchor="e")

        emp_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.aj_emp_treeview.pack(fill="both", expand=True)

        # Tag para saldos negativos
        self.aj_emp_treeview.tag_configure('negativo', background='#ffcccc', foreground='darkred')
        self.aj_emp_treeview.tag_configure('positivo', background='#ccffcc')

        # Vincular selección
        self.aj_emp_treeview.bind('<<TreeviewSelect>>', self.mostrar_egresos_empleado_seleccionado)

        # Panel derecho: Egresos del empleado seleccionado
        right_panel = Frame(resultados_frame, padx=5, pady=5, relief=tk.RIDGE, bd=2)
        right_panel.pack(side=tk.RIGHT, fill="both", expand=True, padx=(5, 0))

        Label(right_panel, text="Egresos del Empleado Seleccionado (marcar para mover)", font=("Arial", 12, "bold")).pack(anchor="w", pady=5)

        # Treeview para egresos con checkboxes simulados
        egr_columns = ("seleccionar", "numero", "rubro", "valor", "fecha_ven")
        egr_scroll = ttk.Scrollbar(right_panel, orient=tk.VERTICAL)

        self.aj_egr_treeview = ttk.Treeview(right_panel, columns=egr_columns, show="headings",
                                             yscrollcommand=egr_scroll.set, height=8)
        egr_scroll.config(command=self.aj_egr_treeview.yview)

        self.aj_egr_treeview.heading("seleccionar", text="Mover", anchor="center")
        self.aj_egr_treeview.heading("numero", text="Número", anchor="center")
        self.aj_egr_treeview.heading("rubro", text="Rubro", anchor="w")
        self.aj_egr_treeview.heading("valor", text="Valor", anchor="e")
        self.aj_egr_treeview.heading("fecha_ven", text="Fecha Venc.", anchor="center")

        self.aj_egr_treeview.column("seleccionar", width=60, anchor="center")
        self.aj_egr_treeview.column("numero", width=70, anchor="center")
        self.aj_egr_treeview.column("rubro", width=180, anchor="w")
        self.aj_egr_treeview.column("valor", width=80, anchor="e")
        self.aj_egr_treeview.column("fecha_ven", width=100, anchor="center")

        egr_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.aj_egr_treeview.pack(fill="both", expand=True)

        # Tags para egresos
        self.aj_egr_treeview.tag_configure('seleccionado', background='#ffffcc')
        self.aj_egr_treeview.tag_configure('sugerido', background='#e6f3ff')

        # Vincular doble clic para seleccionar/deseleccionar
        self.aj_egr_treeview.bind('<Double-1>', self.toggle_egreso_seleccionado)

        # Panel inferior: Resumen
        resumen_frame = Frame(main_frame, padx=10, pady=10, relief=tk.GROOVE, bd=2)
        resumen_frame.pack(fill="x", expand=False, pady=(10, 0))

        self.aj_resumen_label = Label(resumen_frame, text="Seleccione empleados para analizar...",
                                       font=("Arial", 11), anchor="w")
        self.aj_resumen_label.pack(fill="x")

        # Variables para tracking
        self.aj_empleados_data = {}
        self.aj_egresos_seleccionados = {}

    def obtener_fechas_periodo(self):
        """Obtiene las fechas de inicio y fin del período seleccionado"""
        mes_nombre = self.aj_mes_combo.get()
        meses = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
                "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
        mes = meses.get(mes_nombre, 1)
        año = int(self.aj_año_spin.get())

        fecha_inicio = datetime(año, mes, 1)
        # Último día del mes
        if mes == 12:
            fecha_fin = datetime(año + 1, 1, 1) - timedelta(days=1)
        else:
            fecha_fin = datetime(año, mes + 1, 1) - timedelta(days=1)

        return fecha_inicio, fecha_fin

    def calcular_rol_empleado(self, cursor, codigo_empleado, fecha_inicio, fecha_fin):
        """
        Calcula el rol de un empleado usando la MISMA LÓGICA del generador de roles.
        Retorna: (total_ingresos, total_egresos, saldo, detalle_egresos)
        """
        # Mapeo de códigos de CLASE a conceptos (igual que el generador de roles)
        mapeo_conceptos = {
            100: 'SUELDO', 102: 'BONIFICACION', 104: 'FONDO_RESERVA',
            107: 'DECIMO_TERCERA', 108: 'DECIMO_CUARTA', 110: 'MANIOBRAS',
            111: 'REEMBOLSOS', 113: 'SOBRETIEMPO_25', 114: 'SOBRETIEMPO_50',
            115: 'SOBRETIEMPO_100', 120: 'MOVILIZACION', 200: 'APORT_IESS',
            201: 'ANTICIPOS_OTROS', 202: 'ANTICIPO_SUELDO', 203: 'MULTAS',
            204: 'PRESTAMOS_QUIROGRAFARIOS', 205: 'PRESTAMOS_COMPANIA',
            206: 'PENSION_ALIMENTICIA', 207: 'PRESTAMO_HIPOTECARIO',
            217: 'ANTICIPOS_OTROS', 218: 'APORT_IESS_CONYUGE',
            219: 'IMPUESTO_RENTA', 250: 'ANTICIPOS_SURTIDOS',
        }

        conceptos_ingresos = ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA',
                             'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25',
                             'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION']

        conceptos_egresos = ['APORT_IESS', 'PRESTAMOS_QUIROGRAFARIOS', 'PRESTAMOS_COMPANIA',
                            'ANTICIPO_SUELDO', 'ANTICIPOS_OTROS', 'ANTICIPOS_SURTIDOS',
                            'APORT_IESS_CONYUGE', 'IMPUESTO_RENTA', 'MULTAS',
                            'PENSION_ALIMENTICIA', 'PRESTAMO_HIPOTECARIO']

        # Códigos que se IGNORAN completamente (no suman a ingresos ni egresos)
        codigos_ignorar = {105, 126, 199}

        # Inicializar conceptos
        valores = {concepto: 0.0 for concepto in conceptos_ingresos + conceptos_egresos}

        # Obtener ANTIQUINC del empleado
        cursor.execute("SELECT ANTIQUINC FROM [insevig].[dbo].[RPEMPLEA] WHERE EMPLEADO = ?", (codigo_empleado,))
        row_emp = cursor.fetchone()
        antiquinc = row_emp[0] if row_emp and row_emp[0] else 0

        # Obtener todos los movimientos del período
        query_movimientos = """
        SELECT NUMERO, SECUENCIA, CLASE, VALOR, FECHA_VEN, CONCEPTO, CODIGO, ASENTADO, OBSERV
        FROM [insevig].[dbo].[RPINGDES]
        WHERE EMPLEADO = ?
          AND FECHA_VEN >= ?
          AND FECHA_VEN <= ?
        """
        cursor.execute(query_movimientos, (codigo_empleado, fecha_inicio, fecha_fin))
        movimientos = cursor.fetchall()

        egresos_detalle = []

        for mov in movimientos:
            numero, secuencia, clase, valor, fecha_ven, concepto, codigo, asentado, observ = mov

            if clase is None:
                continue

            clase_int = int(clase)
            valor_float = float(valor) if valor else 0.0

            # IGNORAR completamente estos códigos (no suman a nada)
            if clase_int in codigos_ignorar:
                continue

            # Guardar detalle de egresos para la tabla (solo EGR)
            if codigo == 'EGR':
                # Obtener nombre del rubro
                cursor.execute("""
                    SELECT NOMBRE_L FROM [insevig].[dbo].[RPRUBROS]
                    WHERE CLASE = ? AND CODIGO = 'EGR' AND CODEMP = '01' AND CODSUC = '001'
                """, (clase,))
                rubro_row = cursor.fetchone()
                nombre_rubro = rubro_row[0] if rubro_row else str(clase)

                egresos_detalle.append((numero, codigo_empleado, secuencia, clase,
                                        valor_float, fecha_ven, concepto, nombre_rubro))

            # Mapear a concepto
            if clase_int in mapeo_conceptos:
                concepto_nombre = mapeo_conceptos[clase_int]

                # Décimos (107, 108) solo se cuentan si ASENTADO = True
                if concepto_nombre in ['DECIMO_TERCERA', 'DECIMO_CUARTA']:
                    if asentado:
                        valores[concepto_nombre] += round(valor_float, 2)
                elif concepto_nombre in valores:
                    valores[concepto_nombre] += round(valor_float, 2)
            else:
                # Códigos no mapeados que son EGR van a ANTICIPOS_SURTIDOS
                if codigo == 'EGR':
                    valores['ANTICIPOS_SURTIDOS'] += round(valor_float, 2)
                # Códigos no mapeados que son ING se IGNORAN (no se suman a nada)

        # Calcular totales de ingresos y egresos
        total_ingresos = round(sum(valores[c] for c in conceptos_ingresos), 2)
        total_egresos = round(sum(valores[c] for c in conceptos_egresos), 2)

        # FONDO DE RESERVA cuando ANTIQUINC = 0 (fondo va al IESS):
        # - El FR aparece como INGRESO (el empleado lo "gana")
        # - Y también como EGRESO (se envía al IESS)
        if antiquinc == 0:
            if valores['FONDO_RESERVA'] > 0:
                # FR ya está en ingresos (vino de la BD), agregar mismo valor a egresos
                total_egresos += valores['FONDO_RESERVA']
            else:
                # FR no vino de la BD, calcularlo y agregar a ambos
                base_fondo = (valores['SUELDO'] + valores['BONIFICACION'] + valores['MANIOBRAS'] +
                             valores['SOBRETIEMPO_25'] + valores['SOBRETIEMPO_50'] + valores['SOBRETIEMPO_100'])
                fondo_reserva_calculado = round(base_fondo * 0.0833, 2)
                total_ingresos += fondo_reserva_calculado
                total_egresos += fondo_reserva_calculado

        saldo = round(total_ingresos - total_egresos, 2)

        # Ordenar egresos por valor DESC
        egresos_detalle.sort(key=lambda x: x[4], reverse=True)

        return total_ingresos, total_egresos, saldo, egresos_detalle

    def analizar_empleados_en_contra(self):
        """Analiza los empleados ingresados para identificar quiénes están en contra"""
        # Obtener códigos de empleados
        texto_codigos = self.aj_codigos_text.get("1.0", tk.END).strip()

        if not texto_codigos:
            messagebox.showwarning("Sin Datos", "Por favor ingrese los códigos de los empleados a analizar.")
            return

        # Parsear códigos (separados por comas, espacios o líneas)
        import re
        codigos = re.split(r'[,\s\n]+', texto_codigos)
        codigos = [c.strip() for c in codigos if c.strip()]

        if not codigos:
            messagebox.showwarning("Sin Datos", "No se encontraron códigos válidos.")
            return

        # Limpiar treeviews
        for item in self.aj_emp_treeview.get_children():
            self.aj_emp_treeview.delete(item)
        for item in self.aj_egr_treeview.get_children():
            self.aj_egr_treeview.delete(item)

        # Obtener período
        fecha_inicio, fecha_fin = self.obtener_fechas_periodo()

        # Cargar rubros si es necesario
        if not self.cache_rubros:
            self.cargar_rubros_cache()

        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()
            self.aj_empleados_data = {}
            empleados_en_contra = 0
            total_en_contra = 0.0

            for codigo in codigos:
                # Obtener info del empleado
                query_emp = """
                SELECT EMPLEADO, APELLIDOS, NOMBRES
                FROM [insevig].[dbo].[RPEMPLEA]
                WHERE EMPLEADO = ?
                """
                cursor.execute(query_emp, (codigo,))
                emp_info = cursor.fetchone()

                if not emp_info:
                    continue

                nombre_completo = f"{emp_info[1]} {emp_info[2]}".strip()

                # Calcular rol usando la misma lógica del generador de roles
                total_ingresos, total_egresos, saldo, egresos_detalle = self.calcular_rol_empleado(
                    cursor, codigo, fecha_inicio, fecha_fin
                )

                # Guardar datos
                self.aj_empleados_data[codigo] = {
                    'nombre': nombre_completo,
                    'ingresos': total_ingresos,
                    'egresos': total_egresos,
                    'saldo': saldo,
                    'egresos_detalle': egresos_detalle
                }

                # Determinar tag (tolerancia de 0.05 para errores de redondeo)
                TOLERANCIA = -0.05
                tag = 'negativo' if saldo < TOLERANCIA else 'positivo'

                # Insertar en treeview
                self.aj_emp_treeview.insert("", "end", iid=codigo, values=(
                    codigo,
                    nombre_completo[:25],
                    f"{total_ingresos:,.2f}",
                    f"{total_egresos:,.2f}",
                    f"{saldo:,.2f}"
                ), tags=(tag,))

                if saldo < TOLERANCIA:
                    empleados_en_contra += 1
                    total_en_contra += abs(saldo)

            # Actualizar resumen
            self.aj_resumen_label.config(
                text=f"Analizados: {len(self.aj_empleados_data)} empleados | "
                     f"En contra: {empleados_en_contra} | "
                     f"Total en contra: ${total_en_contra:,.2f}"
            )

            if empleados_en_contra > 0:
                messagebox.showinfo("Análisis Completado",
                                   f"Se encontraron {empleados_en_contra} empleados con saldo en contra.\n\n"
                                   f"Seleccione un empleado para ver sus egresos y marcar cuáles mover.")
            else:
                messagebox.showinfo("Análisis Completado",
                                   "Ninguno de los empleados analizados tiene saldo en contra.\n\n"
                                   "Nota: Si esperaba ver empleados en contra, verifique que:\n"
                                   "1. El período seleccionado sea correcto\n"
                                   "2. Los egresos no hayan sido movidos previamente")

        except Exception as e:
            messagebox.showerror("Error", f"Error al analizar empleados:\n{str(e)}")
        finally:
            self.cerrar_conexion()

    def mostrar_egresos_empleado_seleccionado(self, event=None):
        """Muestra los egresos del empleado seleccionado en el treeview derecho"""
        seleccion = self.aj_emp_treeview.selection()

        if not seleccion:
            return

        codigo = seleccion[0]

        if codigo not in self.aj_empleados_data:
            return

        # Limpiar treeview de egresos
        for item in self.aj_egr_treeview.get_children():
            self.aj_egr_treeview.delete(item)

        empleado_data = self.aj_empleados_data[codigo]
        saldo = empleado_data['saldo']

        # Inicializar selección si no existe (ahora usa tupla numero,secuencia)
        if codigo not in self.aj_egresos_seleccionados:
            self.aj_egresos_seleccionados[codigo] = set()

        # Sugerir egresos a mover si el saldo es negativo (tolerancia de 0.05)
        # CORREGIDO: Usar tupla (numero, secuencia) para identificar únicamente cada egreso
        TOLERANCIA = -0.05
        egresos_sugeridos = set()
        if saldo < TOLERANCIA:
            acumulado = 0.0
            deficit = abs(saldo)
            # Ordenar por valor DESC para mover los más grandes primero
            egresos_ordenados = sorted(empleado_data['egresos_detalle'], key=lambda x: float(x[4]) if x[4] else 0, reverse=True)
            for egreso in egresos_ordenados:
                numero = int(egreso[0])
                secuencia = int(egreso[2]) if egreso[2] else 0
                valor = float(egreso[4]) if egreso[4] else 0.0
                # Sugerir este egreso si aún no hemos cubierto el déficit
                if acumulado < deficit:
                    egresos_sugeridos.add((numero, secuencia))
                    acumulado += valor

        # Mostrar egresos
        for egreso in empleado_data['egresos_detalle']:
            numero = int(egreso[0])
            secuencia = int(egreso[2]) if egreso[2] else 0
            clase = str(egreso[3]).strip()
            valor = float(egreso[4]) if egreso[4] else 0.0
            fecha_ven = egreso[5].strftime("%d/%m/%Y") if egreso[5] else ""
            rubro_nombre = egreso[7] if egreso[7] else self.obtener_nombre_rubro(clase)

            # Clave única para este egreso
            egreso_key = (numero, secuencia)

            # Determinar si está seleccionado
            esta_seleccionado = egreso_key in self.aj_egresos_seleccionados[codigo]
            marca = "✓" if esta_seleccionado else ""

            # Determinar tag
            if esta_seleccionado:
                tag = 'seleccionado'
            elif egreso_key in egresos_sugeridos:
                tag = 'sugerido'
            else:
                tag = ''

            # ID único para el item
            item_id = f"{codigo}_{numero}_{secuencia}"

            self.aj_egr_treeview.insert("", "end", iid=item_id, values=(
                marca,
                numero,
                rubro_nombre[:30] if rubro_nombre else "",
                f"{valor:,.2f}",
                fecha_ven
            ), tags=(tag,))

    def toggle_egreso_seleccionado(self, event):
        """Alterna la selección de un egreso al hacer doble clic"""
        item = self.aj_egr_treeview.identify_row(event.y)

        if not item:
            return

        # Obtener código de empleado del item seleccionado en el otro treeview
        seleccion_emp = self.aj_emp_treeview.selection()
        if not seleccion_emp:
            return

        codigo = seleccion_emp[0]

        # Parsear el item_id para obtener número y secuencia
        partes = item.split('_')
        if len(partes) >= 3:
            numero = int(partes[1])
            secuencia = int(partes[2])
            egreso_key = (numero, secuencia)

            # Toggle selección
            if codigo not in self.aj_egresos_seleccionados:
                self.aj_egresos_seleccionados[codigo] = set()

            if egreso_key in self.aj_egresos_seleccionados[codigo]:
                self.aj_egresos_seleccionados[codigo].discard(egreso_key)
            else:
                self.aj_egresos_seleccionados[codigo].add(egreso_key)

            # Actualizar vista
            self.mostrar_egresos_empleado_seleccionado()

            # Actualizar resumen
            self.actualizar_resumen_ajuste()

    def seleccionar_egresos_sugeridos(self):
        """Selecciona automáticamente los egresos sugeridos para todos los empleados en contra.
        OBJETIVO: Dejar el saldo en 0 o lo más cercano posible sin quedarse en contra."""
        if not self.aj_empleados_data:
            messagebox.showwarning("Sin Datos", "Primero debe analizar los empleados.")
            return

        total_egresos_seleccionados = 0
        resumen_por_empleado = []

        for codigo, data in self.aj_empleados_data.items():
            saldo = data['saldo']

            if saldo >= 0:
                continue  # No está en contra, no necesita ajuste

            # Inicializar selección
            if codigo not in self.aj_egresos_seleccionados:
                self.aj_egresos_seleccionados[codigo] = set()
            else:
                self.aj_egresos_seleccionados[codigo].clear()

            deficit = abs(saldo)

            # Ordenar egresos por valor DESC para mover los más grandes primero
            egresos_ordenados = sorted(data['egresos_detalle'],
                                       key=lambda x: float(x[4]) if x[4] else 0,
                                       reverse=True)

            acumulado = 0.0
            egresos_a_mover = []

            for egreso in egresos_ordenados:
                numero = int(egreso[0])
                secuencia = int(egreso[2]) if egreso[2] else 0
                valor = float(egreso[4]) if egreso[4] else 0.0
                egreso_key = (numero, secuencia)

                # Mover egresos hasta cubrir el déficit (dejar saldo >= 0)
                if acumulado < deficit:
                    self.aj_egresos_seleccionados[codigo].add(egreso_key)
                    acumulado += valor
                    egresos_a_mover.append((numero, valor))
                    total_egresos_seleccionados += 1

            nuevo_saldo = saldo + acumulado
            resumen_por_empleado.append(f"  {codigo}: Saldo {saldo:,.2f} -> {nuevo_saldo:,.2f} (moviendo ${acumulado:,.2f})")

        # Actualizar vista
        self.mostrar_egresos_empleado_seleccionado()
        self.actualizar_resumen_ajuste()

        # Mostrar resumen detallado
        resumen_texto = f"Se han seleccionado {total_egresos_seleccionados} egresos para mover.\n\n"
        resumen_texto += "Resultado esperado por empleado:\n"
        resumen_texto += "\n".join(resumen_por_empleado[:10])  # Mostrar máximo 10
        if len(resumen_por_empleado) > 10:
            resumen_texto += f"\n  ... y {len(resumen_por_empleado) - 10} más"
        resumen_texto += "\n\nPuede revisar y ajustar la selección haciendo doble clic en cada egreso."

        messagebox.showinfo("Selección Automática", resumen_texto)

    def actualizar_resumen_ajuste(self):
        """Actualiza el resumen de egresos seleccionados"""
        total_egresos = 0
        total_valor = 0.0

        for codigo, egresos_keys in self.aj_egresos_seleccionados.items():
            if codigo in self.aj_empleados_data:
                for egreso in self.aj_empleados_data[codigo]['egresos_detalle']:
                    numero = int(egreso[0])
                    secuencia = int(egreso[2]) if egreso[2] else 0
                    egreso_key = (numero, secuencia)
                    if egreso_key in egresos_keys:
                        total_egresos += 1
                        total_valor += float(egreso[4]) if egreso[4] else 0.0

        empleados_en_contra = sum(1 for d in self.aj_empleados_data.values() if d['saldo'] < 0)

        # Calcular saldo esperado después de mover
        saldo_esperado_total = 0.0
        for codigo, data in self.aj_empleados_data.items():
            if data['saldo'] < 0:
                valor_a_mover = 0.0
                if codigo in self.aj_egresos_seleccionados:
                    for egreso in data['egresos_detalle']:
                        numero = int(egreso[0])
                        secuencia = int(egreso[2]) if egreso[2] else 0
                        if (numero, secuencia) in self.aj_egresos_seleccionados[codigo]:
                            valor_a_mover += float(egreso[4]) if egreso[4] else 0.0
                saldo_esperado = data['saldo'] + valor_a_mover
                saldo_esperado_total += saldo_esperado

        self.aj_resumen_label.config(
            text=f"Empleados en contra: {empleados_en_contra} | "
                 f"Egresos a mover: {total_egresos} | "
                 f"Valor: ${total_valor:,.2f} | "
                 f"Saldo esperado después: ${saldo_esperado_total:,.2f}"
        )

    def aplicar_ajuste_inteligente(self):
        """Aplica los cambios moviendo los egresos seleccionados al siguiente período"""
        # Verificar que hay egresos seleccionados
        total_egresos = sum(len(keys) for keys in self.aj_egresos_seleccionados.values())

        if total_egresos == 0:
            messagebox.showwarning("Sin Selección",
                                  "No hay egresos seleccionados para mover.\n\n"
                                  "Seleccione los egresos haciendo doble clic o use 'Seleccionar Egresos Sugeridos'.")
            return

        # Calcular fecha destino (primer día del siguiente mes)
        fecha_inicio, fecha_fin = self.obtener_fechas_periodo()
        fecha_destino = fecha_fin + timedelta(days=1)  # Primer día del siguiente mes

        # Calcular resumen esperado
        resumen_esperado = []
        for codigo, data in self.aj_empleados_data.items():
            if codigo in self.aj_egresos_seleccionados and self.aj_egresos_seleccionados[codigo]:
                valor_a_mover = 0.0
                for egreso in data['egresos_detalle']:
                    numero = int(egreso[0])
                    secuencia = int(egreso[2]) if egreso[2] else 0
                    if (numero, secuencia) in self.aj_egresos_seleccionados[codigo]:
                        valor_a_mover += float(egreso[4]) if egreso[4] else 0.0
                saldo_esperado = data['saldo'] + valor_a_mover
                resumen_esperado.append(f"  {codigo}: {data['saldo']:,.2f} -> {saldo_esperado:,.2f}")

        # Contar cuántos de los seleccionados son ANTICIPOS_OTROS (no se mueven, se cuadran a 0)
        total_anticipos_otros = 0
        for codigo, data in self.aj_empleados_data.items():
            if codigo in self.aj_egresos_seleccionados:
                for egreso in data['egresos_detalle']:
                    numero = int(egreso[0])
                    secuencia = int(egreso[2]) if egreso[2] else 0
                    clase_egr = int(egreso[3]) if egreso[3] else 0
                    if (numero, secuencia) in self.aj_egresos_seleccionados[codigo] and clase_egr in (201, 217):
                        total_anticipos_otros += 1

        # Confirmación detallada
        detalles_cambios = f"Se moverán {total_egresos} egresos al período {fecha_destino.strftime('%d/%m/%Y')}.\n\n"
        detalles_cambios += "Resultado esperado:\n"
        detalles_cambios += "\n".join(resumen_esperado[:8])
        if len(resumen_esperado) > 8:
            detalles_cambios += f"\n  ... y {len(resumen_esperado) - 8} más"
        if total_anticipos_otros > 0:
            detalles_cambios += (f"\n\nNOTA: {total_anticipos_otros} de los seleccionados son "
                                  f"ANTICIPOS OTROS (clase 201/217). Estos NO se moverán de fecha: "
                                  f"se cuadrarán a 0 en el mes actual, ya que ese concepto se cuadra "
                                  f"por un proceso distinto y no se traslada al siguiente mes.")
        detalles_cambios += "\n\nSe creará un respaldo automático antes de aplicar los cambios."

        confirmar = messagebox.askyesno("Confirmar Cambios", detalles_cambios + "\n\n¿Está seguro de continuar?")
        if not confirmar:
            return

        if not self.conectar_bd():
            return

        try:
            # Convertir selección a formato para respaldo (numero -> [secuencias])
            egresos_para_respaldo = {}
            for codigo, keys in self.aj_egresos_seleccionados.items():
                egresos_para_respaldo[codigo] = set()
                for numero, secuencia in keys:
                    egresos_para_respaldo[codigo].add(numero)

            # PASO 1: Crear respaldo ANTES de modificar
            registrar_log("INICIO_AJUSTE_INTELIGENTE", {
                "total_egresos": total_egresos,
                "fecha_destino": fecha_destino.strftime("%Y-%m-%d"),
                "empleados": list(self.aj_egresos_seleccionados.keys())
            })

            archivo_respaldo = crear_respaldo_egresos(
                self.conn,
                egresos_para_respaldo,
                f"Ajuste Inteligente - Mover al {fecha_destino.strftime('%d/%m/%Y')}"
            )

            if not archivo_respaldo:
                messagebox.showerror("Error de Respaldo",
                                    "No se pudo crear el respaldo. La operación ha sido cancelada por seguridad.")
                registrar_log("AJUSTE_CANCELADO", {"motivo": "Error al crear respaldo"}, exito=False)
                self.cerrar_conexion()
                return

            # PASO 2: Aplicar cambios
            cursor = self.conn.cursor()
            self.conn.autocommit = False
            actualizados = 0
            cuadrados_sin_traslado = 0
            errores = 0
            cambios_detalle = []

            # Mapa (empleado, numero, secuencia) -> clase, para detectar ANTICIPOS_OTROS
            clase_lookup = {}
            for codigo_emp, data_emp in self.aj_empleados_data.items():
                for egreso in data_emp['egresos_detalle']:
                    num_egr = int(egreso[0])
                    sec_egr = int(egreso[2]) if egreso[2] else 0
                    clase_lookup[(codigo_emp, num_egr, sec_egr)] = int(egreso[3]) if egreso[3] else 0

            for codigo, egresos_keys in self.aj_egresos_seleccionados.items():
                for numero, secuencia in egresos_keys:
                    try:
                        clase_egreso = clase_lookup.get((codigo, numero, secuencia))

                        if clase_egreso in (201, 217):
                            # ANTICIPOS_OTROS (clase 201/217): se cuadran en el mes actual y
                            # NUNCA se trasladan al siguiente mes (ese concepto se cuadra por
                            # un proceso distinto). Se escribe el VALOR a 0 en sitio, sin
                            # mover FECHA_VEN.
                            query_update = """
                            UPDATE [insevig].[dbo].[RPINGDES]
                            SET VALOR = 0
                            WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                            """
                            cursor.execute(query_update, (codigo, numero, secuencia))
                            filas_afectadas = cursor.rowcount
                            actualizados += filas_afectadas
                            cuadrados_sin_traslado += filas_afectadas

                            cambios_detalle.append({
                                "empleado": codigo,
                                "numero": numero,
                                "secuencia": secuencia,
                                "accion": "CUADRADO_ANTICIPO_OTROS_SIN_TRASLADO",
                                "filas_afectadas": filas_afectadas
                            })

                            continue

                        # Obtener fecha original para el log
                        query_original = """
                        SELECT FECHA_VEN FROM [insevig].[dbo].[RPINGDES]
                        WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                        """
                        cursor.execute(query_original, (codigo, numero, secuencia))
                        fecha_original = cursor.fetchone()
                        fecha_original_str = fecha_original[0].strftime("%Y-%m-%d") if fecha_original and fecha_original[0] else "N/A"

                        # Actualizar FECHA_VEN usando NUMERO y SECUENCIA para identificar exactamente
                        query_update = """
                        UPDATE [insevig].[dbo].[RPINGDES]
                        SET FECHA_VEN = ?
                        WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                        """
                        cursor.execute(query_update, (fecha_destino, codigo, numero, secuencia))
                        filas_afectadas = cursor.rowcount
                        actualizados += filas_afectadas

                        cambios_detalle.append({
                            "empleado": codigo,
                            "numero": numero,
                            "secuencia": secuencia,
                            "fecha_original": fecha_original_str,
                            "fecha_nueva": fecha_destino.strftime("%Y-%m-%d"),
                            "filas_afectadas": filas_afectadas
                        })

                    except Exception as e:
                        errores += 1
                        registrar_log("ERROR_ACTUALIZAR_REGISTRO", {
                            "empleado": codigo,
                            "numero": numero,
                            "secuencia": secuencia,
                            "error": str(e)
                        }, exito=False)

            self.conn.commit()

            # PASO 3: Registrar éxito en el log
            registrar_log("AJUSTE_COMPLETADO", {
                "registros_actualizados": actualizados,
                "anticipos_otros_cuadrados_sin_traslado": cuadrados_sin_traslado,
                "errores": errores,
                "archivo_respaldo": archivo_respaldo,
                "fecha_destino": fecha_destino.strftime("%Y-%m-%d"),
                "cambios": cambios_detalle
            })

            # Limpiar selecciones
            self.aj_egresos_seleccionados = {}

            # Mensaje de éxito con información del respaldo
            mensaje_exito = f"Se actualizaron {actualizados} registros correctamente.\n\n"
            mensaje_exito += f"Los egresos fueron movidos al {fecha_destino.strftime('%d/%m/%Y')}.\n\n"
            if cuadrados_sin_traslado > 0:
                mensaje_exito += (f"De estos, {cuadrados_sin_traslado} son ANTICIPOS OTROS "
                                  f"(clase 201/217): se cuadraron a 0 en el mes actual y NO "
                                  f"se trasladaron al siguiente mes.\n\n")
            mensaje_exito += f"Errores: {errores}\n\n"
            mensaje_exito += f"RESPALDO GUARDADO EN:\n{archivo_respaldo}\n\n"
            mensaje_exito += "Si necesita deshacer los cambios, use la opción 'Restaurar Respaldo' en el menú Archivo."

            messagebox.showinfo("Cambios Aplicados", mensaje_exito)

            # Volver a analizar para ver el resultado
            self.analizar_empleados_en_contra()

        except Exception as e:
            if self.conn:
                self.conn.rollback()
            registrar_log("ERROR_AJUSTE_INTELIGENTE", {"error": str(e)}, exito=False)
            messagebox.showerror("Error", f"Error al aplicar cambios:\n{str(e)}\n\nLos cambios han sido revertidos.")
        finally:
            if self.conn:
                try:
                    self.conn.autocommit = True
                except:
                    pass
            self.cerrar_conexion()

    # =========== PESTAÑA DE AJUSTE PRECISO (DIVIDIR EGRESOS) ===========
    def inicializar_tab_ajuste_preciso(self):
        """Inicializa la pestaña para ajuste preciso dividiendo egresos"""
        # Variables
        self.ap_empleados_data = {}
        self.ap_ajustes_calculados = {}

        # Egresos que NO se pueden dividir/mover (IESS, Fondos Reserva, etc.)
        self.egresos_intocables = {200, 218, 219}  # APORT_IESS, APORT_IESS_CONYUGE, IMPUESTO_RENTA

        # Panel principal
        main_frame = Frame(self.tab_ajuste_preciso, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Panel superior para configuración
        config_frame = Frame(main_frame, padx=10, pady=10, relief=tk.RIDGE, bd=2)
        config_frame.pack(fill="x", expand=False, pady=(0, 10))

        # Título
        Label(config_frame, text="Ajuste Preciso - Dividir Egresos para Saldo = 0 (Personal Activo)",
              font=("Arial", 14, "bold"), fg="darkblue").grid(row=0, column=0, columnspan=6, pady=10, sticky="w")

        # Explicación
        Label(config_frame, text="Este ajuste DIVIDE los egresos: una parte queda este mes (para saldo=0) y otra se crea como NUEVO registro para el próximo mes.",
              font=("Arial", 9), fg="gray").grid(row=1, column=0, columnspan=6, sticky="w", padx=5)

        # Período del rol
        Label(config_frame, text="Período del Rol:", font=("Arial", 11)).grid(row=2, column=0, sticky="w", padx=5, pady=5)

        periodo_frame = Frame(config_frame)
        periodo_frame.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        Label(periodo_frame, text="Mes:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))
        self.ap_mes_combo = ttk.Combobox(periodo_frame, width=10, state="readonly",
                                          values=["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        hoy = datetime.now()
        mes_anterior = hoy.month - 1 if hoy.month > 1 else 12
        self.ap_mes_combo.current(mes_anterior - 1)
        self.ap_mes_combo.pack(side=tk.LEFT, padx=(0, 15))

        Label(periodo_frame, text="Año:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))
        año_actual = hoy.year if hoy.month > 1 else hoy.year - 1
        self.ap_año_spin = ttk.Spinbox(periodo_frame, from_=2020, to=2030, width=6)
        self.ap_año_spin.set(año_actual)
        self.ap_año_spin.pack(side=tk.LEFT)

        # Campo para códigos de empleados
        Label(config_frame, text="Códigos de Empleados:", font=("Arial", 11)).grid(row=3, column=0, sticky="nw", padx=5, pady=5)

        codigos_frame = Frame(config_frame)
        codigos_frame.grid(row=3, column=1, columnspan=3, sticky="w", padx=5, pady=5)

        self.ap_codigos_text = tk.Text(codigos_frame, width=50, height=2, font=("Arial", 10))
        self.ap_codigos_text.pack(side=tk.LEFT, fill="x", expand=True)

        # Botones de acción
        botones_frame = Frame(config_frame)
        botones_frame.grid(row=4, column=0, columnspan=6, pady=10)

        Button(botones_frame, text="1. Analizar Empleados", command=self.ap_analizar_empleados,
               bg="#FF9800", fg="white", font=("Arial", 11, "bold"), width=18).pack(side=tk.LEFT, padx=5)

        Button(botones_frame, text="2. Calcular Ajustes", command=self.ap_calcular_ajustes,
               bg="#2196F3", fg="white", font=("Arial", 11, "bold"), width=18).pack(side=tk.LEFT, padx=5)

        Button(botones_frame, text="3. APLICAR DIVISIÓN", command=self.ap_aplicar_division,
               bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=18).pack(side=tk.LEFT, padx=5)

        # Panel de resultados
        resultados_frame = Frame(main_frame, relief=tk.RIDGE, bd=2)
        resultados_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Treeview para mostrar los ajustes calculados
        columns = ("empleado", "nombre", "saldo_actual", "egreso_dividir", "valor_original",
                   "queda_mes", "pasa_siguiente", "saldo_final")

        scroll_y = ttk.Scrollbar(resultados_frame, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(resultados_frame, orient=tk.HORIZONTAL)

        self.ap_treeview = ttk.Treeview(resultados_frame, columns=columns, show="headings",
                                         yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.config(command=self.ap_treeview.yview)
        scroll_x.config(command=self.ap_treeview.xview)

        # Configurar columnas
        self.ap_treeview.heading("empleado", text="Empleado", anchor="center")
        self.ap_treeview.heading("nombre", text="Nombre", anchor="w")
        self.ap_treeview.heading("saldo_actual", text="Saldo Actual", anchor="e")
        self.ap_treeview.heading("egreso_dividir", text="Egreso a Dividir", anchor="w")
        self.ap_treeview.heading("valor_original", text="Valor Original", anchor="e")
        self.ap_treeview.heading("queda_mes", text="Queda Este Mes", anchor="e")
        self.ap_treeview.heading("pasa_siguiente", text="Pasa al Siguiente", anchor="e")
        self.ap_treeview.heading("saldo_final", text="Saldo Final", anchor="e")

        self.ap_treeview.column("empleado", width=70, anchor="center")
        self.ap_treeview.column("nombre", width=150, anchor="w")
        self.ap_treeview.column("saldo_actual", width=90, anchor="e")
        self.ap_treeview.column("egreso_dividir", width=180, anchor="w")
        self.ap_treeview.column("valor_original", width=90, anchor="e")
        self.ap_treeview.column("queda_mes", width=100, anchor="e")
        self.ap_treeview.column("pasa_siguiente", width=100, anchor="e")
        self.ap_treeview.column("saldo_final", width=80, anchor="e")

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.ap_treeview.pack(fill="both", expand=True)

        # Tags para colores
        self.ap_treeview.tag_configure('negativo', background='#ffcccc')
        self.ap_treeview.tag_configure('cero', background='#ccffcc')
        self.ap_treeview.tag_configure('division', background='#fff3cd')
        self.ap_treeview.tag_configure('anticipo_cuadre', background='#ffd699')

        # Panel de resumen
        resumen_frame = Frame(main_frame, padx=10, pady=10, relief=tk.GROOVE, bd=2)
        resumen_frame.pack(fill="x", expand=False)

        self.ap_resumen_label = Label(resumen_frame, text="Ingrese códigos de empleados y presione 'Analizar Empleados'",
                                       font=("Arial", 11), anchor="w")
        self.ap_resumen_label.pack(fill="x")

        # Info sobre egresos intocables
        info_frame = Frame(main_frame, padx=10, pady=5)
        info_frame.pack(fill="x")
        Label(info_frame, text="Egresos que NO se dividen: APORT.IESS, APORT.IESS CONYUGE, IMPUESTO RENTA",
              font=("Arial", 9, "italic"), fg="red").pack(anchor="w")
        Label(info_frame, text="ANTICIPOS OTROS (clase 201/217): se cuadran en el mes actual (a 0 o proporcional), el sobrante NO se traslada al siguiente mes",
              font=("Arial", 9, "italic"), fg="#b36b00").pack(anchor="w")

        # Botón de diagnóstico
        Button(info_frame, text="Diagnóstico Detallado", command=self.ap_diagnostico_detallado,
               bg="#9C27B0", fg="white", font=("Arial", 9)).pack(anchor="e", pady=5)

    def ap_diagnostico_detallado(self):
        """Muestra diagnóstico detallado del cálculo del rol para los empleados"""
        if not self.ap_empleados_data:
            messagebox.showwarning("Sin Datos", "Primero debe analizar los empleados.")
            return

        fecha_inicio, fecha_fin = self.ap_obtener_fechas_periodo()

        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()

            # Crear ventana de diagnóstico
            diag_window = tk.Toplevel(self.root)
            diag_window.title("Diagnóstico Detallado de Cálculo de Rol")
            diag_window.geometry("900x600")

            # Text widget con scroll
            text_frame = Frame(diag_window)
            text_frame.pack(fill="both", expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(text_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=("Courier", 9))
            text_widget.pack(fill="both", expand=True)
            scrollbar.config(command=text_widget.yview)

            # Generar diagnóstico
            diagnostico = f"{'='*80}\n"
            diagnostico += f"DIAGNÓSTICO DE CÁLCULO DE ROL\n"
            diagnostico += f"Período: {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}\n"
            diagnostico += f"{'='*80}\n\n"

            for codigo, data in self.ap_empleados_data.items():
                diagnostico += f"\n{'='*80}\n"
                diagnostico += f"EMPLEADO: {codigo} - {data['nombre']}\n"
                diagnostico += f"{'='*80}\n"

                # Obtener ANTIQUINC
                cursor.execute("SELECT ANTIQUINC, SUELDO FROM [insevig].[dbo].[RPEMPLEA] WHERE EMPLEADO = ?", (codigo,))
                emp_row = cursor.fetchone()
                antiquinc = emp_row[0] if emp_row and emp_row[0] else 0
                sueldo_base = emp_row[1] if emp_row and emp_row[1] else 0

                diagnostico += f"ANTIQUINC: {antiquinc} (0=Fondo Reserva al IESS, 1=Acumulado)\n"
                diagnostico += f"SUELDO BASE EN FICHA: {sueldo_base}\n\n"

                # Obtener todos los movimientos
                cursor.execute("""
                    SELECT NUMERO, SECUENCIA, CLASE, VALOR, CODIGO, CONCEPTO, ASENTADO, FECHA_VEN
                    FROM [insevig].[dbo].[RPINGDES]
                    WHERE EMPLEADO = ? AND FECHA_VEN >= ? AND FECHA_VEN <= ?
                    ORDER BY CODIGO, CLASE
                """, (codigo, fecha_inicio, fecha_fin))
                movimientos = cursor.fetchall()

                # Separar ingresos y egresos
                ingresos = []
                egresos = []
                total_ing = 0.0
                total_egr = 0.0

                diagnostico += "MOVIMIENTOS ENCONTRADOS:\n"
                diagnostico += "-" * 70 + "\n"
                diagnostico += f"{'CODIGO':<6} {'CLASE':<6} {'VALOR':>12} {'ASENTADO':<8} {'CONCEPTO':<30}\n"
                diagnostico += "-" * 70 + "\n"

                for mov in movimientos:
                    numero, secuencia, clase, valor, tipo, concepto, asentado, fecha_ven = mov
                    valor = float(valor) if valor else 0.0
                    clase_int = int(clase) if clase else 0

                    diagnostico += f"{tipo:<6} {clase_int:<6} {valor:>12.2f} {str(asentado):<8} {(concepto or '')[:30]:<30}\n"

                    if tipo == 'ING':
                        ingresos.append((clase_int, valor, concepto, asentado))
                        total_ing += valor
                    elif tipo == 'EGR':
                        egresos.append((clase_int, valor, concepto, asentado))
                        total_egr += valor

                diagnostico += "-" * 70 + "\n\n"

                # Calcular según la lógica del programa
                diagnostico += "CÁLCULO SEGÚN LÓGICA DEL PROGRAMA:\n"
                diagnostico += "-" * 40 + "\n"

                # Mapeo de conceptos
                mapeo = {
                    100: 'SUELDO', 102: 'BONIFICACION', 104: 'FONDO_RESERVA',
                    107: 'DECIMO_TERCERA', 108: 'DECIMO_CUARTA', 110: 'MANIOBRAS',
                    111: 'REEMBOLSOS', 113: 'SOBRETIEMPO_25', 114: 'SOBRETIEMPO_50',
                    115: 'SOBRETIEMPO_100', 120: 'MOVILIZACION', 200: 'APORT_IESS',
                    201: 'ANTICIPOS_OTROS', 202: 'ANTICIPO_SUELDO', 203: 'MULTAS',
                    204: 'PREST_QUIROG', 205: 'PREST_CIA', 206: 'PENSION_ALIM',
                    207: 'PREST_HIPOT', 217: 'ANTICIPOS_OTROS', 218: 'APORT_IESS_CON',
                    219: 'IMP_RENTA', 250: 'ANTIC_SURTIDOS',
                }

                # Códigos que se IGNORAN completamente (igual que calcular_rol_empleado)
                codigos_ignorar = {105, 126, 199}

                valores = {}
                otros_egr_no_mapeados = 0.0  # Para códigos EGR no mapeados que van a ANTICIPOS_SURTIDOS

                # Procesar INGRESOS
                for clase, valor, concepto, asentado in ingresos:
                    if clase in codigos_ignorar:
                        diagnostico += f"  (IGNORADO ING: clase {clase} = {valor:.2f})\n"
                        continue
                    nombre = mapeo.get(clase, None)
                    if nombre is None:
                        # Ingresos no mapeados se IGNORAN (no se suman a nada)
                        diagnostico += f"  (IGNORADO ING NO MAPEADO: clase {clase} = {valor:.2f})\n"
                        continue
                    # Décimos solo si asentado
                    if clase in [107, 108] and not asentado:
                        diagnostico += f"  (IGNORADO DECIMO: {nombre} no asentado = {valor:.2f})\n"
                        continue
                    if nombre not in valores:
                        valores[nombre] = 0.0
                    valores[nombre] += valor

                # Procesar EGRESOS
                for clase, valor, concepto, asentado in egresos:
                    if clase in codigos_ignorar:
                        diagnostico += f"  (IGNORADO EGR: clase {clase} = {valor:.2f})\n"
                        continue
                    nombre = mapeo.get(clase, None)
                    if nombre is None:
                        # Egresos no mapeados van a ANTICIPOS_SURTIDOS
                        otros_egr_no_mapeados += valor
                        diagnostico += f"  (EGR NO MAPEADO clase {clase} -> ANTIC_SURTIDOS: {valor:.2f})\n"
                        continue
                    if nombre not in valores:
                        valores[nombre] = 0.0
                    valores[nombre] += valor

                # Agregar otros egresos no mapeados a ANTIC_SURTIDOS
                if otros_egr_no_mapeados > 0:
                    if 'ANTIC_SURTIDOS' not in valores:
                        valores['ANTIC_SURTIDOS'] = 0.0
                    valores['ANTIC_SURTIDOS'] += otros_egr_no_mapeados

                diagnostico += "Valores por concepto:\n"
                for nombre, valor in sorted(valores.items()):
                    diagnostico += f"  {nombre}: {valor:.2f}\n"

                # Totales
                conceptos_ing = ['SUELDO', 'BONIFICACION', 'FONDO_RESERVA', 'DECIMO_TERCERA',
                                'DECIMO_CUARTA', 'MANIOBRAS', 'REEMBOLSOS', 'SOBRETIEMPO_25',
                                'SOBRETIEMPO_50', 'SOBRETIEMPO_100', 'MOVILIZACION']
                conceptos_egr = ['APORT_IESS', 'PREST_QUIROG', 'PREST_CIA', 'ANTICIPO_SUELDO',
                                'ANTICIPOS_OTROS', 'ANTIC_SURTIDOS', 'APORT_IESS_CON',
                                'IMP_RENTA', 'MULTAS', 'PENSION_ALIM', 'PREST_HIPOT']

                suma_ing = sum(valores.get(c, 0) for c in conceptos_ing)
                suma_egr = sum(valores.get(c, 0) for c in conceptos_egr)

                diagnostico += f"\nSuma Ingresos (sin FR en IESS): {suma_ing:.2f}\n"
                diagnostico += f"Suma Egresos (sin FR en IESS): {suma_egr:.2f}\n"

                # Fondo de reserva si ANTIQUINC = 0 (FR va al IESS)
                if antiquinc == 0:
                    fr_de_bd = valores.get('FONDO_RESERVA', 0)
                    if fr_de_bd > 0:
                        # FR ya está en ingresos (vino de BD), agregar mismo valor a egresos
                        diagnostico += f"\nFONDO RESERVA EN IESS (ANTIQUINC=0):\n"
                        diagnostico += f"  FR de BD (ya en ingresos): {fr_de_bd:.2f}\n"
                        diagnostico += f"  Se agrega TAMBIÉN a EGRESOS (va al IESS)\n"
                        suma_egr += fr_de_bd
                    else:
                        # FR no vino de BD, calcularlo
                        base_fr = valores.get('SUELDO', 0) + valores.get('BONIFICACION', 0) + valores.get('MANIOBRAS', 0)
                        base_fr += valores.get('SOBRETIEMPO_25', 0) + valores.get('SOBRETIEMPO_50', 0) + valores.get('SOBRETIEMPO_100', 0)
                        fr_calculado = round(base_fr * 0.0833, 2)
                        diagnostico += f"\nFONDO RESERVA CALCULADO (ANTIQUINC=0):\n"
                        diagnostico += f"  Base: {base_fr:.2f}\n"
                        diagnostico += f"  FR 8.33%: {fr_calculado:.2f}\n"
                        diagnostico += f"  Se suma a INGRESOS Y EGRESOS\n"
                        suma_ing += fr_calculado
                        suma_egr += fr_calculado

                saldo_calculado = round(suma_ing - suma_egr, 2)

                diagnostico += f"\n{'='*40}\n"
                diagnostico += f"TOTAL INGRESOS: {suma_ing:.2f}\n"
                diagnostico += f"TOTAL EGRESOS:  {suma_egr:.2f}\n"
                diagnostico += f"SALDO CALCULADO: {saldo_calculado:.2f}\n"
                diagnostico += f"{'='*40}\n"

                # Tolerancia de 0.05 para errores de redondeo
                TOLERANCIA = -0.05
                if saldo_calculado < TOLERANCIA:
                    diagnostico += f">>> EMPLEADO EN CONTRA: ${abs(saldo_calculado):.2f}\n"
                else:
                    diagnostico += f">>> EMPLEADO OK (saldo positivo o balanceado)\n"

                diagnostico += "\n"

            text_widget.insert(tk.END, diagnostico)
            text_widget.config(state=tk.DISABLED)

            # Botón para copiar
            Button(diag_window, text="Copiar al Portapapeles",
                   command=lambda: self.root.clipboard_clear() or self.root.clipboard_append(diagnostico)).pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Error en diagnóstico:\n{str(e)}")
        finally:
            self.cerrar_conexion()

    def ap_obtener_fechas_periodo(self):
        """Obtiene las fechas del período para ajuste preciso"""
        mes_nombre = self.ap_mes_combo.get()
        meses = {"Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
                "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12}
        mes = meses.get(mes_nombre, 1)
        año = int(self.ap_año_spin.get())

        fecha_inicio = datetime(año, mes, 1)
        if mes == 12:
            fecha_fin = datetime(año + 1, 1, 1) - timedelta(days=1)
        else:
            fecha_fin = datetime(año, mes + 1, 1) - timedelta(days=1)

        return fecha_inicio, fecha_fin

    def ap_analizar_empleados(self):
        """Analiza los empleados para el ajuste preciso"""
        texto_codigos = self.ap_codigos_text.get("1.0", tk.END).strip()

        if not texto_codigos:
            messagebox.showwarning("Sin Datos", "Por favor ingrese los códigos de los empleados.")
            return

        import re
        codigos = re.split(r'[,\s\n]+', texto_codigos)
        codigos = [c.strip() for c in codigos if c.strip()]

        if not codigos:
            messagebox.showwarning("Sin Datos", "No se encontraron códigos válidos.")
            return

        # Limpiar treeview
        for item in self.ap_treeview.get_children():
            self.ap_treeview.delete(item)

        fecha_inicio, fecha_fin = self.ap_obtener_fechas_periodo()

        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()
            self.ap_empleados_data = {}
            empleados_en_contra = 0

            for codigo in codigos:
                # Obtener info del empleado
                cursor.execute("""
                    SELECT EMPLEADO, APELLIDOS, NOMBRES, ESTADO
                    FROM [insevig].[dbo].[RPEMPLEA]
                    WHERE EMPLEADO = ?
                """, (codigo,))
                emp_info = cursor.fetchone()

                if not emp_info:
                    continue

                nombre_completo = f"{emp_info[1]} {emp_info[2]}".strip()
                estado = emp_info[3]

                # Calcular rol
                total_ingresos, total_egresos, saldo, egresos_detalle = self.calcular_rol_empleado(
                    cursor, codigo, fecha_inicio, fecha_fin
                )

                # Guardar datos
                self.ap_empleados_data[codigo] = {
                    'nombre': nombre_completo,
                    'estado': estado,
                    'ingresos': total_ingresos,
                    'egresos': total_egresos,
                    'saldo': saldo,
                    'egresos_detalle': egresos_detalle
                }

                # Mostrar en treeview (tolerancia de 0.05 para errores de redondeo)
                TOLERANCIA = -0.05
                tag = 'negativo' if saldo < TOLERANCIA else 'cero'
                self.ap_treeview.insert("", "end", iid=f"emp_{codigo}", values=(
                    codigo,
                    nombre_completo[:20],
                    f"{saldo:,.2f}",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-"
                ), tags=(tag,))

                if saldo < TOLERANCIA:
                    empleados_en_contra += 1

            self.ap_resumen_label.config(
                text=f"Analizados: {len(self.ap_empleados_data)} | En contra: {empleados_en_contra} | "
                     f"Presione 'Calcular Ajustes' para ver la división de egresos"
            )

            if empleados_en_contra > 0:
                messagebox.showinfo("Análisis Completado",
                                   f"Se encontraron {empleados_en_contra} empleados con saldo negativo.\n\n"
                                   f"Presione 'Calcular Ajustes' para calcular cómo dividir los egresos.")

        except Exception as e:
            messagebox.showerror("Error", f"Error al analizar:\n{str(e)}")
        finally:
            self.cerrar_conexion()

    def ap_calcular_ajustes(self):
        """Calcula cómo dividir los egresos para que el saldo quede en 0"""
        if not self.ap_empleados_data:
            messagebox.showwarning("Sin Datos", "Primero debe analizar los empleados.")
            return

        # Limpiar treeview
        for item in self.ap_treeview.get_children():
            self.ap_treeview.delete(item)

        self.ap_ajustes_calculados = {}
        total_ajustes = 0

        # Tolerancia de 0.05 para errores de redondeo
        TOLERANCIA = -0.05

        for codigo, data in self.ap_empleados_data.items():
            saldo = data['saldo']
            nombre = data['nombre']

            if saldo >= TOLERANCIA:
                # No necesita ajuste
                self.ap_treeview.insert("", "end", iid=f"ok_{codigo}", values=(
                    codigo, nombre[:20], f"{saldo:,.2f}",
                    "No necesita ajuste", "-", "-", "-", f"{saldo:,.2f}"
                ), tags=('cero',))
                continue

            # Necesita ajuste - encontrar egresos que se pueden dividir
            deficit = abs(saldo)
            egresos_disponibles = []

            for egreso in data['egresos_detalle']:
                numero, empleado, secuencia, clase, valor, fecha_ven, concepto, nombre_rubro = egreso
                clase_int = int(clase) if clase else 0

                # Excluir egresos intocables
                if clase_int not in self.egresos_intocables and valor > 0:
                    egresos_disponibles.append({
                        'numero': numero,
                        'secuencia': secuencia,
                        'clase': clase_int,
                        'valor': valor,
                        'concepto': concepto,
                        'nombre_rubro': nombre_rubro,
                        'fecha_ven': fecha_ven
                    })

            # Ordenar por valor DESC
            egresos_disponibles.sort(key=lambda x: x['valor'], reverse=True)

            ajustes_empleado = []
            deficit_restante = deficit

            for egreso in egresos_disponibles:
                if deficit_restante <= 0:
                    break

                valor_original = egreso['valor']
                # ANTICIPOS_OTROS (clase 201/217) se cuadran en el mes actual: el sobrante
                # se escribe a 0/proporcional y NUNCA se traslada al siguiente mes, porque
                # ese concepto se cuadra por un proceso distinto.
                es_anticipo_otros = egreso['clase'] in (201, 217)

                if valor_original <= deficit_restante:
                    # Se consume completo para cuadrar el déficit
                    queda_mes = 0
                    pasa_siguiente = valor_original
                    deficit_restante -= valor_original
                else:
                    # Dividir este egreso
                    queda_mes = valor_original - deficit_restante
                    pasa_siguiente = deficit_restante
                    deficit_restante = 0

                ajuste = {
                    'numero': egreso['numero'],
                    'secuencia': egreso['secuencia'],
                    'clase': egreso['clase'],
                    'valor_original': valor_original,
                    'queda_mes': round(queda_mes, 2),
                    'pasa_siguiente': round(pasa_siguiente, 2),
                    'concepto': egreso['concepto'],
                    'nombre_rubro': egreso['nombre_rubro'],
                    'fecha_ven': egreso['fecha_ven'],
                    'es_anticipo_otros': es_anticipo_otros
                }
                ajustes_empleado.append(ajuste)
                total_ajustes += 1

                # Mostrar en treeview
                # Para ANTICIPOS_OTROS el sobrante se escribe a 0 en el mes actual (no se
                # traslada), por lo que no afecta el saldo esperado del siguiente mes.
                saldo_final = saldo + sum(
                    a['pasa_siguiente'] for a in ajustes_empleado if not a['es_anticipo_otros']
                )

                if es_anticipo_otros:
                    tag = 'anticipo_cuadre'
                    nombre_rubro_mostrar = (egreso['nombre_rubro'][:20] if egreso['nombre_rubro'] else f"Clase {egreso['clase']}") + " [CUADRE]"
                    pasa_siguiente_texto = f"{pasa_siguiente:,.2f} (no traslada)"
                else:
                    tag = 'division'
                    nombre_rubro_mostrar = egreso['nombre_rubro'][:25] if egreso['nombre_rubro'] else f"Clase {egreso['clase']}"
                    pasa_siguiente_texto = f"{pasa_siguiente:,.2f}"

                self.ap_treeview.insert("", "end", values=(
                    codigo,
                    nombre[:20],
                    f"{saldo:,.2f}",
                    nombre_rubro_mostrar,
                    f"{valor_original:,.2f}",
                    f"{queda_mes:,.2f}",
                    pasa_siguiente_texto,
                    f"{saldo_final:,.2f}"
                ), tags=(tag,))

            if ajustes_empleado:
                self.ap_ajustes_calculados[codigo] = {
                    'nombre': nombre,
                    'saldo_original': saldo,
                    'ajustes': ajustes_empleado
                }

        # Resumen
        empleados_ajustar = len(self.ap_ajustes_calculados)
        self.ap_resumen_label.config(
            text=f"Ajustes calculados: {total_ajustes} egresos a dividir en {empleados_ajustar} empleados | "
                 f"Presione 'APLICAR DIVISIÓN' para ejecutar"
        )

        if empleados_ajustar > 0:
            messagebox.showinfo("Cálculo Completado",
                               f"Se calcularon {total_ajustes} divisiones de egresos.\n\n"
                               f"Revise la tabla y presione 'APLICAR DIVISIÓN' para ejecutar los cambios.")

    def ap_aplicar_division(self):
        """Aplica la división de egresos: modifica el original y crea nuevo registro - VERSIÓN CORREGIDA"""
        if not self.ap_ajustes_calculados:
            messagebox.showwarning("Sin Ajustes", "Primero debe calcular los ajustes.")
            return

        # Contar total de operaciones
        total_ops = sum(len(data['ajustes']) for data in self.ap_ajustes_calculados.values())

        # Obtener fecha del siguiente mes
        fecha_inicio, fecha_fin = self.ap_obtener_fechas_periodo()
        fecha_siguiente_mes = fecha_fin + timedelta(days=1)

        # Contar operaciones de anticipos otros (se cuadran, no se trasladan)
        total_anticipos_otros = sum(
            1 for data in self.ap_ajustes_calculados.values()
            for ajuste in data['ajustes'] if ajuste.get('es_anticipo_otros')
        )

        # Confirmación
        confirmar = messagebox.askyesno("Confirmar División de Egresos",
            f"Se realizarán {total_ops} operaciones:\n\n"
            f"• Modificar valor de egresos originales (lo que queda este mes)\n"
            f"• Crear NUEVOS registros para el siguiente mes ({fecha_siguiente_mes.strftime('%d/%m/%Y')})\n\n"
            f"Los nuevos registros tendrán el comentario 'SALDO PENDIENTE MES ANTERIOR'\n\n"
            + (f"NOTA: {total_anticipos_otros} de estas operaciones son ANTICIPOS OTROS "
               f"(clase 201/217): se cuadrarán en el mes actual (a 0 o proporcional) y su "
               f"sobrante NO se trasladará al siguiente mes.\n\n" if total_anticipos_otros else "")
            + f"IMPORTANTE: Se creará un respaldo automático antes de cada modificación.\n\n"
            f"¿Está seguro de continuar?")

        if not confirmar:
            return

        if not self.conectar_bd():
            return

        try:
            # Log inicio
            registrar_log("INICIO_AJUSTE_PRECISO", {
                "total_operaciones": total_ops,
                "fecha_siguiente_mes": fecha_siguiente_mes.strftime("%Y-%m-%d"),
                "empleados": list(self.ap_ajustes_calculados.keys())
            })

            modificados = 0
            creados = 0
            cuadrados_sin_traslado = 0
            errores = 0
            errores_detalles = []
            detalles_cambios = []

            # CRÍTICO: Procesar cada empleado en su propia transacción
            for codigo, data in self.ap_ajustes_calculados.items():
                for ajuste in data['ajustes']:
                    # Crear nueva conexión y cursor para cada operación
                    conn_individual = None
                    try:
                        # Conectar con autocommit desactivado
                        conn_str = (
                            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                            f'SERVER={self.server};'
                            f'DATABASE={self.database};'
                            f'UID={self.username};'
                            f'PWD={self.password};'
                            f'Encrypt=No;'
                            f'TrustServerCertificate=yes;'
                        )
                        conn_individual = pyodbc.connect(conn_str)
                        conn_individual.autocommit = False
                        cursor = conn_individual.cursor()

                        numero = ajuste['numero']
                        secuencia = ajuste['secuencia']
                        valor_original = ajuste['valor_original']
                        queda_mes = ajuste['queda_mes']
                        pasa_siguiente = ajuste['pasa_siguiente']
                        concepto_original = ajuste['concepto'] or ""

                        # PASO 1: CREAR RESPALDO ANTES DE MODIFICAR
                        empleados_numeros = {codigo: [numero]}
                        archivo_respaldo = crear_respaldo_egresos(
                            conn_individual,
                            empleados_numeros,
                            f"Ajuste Preciso - Emp:{codigo} Num:{numero} Sec:{secuencia}"
                        )

                        if not archivo_respaldo:
                            raise Exception("No se pudo crear el respaldo - operación cancelada por seguridad")

                        if ajuste.get('es_anticipo_otros'):
                            # CASO ESPECIAL: ANTICIPOS_OTROS (clase 201/217) se cuadran en el
                            # mes actual. El sobrante NO se traslada al siguiente mes (ese
                            # concepto se cuadra por un proceso distinto) - simplemente se
                            # escribe el VALOR a 0 o al proporcional que corresponda, sin
                            # crear ningún registro nuevo ni mover FECHA_VEN.
                            cursor.execute("""
                                UPDATE [insevig].[dbo].[RPINGDES]
                                SET VALOR = ?
                                WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                            """, (queda_mes, codigo, numero, secuencia))

                            if cursor.rowcount == 0:
                                raise Exception(f"No se encontró el registro a cuadrar (Emp:{codigo} Num:{numero} Sec:{secuencia})")

                            modificados += cursor.rowcount
                            cuadrados_sin_traslado += 1

                            detalles_cambios.append({
                                "empleado": codigo,
                                "numero": numero,
                                "secuencia": secuencia,
                                "valor_original": valor_original,
                                "queda_mes": queda_mes,
                                "respaldo": archivo_respaldo,
                                "accion": "CUADRADO_ANTICIPO_OTROS_SIN_TRASLADO"
                            })

                        elif queda_mes > 0:
                            # CASO 1: Dividir - modificar el original y crear NUEVO egreso

                            # Actualizar el registro original con el valor que queda este mes
                            cursor.execute("""
                                UPDATE [insevig].[dbo].[RPINGDES]
                                SET VALOR = ?
                                WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                            """, (queda_mes, codigo, numero, secuencia))

                            if cursor.rowcount == 0:
                                raise Exception(f"No se encontró el registro a modificar (Emp:{codigo} Num:{numero} Sec:{secuencia})")

                            modificados += cursor.rowcount

                            # Obtener el SIGUIENTE NUMERO desde la tabla RPCONTRL con bloqueo
                            cursor.execute("""
                                SELECT ULT_EGR FROM [insevig].[dbo].[RPCONTRL] WITH (UPDLOCK, HOLDLOCK)
                            """)
                            ult_egr = cursor.fetchone()
                            if ult_egr and ult_egr[0] is not None:
                                nuevo_numero = int(ult_egr[0]) + 1
                            else:
                                raise Exception("No se pudo obtener ULT_EGR de RPCONTRL")

                            # Obtener datos del registro original para copiar
                            cursor.execute("""
                                SELECT FECHA, CODSUC, CODEMP, CODIGO, CLASE, DEPTO, SECCION,
                                       HORAS, DIAS, ASENTADO, ACTUALIZA, APORTA, MONTO,
                                       DIVIDENDO, ROL, TIPO_PGO, TIPO_TRA, OBSERV
                                FROM [insevig].[dbo].[RPINGDES]
                                WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                            """, (codigo, numero, secuencia))
                            reg_original = cursor.fetchone()

                            if not reg_original:
                                raise Exception(f"No se pudo obtener datos del registro original")

                            # TRUNCAR textos para evitar errores de límite de campo
                            # CONCEPTO: máximo 30 caracteres
                            nuevo_concepto = f"{concepto_original} - SALDO PDTE"
                            if len(nuevo_concepto) > 30:
                                nuevo_concepto = nuevo_concepto[:30]

                            # OBSERV: máximo 700 caracteres
                            observ_original = reg_original[17] if reg_original[17] else ""
                            nueva_observ = f"Dividido #{numero} Sec:{secuencia} Orig:${valor_original:.2f} Queda:${queda_mes:.2f} Pasa:${pasa_siguiente:.2f}"

                            # Si la observación original cabe, agregarla
                            if len(observ_original) + len(nueva_observ) + 3 <= 700:
                                nueva_observ = f"{observ_original} | {nueva_observ}"

                            # Truncar si excede el límite
                            if len(nueva_observ) > 700:
                                nueva_observ = nueva_observ[:697] + "..."

                            # Insertar nuevo registro para el siguiente mes
                            cursor.execute("""
                                INSERT INTO [insevig].[dbo].[RPINGDES]
                                (NUMERO, FECHA, EMPLEADO, CODSUC, CODEMP, CODIGO, CLASE, SECUENCIA,
                                 DEPTO, SECCION, HORAS, VALOR, FECHA_VEN, CONCEPTO, DIAS,
                                 ASENTADO, ACTUALIZA, APORTA, MONTO, DIVIDENDO, ROL, TIPO_PGO, TIPO_TRA, OBSERV)
                                VALUES (?, ?, ?, ?, ?, 'EGR', ?, 1, ?, ?, ?, ?, ?, ?, ?,
                                        ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                nuevo_numero, reg_original[0], codigo, reg_original[1], reg_original[2],
                                reg_original[4], reg_original[5], reg_original[6],
                                reg_original[7], pasa_siguiente, fecha_siguiente_mes, nuevo_concepto,
                                reg_original[8], reg_original[9], reg_original[10], reg_original[11],
                                reg_original[12], reg_original[13], reg_original[14], reg_original[15],
                                reg_original[16], nueva_observ
                            ))

                            # Actualizar RPCONTRL con el nuevo número
                            cursor.execute("""
                                UPDATE [insevig].[dbo].[RPCONTRL] SET ULT_EGR = ?
                            """, (nuevo_numero,))

                            creados += 1

                            # Registrar detalle
                            detalles_cambios.append({
                                "empleado": codigo,
                                "numero_original": numero,
                                "secuencia_original": secuencia,
                                "nuevo_numero": nuevo_numero,
                                "valor_original": valor_original,
                                "queda_mes": queda_mes,
                                "pasa_siguiente": pasa_siguiente,
                                "respaldo": archivo_respaldo,
                                "accion": "DIVIDIDO"
                            })

                        else:
                            # CASO 2: Mover todo al siguiente mes (valor queda_mes = 0)
                            # Truncar el texto a agregar en OBSERV
                            texto_movido = " - MOVIDO AL SGT MES"

                            cursor.execute("""
                                UPDATE [insevig].[dbo].[RPINGDES]
                                SET FECHA_VEN = ?,
                                    OBSERV = CASE
                                        WHEN LEN(ISNULL(OBSERV, '')) + ? <= 700
                                        THEN ISNULL(OBSERV, '') + ?
                                        ELSE LEFT(ISNULL(OBSERV, ''), 700 - ?) + ?
                                    END
                                WHERE EMPLEADO = ? AND NUMERO = ? AND SECUENCIA = ? AND CODIGO = 'EGR'
                            """, (fecha_siguiente_mes, len(texto_movido), texto_movido,
                                  len(texto_movido), texto_movido, codigo, numero, secuencia))

                            if cursor.rowcount == 0:
                                raise Exception(f"No se encontró el registro a mover")

                            modificados += cursor.rowcount

                            # Registrar detalle
                            detalles_cambios.append({
                                "empleado": codigo,
                                "numero": numero,
                                "secuencia": secuencia,
                                "valor_original": valor_original,
                                "respaldo": archivo_respaldo,
                                "accion": "MOVIDO"
                            })

                        # COMMIT individual por empleado - si llega aquí, todo salió bien
                        conn_individual.commit()

                    except Exception as e:
                        # Rollback individual - solo afecta este empleado
                        if conn_individual:
                            conn_individual.rollback()

                        errores += 1
                        error_msg = str(e)
                        errores_detalles.append({
                            "empleado": codigo,
                            "numero": numero,
                            "error": error_msg
                        })

                        registrar_log("ERROR_DIVISION_EGRESO", {
                            "empleado": codigo,
                            "numero": ajuste['numero'],
                            "secuencia": secuencia,
                            "error": error_msg
                        }, exito=False)

                    finally:
                        # Cerrar conexión individual
                        if conn_individual:
                            try:
                                conn_individual.close()
                            except:
                                pass

            # Log éxito general
            registrar_log("AJUSTE_PRECISO_COMPLETADO", {
                "registros_modificados": modificados,
                "registros_creados": creados,
                "anticipos_otros_cuadrados_sin_traslado": cuadrados_sin_traslado,
                "errores": errores,
                "cambios": detalles_cambios[:10],  # Solo primeros 10 para no saturar el log
                "errores_detalles": errores_detalles
            })

            # Limpiar
            self.ap_ajustes_calculados = {}

            # Mensaje detallado
            mensaje = f"Operación completada:\n\n"
            mensaje += f"• Registros modificados: {modificados}\n"
            mensaje += f"• Nuevos registros creados: {creados}\n"
            if cuadrados_sin_traslado > 0:
                mensaje += f"• Anticipos Otros cuadrados sin traslado a próximo mes: {cuadrados_sin_traslado}\n"
            mensaje += f"• Errores: {errores}\n\n"

            if creados > 0:
                mensaje += f"Los nuevos egresos fueron creados para {fecha_siguiente_mes.strftime('%d/%m/%Y')}\n\n"

            if errores > 0:
                mensaje += f"ATENCIÓN: Hubo {errores} error(es). Revise el log para detalles.\n"
                mensaje += f"Los empleados con errores NO fueron modificados (rollback individual)."
            else:
                mensaje += "Todos los respaldos se crearon exitosamente."

            if errores > 0:
                messagebox.showwarning("División Completada con Errores", mensaje)
            else:
                messagebox.showinfo("División Completada Exitosamente", mensaje)

            # Volver a analizar
            self.ap_analizar_empleados()

        except Exception as e:
            registrar_log("ERROR_AJUSTE_PRECISO_GENERAL", {"error": str(e)}, exito=False)
            messagebox.showerror("Error General", f"Error al procesar división:\n{str(e)}")
        finally:
            self.cerrar_conexion()

def exportar_tabla_a_excel():
    """
    Función auxiliar para exportar la tabla RPINGDES completa a Excel.
    Útil para verificar los cambios realizados.
    """
    try:
        # Mostrar ventana de diálogo
        export_window = tk.Toplevel()
        export_window.title("Exportar Tabla a Excel")
        export_window.geometry("400x200")
        export_window.resizable(False, False)
        
        Label(export_window, text="Exportar Tabla RPINGDES a Excel", 
              font=("Arial", 14, "bold")).pack(pady=10)
        
        Label(export_window, text="Esta operación puede tardar varios minutos\ndependiendo del tamaño de la tabla.").pack(pady=10)
        
        progress_label = Label(export_window, text="Estado: Esperando...")
        progress_label.pack(pady=10)
        
        def iniciar_exportacion():
            progress_label.config(text="Estado: Conectando a la base de datos...")
            
            try:
                # Parámetros de conexión
                server = 'SERVER\\server'
                database = 'insevig'
                username = 'sa'
                password = 'puntosoft123*'
                
                # Cadena de conexión
                conn_str = (
                    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                    f'SERVER={server};'
                    f'DATABASE={database};'
                    f'UID={username};'
                    f'PWD={password};'
                    f'Encrypt=No;'
                    f'TrustServerCertificate=yes;'
                    f'ApplicationIntent=ReadOnly;'
                )
                
                # Establecer conexión
                progress_label.config(text="Estado: Conectando a la base de datos...")
                conn = pyodbc.connect(conn_str)
                
                # Ejecutar consulta para obtener los datos
                progress_label.config(text="Estado: Ejecutando consulta...")
                query = "SELECT * FROM [dbo].[RPINGDES]"
                df = pd.read_sql(query, conn)
                
                # Cerrar la conexión
                conn.close()
                
                # Verificar si se obtuvieron datos
                if df.empty:
                    progress_label.config(text="Estado: No se encontraron datos.")
                    messagebox.showwarning("Sin Datos", "No se encontraron datos en la tabla RPINGDES.")
                    return
                
                # Crear nombre de archivo con timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archivo_excel = f"RPINGDES_{timestamp}.xlsx"
                
                # Crear un escritor de Excel
                progress_label.config(text=f"Estado: Creando archivo Excel...")
                
                with pd.ExcelWriter(archivo_excel, engine='xlsxwriter') as writer:
                    # Convertir el DataFrame a Excel
                    df.to_excel(writer, sheet_name='RPINGDES', index=False)
                    
                    # Obtener el objeto workbook y worksheet
                    workbook = writer.book
                    worksheet = writer.sheets['RPINGDES']
                    
                    # Definir formatos
                    header_format = workbook.add_format({
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'fg_color': '#D7E4BC',
                        'border': 1
                    })
                    
                    # Aplicar formato a encabezados
                    for col_num, value in enumerate(df.columns.values):
                        worksheet.write(0, col_num, value, header_format)
                    
                    # Ajustar ancho de columnas basado en el contenido
                    for i, col in enumerate(df.columns):
                        column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(i, i, column_width)
                
                progress_label.config(text=f"Estado: ¡Exportación completada!")
                messagebox.showinfo("Éxito", f"Archivo Excel creado exitosamente: {os.path.abspath(archivo_excel)}")
                export_window.destroy()
                
            except Exception as e:
                progress_label.config(text=f"Estado: Error - {str(e)}")
                messagebox.showerror("Error", f"Error al exportar tabla a Excel: {e}")
        
        # Botones
        Button(export_window, text="Iniciar Exportación", command=iniciar_exportacion,
               bg="#4CAF50", fg="white", font=("Arial", 11)).pack(pady=10)
        
        Button(export_window, text="Cancelar", command=export_window.destroy,
               bg="#f44336", fg="white", font=("Arial", 11)).pack()
        
        # Centrar la ventana
        export_window.update_idletasks()
        width = export_window.winfo_width()
        height = export_window.winfo_height()
        x = (export_window.winfo_screenwidth() // 2) - (width // 2)
        y = (export_window.winfo_screenheight() // 2) - (height // 2)
        export_window.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        export_window.transient()
        export_window.grab_set()
        
    except Exception as e:
        messagebox.showerror("Error", f"Error al abrir la ventana de exportación: {e}")

def abrir_carpeta_logs():
    """Abre la carpeta de logs en el explorador de archivos"""
    try:
        abrir_ruta_multiplataforma(CARPETA_LOGS)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir la carpeta de logs:\n{e}")

def abrir_carpeta_respaldos():
    """Abre la carpeta de respaldos en el explorador de archivos"""
    try:
        abrir_ruta_multiplataforma(CARPETA_RESPALDOS)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir la carpeta de respaldos:\n{e}")

def restaurar_respaldo_gui(app):
    """Interfaz gráfica para restaurar desde un respaldo"""
    # Listar respaldos disponibles
    try:
        archivos = [f for f in os.listdir(CARPETA_RESPALDOS) if f.endswith('.json')]
        archivos.sort(reverse=True)  # Más recientes primero

        if not archivos:
            messagebox.showinfo("Sin Respaldos", "No hay archivos de respaldo disponibles.")
            return

        # Crear ventana de selección
        ventana = tk.Toplevel()
        ventana.title("Restaurar desde Respaldo")
        ventana.geometry("600x400")
        ventana.resizable(True, True)

        Label(ventana, text="Seleccione un archivo de respaldo para restaurar:",
              font=("Arial", 12, "bold")).pack(pady=10)

        # Frame para lista con scroll
        list_frame = Frame(ventana)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Courier", 10), height=15)
        listbox.pack(fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        # Llenar lista con detalles de cada respaldo
        respaldos_info = {}
        for archivo in archivos:
            try:
                ruta_completa = os.path.join(CARPETA_RESPALDOS, archivo)
                with open(ruta_completa, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    fecha = data.get('fecha_respaldo', 'Fecha desconocida')
                    motivo = data.get('motivo', 'Sin motivo')
                    num_registros = len(data.get('registros', []))
                    info = f"{archivo} | {fecha} | {num_registros} reg. | {motivo[:30]}"
                    listbox.insert(tk.END, info)
                    respaldos_info[info] = ruta_completa
            except:
                listbox.insert(tk.END, f"{archivo} (Error al leer)")
                respaldos_info[f"{archivo} (Error al leer)"] = os.path.join(CARPETA_RESPALDOS, archivo)

        # Label para mostrar detalles
        detalles_label = Label(ventana, text="", font=("Arial", 9), fg="gray", wraplength=550)
        detalles_label.pack(pady=5)

        def mostrar_detalles(event):
            seleccion = listbox.curselection()
            if seleccion:
                info = listbox.get(seleccion[0])
                ruta = respaldos_info.get(info)
                if ruta and os.path.exists(ruta):
                    try:
                        with open(ruta, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            empleados = set(r.get('EMPLEADO', '') for r in data.get('registros', []))
                            detalles_label.config(text=f"Empleados: {', '.join(sorted(empleados)[:10])}...")
                    except:
                        pass

        listbox.bind('<<ListboxSelect>>', mostrar_detalles)

        def ejecutar_restauracion():
            seleccion = listbox.curselection()
            if not seleccion:
                messagebox.showwarning("Sin Selección", "Seleccione un archivo de respaldo.")
                return

            info = listbox.get(seleccion[0])
            ruta = respaldos_info.get(info)

            if not ruta or not os.path.exists(ruta):
                messagebox.showerror("Error", "No se puede acceder al archivo de respaldo.")
                return

            # Confirmar restauración
            confirmar = messagebox.askyesno("Confirmar Restauración",
                                           f"¿Está seguro de restaurar los datos desde:\n\n{os.path.basename(ruta)}?\n\n"
                                           "Esto revertirá los cambios hechos a las fechas de vencimiento.")
            if not confirmar:
                return

            # Conectar y restaurar
            try:
                conn_str = (
                    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                    f'SERVER={app.server};'
                    f'DATABASE={app.database};'
                    f'UID={app.username};'
                    f'PWD={app.password};'
                    f'Encrypt=No;'
                    f'TrustServerCertificate=yes;'
                )
                conn = pyodbc.connect(conn_str)

                restaurados = restaurar_desde_respaldo(conn, ruta)

                conn.close()

                messagebox.showinfo("Restauración Exitosa",
                                   f"Se restauraron {restaurados} registros correctamente.\n\n"
                                   "Los datos han sido revertidos al estado del respaldo.")
                ventana.destroy()

            except Exception as e:
                messagebox.showerror("Error de Restauración", f"Error al restaurar:\n{str(e)}")
                registrar_log("ERROR_RESTAURACION_GUI", {"error": str(e)}, exito=False)

        # Botones
        btn_frame = Frame(ventana)
        btn_frame.pack(pady=10)

        Button(btn_frame, text="Restaurar Seleccionado", command=ejecutar_restauracion,
               bg="#FF9800", fg="white", font=("Arial", 11, "bold"), width=20).pack(side=tk.LEFT, padx=10)

        Button(btn_frame, text="Cancelar", command=ventana.destroy,
               bg="#f44336", fg="white", font=("Arial", 11), width=12).pack(side=tk.LEFT, padx=10)

        # Centrar ventana
        ventana.update_idletasks()
        x = (ventana.winfo_screenwidth() // 2) - (ventana.winfo_width() // 2)
        y = (ventana.winfo_screenheight() // 2) - (ventana.winfo_height() // 2)
        ventana.geometry(f'+{x}+{y}')

        ventana.transient()
        ventana.grab_set()

    except Exception as e:
        messagebox.showerror("Error", f"Error al listar respaldos:\n{str(e)}")

def restaurar_empleados_manual():
    """Restaura egresos de empleados específicos moviendo FECHA_VEN de Enero a Diciembre"""
    import pyodbc

    ventana = tk.Toplevel()
    ventana.title("Restaurar Empleados Manual")
    ventana.geometry("500x400")

    Label(ventana, text="RESTAURAR EGRESOS DE EMPLEADOS", font=("Arial", 12, "bold")).pack(pady=10)
    Label(ventana, text="Esta función mueve los egresos de Enero 2026 de vuelta a Diciembre 2025").pack()

    Label(ventana, text="\nIngrese los códigos de empleados (uno por línea):").pack()

    text_frame = Frame(ventana)
    text_frame.pack(fill="both", expand=True, padx=20, pady=10)

    codigos_text = tk.Text(text_frame, height=8, width=30)
    codigos_text.pack()

    resultado_label = Label(ventana, text="", fg="blue")
    resultado_label.pack(pady=10)

    def ver_estado():
        """Muestra el estado actual de los egresos de los empleados"""
        import re
        texto = codigos_text.get("1.0", tk.END).strip()
        codigos = re.split(r'[,\s\n]+', texto)
        codigos = [c.strip() for c in codigos if c.strip()]

        if not codigos:
            messagebox.showwarning("Sin Datos", "Ingrese códigos de empleados")
            return

        try:
            conn_str = (
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=SERVER\\server;'
                'DATABASE=insevig;'
                'UID=sa;'
                'PWD=puntosoft123*;'
                'Encrypt=No;'
                'TrustServerCertificate=yes;'
            )
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            info = "ESTADO ACTUAL DE EGRESOS:\n" + "="*50 + "\n\n"

            for codigo in codigos:
                cursor.execute("""
                    SELECT NUMERO, SECUENCIA, CLASE, VALOR, FECHA_VEN, CONCEPTO
                    FROM [insevig].[dbo].[RPINGDES]
                    WHERE EMPLEADO = ? AND CODIGO = 'EGR'
                    AND FECHA_VEN >= CONVERT(datetime, '20251201', 112)
                    AND FECHA_VEN <= CONVERT(datetime, '20260131', 112)
                    ORDER BY FECHA_VEN
                """, (codigo,))

                egresos = cursor.fetchall()
                info += f"\nEMPLEADO {codigo}:\n"
                info += "-"*40 + "\n"

                if egresos:
                    for e in egresos:
                        try:
                            numero = int(e[0]) if e[0] else 0
                            secuencia = int(e[1]) if e[1] else 0
                            clase = str(e[2]) if e[2] else ""
                            valor = float(e[3]) if e[3] else 0.0
                            fecha = e[4].strftime("%d/%m/%Y") if e[4] else "N/A"
                            concepto = str(e[5])[:20] if e[5] else ""
                            info += f"  #{numero} Sec:{secuencia} Clase:{clase} ${valor:.2f} -> {fecha} ({concepto})\n"
                        except:
                            info += f"  Error leyendo registro\n"
                else:
                    info += "  No tiene egresos en Dic 2025 / Ene 2026\n"

            conn.close()

            # Mostrar en ventana
            info_window = tk.Toplevel(ventana)
            info_window.title("Estado de Egresos")
            info_window.geometry("600x400")

            text_info = tk.Text(info_window, wrap=tk.WORD)
            text_info.pack(fill="both", expand=True, padx=10, pady=10)
            text_info.insert(tk.END, info)
            text_info.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")

    def ejecutar_restauracion():
        """Ejecuta la restauración moviendo de Enero a Diciembre"""
        import re
        texto = codigos_text.get("1.0", tk.END).strip()
        codigos = re.split(r'[,\s\n]+', texto)
        codigos = [c.strip() for c in codigos if c.strip()]

        if not codigos:
            messagebox.showwarning("Sin Datos", "Ingrese códigos de empleados")
            return

        confirmar = messagebox.askyesno("Confirmar",
            f"Se moverán TODOS los egresos de Enero 2026 a Diciembre 2025\n"
            f"para los empleados: {', '.join(codigos)}\n\n"
            f"¿Está seguro?")

        if not confirmar:
            return

        try:
            conn_str = (
                'DRIVER={ODBC Driver 17 for SQL Server};'
                'SERVER=SERVER\\server;'
                'DATABASE=insevig;'
                'UID=sa;'
                'PWD=puntosoft123*;'
                'Encrypt=No;'
                'TrustServerCertificate=yes;'
            )
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            total_actualizados = 0
            detalles = []

            for codigo in codigos:
                # Actualizar FECHA_VEN de Enero 2026 a 31/12/2025
                cursor.execute("""
                    UPDATE [insevig].[dbo].[RPINGDES]
                    SET FECHA_VEN = CONVERT(datetime, '20251231', 112)
                    WHERE EMPLEADO = ? AND CODIGO = 'EGR'
                    AND FECHA_VEN >= CONVERT(datetime, '20260101', 112)
                    AND FECHA_VEN <= CONVERT(datetime, '20260131', 112)
                """, (codigo,))

                filas = cursor.rowcount
                total_actualizados += filas
                detalles.append(f"Empleado {codigo}: {filas} egresos restaurados")

            conn.commit()
            conn.close()

            # Log
            registrar_log("RESTAURACION_MANUAL", {
                "empleados": codigos,
                "total_restaurados": total_actualizados,
                "detalles": detalles
            })

            messagebox.showinfo("Restauración Completada",
                f"Egresos restaurados a Diciembre 2025:\n\n" +
                "\n".join(detalles) +
                f"\n\nTotal: {total_actualizados} registros")

            resultado_label.config(text=f"Restaurados: {total_actualizados} registros", fg="green")

        except Exception as e:
            messagebox.showerror("Error", f"Error: {str(e)}")

    btn_frame = Frame(ventana)
    btn_frame.pack(pady=10)

    Button(btn_frame, text="Ver Estado Actual", command=ver_estado, bg="lightblue").pack(side=tk.LEFT, padx=5)
    Button(btn_frame, text="RESTAURAR A DICIEMBRE", command=ejecutar_restauracion, bg="orange").pack(side=tk.LEFT, padx=5)
    Button(btn_frame, text="Cerrar", command=ventana.destroy).pack(side=tk.LEFT, padx=5)

def main():
    root = tk.Tk()
    root.title("Modificador RPINGDES Completo v2.0 - Ver Egresos y Ajuste Inteligente")
    
    # Crear una barra de menú
    menu_bar = tk.Menu(root)
    
    # Crear el menú Archivo
    file_menu = tk.Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="Exportar RPINGDES a Excel", command=exportar_tabla_a_excel)
    file_menu.add_separator()
    file_menu.add_command(label="Restaurar desde Respaldo", command=lambda: restaurar_respaldo_gui(app))
    file_menu.add_command(label="Restaurar Empleados Manual", command=restaurar_empleados_manual)
    file_menu.add_separator()
    file_menu.add_command(label="Ver Logs", command=abrir_carpeta_logs)
    file_menu.add_command(label="Ver Respaldos", command=abrir_carpeta_respaldos)
    file_menu.add_separator()
    file_menu.add_command(label="Salir", command=root.destroy)
    
    # Agregar el menú Archivo a la barra de menú
    menu_bar.add_cascade(label="Archivo", menu=file_menu)
    
    # Crear el menú Ayuda
    help_menu = tk.Menu(menu_bar, tearoff=0)
    
    def mostrar_acerca_de():
        messagebox.showinfo("Acerca de",
                          "Modificador RPINGDES Completo v2.0\n\n"
                          "Aplicación para modificar la tabla RPINGDES:\n"
                          "- Modificación de registros individuales (FECHA_VEN y VALOR)\n"
                          "- Modificación masiva de préstamos con múltiples cuotas\n"
                          "- Consulta de Egresos del Período con generación de PDF\n"
                          "- Ajuste Inteligente de Egresos para evitar saldos en contra\n\n"
                          "Desarrollado para INSEVIG")
    
    help_menu.add_command(label="Acerca de", command=mostrar_acerca_de)
    
    # Agregar el menú Ayuda a la barra de menú
    menu_bar.add_cascade(label="Ayuda", menu=help_menu)
    
    # Configurar la barra de menú
    root.config(menu=menu_bar)
    
    app = ModificadorRPINGDESApp(root)
    
    # Centrar la ventana
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry('{}x{}+{}+{}'.format(width, height, x, y))
    
    root.mainloop()

if __name__ == "__main__":
    main()
