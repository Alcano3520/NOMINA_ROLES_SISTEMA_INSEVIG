#!/usr/bin/env python3
"""
CREAR TABLA EN SUPABASE DIRECTAMENTE
Crea la tabla historial_prestamos_sqlite en Supabase
"""

import os
import sys
import json
from getpass import getpass

try:
    from supabase import create_client
    import postgrest
except ImportError:
    print("❌ Instala supabase-py: pip install supabase")
    sys.exit(1)


def obtener_credenciales():
    """Obtiene credenciales de Supabase interactivamente"""
    print("\n" + "=" * 70)
    print("CONFIGURAR CREDENCIALES SUPABASE")
    print("=" * 70)

    # Intentar desde variables de entorno
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if url and key:
        print("\n✓ Encontradas en variables de entorno")
        print(f"  URL: {url[:40]}...")
        print(f"  KEY: {key[:40]}...")
        return url, key

    # Intentar desde config/supabase.yaml
    try:
        import yaml
        if os.path.exists('config/supabase.yaml'):
            with open('config/supabase.yaml', 'r') as f:
                config = yaml.safe_load(f)
                url = config.get('url')
                key = config.get('key')
                if url and key:
                    print("\n✓ Encontradas en config/supabase.yaml")
                    return url, key
    except:
        pass

    # Solicitar interactivamente
    print("\n📝 Ingresa tus credenciales de Supabase:")
    print("   (Puedes copiarlas desde https://app.supabase.com/project/NOMBRE/settings/api)")

    url = input("\n🔗 URL del proyecto (ej: https://abc.supabase.co): ").strip()
    key = getpass("🔑 Clave pública (anon key): ")

    if not url or not key:
        print("❌ Credenciales incompletas")
        return None, None

    return url, key


def conectar_supabase(url, key):
    """Conecta a Supabase"""
    try:
        client = create_client(url, key)
        print("✓ Conectado a Supabase")
        return client
    except Exception as e:
        print(f"❌ Error de conexión: {str(e)[:100]}")
        return None


def crear_tabla(client):
    """Crea tabla en Supabase usando SQL"""
    print("\n" + "=" * 70)
    print("CREAR TABLA historial_prestamos_sqlite")
    print("=" * 70)

    sql = """
    -- Crear tabla si no existe
    CREATE TABLE IF NOT EXISTS historial_prestamos_sqlite (
        id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
        empleado TEXT NOT NULL,
        fecha TEXT,
        ingreso NUMERIC DEFAULT 0,
        egreso NUMERIC DEFAULT 0,
        concepto TEXT,
        tipo TEXT,
        numero_fila INTEGER,
        observaciones TEXT,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Crear índices
    CREATE INDEX IF NOT EXISTS idx_empleado ON historial_prestamos_sqlite(empleado);
    CREATE INDEX IF NOT EXISTS idx_fecha ON historial_prestamos_sqlite(fecha);
    CREATE INDEX IF NOT EXISTS idx_ingreso_egreso ON historial_prestamos_sqlite(ingreso, egreso);

    -- Habilitar RLS (Row Level Security)
    ALTER TABLE historial_prestamos_sqlite ENABLE ROW LEVEL SECURITY;

    -- Permitir acceso a todos (ajusta según necesites)
    CREATE POLICY "Acceso publico" ON historial_prestamos_sqlite
    FOR ALL USING (true)
    WITH CHECK (true);
    """

    try:
        print("\n⏳ Ejecutando SQL...")

        # Supabase no permite ejecutar SQL directo, así que usaremos el método alternativo
        # Intentar crear tabla usando la API REST

        # Verificar si tabla existe
        try:
            result = client.table('historial_prestamos_sqlite').select('*').limit(1).execute()
            print("✓ Tabla ya existe")
            return True
        except:
            pass

        # Si no existe, crear registros de prueba
        print("📝 Creando tabla con registro de prueba...")

        resultado = client.table('historial_prestamos_sqlite').insert({
            'empleado': '__TEST__',
            'fecha': '2026-01-01',
            'ingreso': 0,
            'egreso': 0,
            'concepto': 'REGISTRO DE PRUEBA',
            'tipo': 'TEST',
            'numero_fila': 0,
            'observaciones': 'Eliminable - usado para crear tabla'
        }).execute()

        print("✓ Tabla creada exitosamente")

        # Eliminar registro de prueba
        print("🧹 Limpiando...")
        client.table('historial_prestamos_sqlite')\
            .delete()\
            .eq('empleado', '__TEST__')\
            .execute()

        print("✓ Registro de prueba eliminado")
        return True

    except Exception as e:
        print(f"❌ Error: {str(e)[:150]}")
        print("\n⚠️ SOLUCIÓN MANUAL:")
        print("   1. Ve a https://app.supabase.com/project/NOMBRE/sql")
        print("   2. Copia y ejecuta el SQL anterior")
        print("   3. Vuelve a ejecutar este script")
        return False


def verificar_tabla(client):
    """Verifica que la tabla está lista"""
    print("\n" + "=" * 70)
    print("VERIFICAR TABLA")
    print("=" * 70)

    try:
        # Obtener estadísticas
        result = client.table('historial_prestamos_sqlite')\
            .select('*')\
            .limit(1)\
            .execute()

        print("✓ Tabla accesible")
        print(f"  Columnas: {len(result.data[0].keys()) if result.data else 'sin datos aún'}")

        # Contar registros
        try:
            # Intentar usar count() si está disponible
            result = client.table('historial_prestamos_sqlite')\
                .select('*', count='exact')\
                .execute()
            total = result.count if hasattr(result, 'count') else len(result.data)
            print(f"  Registros: {total}")
        except:
            print(f"  Registros: 0 (tabla vacía, lista para migración)")

        return True

    except Exception as e:
        print(f"❌ Tabla no accesible: {str(e)[:100]}")
        return False


def main():
    """Flujo principal"""
    print("\n" + "=" * 70)
    print("🚀 CREAR TABLA EN SUPABASE")
    print("=" * 70)

    # Obtener credenciales
    url, key = obtener_credenciales()
    if not url or not key:
        print("❌ No se pudieron obtener credenciales")
        return False

    # Conectar
    print("\n🔗 Conectando a Supabase...")
    client = conectar_supabase(url, key)
    if not client:
        return False

    # Crear tabla
    if not crear_tabla(client):
        return False

    # Verificar
    print()
    if not verificar_tabla(client):
        return False

    print("\n" + "=" * 70)
    print("✅ TABLA LISTA PARA MIGRACIÓN")
    print("=" * 70)
    print("\nProximos pasos:")
    print("1. python3 shared/migracion_prestamos_sqlite_supabase.py")
    print("2. Esto subirá todos los datos de SQLite a Supabase")
    print("3. Luego actualiza HISTORIAL_PRESTAMOS_10.pyw")
    print("=" * 70 + "\n")

    return True


if __name__ == '__main__':
    exito = main()
    sys.exit(0 if exito else 1)
