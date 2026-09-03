"""Repositorios por dominio. Cada módulo de la app usa SOLO su propio repo.

Regla (tests/test_arquitectura.py): `core/repos/<a>.py` no importa
`core/repos/<b>.py`. Lo común va en `core/datos`, `core/concepts`, `core/db`.
"""
