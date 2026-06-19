"""
Detección automática de disponibilidad de base de datos.
Intenta SQL Server y fallback a Supabase si no está disponible.
"""

import pyodbc
import sys

def detectar_sql_server():
    """
    Intenta conectar a SQL Server.
    Retorna: True si está disponible, False si no
    """
    try:
        server = '192.168.2.115'
        database = 'insevig'
        username = 'sa'
        password = 'puntosoft123*'

        # Intentar con diferentes drivers
        drivers = [
            'ODBC Driver 18 for SQL Server',
            'ODBC Driver 17 for SQL Server',
            'ODBC Driver 13 for SQL Server',
            'ODBC Driver 11 for SQL Server',
            'SQL Server Native Client 11.0'
        ]

        for driver in drivers:
            try:
                conn_str = (
                    f'Driver={{{driver}}};'
                    f'Server={server};'
                    f'Database={database};'
                    f'UID={username};'
                    f'PWD={password};'
                    f'TrustServerCertificate=yes'
                )
                conn = pyodbc.connect(conn_str, timeout=3)
                conn.close()
                print(f"✓ SQL Server disponible (driver: {driver})")
                return True
            except Exception as e:
                continue

        print("✗ SQL Server no disponible")
        return False

    except Exception as e:
        print(f"✗ Error detectando SQL Server: {e}")
        return False


def detectar_supabase():
    """
    Intenta conectar a Supabase.
    Retorna: True si está disponible, False si no
    """
    try:
        from supabase import create_client
        import os

        # Cargar credenciales
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            # Intentar cargar desde config/supabase.yaml
            try:
                import yaml
                with open('config/supabase.yaml', 'r') as f:
                    config = yaml.safe_load(f)
                    supabase_url = config.get('url')
                    supabase_key = config.get('key')
            except:
                print("✗ Supabase: credenciales no encontradas")
                return False

        client = create_client(supabase_url, supabase_key)

        # Probar conexión
        result = client.table('rpemplea').select('*').limit(1).execute()
        print("✓ Supabase disponible")
        return True

    except Exception as e:
        print(f"✗ Supabase no disponible: {e}")
        return False


def obtener_fuente_recomendada():
    """
    Retorna: 'SQL Server' o 'Supabase' según disponibilidad
    """
    if detectar_sql_server():
        return 'SQL Server'
    elif detectar_supabase():
        return 'Supabase'
    else:
        print("⚠️ ADVERTENCIA: Ni SQL Server ni Supabase están disponibles")
        return 'SQL Server'  # Default


if __name__ == '__main__':
    fuente = obtener_fuente_recomendada()
    print(f"\nFuente recomendada: {fuente}")
