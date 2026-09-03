from core import storage


def test_guardar_leer_listar(app_db):
    p = storage.guardar("job-1", "reporte.xlsx", b"contenido")
    assert p.exists()
    assert storage.leer("job-1", "reporte.xlsx") == b"contenido"
    assert [x.name for x in storage.listar("job-1")] == ["reporte.xlsx"]


def test_evita_path_traversal(app_db):
    p = storage.guardar("job-2", "../../escape.txt", b"x")
    assert p.name == "escape.txt"
    assert "job-2" in str(p.parent)


def test_listar_job_inexistente(app_db):
    assert storage.listar("nope") == []
