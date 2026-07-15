#!/usr/bin/env python3
"""
MIGRACIÓN: SQLite → Supabase para Historial de Préstamos
Sube datos locales de SQLite a Supabase para sincronizar con el resto del sistema
"""

import sqlite3
import os
import sys
from datetime import datetime

try:
    from supabase import create_client
except ImportError:
    print("❌ Instala supabase-py: pip install supabase")
    sys.exit(1)


def conectar_supabase():
    """Conecta a Supabase usando variables de entorno"""
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        # Intentar cargar desde config/supabase.yaml
        try:
            import yaml
            with open('config/supabase.yaml', 'r') as f:
                config = yaml.safe_load(f)
                url = config.get('url')
                key = config.get('key')
        except:
            print("❌ Credenciales Supabase no encontradas")
            print("   Define SUPABASE_URL y SUPABASE_KEY, o crea config/supabase.yaml")
            sys.exit(1)

    return create_client(url, key)


def conectar_sqlite(ruta):
    """Conecta a SQLite local"""
    if not os.path.exists(ruta):
        print(f"❌ Archivo SQLite no encontrado: {ruta}")
        return None
    return sqlite3.connect(ruta)


def crear_tabla_supabase(client):
    """Crea tabla en Supabase si no existe"""
    try:
        print("📊 Verificando tabla en Supabase...")

        # Intentar crear tabla si no existe
        client.table('historial_prestamos_sqlite').select('*').limit(1).execute()
        print("✓ Tabla ya existe")
        return True
    except:
        print("⚠️ Tabla no existe, créala en Supabase con esta estructura:")
        print("""
        CREATE TABLE historial_prestamos_sqlite (
            id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
            empleado TEXT NOT NULL,
            fecha TEXT,
            ingreso NUMERIC,
            egreso NUMERIC,
            concepto TEXT,
            tipo TEXT,
            numero_fila INTEGER,
            observaciones TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_empleado ON historial_prestamos_sqlite(empleado);
        CREATE INDEX idx_fecha ON historial_prestamos_sqlite(fecha);
        """)
        return False


def migrar_datos(sqlite_ruta, supabase_client):
    """Migra datos de SQLite a Supabase"""

    print("\n" + "=" * 70)
    print("MIGRANDO DATOS: SQLite → Supabase")
    print("=" * 70)

    # Conectar a SQLite
    conn_sqlite = conectar_sqlite(sqlite_ruta)
    if not conn_sqlite:
        return False

    try:
        cursor = conn_sqlite.cursor()

        # Obtener datos de SQLite
        print("\n📖 Leyendo datos de SQLite...")
        cursor.execute("""
            SELECT
                EMPLEADO,
                FECHA,
                INGRESO,
                EGRESO,
                CONCEPTO,
                TIPO,
                NUMERO_FILA
            FROM historial_prestamos
            ORDER BY FECHA DESC
        """)

        datos = cursor.fetchall()
        total = len(datos)
        print(f"✓ {total} registros encontrados")

        if total == 0:
            print("⚠️ No hay datos para migrar")
            return True

        # Preparar datos para Supabase
        print("\n📤 Preparando datos para Supabase...")
        registros = []

        for empleado, fecha, ingreso, egreso, concepto, tipo, numero_fila in datos:
            registros.append({
                'empleado': str(empleado),
                'fecha': str(fecha) if fecha else None,
                'ingreso': float(ingreso) if ingreso else 0,
                'egreso': float(egreso) if egreso else 0,
                'concepto': str(concepto) if concepto else '',
                'tipo': str(tipo) if tipo else '',
                'numero_fila': int(numero_fila) if numero_fila else None,
            })

        # Subir a Supabase en lotes
        print("\n⬆️ Subiendo a Supabase...")
        lote_size = 100
        registros_subidos = 0

        for i in range(0, len(registros), lote_size):
            lote = registros[i:i+lote_size]
            try:
                response = supabase_client.table('historial_prestamos_sqlite')\
                    .insert(lote)\
                    .execute()
                registros_subidos += len(lote)
                print(f"  ✓ {registros_subidos}/{total} registros")
            except Exception as e:
                print(f"  ❌ Error en lote {i//lote_size + 1}: {str(e)[:50]}")
                # Continuar con el siguiente lote

        print(f"\n✅ Migración completada: {registros_subidos}/{total} registros")
        return True

    except Exception as e:
        print(f"\n❌ Error durante migración: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn_sqlite.close()


def main():
    """Ejecuta la migración"""
    print("\n" + "=" * 70)
    print("HERRAMIENTA DE MIGRACIÓN: SQLite → Supabase")
    print("=" * 70)

    # Rutas posibles de SQLite
    rutas_sqlite = [
        r"\\server\Respaldo 2017\Base\Saldo_prestamos_driver.db",
        "/mnt/server/Base/Saldo_prestamos_driver.db",
        "./Saldo_prestamos_driver.db",
        os.path.expanduser("~/Saldo_prestamos_driver.db"),
    ]

    # Encontrar archivo SQLite
    sqlite_ruta = None
    for ruta in rutas_sqlite:
        if os.path.exists(ruta):
            sqlite_ruta = ruta
            print(f"\n✓ Encontrado: {ruta}")
            break

    if not sqlite_ruta:
        print(f"\n❌ No se encontró Saldo_prestamos_driver.db en:")
        for ruta in rutas_sqlite:
            print(f"   - {ruta}")
        print("\nOpciones:")
        print("1. Montar carpeta de red: //server/Respaldo 2017")
        print("2. Proporcionar ruta manual")
        return False

    # Conectar a Supabase
    print("\n🔗 Conectando a Supabase...")
    try:
        supabase_client = conectar_supabase()
        print("✓ Conectado a Supabase")
    except Exception as e:
        print(f"❌ Error conectando a Supabase: {e}")
        return False

    # Crear tabla si es necesario
    if not crear_tabla_supabase(supabase_client):
        print("\n⚠️ Tabla no existe. Créala primero en Supabase.")
        return False

    # Migrar datos
    exito = migrar_datos(sqlite_ruta, supabase_client)

    print("\n" + "=" * 70)
    if exito:
        print("✅ MIGRACIÓN EXITOSA")
        print("\nProximos pasos:")
        print("1. Verifica los datos en Supabase")
        print("2. Modifica HISTORIAL_PRESTAMOS_10.pyw para usar Supabase")
        print("3. Prueba el módulo de Préstamos")
    else:
        print("❌ MIGRACIÓN FALLIDA")
        print("Revisa los errores arriba")
    print("=" * 70 + "\n")

    return exito


if __name__ == '__main__':
    exito = main()
    sys.exit(0 if exito else 1)
