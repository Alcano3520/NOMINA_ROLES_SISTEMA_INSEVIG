# Prompt para un desarrollador nuevo (persona o sesión de IA)

> Copiá todo lo de abajo y pegáselo a quien vaya a trabajar en el repo.

---

Vas a trabajar en `NOMINA_ROLES_SISTEMA_INSEVIG`: la migración de las apps de
escritorio Tkinter de RRHH/Nómina de INSEVIG a **una sola app web Reflex**
(Python), servida en el servidor NAS de la empresa. Es un trabajo incremental,
un módulo por vez.

## 1. Antes de tocar nada, leé (en este orden)

1. `docs/ESTADO_MIGRACION.md` — dónde está todo, qué falta, qué NO se toca, cómo
   no pisarse. Es el índice vivo.
2. `docs/CONTRATOS.md` — los archivos **congelados** (núcleo compartido). No se
   editan sin acordar y sin actualizar todos sus consumidores + tests.
3. `docs/modulos/<mod>.md` del módulo que te toque.
4. `CLAUDE.md` (raíz) — convenciones del repo original.

## 2. Setup

Todos los repos van como carpetas hermanas bajo `~/Documentos/mis_proyecto/`:

```bash
mkdir -p ~/Documentos/mis_proyecto && cd ~/Documentos/mis_proyecto
git clone https://github.com/Alcano3520/NOMINA_ROLES_SISTEMA_INSEVIG.git
git clone https://github.com/Alcano3520/sistema_sanciones_RRHH.git   # fuente de sanciones/faltas (referencia, NO tocar)

cd NOMINA_ROLES_SISTEMA_INSEVIG
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[web,dev]"
cp .env.example .env      # completar SUPABASE_* solo si vas a probar contra datos reales

# verde antes de cualquier commit:
ruff check core/ insevig_web/ tests/
mypy --config-file pyproject.toml core/
pytest
reflex export --backend-only --env prod   # compila todas las páginas

# app local:
reflex run                 # http://localhost:3000
python -m insevig_web.seed # usuario admin/admin + permisos
```

Cuando toque anexar otra app de RRHH (ej. envío de correos, lector de cédulas,
IESS, parametrización), cloná su repo como carpeta hermana. **No toques**
`rpa_bot_mrl` / `ingresosMrl` ni proyectos no-RRHH.

## 3. Arquitectura (3 capas)

- `core/` — lógica de negocio pura, sin UI, testeable con pytest. `repos/`,
  `excel/`, `pdf/`, `email/`, dominios propios (`faltas/`, `sanciones/`, ...).
- `insevig_web/` — app Reflex: `pages/`, `states/`, `components/`, `registry.py`.
- BD de la app (alembic + `models.py`): auth, permisos, auditoría, jobs.

Datos: SQL Server `192.168.2.115` (fuente de verdad, escritura mínima), Supabase
(espejo de lectura, 2 proyectos), Postgres local (datos de la app). Todo acceso
va por `core/repos/*`, nunca queries sueltas en la UI. El selector de fuente cae
solo a Supabase si SQL Server no responde.

## 4. Cómo anexar una app vieja como módulo `<mod>`

La rebanada vertical = **exactamente** estos archivos:

```
core/repos/<mod>.py                 (+ core/<dominio>/ propio si aplica)
core/excel/<mod>_*.py  core/pdf/<mod>_*.py
insevig_web/states/<mod>_state.py
insevig_web/pages/<mod>/*.py
tests/unit/test_<mod>_*.py
docs/modulos/<mod>.md
```

+ una línea `ModuleSpec(...)` en `insevig_web/registry.py`. La shell (sidebar,
layout) NO se toca — se auto-arma desde el registry.

Proceso:

1. **FASE -1**: abrí los `core/repos/*` que podrían solaparse y decidí
   explícitamente extender / reemplazar / módulo aparte. Nunca portar de cero
   sin mirar.
2. **Trasplante, no reescritura**: copiá queries, fórmulas y orden de pasos
   igual que el legado; adaptá solo el transporte (`requests` → `supabase-py`,
   Tkinter → Reflex, `asyncio.to_thread` para llamadas sync desde un state).
3. Bugs del legado: replicar con `# LEGADO: <bug> — [replicado | corregido]: por qué`.
   Los que son decisión de negocio, escalarlos al usuario.
4. Escrituras a SQL Server: `dry_run`/vista previa + `core.audit.audit_scope`.
   Superficie permitida: `RPEMPLEA`, `RPEMPOBSERV`, `RPINGDES`, `RPHORTOT`.
5. Alta de módulo = tocar archivos congelados (`registry.py`,
   `tests/test_arquitectura.py::MODULOS`, `auth._TODOS_MODULOS` +
   `PERMISOS_POR_DEFECTO`, `components/sidebar.py`). Preparalo como **un bloque
   único** y pedí OK al usuario antes de mergear.
6. Patrón de UI: copiá `insevig_web/states/empleados_state.py` +
   `pages/empleados/buscar.py`. Usá los componentes de `components/ui/*`, no
   crees estilos. `pagina(..., requiere=(mod, accion))` envuelve toda página.
7. Cerrar: `ruff` + `mypy core` + `pytest` verdes, `reflex export` compila,
   actualizá `docs/modulos/<mod>.md` **y** la tabla de `docs/ESTADO_MIGRACION.md`
   en el mismo commit.

## 5. Reglas para no pisarse

- `git pull` antes de empezar. **Commit + push a `main` apenas hay un cambio
  coherente** — nada se queda local. Mensajes de commit que digan qué toca y por qué.
- Un módulo por persona. `tests/test_arquitectura.py` falla si dos módulos se
  cruzan o el registry queda incoherente.
- Gotchas de Reflex ya conocidos (buscá ejemplos en el repo antes de pelear con esto):
  - `.to(str)` para render de texto/fechas; `.to_string()` **agrega comillas** en la UI.
  - `X["a"] + " " + Y["b"]` sobre items de dict sin tipar → usar f-strings.
  - `X["n"].to(float) > 0` para comparar numéricos de dicts sin tipar.
  - Llamadas a `core/` (síncronas) desde un state: `await asyncio.to_thread(fn, ...)`.
  - `@rx.event(background=True)` no sirve para handlers de `rx.upload`.
- No commitees credenciales. `config/supabase.yaml` y `.env` están gitignored.
- El deploy lo hace otra sesión sobre el NAS. Vos hacés `git push` y avisás.
  Un deploy por vez.

## 6. Qué tomar ahora

Ver `docs/ESTADO_MIGRACION.md` §5 "Pendientes conocidos" y la tabla de módulos
(los 🟡 tienen trabajo). El `_utilitarios/README.md` lista las apps sueltas que
faltan absorber.
