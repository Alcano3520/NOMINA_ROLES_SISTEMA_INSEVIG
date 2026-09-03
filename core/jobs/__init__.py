"""Ejecución de operaciones largas (reportes 2.5M, lote de PDF, envío de correos)
como jobs en segundo plano, con progreso, cancelación y persistencia.
"""

from core.jobs.runner import JobContext, JobRunner, get_runner

__all__ = ["JobContext", "JobRunner", "get_runner"]
