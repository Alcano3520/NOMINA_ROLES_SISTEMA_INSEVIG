import pyodbc
import os
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

CARPETA_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs_modificaciones")
if not os.path.exists(CARPETA_LOGS):
    os.makedirs(CARPETA_LOGS)

# Tablas de nomina/RRHH que usa el Modificador de Egresos y Prestamos
TABLAS_NOMINA = {"RPINGDES", "RPCONTRL", "RPEMPLEA", "RPRUBROS", "DBTABLAS", "RPINGDESRES"}


def registrar_log(tipo_operacion, detalles):
    try:
        archivo_log = os.path.join(CARPETA_LOGS, f"log_{datetime.now().strftime('%Y%m')}.txt")
        with open(archivo_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {tipo_operacion}\n")
            f.write(f"{'-'*80}\n")
            for key, value in detalles.items():
                f.write(f"  {key}: {value}\n")
            f.write(f"{'='*80}\n")
    except Exception:
        pass


def formatear_duracion(segundos):
    segundos = int(segundos or 0)
    if segundos < 60:
        return f"{segundos}s"
    minutos, s = divmod(segundos, 60)
    if minutos < 60:
        return f"{minutos}m {s}s"
    horas, m = divmod(minutos, 60)
    return f"{horas}h {m}m"


class DiagnosticoBloqueosApp:
    def __init__(self, root):
        self.root = root
        self.root.title("¿Quién tiene bloqueado el sistema?")
        self.root.geometry("720x560")

        self.server = 'SERVER\\server'
        self.database = 'insevig'
        self.username = 'sa'
        self.password = 'puntosoft123*'

        self.conn = None
        self.transacciones_data = {}

        self._construir_interfaz()
        self.verificar_ahora()
        # Un unico ciclo persistente de auto-actualizacion (no se duplica con clics manuales)
        self.root.after(10000, self._auto_tick)

    def conectar_bd(self):
        try:
            conn_str = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password};'
                f'Encrypt=No;'
                f'TrustServerCertificate=yes;'
            )
            self.conn = pyodbc.connect(conn_str, timeout=5, autocommit=True)
            return True
        except Exception as e:
            messagebox.showerror("Error de Conexión", f"No se pudo conectar a la base de datos:\n{str(e)}")
            return False

    def cerrar_conexion(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def _construir_interfaz(self):
        main_frame = tk.Frame(self.root, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="¿Quién tiene bloqueado el sistema?",
                 font=("Arial", 16, "bold")).pack(anchor="w")
        tk.Label(main_frame,
                 text="Presiona el botón cuando el Modificador de Egresos se quede colgado al procesar.",
                 font=("Arial", 9), fg="gray").pack(anchor="w", pady=(0, 10))

        botones_top = tk.Frame(main_frame)
        botones_top.pack(fill="x", pady=(0, 10))

        tk.Button(botones_top, text="VERIFICAR AHORA", command=self.verificar_ahora,
                  bg="#2196F3", fg="white", font=("Arial", 13, "bold"), height=1).pack(side=tk.LEFT, fill="x", expand=True)

        self.auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(botones_top, text="Actualizar solo cada 10 seg.", variable=self.auto_var,
                        font=("Arial", 9)).pack(side=tk.LEFT, padx=(10, 0))

        self.resultado_text = ScrolledText(main_frame, wrap=tk.WORD, font=("Consolas", 11), height=18)
        self.resultado_text.pack(fill="both", expand=True, pady=(0, 15))
        self.resultado_text.tag_configure("titulo", font=("Consolas", 11, "bold"))
        self.resultado_text.tag_configure("rojo", foreground="#c62828", font=("Consolas", 11, "bold"))
        self.resultado_text.tag_configure("verde", foreground="#2e7d32", font=("Consolas", 11, "bold"))
        self.resultado_text.tag_configure("gris", foreground="gray")

        # Panel para matar una sesion, simple: numero + boton
        matar_frame = tk.LabelFrame(main_frame, text="Si encontraste un problema, libéralo aquí", padx=10, pady=10)
        matar_frame.pack(fill="x")

        fila = tk.Frame(matar_frame)
        fila.pack(fill="x")
        tk.Label(fila, text="Número de sesión (SPID) a terminar:", font=("Arial", 10)).pack(side=tk.LEFT)
        self.spid_var = tk.StringVar()
        tk.Entry(fila, textvariable=self.spid_var, width=8, font=("Arial", 11)).pack(side=tk.LEFT, padx=8)
        self.matar_boton = tk.Button(fila, text="Liberar (Matar Sesión)", command=self.matar_sesion,
                                      bg="#f44336", fg="white", font=("Arial", 10, "bold"))
        self.matar_boton.pack(side=tk.LEFT)

    def _escribir(self, texto, tag=None):
        if tag:
            self.resultado_text.insert(tk.END, texto, tag)
        else:
            self.resultado_text.insert(tk.END, texto)

    def verificar_ahora(self):
        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()

            # Transacciones abiertas sin confirmar (excluyendo esta misma sesion)
            cursor.execute("""
                SELECT s.session_id, s.host_name, c.client_net_address,
                       at.transaction_begin_time,
                       DATEDIFF(SECOND, at.transaction_begin_time, GETDATE()) AS segundos_abierta
                FROM sys.dm_tran_active_transactions at
                JOIN sys.dm_tran_session_transactions st ON at.transaction_id = st.transaction_id
                JOIN sys.dm_exec_sessions s ON st.session_id = s.session_id
                LEFT JOIN sys.dm_exec_connections c ON s.session_id = c.session_id
                WHERE s.session_id <> @@SPID AND s.is_user_process = 1
                ORDER BY segundos_abierta DESC
            """)
            transacciones = cursor.fetchall()

            # Que tabla tiene bloqueada (con candado) cada sesion.
            # IMPORTANTE: para locks tipo PAGE/KEY/RID, resource_associated_entity_id es un
            # hobt_id (no un object_id), y pasarlo directo a OBJECT_NAME() revienta con
            # "Arithmetic overflow error converting expression to int data type" (8115).
            # Hay que resolver el object_id real via sys.partitions primero.
            cursor.execute("""
                SELECT tl.request_session_id,
                       CASE
                           WHEN tl.resource_type = 'OBJECT' THEN OBJECT_NAME(tl.resource_associated_entity_id)
                           WHEN tl.resource_type IN ('PAGE','KEY','RID') THEN OBJECT_NAME(p.object_id)
                           ELSE NULL
                       END AS tabla
                FROM sys.dm_tran_locks tl
                LEFT JOIN sys.partitions p ON p.hobt_id = tl.resource_associated_entity_id
                WHERE tl.resource_type IN ('OBJECT','PAGE','KEY','RID')
            """)
            tablas_por_sesion = {}
            for session_id, tabla in cursor.fetchall():
                if tabla:
                    tablas_por_sesion.setdefault(session_id, set()).add(tabla)

            self.transacciones_data = {}
            culpables = []

            for session_id, host_name, ip, inicio, segundos in transacciones:
                tablas_lock = tablas_por_sesion.get(session_id, set())
                self.transacciones_data[session_id] = {
                    'host': host_name, 'ip': ip, 'segundos': segundos, 'tablas': tablas_lock
                }
                if tablas_lock & TABLAS_NOMINA:
                    culpables.append((session_id, host_name, ip, segundos, tablas_lock & TABLAS_NOMINA))

            # --- Armar el reporte en texto simple ---
            self.resultado_text.delete("1.0", tk.END)
            self._escribir(f"Verificado a las {datetime.now().strftime('%H:%M:%S')}\n\n", "gris")

            if culpables:
                self._escribir("PROBLEMA ENCONTRADO\n", "rojo")
                self._escribir("Esta sesión tiene bloqueada una tabla de nómina y muy probablemente "
                                "es la causa de que el programa se quede colgado:\n\n")
                for session_id, host, ip, segundos, tablas in culpables:
                    self._escribir(
                        f"  ➤ SESIÓN {session_id}  —  Equipo: {host or '?'}  (IP: {ip or '?'})\n"
                        f"     Bloqueada hace: {formatear_duracion(segundos)}\n"
                        f"     Tabla bloqueada: {', '.join(sorted(tablas))}\n\n",
                        "rojo"
                    )
                # Se llena solo el numero de sesion mas antigua/problematica, para no tener que escribirlo
                primer_culpable = culpables[0][0]
                self.spid_var.set(str(primer_culpable))
                self.matar_boton.config(text=f"Liberar sesión {primer_culpable} ahora")
                self._escribir(f"Ya se llenó abajo el número {primer_culpable}. Solo presiona "
                                "'Liberar sesión ahora' (o escribe otro número si prefieres).\n\n")
            else:
                self.spid_var.set("")
                self.matar_boton.config(text="Liberar (Matar Sesión)")
                self._escribir("Todo bien: ninguna sesión tiene bloqueada una tabla de nómina ahora mismo.\n\n", "verde")
                self._escribir("Si el programa sigue colgado, puede ser otra cosa (red, servidor lento). "
                                "Esta ventana se actualiza sola cada 10 segundos.\n\n", "gris")

            if transacciones:
                self._escribir("-" * 60 + "\n", "gris")
                self._escribir(f"Otras conexiones abiertas en este momento ({len(transacciones)}):\n\n", "gris")
                for session_id, host_name, ip, inicio, segundos in transacciones:
                    if any(session_id == c[0] for c in culpables):
                        continue
                    self._escribir(
                        f"  SPID {session_id} — {host_name or '?'} — sin confirmar hace {formatear_duracion(segundos)}\n",
                        "gris"
                    )

        except Exception as e:
            messagebox.showerror("Error", f"Error al verificar bloqueos:\n{str(e)}")
        finally:
            self.cerrar_conexion()

    def _auto_tick(self):
        """Ciclo unico que se reprograma solo cada 10s; si el checkbox esta marcado, verifica."""
        if self.auto_var.get():
            self.verificar_ahora()
        self.root.after(10000, self._auto_tick)

    def matar_sesion(self):
        texto = self.spid_var.get().strip()
        if not texto.isdigit():
            messagebox.showwarning("Dato inválido", "Escribe solo el número de sesión (SPID), por ejemplo: 78")
            return

        session_id = int(texto)
        info = self.transacciones_data.get(session_id, {})

        mensaje = (
            f"¿Seguro que quieres terminar la sesión {session_id}?\n\n"
            f"Equipo: {info.get('host', '(no verificado en el último chequeo)')}\n"
            f"IP: {info.get('ip', '?')}\n\n"
            "Esto desconecta esa sesión de inmediato y deshace (ROLLBACK) cualquier "
            "cambio suyo que no se haya confirmado todavía. No afecta datos ya guardados."
        )
        if not messagebox.askyesno("Confirmar", mensaje, icon=messagebox.WARNING):
            return
        if not messagebox.askyesno("Confirmación Final", f"Última confirmación: ¿matar la sesión {session_id} ahora?",
                                    icon=messagebox.WARNING):
            return

        if not self.conectar_bd():
            return

        try:
            cursor = self.conn.cursor()
            # KILL no se puede ejecutar dentro de una transaccion de usuario (error 6115).
            # autocommit=True no basta por si solo con este driver: hay que apagar
            # explicitamente las transacciones implicitas antes de mandar el KILL.
            cursor.execute("SET IMPLICIT_TRANSACTIONS OFF")
            cursor.execute(f"KILL {session_id}")
            registrar_log("KILL_SESION_BD", {
                "session_id": session_id,
                "host": info.get('host'),
                "ip": info.get('ip'),
                "segundos_transaccion_abierta": info.get('segundos'),
            })
            messagebox.showinfo("Listo", f"La sesión {session_id} fue terminada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo matar la sesión:\n{str(e)}")
        finally:
            self.cerrar_conexion()
            self.spid_var.set("")
            self.verificar_ahora()


def main():
    root = tk.Tk()
    app = DiagnosticoBloqueosApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
