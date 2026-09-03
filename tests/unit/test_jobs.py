import time

from core.jobs.runner import JobContext, JobRunner, leer_job


def _esperar(job_id, estados=("ok", "error", "cancelado"), timeout=5.0):
    fin = time.time() + timeout
    while time.time() < fin:
        j = leer_job(job_id)
        if j and j.status in estados:
            return j
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} no terminó: {leer_job(job_id).status}")


def test_job_ok_reporta_progreso(app_db):
    runner = JobRunner(workers=1)

    def trabajo(ctx: JobContext):
        for i in range(1, 4):
            ctx.progreso(i, 3, f"paso {i}")

    jid = runner.encolar("demo", {}, creado_por="tester", fn=trabajo)
    j = _esperar(jid)
    assert j.status == "ok"
    assert j.progress == 3 and j.total == 3
    assert j.message == "paso 3"


def test_job_error(app_db):
    runner = JobRunner(workers=1)

    def trabajo(ctx: JobContext):
        raise ValueError("boom")

    jid = runner.encolar("demo", {}, creado_por="t", fn=trabajo)
    j = _esperar(jid)
    assert j.status == "error"
    assert "boom" in j.error


def test_job_cancelacion_cooperativa(app_db):
    runner = JobRunner(workers=1)

    def trabajo(ctx: JobContext):
        for i in range(100):
            if ctx.cancelado:
                return
            ctx.progreso(i, 100)
            time.sleep(0.01)

    jid = runner.encolar("demo", {}, creado_por="t", fn=trabajo)
    time.sleep(0.05)
    JobRunner.cancelar(jid)
    j = _esperar(jid)
    assert j.status == "cancelado"
