from core.config import Settings


def _settings(**over) -> Settings:
    base = dict(
        _env_file=None,  # ignora .env del repo en el test
        sqlserver_host="db.local",
        sqlserver_user_ro="ro",
        sqlserver_pwd_ro="secreto",
        sqlserver_user_rw="rw",
        sqlserver_pwd_rw="secreto_rw",
        supabase_url="https://x.supabase.co",
        supabase_key="k",
    )
    base.update(over)
    return Settings(**base)


def test_driver_list_se_parsea():
    s = _settings(sqlserver_drivers="ODBC Driver 17 for SQL Server, SQL Server ")
    assert s.driver_list == ["ODBC Driver 17 for SQL Server", "SQL Server"]


def test_dsn_lectura_es_readonly():
    dsn = _settings().sqlserver_dsn(driver="ODBC Driver 17 for SQL Server")
    assert "UID=ro" in dsn and "PWD=secreto" in dsn
    assert "ApplicationIntent=ReadOnly" in dsn
    assert "Encrypt=no" in dsn


def test_dsn_escritura_usa_login_rw_y_sin_readonly():
    dsn = _settings().sqlserver_dsn(driver="X", write=True)
    assert "UID=rw" in dsn and "PWD=secreto_rw" in dsn
    assert "ApplicationIntent=ReadOnly" not in dsn


def test_flags_se_parsean():
    assert _settings(feature_flags="narrativa, tts").flags == {"narrativa", "tts"}
    assert _settings(feature_flags="").flags == set()
