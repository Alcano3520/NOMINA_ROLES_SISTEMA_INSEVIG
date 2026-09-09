"""Cliente único de Supabase (PostgREST, solo lectura en la práctica).

Reemplaza los ~10 `create_client(...)` con el JWT hardcodeado repartidos por los
módulos. La key sale de `core.config` (`.env` o `config/supabase.yaml`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from core.config import get_settings

if TYPE_CHECKING:
    from supabase import Client


class SupabaseNoConfigurado(RuntimeError):
    pass


@lru_cache
def get_client() -> Client:
    from supabase import create_client

    s = get_settings()
    if not s.supabase_url or not s.supabase_key:
        raise SupabaseNoConfigurado(
            "Falta SUPABASE_URL / SUPABASE_KEY (en .env o config/supabase.yaml)."
        )
    return create_client(s.supabase_url, s.supabase_key)


# ── Proyecto SANCIONES (syxzopyevfuwymmltbwn) — backend puro, sin UI ─────────
# Ver contrato C4. Las *_service_key SOLO se usan server-side (core/).


@lru_cache
def get_client_sanciones(*, service: bool = False) -> Client:
    """Cliente del proyecto Supabase de sanciones. `service=True` usa la
    SERVICE key (solo para leer `profiles`); por defecto, la ANON key.
    """
    from supabase import create_client

    s = get_settings()
    key = s.supabase_sanciones_service_key if service else s.supabase_sanciones_anon_key
    if not s.supabase_sanciones_url or not key:
        raise SupabaseNoConfigurado(
            "Falta SUPABASE_SANCIONES_URL / "
            + ("SUPABASE_SANCIONES_SERVICE_KEY" if service else "SUPABASE_SANCIONES_ANON_KEY")
        )
    return create_client(s.supabase_sanciones_url, key)
