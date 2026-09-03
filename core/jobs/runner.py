"""JobRunner sobre un ThreadPoolExecutor acotado.

El backend Reflex corre en un solo proceso (workers=1), así que el pool y el
poll de progreso comparten estado. Para ~10 usuarios sobra.

Uso desde un state de Reflex:

    job_id = get_runner().encolar("reporte_consolidado", {"periodo": "2026-06"},
                                  creado_por=self.username, fn=mi_trabajo)
    # ... y un @rx.event(background=True) hace poll de leer_job(job_id)

`mi_trabajo(ctx: JobContext) -> None` reporta con `ctx.progreso(i, total, msg)`
y respeta `ctx.cancelado`.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache

import sqlmodel

from core.config import get_settings
from core.db import appdb
from core.db.models import Job

log = logging.getLogger(__name__)


def _get(s, job_id: int) -> Job:
    j = s.get(Job, job_id)
    if j is None:
        raise LookupError(f"Job {job_id} no existe")
    return j


@dataclass
class JobContext:
    job_id: int

    @property
    def cancelado(self) -> bool:
        with appdb.session() as s:
            j = s.get(Job, self.job_id)
            return bool(j and j.cancel_requested)

    def progreso(self, hecho: int, total: int, mensaje: str = "") -> None:
        with appdb.session() as s:
            j = s.get(Job, self.job_id)
            if j is None:
                return
            j.progress, j.total = hecho, total
            if mensaje:
                j.message = mensaje
            s.add(j)
            s.commit()


class JobRunner:
    def __init__(self, workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="job")

    def encolar(
        self,
        tipo: str,
        params: dict,
        *,
        creado_por: str,
        fn: Callable[[JobContext], None],
    ) -> int:
        with appdb.session() as s:
            j = Job(
                tipo=tipo,
                params_json=json.dumps(params, default=str),
                created_by=creado_por,
                status="pendiente",
            )
            s.add(j)
            s.commit()
            s.refresh(j)
            assert j.id is not None
            job_id = j.id
        self._pool.submit(self._ejecutar, job_id, fn)
        return job_id

    @staticmethod
    def _ejecutar(job_id: int, fn: Callable[[JobContext], None]) -> None:
        with appdb.session() as s:
            j = _get(s, job_id)
            j.status = "corriendo"
            j.started_at = dt.datetime.now(dt.UTC)
            s.add(j)
            s.commit()
        try:
            fn(JobContext(job_id))
            estado, err = "ok", ""
        except Exception as e:  # noqa: BLE001
            log.exception("Job %s (%s) falló", job_id, fn)
            estado, err = "error", f"{e}\n{traceback.format_exc()}"
        with appdb.session() as s:
            j = _get(s, job_id)
            j.status = "cancelado" if (j.cancel_requested and estado != "error") else estado
            j.error = err[:4000]
            j.finished_at = dt.datetime.now(dt.UTC)
            s.add(j)
            s.commit()

    @staticmethod
    def cancelar(job_id: int) -> None:
        with appdb.session() as s:
            j = s.get(Job, job_id)
            if j is not None and j.status in ("pendiente", "corriendo"):
                j.cancel_requested = True
                s.add(j)
                s.commit()


def leer_job(job_id: int) -> Job | None:
    with appdb.session() as s:
        j = s.get(Job, job_id)
        if j:
            s.expunge(j)
        return j


def jobs_recientes(creado_por: str | None = None, limite: int = 20) -> list[Job]:
    with appdb.session() as s:
        q = sqlmodel.select(Job).order_by(sqlmodel.col(Job.created_at).desc()).limit(limite)
        if creado_por:
            q = q.where(Job.created_by == creado_por)
        res = s.exec(q).all()
        for j in res:
            s.expunge(j)
        return list(res)


@lru_cache
def get_runner() -> JobRunner:
    return JobRunner(workers=max(2, get_settings().sqlserver_pool_size // 2))
