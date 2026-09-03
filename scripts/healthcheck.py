"""Chequeo de conectividad: SQL Server, Supabase y la BD de la app.

    python -m scripts.healthcheck

Sale con código 0 si TODO responde, 1 si algo falla. Úsalo tras editar `.env`
y en el arranque del servicio.
"""

from __future__ import annotations

import sys

from core.config import get_settings


def _check(nombre: str, fn) -> bool:
    try:
        fn()
        print(f"  OK    {nombre}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  FALLA {nombre}: {e}")
        return False


def main() -> int:
    s = get_settings()
    print("Configuración efectiva:")
    print(f"  SQL Server : {s.sqlserver_host}/{s.sqlserver_db} (drivers: {', '.join(s.driver_list)})")
    print(f"  Supabase   : {s.supabase_url or '(no configurado)'}")
    print(f"  BD app     : {s.app_db_url.split('://')[0]}://…")
    print(f"  Email      : {s.email_backend}")
    print("Comprobando:")

    ok = True

    def sql():
        from core.db import sqlserver

        with sqlserver.conexion() as c:
            c.cursor().execute("SELECT 1").fetchone()

    def sup():
        from core.db import supabase_client

        supabase_client.get_client().table("rpemplea").select("codemp").limit(1).execute()

    def app():
        import sqlalchemy as sa

        from core.db import appdb

        with appdb.get_engine().connect() as conn:
            conn.execute(sa.text("SELECT 1"))

    ok &= _check("SQL Server", sql)
    if s.supabase_url:
        ok &= _check("Supabase", sup)
    else:
        print("  SKIP  Supabase (no configurado)")
    ok &= _check("BD de la app", app)

    print("RESULTADO:", "todo OK" if ok else "hay fallos")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
