"""Configuración centralizada. Único lugar con credenciales (vía `.env`).

Reemplaza los valores hardcodeados y duplicados de:
  - shared/obtener_datos.py  (SUPABASE_URL/KEY, server/sa/password)
  - shared/detect_db.py      (server/sa/password + lista de drivers)
  - ~20 helpers de conexión copiados en los módulos .pyw
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DRIVERS_DEFAULT = (
    "ODBC Driver 17 for SQL Server,"
    "ODBC Driver 18 for SQL Server,"
    "ODBC Driver 13 for SQL Server,"
    "ODBC Driver 11 for SQL Server,"
    "SQL Server Native Client 11.0,"
    "SQL Server"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── SQL Server ────────────────────────────────────────────────────────────
    sqlserver_host: str = "192.168.2.115"
    sqlserver_db: str = "insevig"
    sqlserver_user_ro: str = "sa"
    sqlserver_pwd_ro: str = ""
    sqlserver_user_rw: str = ""
    sqlserver_pwd_rw: str = ""
    sqlserver_drivers: str = _DRIVERS_DEFAULT
    sqlserver_filter: str = "CODEMP='10' AND CODSUC='10'"
    sqlserver_encrypt: str = "no"
    sqlserver_trust_cert: bool = True
    sqlserver_timeout: int = 10
    sqlserver_pool_size: int = 5

    # ── Supabase (solo lectura) ──────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""

    # ── Postgres de la app ───────────────────────────────────────────────────
    app_db_url: str = "sqlite:///./var/insevig_app.db"

    # ── Email ────────────────────────────────────────────────────────────────
    email_backend: str = "console"  # console | smtp | graph
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    smtp_sender: str = ""
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    graph_sender: str = ""

    # ── IA ───────────────────────────────────────────────────────────────────
    ia_provider: str = "none"  # none | groq | openrouter | ollama
    ia_api_key: str = ""
    ia_base_url: str = "http://localhost:11434"
    ia_model: str = "llama3.1"

    # ── App ──────────────────────────────────────────────────────────────────
    secret_key: str = "dev-insecure-change-me"
    storage_dir: Path = Path("./var/storage")
    feature_flags: str = ""

    # ── Derivados ────────────────────────────────────────────────────────────
    @property
    def driver_list(self) -> list[str]:
        return [d.strip() for d in self.sqlserver_drivers.split(",") if d.strip()]

    @property
    def flags(self) -> set[str]:
        return {f.strip() for f in self.feature_flags.split(",") if f.strip()}

    def sqlserver_dsn(self, *, driver: str, write: bool = False) -> str:
        user = self.sqlserver_user_rw if write else self.sqlserver_user_ro
        pwd = self.sqlserver_pwd_rw if write else self.sqlserver_pwd_ro
        parts = [
            f"DRIVER={{{driver}}}",
            f"SERVER={self.sqlserver_host}",
            f"DATABASE={self.sqlserver_db}",
            f"UID={user}",
            f"PWD={pwd}",
            f"Encrypt={self.sqlserver_encrypt}",
            f"TrustServerCertificate={'yes' if self.sqlserver_trust_cert else 'no'}",
        ]
        if not write:
            parts.append("ApplicationIntent=ReadOnly")
        return ";".join(parts) + ";"

    @model_validator(mode="after")
    def _fallback_supabase_yaml(self) -> Settings:
        """Continuidad con el `config/supabase.yaml` que ya usan los .pyw (dev)."""
        if not (self.supabase_url and self.supabase_key):
            p = Path("config/supabase.yaml")
            if p.exists():
                try:
                    import yaml

                    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                    self.supabase_url = self.supabase_url or str(data.get("url", "") or "")
                    self.supabase_key = self.supabase_key or str(data.get("key", "") or "")
                except Exception:  # noqa: BLE001 - config opcional
                    pass
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
