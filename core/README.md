# core/ — núcleo de negocio (sin UI)

Paquete Python síncrono y testeable con `pytest`. Toda la lógica de negocio,
acceso a datos, generación de documentos, email, auditoría y jobs vive aquí.
La app Reflex (`insevig_web/`, aún no creada) solo consume `core`.

Plan completo: `~/.claude/plans/wise-soaring-turing.md`.

## Estado (Fase 0, en progreso)

| Módulo | Estado | Reemplaza a |
|---|---|---|
| `config.py` | ✅ | credenciales hardcodeadas de `shared/*` y ~20 `.pyw` |
| `utils.py` | ✅ | `formatear_cedula` / `str(int(x)).zfill(10)` disperso |
| `concepts.py` | ✅ | mapa CLASE→concepto duplicado 4+ veces |
| `datos/` (port, postproceso, service, fuente_sqlserver, fuente_supabase) | ✅ | `shared/obtener_datos.py` (`ObtenerDatos`), de-duplicando las 2 rutas |
| `db/sqlserver.py` (fallback de drivers) | ✅ básico — falta pool | `_get_sql_conn` copiado en cada módulo |
| `db/supabase_client.py` | ✅ | `create_client(...)` con JWT hardcodeado ×10 |
| `db/health.py` | ✅ | `shared/detect_db.py` |
| `logging_setup.py` | ✅ | — |
| `repos/`, `audit/`, `excel/`, `pdf/`, `email/`, `narrativa/`, `jobs/`, `storage.py` | ⬜ pendiente | reportes/, empleados/, roles/, envio_roles/, ... |

## Uso

```python
from core.datos.service import datos_empleado

emp = datos_empleado("2026-06", "1712345678", fuente="sqlserver")
if emp:
    print(emp.total_recibir)
    serie = emp.to_series()   # compatible con roles/ y reportes/
```

## Desarrollo

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[web,dev]"
cp .env.example .env          # completar credenciales

pytest                        # unitarias (usa fakes, no toca BD)
pytest -m integration         # requiere SQL Server / Supabase reales
ruff check core tests
mypy core
```

## Reglas que no se rompen

- Escrituras **siempre** a SQL Server; el selector de fuente solo afecta lecturas.
- Toda escritura pasa por `core/audit/` (pendiente).
- Cero acceso a SMB/SQLite en runtime.
- `concepts.CLASE_A_CONCEPTO` es "NO CAMBIAR" — ver `tests/unit/test_concepts.py`.
- Normalización de cédula: `core.utils.normalizar_cedula`.
