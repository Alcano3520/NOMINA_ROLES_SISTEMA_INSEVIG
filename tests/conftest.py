from __future__ import annotations

import pytest


@pytest.fixture
def app_db(tmp_path, monkeypatch):
    """BD de la app en un SQLite temporal, con tablas creadas."""
    import core.config as config
    import core.db.appdb as appdb

    db_file = tmp_path / "test_app.db"
    monkeypatch.setenv("APP_DB_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    config.get_settings.cache_clear()
    appdb.get_engine.cache_clear()

    import core.db.models  # noqa: F401  registra tablas

    appdb.crear_tablas()
    yield appdb

    appdb.get_engine.cache_clear()
    config.get_settings.cache_clear()
