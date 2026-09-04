"""Genera un resumen en español sencillo del historial de préstamos de un empleado.

Porta `_llamar_ia` de `prestamos/HISTORIAL_PRESTAMOS_10.pyw`. Proveedor por config
(`IA_PROVIDER` ∈ groq | openrouter | ollama | none). Se ejecuta como Job.
Para uso 100% offline: `IA_PROVIDER=ollama` + `IA_BASE_URL` a un Ollama local.
"""

from __future__ import annotations

import httpx

from core.parametros import get_ia_config

_SYSTEM = (
    "Eres asistente de nomina. Escribe en espanol muy sencillo, con frases cortas. "
    "DOS parrafos sin titulos ni listas. Parrafo 1: por cada prestamo que aun debe, "
    "di de que fue, cuando se lo dieron, cuanto debe y cuando terminaria de pagarlo. "
    "Parrafo 2: los prestamos ya cancelados. La ultima frase copia EXACTO el monto de "
    "'TOTAL DEUDA HOY (OFICIAL)'. Nada de terminos contables."
)

_FALLBACK_OPENROUTER = [
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]


class NarrativaNoDisponible(RuntimeError):
    pass


def _contexto(movimientos: list, deuda_hoy: float) -> str:
    lineas = ["MOVIMIENTOS DE PRESTAMOS:"]
    for m in movimientos:
        lineas.append(
            f"- {m.fecha} | {m.concepto or 'PRESTAMO'} | valor {m.valor:+.2f} | origen {m.origen}"
        )
    lineas.append(f"\nTOTAL DEUDA HOY (OFICIAL): ${deuda_hoy:,.2f}")
    return "\n".join(lineas)


def narrar_prestamos(movimientos: list, deuda_hoy: float) -> str:
    cfg = get_ia_config()
    prov = cfg["provider"].lower()
    if prov in ("", "none"):
        raise NarrativaNoDisponible("IA desactivada (IA_PROVIDER=none).")
    contexto = _contexto(movimientos, deuda_hoy)

    if prov == "ollama":
        url = cfg["base_url"].rstrip("/") + "/api/chat"
        r = httpx.post(
            url,
            json={
                "model": cfg["model"] or "llama3",
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": contexto},
                ],
                "stream": False,
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    if prov == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        modelos = list(dict.fromkeys([cfg["model"], *_FALLBACK_OPENROUTER]))
        modelos = [m for m in modelos if m]
    else:  # groq
        url = "https://api.groq.com/openai/v1/chat/completions"
        modelos = [cfg["model"] or "llama-3.1-8b-instant"]

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    ultimo = "sin respuesta"
    for modelo in modelos:
        try:
            r = httpx.post(
                url,
                headers=headers,
                json={
                    "model": modelo,
                    "messages": [
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": contexto},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 950,
                },
                timeout=60,
            )
            if r.status_code == 200 and "choices" in r.json():
                return r.json()["choices"][0]["message"]["content"].strip()
            ultimo = r.text[:300]
        except httpx.HTTPError as e:  # noqa: PERF203
            ultimo = str(e)
    raise NarrativaNoDisponible(f"Ningún modelo respondió: {ultimo}")
